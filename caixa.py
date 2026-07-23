"""
Módulo de Caixa
Sistema: Lava-Jato
Autor: RINEAL Analytics

Controle do caixa diário: abertura (com fundo inicial), movimentações
(entradas de comandas / saídas de despesas) e fechamento com conferência
do saldo esperado x saldo real. Só pode haver UM caixa aberto por vez.

Cada movimento guarda a FORMA DE PAGAMENTO, copiada da comanda ou da despesa
que o originou. É isso que permite separar, no fechamento, o dinheiro que está
de fato na gaveta do que caiu no banco (pix/cartão): sem essa separação o caixa
acusaria falta todo dia em que alguém pagasse no cartão.
"""

from decimal import Decimal

from conexao import conectar


# Formas que resultam em dinheiro físico na gaveta — as únicas que o operador
# consegue contar no fechamento. Movimento sem forma (NULL) conta como dinheiro:
# é o caso dos lançamentos anteriores a esta coluna existir e o padrão do balcão.
FORMAS_EM_ESPECIE = ('dinheiro',)


def _em_especie(forma):
    """True se a forma de pagamento vira dinheiro na gaveta (NULL = dinheiro)."""
    return (forma or 'dinheiro') in FORMAS_EM_ESPECIE


def caixa_aberto():
    """
    Retorna o caixa atualmente aberto (tupla), ou None se não houver nenhum.
    Tupla: (id_caixa, data_abertura, valor_inicial, id_funcionario).
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT id_caixa, data_abertura, valor_inicial, id_funcionario
            FROM caixa
            WHERE status = 'aberto'
            ORDER BY data_abertura DESC
            LIMIT 1;
            """
        )
        return cursor.fetchone()

    except Exception as erro:
        print(f"Erro ao consultar caixa aberto: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def abrir_caixa(valor_inicial=0, id_funcionario=None, observacoes=None):
    """
    Abre um novo caixa com o fundo inicial informado.
    Falha se já existir um caixa aberto. Retorna o id_caixa, ou None.
    """
    # Invariante do módulo: só pode haver UM caixa aberto por vez. Barra a abertura
    # se já existir um (senão as movimentações não saberiam a qual caixa pertencem).
    if caixa_aberto():
        print("Já existe um caixa aberto. Feche-o antes de abrir outro.")
        return None

    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            INSERT INTO caixa (valor_inicial, id_funcionario, status, observacoes)
            VALUES (%s, %s, 'aberto', %s)
            RETURNING id_caixa;
            """,
            (valor_inicial, id_funcionario, observacoes)
        )
        id_caixa = cursor.fetchone()[0]
        conexao.commit()
        return id_caixa

    except Exception as erro:
        print(f"Erro ao abrir caixa: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def _registrar_movimento(tipo, valor, descricao, id_ordem, id_despesa, forma_pagamento):
    """Insere um movimento (entrada/saida) no caixa aberto. Uso interno."""
    if valor is None or valor <= 0:
        print("Valor do movimento deve ser maior que zero.")
        return None

    aberto = caixa_aberto()
    if not aberto:
        print("Nenhum caixa aberto. Abra o caixa antes de registrar movimentos.")
        return None
    id_caixa = aberto[0]

    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            INSERT INTO caixa_movimento (id_caixa, tipo, valor, descricao, id_ordem,
                                         id_despesa, forma_pagamento)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id_movimento;
            """,
            (id_caixa, tipo, valor, descricao, id_ordem, id_despesa, forma_pagamento)
        )
        id_mov = cursor.fetchone()[0]
        conexao.commit()
        return id_mov

    except Exception as erro:
        print(f"Erro ao registrar movimento de caixa: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def registrar_entrada(valor, descricao=None, id_ordem=None, forma_pagamento=None):
    """Registra uma entrada no caixa aberto (ex.: pagamento de comanda)."""
    return _registrar_movimento('entrada', valor, descricao, id_ordem, None,
                                forma_pagamento)


def registrar_saida(valor, descricao=None, id_despesa=None, forma_pagamento=None):
    """Registra uma saída no caixa aberto (ex.: despesa paga no dia)."""
    return _registrar_movimento('saida', valor, descricao, None, id_despesa,
                                forma_pagamento)


def total_entradas_da_ordem(id_ordem):
    """
    Soma tudo que JÁ entrou no caixa para uma comanda (em qualquer caixa,
    aberto ou fechado). Usado pela tela de Comandas ao salvar o pagamento:
    lança só a DIFERENÇA para o valor pago, evitando entrada duplicada
    quando o pagamento é salvo mais de uma vez.
    Retorna Decimal (0 se nada lançado), ou None em caso de erro.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT COALESCE(SUM(valor), 0)
            FROM caixa_movimento
            WHERE id_ordem = %s AND tipo = 'entrada';
            """,
            (id_ordem,)
        )
        return cursor.fetchone()[0]

    except Exception as erro:
        print(f"Erro ao somar entradas da comanda no caixa: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def total_saidas_da_despesa(id_despesa):
    """
    Espelho de total_entradas_da_ordem para o outro lado da ponte: soma tudo que
    JÁ saiu do caixa para uma despesa (em qualquer caixa, aberto ou fechado).
    Usado pela tela de Despesas ao marcar como paga: lança só a DIFERENÇA, então
    marcar/corrigir o pagamento mais de uma vez não duplica a saída.
    Retorna Decimal (0 se nada lançado), ou None em caso de erro.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT COALESCE(SUM(valor), 0)
            FROM caixa_movimento
            WHERE id_despesa = %s AND tipo = 'saida';
            """,
            (id_despesa,)
        )
        return cursor.fetchone()[0]

    except Exception as erro:
        print(f"Erro ao somar saídas da despesa no caixa: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def resumo_por_forma(id_caixa=None):
    """
    Quebra o caixa por forma de pagamento — a base da conferência do fechamento.
    Se id_caixa for None, usa o caixa aberto.

    Retorna dict, ou None em caso de erro:
      {
        'valor_inicial':      Decimal,   fundo de caixa da abertura
        'linhas':             [(forma, entradas, saidas), ...] ordenadas por forma
        'outras_formas':      idem, só as que NÃO são espécie (pix, cartão...)
        'entradas':           Decimal,   total de entradas (todas as formas)
        'saidas':             Decimal,   total de saídas (todas as formas)
        'esperado_total':     Decimal,   fundo + entradas - saídas  (o giro do dia)
        'esperado_dinheiro':  Decimal,   fundo + entradas em espécie - saídas em espécie
      }

    'esperado_dinheiro' é o que deve estar NA GAVETA e o único número comparável
    com a contagem física; 'esperado_total' inclui pix/cartão, que estão no banco.
    """
    if id_caixa is None:
        aberto = caixa_aberto()
        if not aberto:
            print("Nenhum caixa aberto.")
            return None
        id_caixa = aberto[0]

    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute("SELECT valor_inicial FROM caixa WHERE id_caixa = %s;", (id_caixa,))
        linha = cursor.fetchone()
        if not linha:
            print(f"Caixa {id_caixa} não encontrado.")
            return None
        valor_inicial = linha[0]

        # Movimento sem forma (NULL/'') conta como dinheiro — ver FORMAS_EM_ESPECIE.
        # O agrupamento normaliza aqui, no banco, para não aparecer "—" na tela.
        cursor.execute(
            """
            SELECT COALESCE(NULLIF(BTRIM(forma_pagamento), ''), 'dinheiro') AS forma,
                   COALESCE(SUM(CASE WHEN tipo = 'entrada' THEN valor END), 0),
                   COALESCE(SUM(CASE WHEN tipo = 'saida'   THEN valor END), 0)
            FROM caixa_movimento
            WHERE id_caixa = %s
            GROUP BY 1
            ORDER BY 1;
            """,
            (id_caixa,)
        )
        linhas = cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao resumir o caixa por forma de pagamento: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()

    entradas = sum((l[1] for l in linhas), Decimal('0'))
    saidas = sum((l[2] for l in linhas), Decimal('0'))
    especie = [l for l in linhas if _em_especie(l[0])]
    entradas_especie = sum((l[1] for l in especie), Decimal('0'))
    saidas_especie = sum((l[2] for l in especie), Decimal('0'))

    return {
        'valor_inicial': valor_inicial,
        'linhas': linhas,
        'outras_formas': [l for l in linhas if not _em_especie(l[0])],
        'entradas': entradas,
        'saidas': saidas,
        'esperado_total': valor_inicial + entradas - saidas,
        'esperado_dinheiro': valor_inicial + entradas_especie - saidas_especie,
    }


def saldo_esperado(id_caixa=None):
    """
    Calcula o saldo esperado do caixa: valor_inicial + entradas - saídas.
    Se id_caixa for None, usa o caixa aberto. Retorna Decimal/None.
    """
    if id_caixa is None:
        aberto = caixa_aberto()
        if not aberto:
            print("Nenhum caixa aberto.")
            return None
        id_caixa = aberto[0]

    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        # saldo = fundo inicial + total de entradas - total de saídas.
        # O CASE WHEN dentro do SUM soma o valor só quando o tipo bate (senão é NULL,
        # que o SUM ignora); COALESCE(...,0) cobre o caixa ainda sem movimentos.
        # LEFT JOIN garante que um caixa sem nenhum movimento ainda retorne uma linha.
        cursor.execute(
            """
            SELECT c.valor_inicial
                 + COALESCE(SUM(CASE WHEN m.tipo = 'entrada' THEN m.valor END), 0)
                 - COALESCE(SUM(CASE WHEN m.tipo = 'saida'   THEN m.valor END), 0)
            FROM caixa c
            LEFT JOIN caixa_movimento m ON m.id_caixa = c.id_caixa
            WHERE c.id_caixa = %s
            GROUP BY c.valor_inicial;
            """,
            (id_caixa,)
        )
        linha = cursor.fetchone()
        return linha[0] if linha else None

    except Exception as erro:
        print(f"Erro ao calcular saldo esperado: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def fechar_caixa(saldo_real, id_funcionario=None, observacoes=None):
    """
    Fecha o caixa aberto. O 'saldo_real' é o DINHEIRO CONTADO NA GAVETA, então a
    conferência é feita contra o esperado EM ESPÉCIE — pix e cartão entraram no
    caixa mas foram para o banco, e cobrá-los da gaveta faria o caixa acusar
    falta todo dia em que alguém pagasse no cartão.

    Retorna dict, ou None se não houver caixa aberto:
      {id_caixa, esperado (=espécie), esperado_total, real, diferenca, resumo}
    'diferenca' > 0 sobra, < 0 falta. 'resumo' é o resumo_por_forma() do caixa.
    """
    aberto = caixa_aberto()
    if not aberto:
        print("Nenhum caixa aberto para fechar.")
        return None
    id_caixa = aberto[0]

    # O saldo_real chega da interface como float; o saldo esperado vem do banco
    # como Decimal. Converter aqui para Decimal (via str, sem ruído de binário)
    # evita o 'float - Decimal' (TypeError) no cálculo da diferença mais abaixo.
    saldo_real = Decimal(str(saldo_real))

    resumo = resumo_por_forma(id_caixa)
    esperado = resumo['esperado_dinheiro'] if resumo else None

    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            UPDATE caixa
            SET status = 'fechado',
                data_fechamento = NOW(),
                saldo_final = %s,
                id_funcionario = COALESCE(%s, id_funcionario),
                observacoes = COALESCE(%s, observacoes)
            WHERE id_caixa = %s;
            """,
            (saldo_real, id_funcionario, observacoes, id_caixa)
        )
        conexao.commit()

        diferenca = saldo_real - esperado if esperado is not None else None
        return {
            'id_caixa': id_caixa,
            'esperado': esperado,                 # em espécie (o que estava na gaveta)
            'esperado_total': resumo['esperado_total'] if resumo else None,
            'real': saldo_real,
            'diferenca': diferenca,
            'resumo': resumo,
        }

    except Exception as erro:
        print(f"Erro ao fechar caixa: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def movimentos_do_caixa(id_caixa):
    """
    Lista as movimentações de um caixa, da mais antiga para a mais recente.
    Tuplas: (id_movimento, tipo, valor, descricao, id_ordem, id_despesa, data_mov,
             forma_pagamento).
    'forma_pagamento' entra no FIM do SELECT de propósito: a tela lê a tupla por
    posição, então os índices antigos seguem valendo.
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT id_movimento, tipo, valor, descricao, id_ordem, id_despesa, data_mov,
                   forma_pagamento
            FROM caixa_movimento
            WHERE id_caixa = %s
            ORDER BY data_mov;
            """,
            (id_caixa,)
        )
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar movimentos do caixa: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


def historico_caixas(limite=30):
    """
    Lista os caixas (abertos e fechados), do mais recente para o mais antigo.
    Tuplas: (id_caixa, data_abertura, data_fechamento, valor_inicial,
             saldo_final, status).
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT id_caixa, data_abertura, data_fechamento, valor_inicial,
                   saldo_final, status
            FROM caixa
            ORDER BY data_abertura DESC
            LIMIT %s;
            """,
            (limite,)
        )
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar histórico de caixas: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


# ================================================================
# TESTE RÁPIDO (rode este arquivo diretamente para testar)
# ================================================================
if __name__ == "__main__":
    print("Abrindo caixa com fundo de R$100...")
    cid = abrir_caixa(valor_inicial=100, observacoes="Caixa de teste")
    print(f"Caixa aberto: {cid}")

    print("\nTentando abrir outro caixa (deve falhar):")
    print("  ->", abrir_caixa(valor_inicial=50))

    if cid:
        print("\nRegistrando entradas de R$40 (dinheiro) e R$60 (pix), saída de R$25...")
        registrar_entrada(40, "Pagamento comanda 1", id_ordem=1, forma_pagamento="dinheiro")
        registrar_entrada(60, "Pagamento comanda 2", id_ordem=1, forma_pagamento="pix")
        registrar_saida(25, "Compra de pano", forma_pagamento="dinheiro")

        print("Saldo esperado, giro total (100 + 100 - 25 = 175):", saldo_esperado(cid))

        r = resumo_por_forma(cid)
        print("\nResumo por forma:")
        for forma, ent, sai in r['linhas']:
            print(f"   {forma:<10} entradas {ent}  saídas {sai}")
        print("  Esperado na GAVETA (100 + 40 - 25 = 115):", r['esperado_dinheiro'])
        print("  Esperado TOTAL    (com o pix)          :", r['esperado_total'])

        print("\nFechando com R$115 contados na gaveta (deve bater, apesar do pix)...")
        resultado = fechar_caixa(saldo_real=115)
        print("  Esperado (espécie):", resultado['esperado'])
        print("  Diferença         :", resultado['diferenca'])

        print("\nMovimentos do caixa:")
        for m in movimentos_do_caixa(cid):
            print("  ", m)
