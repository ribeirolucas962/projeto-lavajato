"""
Módulo de Caixa
Sistema: Lava-Jato
Autor: RINEAL Analytics

Controle do caixa diário: abertura (com fundo inicial), movimentações
(entradas de comandas / saídas de despesas) e fechamento com conferência
do saldo esperado x saldo real. Só pode haver UM caixa aberto por vez.
"""

from conexao import conectar


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


def _registrar_movimento(tipo, valor, descricao, id_ordem, id_despesa):
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
            INSERT INTO caixa_movimento (id_caixa, tipo, valor, descricao, id_ordem, id_despesa)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id_movimento;
            """,
            (id_caixa, tipo, valor, descricao, id_ordem, id_despesa)
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


def registrar_entrada(valor, descricao=None, id_ordem=None):
    """Registra uma entrada no caixa aberto (ex.: pagamento de comanda)."""
    return _registrar_movimento('entrada', valor, descricao, id_ordem, None)


def registrar_saida(valor, descricao=None, id_despesa=None):
    """Registra uma saída no caixa aberto (ex.: despesa paga no dia)."""
    return _registrar_movimento('saida', valor, descricao, None, id_despesa)


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
    Fecha o caixa aberto. Compara o saldo esperado (calculado) com o saldo_real
    (contado na gaveta) e grava o fechamento.
    Retorna dict {id_caixa, esperado, real, diferenca}, ou None se não houver caixa.
    """
    aberto = caixa_aberto()
    if not aberto:
        print("Nenhum caixa aberto para fechar.")
        return None
    id_caixa = aberto[0]

    esperado = saldo_esperado(id_caixa)

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
            'esperado': esperado,
            'real': saldo_real,
            'diferenca': diferenca,
        }

    except Exception as erro:
        print(f"Erro ao fechar caixa: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def movimentos_do_caixa(id_caixa):
    """Lista as movimentações de um caixa, da mais antiga para a mais recente."""
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT id_movimento, tipo, valor, descricao, id_ordem, id_despesa, data_mov
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
        print("\nRegistrando entrada de R$40 (comanda) e saída de R$25 (despesa)...")
        registrar_entrada(40, "Pagamento comanda 1", id_ordem=1)
        registrar_saida(25, "Compra de pano")

        print("Saldo esperado (100 + 40 - 25 = 115):", saldo_esperado(cid))

        print("\nFechando caixa com saldo real contado de R$110...")
        resultado = fechar_caixa(saldo_real=110)
        print("  Resultado:", resultado)

        print("\nMovimentos do caixa:")
        for m in movimentos_do_caixa(cid):
            print("  ", m)
