"""
Módulo de Agendamento
Sistema: Lava-Jato
Autor: RINEAL Analytics

CRUD da tabela agendamento + serviços desejados (agendamento_servico).
Inclui controle de status e verificação de conflito de horário/box.
"""

from conexao import conectar

# Valores aceitos pelos CHECKs do banco (mantenha em sincronia com criar_tabelas.sql).
STATUS_VALIDOS = ('agendado', 'confirmado', 'em_espera', 'em_execucao',
                  'concluido', 'cancelado', 'nao_compareceu')
ORIGENS_VALIDAS = ('manual', 'whatsapp', 'telefone', 'app')

# Status que ainda "ocupam" um box/horário (usados na checagem de conflito).
STATUS_ATIVOS = ('agendado', 'confirmado', 'em_espera', 'em_execucao')


def verificar_conflito(data_hora, duracao_estimada_min, box,
                       ignorar_id=None):
    """
    Verifica se já existe agendamento ATIVO no mesmo box cujo intervalo de tempo
    se sobrepõe ao informado. Sem box (None), não há conflito de box a checar.

    'ignorar_id' permite ignorar o próprio agendamento ao remarcar/editar.
    Retorna a lista de agendamentos conflitantes (vazia = sem conflito).
    """
    if not box:
        return []

    # Se a duração não foi informada, assume 30 min só para o cálculo do intervalo.
    duracao = duracao_estimada_min if duracao_estimada_min else 30

    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()

        # Dois intervalos [inicioA, fimA] e [inicioB, fimB] se SOBREPÕEM quando
        # inicioA < fimB E inicioB < fimA. Aqui A = o novo, B = o já existente:
        #   1ª condição: novo_inicio (%s) < fim_existente (data_hora + duração existente)
        #   2ª condição: inicio_existente (data_hora) < novo_fim (novo_inicio + duração)
        # `|| ' minutes'` monta o texto e ::interval converte em intervalo de tempo.
        # status = ANY(%s): só conta agendamentos que ainda ocupam o box (STATUS_ATIVOS).
        query = """
            SELECT id_agendamento, data_hora, duracao_estimada_min, status
            FROM agendamento
            WHERE box = %s
              AND status = ANY(%s)
              AND %s < (data_hora + (COALESCE(duracao_estimada_min, 30) || ' minutes')::interval)
              AND data_hora < (%s::timestamp + (%s || ' minutes')::interval)
        """
        parametros = [box, list(STATUS_ATIVOS), data_hora, data_hora, duracao]

        if ignorar_id is not None:
            query += " AND id_agendamento <> %s"
            parametros.append(ignorar_id)

        cursor.execute(query, parametros)
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao verificar conflito: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


def criar_agendamento(id_cliente, id_veiculo, data_hora, servicos=None,
                      duracao_estimada_min=None, box=None, origem='manual',
                      observacoes=None, checar_conflito=True):
    """
    Cria um agendamento e vincula os serviços desejados (lista de id_servico).
    Faz tudo numa transação só: ou grava o agendamento + serviços, ou nada.

    Retorna o id_agendamento criado, ou None em caso de erro/conflito.
    """
    if origem not in ORIGENS_VALIDAS:
        print(f"Origem inválida: {origem}. Use uma de: {', '.join(ORIGENS_VALIDAS)}")
        return None

    if checar_conflito and box:
        conflitos = verificar_conflito(data_hora, duracao_estimada_min, box)
        if conflitos:
            print(f"Conflito de horário no box '{box}'. Agendamentos: "
                  f"{[c[0] for c in conflitos]}")
            return None

    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            INSERT INTO agendamento (id_cliente, id_veiculo, data_hora,
                                     duracao_estimada_min, box, origem, observacoes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id_agendamento;
            """,
            (id_cliente, id_veiculo, data_hora, duracao_estimada_min,
             box, origem, observacoes)
        )
        id_agendamento = cursor.fetchone()[0]

        # Mesma transação: insere o agendamento E seus serviços. set() remove ids
        # repetidos na lista; ON CONFLICT DO NOTHING evita erro se o par já existir.
        # Como não há commit no meio, se um serviço falhar o rollback desfaz TUDO
        # (não fica agendamento sem os serviços).
        for id_servico in set(servicos or []):
            cursor.execute(
                """
                INSERT INTO agendamento_servico (id_agendamento, id_servico)
                VALUES (%s, %s)
                ON CONFLICT (id_agendamento, id_servico) DO NOTHING;
                """,
                (id_agendamento, id_servico)
            )

        conexao.commit()
        return id_agendamento

    except Exception as erro:
        print(f"Erro ao criar agendamento: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def buscar_agendamentos(data=None, status=None, id_cliente=None):
    """
    Lista agendamentos com filtros opcionais:
      - data: string 'YYYY-MM-DD' -> só os daquele dia;
      - status: filtra por um status específico;
      - id_cliente: só os de um cliente.
    Traz nome do cliente e placa do veículo (JOINs).
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()

        query = """
            SELECT a.id_agendamento, a.data_hora, c.nome, v.placa,
                   a.duracao_estimada_min, a.box, a.status, a.origem
            FROM agendamento a
            JOIN cliente c ON c.id_cliente = a.id_cliente
            JOIN veiculo v ON v.id_veiculo = a.id_veiculo
            WHERE 1=1
        """
        parametros = []

        if data:
            query += " AND a.data_hora::date = %s"
            parametros.append(data)
        if status:
            query += " AND a.status = %s"
            parametros.append(status)
        if id_cliente:
            query += " AND a.id_cliente = %s"
            parametros.append(id_cliente)

        query += " ORDER BY a.data_hora;"

        cursor.execute(query, parametros)
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar agendamentos: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


def buscar_agendamento_por_id(id_agendamento):
    """
    Retorna um dicionário com os dados do agendamento e a lista de serviços:
      {'agendamento': (tupla com os campos), 'servicos': [(id_servico, nome), ...]}
    Ou None se não encontrado.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT id_agendamento, id_cliente, id_veiculo, data_hora,
                   duracao_estimada_min, box, status, origem, observacoes
            FROM agendamento
            WHERE id_agendamento = %s;
            """,
            (id_agendamento,)
        )
        ag = cursor.fetchone()
        if not ag:
            return None

        cursor.execute(
            """
            SELECT s.id_servico, s.nome
            FROM agendamento_servico ags
            JOIN servico s ON s.id_servico = ags.id_servico
            WHERE ags.id_agendamento = %s
            ORDER BY s.nome;
            """,
            (id_agendamento,)
        )
        servicos = cursor.fetchall()
        return {'agendamento': ag, 'servicos': servicos}

    except Exception as erro:
        print(f"Erro ao buscar agendamento: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def alterar_status(id_agendamento, novo_status):
    """
    Altera o status de um agendamento (ex.: agendado -> confirmado -> concluido).
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
        cursor.execute(
            "UPDATE agendamento SET status = %s, atualizado_em = NOW() WHERE id_agendamento = %s;",
            (novo_status, id_agendamento)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao alterar status: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def remarcar(id_agendamento, nova_data_hora, novo_box=None,
             nova_duracao_min=None, checar_conflito=True):
    """
    Remarca um agendamento para outra data/hora (e opcionalmente outro box/duração).
    Checa conflito ignorando o próprio agendamento. Campos None mantêm o valor atual.
    Retorna True se remarcou, False caso contrário.
    """
    box_para_checar = novo_box
    if checar_conflito and box_para_checar is None:
        # Se não trocou o box, usa o box atual para a checagem de conflito.
        atual = buscar_agendamento_por_id(id_agendamento)
        if atual:
            box_para_checar = atual['agendamento'][5]  # coluna box

    if checar_conflito and box_para_checar:
        conflitos = verificar_conflito(nova_data_hora, nova_duracao_min,
                                       box_para_checar, ignorar_id=id_agendamento)
        if conflitos:
            print(f"Conflito ao remarcar no box '{box_para_checar}': "
                  f"{[c[0] for c in conflitos]}")
            return False

    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            UPDATE agendamento
            SET data_hora = %s,
                box = COALESCE(%s, box),
                duracao_estimada_min = COALESCE(%s, duracao_estimada_min),
                atualizado_em = NOW()
            WHERE id_agendamento = %s;
            """,
            (nova_data_hora, novo_box, nova_duracao_min, id_agendamento)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao remarcar agendamento: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def cancelar_agendamento(id_agendamento):
    """Atalho para marcar o agendamento como 'cancelado'."""
    return alterar_status(id_agendamento, 'cancelado')


def registrar_nao_comparecimento(id_agendamento):
    """Atalho para marcar o agendamento como 'nao_compareceu' (no-show)."""
    return alterar_status(id_agendamento, 'nao_compareceu')


# ================================================================
# TESTE RÁPIDO (rode este arquivo diretamente para testar)
# ================================================================
if __name__ == "__main__":
    from cadastro_veiculo import buscar_veiculos

    veiculos = buscar_veiculos()
    if not veiculos:
        print("Nenhum veículo cadastrado — cadastre um veículo antes de testar agendamento.")
    else:
        id_veiculo = veiculos[0][0]
        id_cliente = veiculos[0][1]
        print(f"Usando veículo {id_veiculo} do cliente {id_cliente}.")

        print("\nCriando agendamento (box A, 14:00, 30 min)...")
        id_ag = criar_agendamento(
            id_cliente=id_cliente,
            id_veiculo=id_veiculo,
            data_hora="2026-06-25 14:00:00",
            servicos=[1],
            duracao_estimada_min=30,
            box="A",
            origem="manual"
        )
        print(f"Agendamento criado: {id_ag}")

        print("\nTentando conflito no MESMO box/horário (deve ser bloqueado)...")
        id_conflito = criar_agendamento(
            id_cliente=id_cliente,
            id_veiculo=id_veiculo,
            data_hora="2026-06-25 14:15:00",
            duracao_estimada_min=30,
            box="A"
        )
        print(f"Resultado (esperado None): {id_conflito}")

        print("\nAgendamentos do dia 2026-06-25:")
        for a in buscar_agendamentos(data="2026-06-25"):
            print(" ", a)
