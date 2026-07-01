"""
Módulo de Ordem de Serviço (Comanda)
Sistema: Lava-Jato
Autor: RINEAL Analytics

CRUD da tabela ordem_servico + itens (ordem_servico_item).
O preço de cada item é buscado em servico_preco conforme o PORTE do veículo
e CONGELADO em preco_aplicado (histórico imune a reajustes futuros).
O valor_total da comanda é recalculado a cada mudança de itens.
"""

from conexao import conectar

# Valores aceitos pelo CHECK de status no banco.
STATUS_VALIDOS = ('aguardando', 'em_execucao', 'finalizado', 'entregue', 'cancelado')


# ----------------------------------------------------------------
# Helpers internos (recebem cursor: rodam dentro de uma transação aberta)
# ----------------------------------------------------------------

def _preco_servico_para_veiculo(cursor, id_servico, id_veiculo):
    """Retorna o preço (Decimal) do serviço para o porte do veículo, ou None."""
    cursor.execute(
        """
        SELECT sp.preco
        FROM servico_preco sp
        JOIN veiculo v ON v.id_categoria = sp.id_categoria
        WHERE sp.id_servico = %s AND v.id_veiculo = %s;
        """,
        (id_servico, id_veiculo)
    )
    linha = cursor.fetchone()
    return linha[0] if linha else None


def _recalcular_total(cursor, id_ordem):
    """Atualiza valor_total da comanda com a soma dos itens. Retorna o total."""
    # Recalcula do zero (SUM dos preco_aplicado dos itens) em vez de somar/subtrair
    # incrementalmente — assim o total nunca "desanda" após adições/remoções.
    # Chamado sempre que os itens mudam, dentro da MESMA transação de quem chamou.
    cursor.execute(
        """
        UPDATE ordem_servico
        SET valor_total = (
                SELECT COALESCE(SUM(preco_aplicado), 0)
                FROM ordem_servico_item
                WHERE id_ordem = %s
            ),
            atualizado_em = NOW()
        WHERE id_ordem = %s
        RETURNING valor_total;
        """,
        (id_ordem, id_ordem)
    )
    return cursor.fetchone()[0]


# ----------------------------------------------------------------
# Operações da comanda
# ----------------------------------------------------------------

def abrir_comanda(id_cliente, id_veiculo, id_funcionario=None,
                  id_agendamento=None):
    """
    Abre uma nova comanda (status 'aguardando', entrada = agora).
    Retorna o id_ordem criado, ou None em caso de erro.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            INSERT INTO ordem_servico (id_cliente, id_veiculo, id_funcionario,
                                       id_agendamento, status)
            VALUES (%s, %s, %s, %s, 'aguardando')
            RETURNING id_ordem;
            """,
            (id_cliente, id_veiculo, id_funcionario, id_agendamento)
        )
        id_ordem = cursor.fetchone()[0]
        conexao.commit()
        return id_ordem

    except Exception as erro:
        print(f"Erro ao abrir comanda: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def adicionar_servico(id_ordem, id_servico, id_funcionario=None, preco=None):
    """
    Adiciona um serviço à comanda. Se 'preco' não for informado, busca na tabela
    de preços conforme o porte do veículo da comanda. Recalcula o total.
    Retorna o id_item criado, ou None em caso de erro (ex.: sem preço definido).
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()

        # Descobre o veículo da comanda (para achar o porte / preço)
        cursor.execute("SELECT id_veiculo FROM ordem_servico WHERE id_ordem = %s;", (id_ordem,))
        linha = cursor.fetchone()
        if not linha:
            print(f"Comanda {id_ordem} não encontrada.")
            return None
        id_veiculo = linha[0]

        if preco is None:
            # Busca o preço pelo PORTE do veículo desta comanda. None => o serviço não
            # tem preço para esse porte; devolvemos None e o app.py avisa o usuário.
            preco = _preco_servico_para_veiculo(cursor, id_servico, id_veiculo)
            if preco is None:
                print(f"Sem preço definido para o serviço {id_servico} no porte "
                      f"do veículo {id_veiculo}. Defina em servico_preco ou informe 'preco'.")
                return None

        # preco_aplicado CONGELA o valor cobrado neste item. Reajustes futuros na
        # tabela de preços NÃO alteram comandas antigas (histórico fiel do que foi pago).
        cursor.execute(
            """
            INSERT INTO ordem_servico_item (id_ordem, id_servico, id_funcionario, preco_aplicado)
            VALUES (%s, %s, %s, %s)
            RETURNING id_item;
            """,
            (id_ordem, id_servico, id_funcionario, preco)
        )
        id_item = cursor.fetchone()[0]

        _recalcular_total(cursor, id_ordem)
        conexao.commit()
        return id_item

    except Exception as erro:
        print(f"Erro ao adicionar serviço à comanda: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def remover_item(id_item):
    """
    Remove um item da comanda e recalcula o total da respectiva ordem.
    Retorna True se removeu, False caso contrário.
    """
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            "DELETE FROM ordem_servico_item WHERE id_item = %s RETURNING id_ordem;",
            (id_item,)
        )
        linha = cursor.fetchone()
        if not linha:
            return False

        _recalcular_total(cursor, linha[0])
        conexao.commit()
        return True

    except Exception as erro:
        print(f"Erro ao remover item: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def alterar_status(id_ordem, novo_status):
    """
    Altera o status da comanda, registrando os horários automaticamente:
      - 'em_execucao'  -> grava inicio_em (se ainda vazio);
      - 'finalizado'   -> grava finalizacao_em (se ainda vazio).
    Retorna True se atualizou, False caso contrário.
    """
    if novo_status not in STATUS_VALIDOS:
        print(f"Status inválido: {novo_status}. Use um de: {', '.join(STATUS_VALIDOS)}")
        return False

    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        # Os CASE gravam o horário só na PRIMEIRA vez que se entra no status (a condição
        # "IS NULL" impede sobrescrever). Assim, voltar a 'em_execucao' não zera o
        # inicio_em original — os tempos de início/fim ficam fiéis ao 1º acontecimento.
        cursor.execute(
            """
            UPDATE ordem_servico
            SET status = %s,
                inicio_em = CASE
                    WHEN %s = 'em_execucao' AND inicio_em IS NULL THEN NOW()
                    ELSE inicio_em END,
                finalizacao_em = CASE
                    WHEN %s = 'finalizado' AND finalizacao_em IS NULL THEN NOW()
                    ELSE finalizacao_em END,
                atualizado_em = NOW()
            WHERE id_ordem = %s;
            """,
            (novo_status, novo_status, novo_status, id_ordem)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao alterar status da comanda: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def registrar_pagamento(id_ordem, forma_pagamento):
    """
    Registra a forma de pagamento da comanda (ex.: 'dinheiro', 'pix', 'cartao').
    Retorna True se atualizou, False caso contrário.
    """
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            "UPDATE ordem_servico SET forma_pagamento = %s, atualizado_em = NOW() WHERE id_ordem = %s;",
            (forma_pagamento, id_ordem)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao registrar pagamento: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def salvar_financeiro(id_ordem, desconto=None, acrescimo=None, forma_pagamento=None,
                      parcelas=None, valor_pago=None, data_pagamento=None,
                      data_vencimento=None):
    """
    Atualiza os campos financeiros da comanda (desconto, acréscimo/juros, forma e
    parcelas, valor pago, datas de pagamento/vencimento). Apenas os campos
    informados (diferentes de None) são alterados (COALESCE).
    O valor_final (total - desconto + acréscimo) e o valor_pendente são calculados
    na exibição, não armazenados. Retorna True se atualizou, False caso contrário.
    """
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            UPDATE ordem_servico
            SET desconto        = COALESCE(%s, desconto),
                acrescimo       = COALESCE(%s, acrescimo),
                forma_pagamento = COALESCE(%s, forma_pagamento),
                parcelas        = COALESCE(%s, parcelas),
                valor_pago      = COALESCE(%s, valor_pago),
                data_pagamento  = COALESCE(%s, data_pagamento),
                data_vencimento = COALESCE(%s, data_vencimento),
                atualizado_em   = NOW()
            WHERE id_ordem = %s;
            """,
            (desconto, acrescimo, forma_pagamento, parcelas, valor_pago,
             data_pagamento, data_vencimento, id_ordem)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao salvar financeiro da comanda: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def buscar_comandas(status=None, id_cliente=None, somente_abertas=False):
    """
    Lista comandas com filtros opcionais. Traz nome do cliente e placa do veículo.
    'somente_abertas' = exclui as já entregues/canceladas (útil para o painel de fila).
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()

        query = """
            SELECT o.id_ordem, c.nome, v.placa, o.status, o.valor_total,
                   o.forma_pagamento, o.entrada_em
            FROM ordem_servico o
            JOIN cliente c ON c.id_cliente = o.id_cliente
            JOIN veiculo v ON v.id_veiculo = o.id_veiculo
            WHERE 1=1
        """
        parametros = []

        if status:
            query += " AND o.status = %s"
            parametros.append(status)
        if id_cliente:
            query += " AND o.id_cliente = %s"
            parametros.append(id_cliente)
        if somente_abertas:
            query += " AND o.status NOT IN ('entregue', 'cancelado')"

        query += " ORDER BY o.entrada_em;"

        cursor.execute(query, parametros)
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar comandas: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


def buscar_comanda_por_id(id_ordem):
    """
    Retorna um dicionário com a comanda e seus itens:
      {'comanda': (tupla), 'itens': [(id_item, nome_servico, preco_aplicado), ...]}
    Ou None se não encontrada.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        # ⚠️ ORDEM DAS COLUNAS = índices que o app.py lê da tupla 'comanda' (por número!):
        #   [0] id_ordem          [1] id_cliente     [2] id_veiculo   [3] id_funcionario
        #   [4] id_agendamento    [5] status         [6] forma_pagamento
        #   [7] valor_total       [8] entrada_em     [9] inicio_em    [10] finalizacao_em
        #   [11] desconto         [12] acrescimo     [13] parcelas    [14] valor_pago
        #   [15] data_pagamento   [16] data_vencimento
        # Se mudar esta ordem, ajuste abrir_detalhe() em app.py (usa 1,2,5,6,7,8,11..16).
        cursor.execute(
            """
            SELECT id_ordem, id_cliente, id_veiculo, id_funcionario, id_agendamento,
                   status, forma_pagamento, valor_total,
                   entrada_em, inicio_em, finalizacao_em,
                   desconto, acrescimo, parcelas, valor_pago,
                   data_pagamento, data_vencimento
            FROM ordem_servico
            WHERE id_ordem = %s;
            """,
            (id_ordem,)
        )
        comanda = cursor.fetchone()
        if not comanda:
            return None

        cursor.execute(
            """
            SELECT i.id_item, s.nome, i.preco_aplicado
            FROM ordem_servico_item i
            JOIN servico s ON s.id_servico = i.id_servico
            WHERE i.id_ordem = %s
            ORDER BY i.id_item;
            """,
            (id_ordem,)
        )
        itens = cursor.fetchall()
        return {'comanda': comanda, 'itens': itens}

    except Exception as erro:
        print(f"Erro ao buscar comanda: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def abrir_de_agendamento(id_agendamento, id_funcionario=None):
    """
    Converte um agendamento em comanda: cria a ordem com o mesmo cliente/veículo,
    copia os serviços do agendamento (com preço pelo porte) e marca o agendamento
    como 'em_execucao'. Retorna o id_ordem criado, ou None em caso de erro.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()

        # Tudo abaixo é UMA transação (um único commit no fim): lê o agendamento,
        # cria a comanda, copia os serviços com preço do porte e marca o agendamento
        # como em execução. Se qualquer passo falhar, o rollback desfaz o conjunto todo.
        cursor.execute(
            "SELECT id_cliente, id_veiculo FROM agendamento WHERE id_agendamento = %s;",
            (id_agendamento,)
        )
        ag = cursor.fetchone()
        if not ag:
            print(f"Agendamento {id_agendamento} não encontrado.")
            return None
        id_cliente, id_veiculo = ag

        cursor.execute(
            """
            INSERT INTO ordem_servico (id_cliente, id_veiculo, id_funcionario,
                                       id_agendamento, status)
            VALUES (%s, %s, %s, %s, 'aguardando')
            RETURNING id_ordem;
            """,
            (id_cliente, id_veiculo, id_funcionario, id_agendamento)
        )
        id_ordem = cursor.fetchone()[0]

        # Copia os serviços desejados do agendamento, com preço pelo porte
        cursor.execute(
            "SELECT id_servico FROM agendamento_servico WHERE id_agendamento = %s;",
            (id_agendamento,)
        )
        for (id_servico,) in cursor.fetchall():
            preco = _preco_servico_para_veiculo(cursor, id_servico, id_veiculo)
            if preco is None:
                print(f"Aviso: serviço {id_servico} sem preço para o porte do veículo "
                      f"{id_veiculo} — não adicionado automaticamente.")
                continue
            cursor.execute(
                """
                INSERT INTO ordem_servico_item (id_ordem, id_servico, id_funcionario, preco_aplicado)
                VALUES (%s, %s, %s, %s);
                """,
                (id_ordem, id_servico, id_funcionario, preco)
            )

        _recalcular_total(cursor, id_ordem)

        # Marca o agendamento como em execução
        cursor.execute(
            "UPDATE agendamento SET status = 'em_execucao', atualizado_em = NOW() WHERE id_agendamento = %s;",
            (id_agendamento,)
        )

        conexao.commit()
        return id_ordem

    except Exception as erro:
        print(f"Erro ao abrir comanda a partir do agendamento: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


# ================================================================
# TESTE RÁPIDO (rode este arquivo diretamente para testar)
# ================================================================
if __name__ == "__main__":
    from cadastro_veiculo import buscar_veiculos

    veiculos = buscar_veiculos()
    if not veiculos:
        print("Nenhum veículo cadastrado — cadastre um veículo antes de testar.")
    else:
        id_veiculo = veiculos[0][0]
        id_cliente = veiculos[0][1]
        print(f"Abrindo comanda para veículo {id_veiculo} (cliente {id_cliente})...")
        id_ordem = abrir_comanda(id_cliente=id_cliente, id_veiculo=id_veiculo)
        print(f"Comanda aberta: {id_ordem}")

        print("\nAdicionando serviço 1 (preço pelo porte)...")
        item = adicionar_servico(id_ordem, id_servico=1)
        print(f"Item criado: {item}")

        print("\nMudando status: em_execucao -> finalizado -> entregue...")
        alterar_status(id_ordem, 'em_execucao')
        alterar_status(id_ordem, 'finalizado')
        registrar_pagamento(id_ordem, 'pix')
        alterar_status(id_ordem, 'entregue')

        print("\nComanda final:")
        dados = buscar_comanda_por_id(id_ordem)
        print("  Comanda:", dados['comanda'])
        for it in dados['itens']:
            print("  Item:", it)
