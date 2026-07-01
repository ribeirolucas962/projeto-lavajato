"""
Módulo de Fidelidade
Sistema: Lava-Jato
Autor: RINEAL Analytics

Sistema de pontos por cliente: acúmulo (ex.: a cada comanda finalizada) e
resgate de benefícios, sempre com histórico em fidelidade_movimento.
O saldo fica em fidelidade_saldo e é atualizado na MESMA transação do movimento.
"""

from conexao import conectar


def saldo_pontos(id_cliente):
    """Retorna o saldo de pontos do cliente (0 se ainda não tiver saldo)."""
    conexao = conectar()
    if not conexao:
        return 0

    try:
        cursor = conexao.cursor()
        cursor.execute(
            "SELECT pontos FROM fidelidade_saldo WHERE id_cliente = %s;",
            (id_cliente,)
        )
        linha = cursor.fetchone()
        return linha[0] if linha else 0

    except Exception as erro:
        print(f"Erro ao consultar saldo de pontos: {erro}")
        return 0

    finally:
        cursor.close()
        conexao.close()


def acumular_pontos(id_cliente, pontos, id_ordem=None, descricao=None):
    """
    Credita pontos ao cliente: soma ao saldo (criando-o se necessário) e grava
    o movimento de acúmulo. Tudo numa transação. Retorna o novo saldo, ou None.
    """
    if pontos is None or pontos <= 0:
        print("Pontos a acumular devem ser maiores que zero.")
        return None

    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()

        # UPSERT que SOMA (não sobrescreve): se o cliente ainda não tem linha de saldo,
        # cria com 'pontos'; se já tem, ACUMULA (saldo_atual + pontos). Note o
        # "fidelidade_saldo.pontos + EXCLUDED.pontos" — sem esse '+', o saldo seria
        # substituído em vez de somado (compare com definir_preco, que sobrescreve).
        cursor.execute(
            """
            INSERT INTO fidelidade_saldo (id_cliente, pontos)
            VALUES (%s, %s)
            ON CONFLICT (id_cliente)
            DO UPDATE SET pontos = fidelidade_saldo.pontos + EXCLUDED.pontos,
                          atualizado_em = NOW()
            RETURNING pontos;
            """,
            (id_cliente, pontos)
        )
        novo_saldo = cursor.fetchone()[0]

        cursor.execute(
            """
            INSERT INTO fidelidade_movimento (id_cliente, tipo, pontos, id_ordem, descricao)
            VALUES (%s, 'acumulo', %s, %s, %s);
            """,
            (id_cliente, pontos, id_ordem, descricao)
        )

        conexao.commit()
        return novo_saldo

    except Exception as erro:
        print(f"Erro ao acumular pontos: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def resgatar_pontos(id_cliente, pontos, descricao=None):
    """
    Resgata pontos do cliente (se houver saldo suficiente): subtrai do saldo e
    grava o movimento de resgate. Tudo numa transação.
    Retorna o novo saldo, ou None em erro/saldo insuficiente.
    """
    if pontos is None or pontos <= 0:
        print("Pontos a resgatar devem ser maiores que zero.")
        return None

    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()

        # Trava a linha do saldo e confere antes de debitar
        cursor.execute(
            "SELECT pontos FROM fidelidade_saldo WHERE id_cliente = %s FOR UPDATE;",
            (id_cliente,)
        )
        linha = cursor.fetchone()
        saldo_atual = linha[0] if linha else 0

        if saldo_atual < pontos:
            print(f"Saldo de pontos insuficiente: disponível {saldo_atual}, solicitado {pontos}.")
            conexao.rollback()
            return None

        cursor.execute(
            """
            UPDATE fidelidade_saldo
            SET pontos = pontos - %s, atualizado_em = NOW()
            WHERE id_cliente = %s
            RETURNING pontos;
            """,
            (pontos, id_cliente)
        )
        novo_saldo = cursor.fetchone()[0]

        cursor.execute(
            """
            INSERT INTO fidelidade_movimento (id_cliente, tipo, pontos, descricao)
            VALUES (%s, 'resgate', %s, %s);
            """,
            (id_cliente, pontos, descricao)
        )

        conexao.commit()
        return novo_saldo

    except Exception as erro:
        print(f"Erro ao resgatar pontos: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def acumular_por_comanda(id_ordem, pontos=1, descricao=None):
    """
    Atalho para creditar pontos a partir de uma comanda finalizada.
    Descobre o cliente pela ordem e evita acumular duas vezes pela mesma comanda.
    Retorna o novo saldo, ou None se já creditado / em erro.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute("SELECT id_cliente FROM ordem_servico WHERE id_ordem = %s;", (id_ordem,))
        linha = cursor.fetchone()
        if not linha:
            print(f"Comanda {id_ordem} não encontrada.")
            return None
        id_cliente = linha[0]

        # Idempotência: se JÁ existe um movimento de 'acumulo' para esta comanda, não
        # credita de novo. Evita pontos em dobro se a função for chamada 2x pela mesma
        # comanda (ex.: reprocessamento). O LIMIT 1 para na primeira ocorrência.
        cursor.execute(
            """
            SELECT 1 FROM fidelidade_movimento
            WHERE id_ordem = %s AND tipo = 'acumulo' LIMIT 1;
            """,
            (id_ordem,)
        )
        if cursor.fetchone():
            print(f"Comanda {id_ordem} já gerou pontos — ignorando.")
            return None

    except Exception as erro:
        print(f"Erro ao preparar acúmulo por comanda: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()

    # Reusa acumular_pontos (abre sua própria conexão/transação)
    return acumular_pontos(id_cliente, pontos, id_ordem=id_ordem,
                           descricao=descricao or f"Pontos da comanda {id_ordem}")


def extrato_pontos(id_cliente, limite=50):
    """
    Lista o histórico de movimentos de pontos do cliente, do mais recente ao mais antigo.
    Tuplas: (id_movimento, tipo, pontos, id_ordem, descricao, data_mov).
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT id_movimento, tipo, pontos, id_ordem, descricao, data_mov
            FROM fidelidade_movimento
            WHERE id_cliente = %s
            ORDER BY data_mov DESC
            LIMIT %s;
            """,
            (id_cliente, limite)
        )
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar extrato de pontos: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


# ================================================================
# TESTE RÁPIDO (rode este arquivo diretamente para testar)
# ================================================================
if __name__ == "__main__":
    cliente = 1

    print(f"Saldo inicial do cliente {cliente}:", saldo_pontos(cliente))

    print("\nAcumulando 10 pontos...")
    print("  novo saldo:", acumular_pontos(cliente, 10, descricao="Bônus inicial"))

    print("\nAcumulando pela comanda 1 (1 ponto)...")
    print("  novo saldo:", acumular_por_comanda(1, pontos=1))

    print("\nTentando de novo pela comanda 1 (deve ignorar):")
    print("  ->", acumular_por_comanda(1, pontos=1))

    print("\nResgatando 5 pontos...")
    print("  novo saldo:", resgatar_pontos(cliente, 5, descricao="Lavagem grátis"))

    print("\nResgatando 999 pontos (deve falhar):")
    print("  ->", resgatar_pontos(cliente, 999))

    print("\nExtrato de pontos:")
    for m in extrato_pontos(cliente):
        print("  ", m)
