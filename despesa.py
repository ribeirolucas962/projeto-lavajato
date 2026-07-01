"""
Módulo de Despesa
Sistema: Lava-Jato
Autor: RINEAL Analytics

CRUD da tabela despesa (saídas financeiras). Controla vencimento x pagamento,
categoria e fornecedor, e fornece totais por período (base de lucratividade).
"""

from conexao import conectar


def inserir_despesa(descricao, valor, categoria=None, data_vencimento=None,
                    data_pagamento=None, id_fornecedor=None, forma_pagamento=None):
    """
    Registra uma despesa. Se 'data_pagamento' for None, a despesa fica em aberto.
    Retorna o id_despesa criado, ou None em caso de erro.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            INSERT INTO despesa (descricao, categoria, valor, data_vencimento,
                                 data_pagamento, id_fornecedor, forma_pagamento)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id_despesa;
            """,
            (descricao, categoria, valor, data_vencimento, data_pagamento,
             id_fornecedor, forma_pagamento)
        )
        id_despesa = cursor.fetchone()[0]
        conexao.commit()
        return id_despesa

    except Exception as erro:
        print(f"Erro ao inserir despesa: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def buscar_despesas(categoria=None, data_inicio=None, data_fim=None,
                    apenas_em_aberto=False):
    """
    Lista despesas com filtros opcionais:
      - categoria: filtra por categoria;
      - data_inicio / data_fim: intervalo sobre a data de vencimento ('YYYY-MM-DD');
      - apenas_em_aberto: só as ainda não pagas (data_pagamento IS NULL).
    Traz o nome do fornecedor quando houver.
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()

        query = """
            SELECT d.id_despesa, d.descricao, d.categoria, d.valor,
                   d.data_vencimento, d.data_pagamento, f.nome_razao_social,
                   d.forma_pagamento
            FROM despesa d
            LEFT JOIN fornecedor f ON f.id_fornecedor = d.id_fornecedor
            WHERE 1=1
        """
        parametros = []

        if categoria:
            query += " AND d.categoria = %s"
            parametros.append(categoria)
        if data_inicio:
            query += " AND d.data_vencimento >= %s"
            parametros.append(data_inicio)
        if data_fim:
            query += " AND d.data_vencimento <= %s"
            parametros.append(data_fim)
        if apenas_em_aberto:
            query += " AND d.data_pagamento IS NULL"

        query += " ORDER BY d.data_vencimento;"

        cursor.execute(query, parametros)
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar despesas: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


def buscar_despesa_por_id(id_despesa):
    """Busca uma despesa pelo id."""
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT id_despesa, descricao, categoria, valor, data_vencimento,
                   data_pagamento, id_fornecedor, forma_pagamento
            FROM despesa
            WHERE id_despesa = %s;
            """,
            (id_despesa,)
        )
        return cursor.fetchone()

    except Exception as erro:
        print(f"Erro ao buscar despesa: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def editar_despesa(id_despesa, descricao=None, categoria=None, valor=None,
                   data_vencimento=None, data_pagamento=None, id_fornecedor=None,
                   forma_pagamento=None):
    """
    Atualiza uma despesa. Apenas os campos informados são alterados.
    (Para quitar uma despesa em aberto, prefira marcar_como_paga.)
    """
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            UPDATE despesa
            SET descricao = COALESCE(%s, descricao),
                categoria = COALESCE(%s, categoria),
                valor = COALESCE(%s, valor),
                data_vencimento = COALESCE(%s, data_vencimento),
                data_pagamento = COALESCE(%s, data_pagamento),
                id_fornecedor = COALESCE(%s, id_fornecedor),
                forma_pagamento = COALESCE(%s, forma_pagamento),
                atualizado_em = NOW()
            WHERE id_despesa = %s;
            """,
            (descricao, categoria, valor, data_vencimento, data_pagamento,
             id_fornecedor, forma_pagamento, id_despesa)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao editar despesa: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def marcar_como_paga(id_despesa, data_pagamento=None, forma_pagamento=None):
    """
    Quita uma despesa: registra a data de pagamento (hoje, se não informada)
    e opcionalmente a forma de pagamento. Retorna True se atualizou.
    """
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            UPDATE despesa
            SET data_pagamento = COALESCE(%s, CURRENT_DATE),
                forma_pagamento = COALESCE(%s, forma_pagamento),
                atualizado_em = NOW()
            WHERE id_despesa = %s;
            """,
            (data_pagamento, forma_pagamento, id_despesa)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao marcar despesa como paga: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def excluir_despesa(id_despesa):
    """
    Exclui uma despesa de fato (a tabela não tem soft delete).
    Retorna True se removeu, False caso contrário.
    """
    # ⚠️ DELETE definitivo (diferente dos outros módulos, que só desativam). Não há
    # como "reativar" depois. Por isso o app.py pede confirmação extra ao excluir.
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute("DELETE FROM despesa WHERE id_despesa = %s;", (id_despesa,))
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao excluir despesa: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def total_por_periodo(data_inicio, data_fim, base='vencimento'):
    """
    Soma o valor das despesas num período.
      - base='vencimento': considera data_vencimento (despesas previstas);
      - base='pagamento':  considera data_pagamento (despesas efetivamente pagas).
    Retorna o total (Decimal/0).
    """
    # 'coluna' é escolhida entre DOIS valores fixos do código (nunca vem do usuário) —
    # por isso é seguro interpolá-la na query com f-string. Nome de COLUNA não pode
    # ser passado como parâmetro %s (só valores podem); as datas continuam via %s.
    # Não passe entrada do usuário para 'base': isso abriria brecha de SQL injection.
    coluna = 'data_pagamento' if base == 'pagamento' else 'data_vencimento'

    conexao = conectar()
    if not conexao:
        return 0

    try:
        cursor = conexao.cursor()
        cursor.execute(
            f"""
            SELECT COALESCE(SUM(valor), 0)
            FROM despesa
            WHERE {coluna} BETWEEN %s AND %s;
            """,
            (data_inicio, data_fim)
        )
        return cursor.fetchone()[0]

    except Exception as erro:
        print(f"Erro ao calcular total de despesas: {erro}")
        return 0

    finally:
        cursor.close()
        conexao.close()


def total_por_categoria(data_inicio=None, data_fim=None):
    """
    Agrupa o total de despesas por categoria (no período, se informado).
    Tuplas: (categoria, total). Base: data_vencimento.
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()

        query = "SELECT COALESCE(categoria, '(sem categoria)'), SUM(valor) FROM despesa WHERE 1=1"
        parametros = []

        if data_inicio:
            query += " AND data_vencimento >= %s"
            parametros.append(data_inicio)
        if data_fim:
            query += " AND data_vencimento <= %s"
            parametros.append(data_fim)

        query += " GROUP BY categoria ORDER BY SUM(valor) DESC;"

        cursor.execute(query, parametros)
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao agrupar despesas por categoria: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


# ================================================================
# TESTE RÁPIDO (rode este arquivo diretamente para testar)
# ================================================================
if __name__ == "__main__":
    print("Registrando despesas de teste...")
    d1 = inserir_despesa("Compra de shampoo", 185.00, categoria="produto",
                         data_vencimento="2026-06-20", id_fornecedor=1)
    d2 = inserir_despesa("Energia elétrica", 430.00, categoria="energia",
                         data_vencimento="2026-06-30")
    print(f"Despesas criadas: {d1}, {d2}")

    if d1:
        print("\nMarcando despesa 1 como paga (pix)...")
        marcar_como_paga(d1, forma_pagamento="pix")

    print("\nDespesas em aberto:")
    for d in buscar_despesas(apenas_em_aberto=True):
        print(" ", d)

    print("\nTotal previsto (vencimento) em junho/2026:",
          total_por_periodo("2026-06-01", "2026-06-30"))

    print("\nTotal por categoria:")
    for c in total_por_categoria():
        print(" ", c)
