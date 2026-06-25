"""
Módulo de Fornecedores
Sistema: Lava-Jato
Autor: RINEAL Analytics

CRUD da tabela fornecedor. Os produtos de cada fornecedor são consultados
via produto.id_fornecedor (módulo de estoque).
"""

from conexao import conectar


def inserir_fornecedor(nome_razao_social, cnpj=None, telefone=None, email=None,
                       condicoes_pagamento=None):
    """
    Cadastra um fornecedor.
    Retorna o id_fornecedor criado, ou None em caso de erro.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            INSERT INTO fornecedor (nome_razao_social, cnpj, telefone, email,
                                    condicoes_pagamento)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id_fornecedor;
            """,
            (nome_razao_social, cnpj, telefone, email, condicoes_pagamento)
        )
        id_fornecedor = cursor.fetchone()[0]
        conexao.commit()
        return id_fornecedor

    except Exception as erro:
        print(f"Erro ao inserir fornecedor: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def buscar_fornecedores(termo=None, apenas_ativos=True):
    """
    Lista fornecedores (busca parcial por nome/razão social ou CNPJ).
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()

        query = """
            SELECT id_fornecedor, nome_razao_social, cnpj, telefone, email,
                   condicoes_pagamento, ativo
            FROM fornecedor
            WHERE 1=1
        """
        parametros = []

        if apenas_ativos:
            query += " AND ativo = TRUE"
        if termo:
            query += " AND (nome_razao_social ILIKE %s OR cnpj ILIKE %s)"
            parametros.extend([f"%{termo}%", f"%{termo}%"])

        query += " ORDER BY nome_razao_social;"

        cursor.execute(query, parametros)
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar fornecedores: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


def buscar_fornecedor_por_id(id_fornecedor):
    """Busca um fornecedor pelo id."""
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT id_fornecedor, nome_razao_social, cnpj, telefone, email,
                   condicoes_pagamento, ativo
            FROM fornecedor
            WHERE id_fornecedor = %s;
            """,
            (id_fornecedor,)
        )
        return cursor.fetchone()

    except Exception as erro:
        print(f"Erro ao buscar fornecedor: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def editar_fornecedor(id_fornecedor, nome_razao_social=None, cnpj=None,
                      telefone=None, email=None, condicoes_pagamento=None):
    """
    Atualiza dados de um fornecedor. Apenas os campos informados são alterados.
    """
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            UPDATE fornecedor
            SET nome_razao_social = COALESCE(%s, nome_razao_social),
                cnpj = COALESCE(%s, cnpj),
                telefone = COALESCE(%s, telefone),
                email = COALESCE(%s, email),
                condicoes_pagamento = COALESCE(%s, condicoes_pagamento),
                atualizado_em = NOW()
            WHERE id_fornecedor = %s;
            """,
            (nome_razao_social, cnpj, telefone, email, condicoes_pagamento,
             id_fornecedor)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao editar fornecedor: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def desativar_fornecedor(id_fornecedor):
    """Desativa um fornecedor (soft delete)."""
    return _set_ativo(id_fornecedor, False)


def reativar_fornecedor(id_fornecedor):
    """Reativa um fornecedor previamente desativado."""
    return _set_ativo(id_fornecedor, True)


def _set_ativo(id_fornecedor, ativo):
    conexao = conectar()
    if not conexao:
        return False
    try:
        cursor = conexao.cursor()
        cursor.execute(
            "UPDATE fornecedor SET ativo = %s, atualizado_em = NOW() WHERE id_fornecedor = %s;",
            (ativo, id_fornecedor)
        )
        conexao.commit()
        return cursor.rowcount > 0
    except Exception as erro:
        print(f"Erro ao alterar status do fornecedor: {erro}")
        conexao.rollback()
        return False
    finally:
        cursor.close()
        conexao.close()


def produtos_do_fornecedor(id_fornecedor, apenas_ativos=True):
    """
    Lista os produtos vinculados a um fornecedor (via produto.id_fornecedor).
    Tuplas: (id_produto, nome, unidade_medida, quantidade, custo_unitario).
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()

        query = """
            SELECT id_produto, nome, unidade_medida, quantidade, custo_unitario
            FROM produto
            WHERE id_fornecedor = %s
        """
        parametros = [id_fornecedor]

        if apenas_ativos:
            query += " AND ativo = TRUE"

        query += " ORDER BY nome;"

        cursor.execute(query, parametros)
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar produtos do fornecedor: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


# ================================================================
# TESTE RÁPIDO (rode este arquivo diretamente para testar)
# ================================================================
if __name__ == "__main__":
    print("Cadastrando fornecedor de teste...")
    fid = inserir_fornecedor(
        nome_razao_social="Distribuidora AutoLimp Ltda",
        cnpj="12.345.678/0001-90",
        telefone="(47) 3333-0000",
        email="contato@autolimp.com",
        condicoes_pagamento="30 dias"
    )
    print(f"Fornecedor criado: {fid}")

    print("\nFornecedores cadastrados:")
    for f in buscar_fornecedores():
        print(" ", f)

    if fid:
        # Vincula o produto de teste (id 1, se existir) a este fornecedor
        from estoque import editar_produto, buscar_produto_por_id
        if buscar_produto_por_id(1):
            editar_produto(1, id_fornecedor=fid)
            print(f"\nProdutos do fornecedor {fid}:")
            for p in produtos_do_fornecedor(fid):
                print(" ", p)
