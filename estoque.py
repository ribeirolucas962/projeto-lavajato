"""
Módulo de Estoque
Sistema: Lava-Jato
Autor: RINEAL Analytics

CRUD da tabela produto + movimentações (movimentacao_estoque).
Cada entrada/saída grava o histórico E atualiza produto.quantidade na MESMA
transação, mantendo o saldo sempre coerente. Saída valida saldo suficiente.
"""

from conexao import conectar


# ----------------------------------------------------------------
# CRUD de produto
# ----------------------------------------------------------------

def inserir_produto(nome, unidade_medida=None, quantidade=0, estoque_minimo=0,
                    custo_unitario=0, id_fornecedor=None):
    """
    Cadastra um produto/insumo. 'quantidade' é o saldo inicial.
    Retorna o id_produto criado, ou None em caso de erro.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            INSERT INTO produto (nome, unidade_medida, quantidade, estoque_minimo,
                                 custo_unitario, id_fornecedor)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id_produto;
            """,
            (nome, unidade_medida, quantidade, estoque_minimo,
             custo_unitario, id_fornecedor)
        )
        id_produto = cursor.fetchone()[0]
        conexao.commit()
        return id_produto

    except Exception as erro:
        print(f"Erro ao inserir produto: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def buscar_produtos(termo=None, apenas_ativos=True):
    """
    Lista produtos (busca parcial por nome), com o nome do fornecedor quando houver.
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()

        # LEFT JOIN (não JOIN): o fornecedor é opcional. Com LEFT, produtos SEM
        # fornecedor ainda aparecem (com f.nome_razao_social = NULL). Um JOIN normal
        # sumiria com eles da lista.
        query = """
            SELECT p.id_produto, p.nome, p.unidade_medida, p.quantidade,
                   p.estoque_minimo, p.custo_unitario, f.nome_razao_social, p.ativo
            FROM produto p
            LEFT JOIN fornecedor f ON f.id_fornecedor = p.id_fornecedor
            WHERE 1=1
        """
        parametros = []

        if apenas_ativos:
            query += " AND p.ativo = TRUE"
        if termo:
            query += " AND p.nome ILIKE %s"
            parametros.append(f"%{termo}%")

        query += " ORDER BY p.nome;"

        cursor.execute(query, parametros)
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar produtos: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


def buscar_produto_por_id(id_produto):
    """Busca um produto pelo id."""
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT id_produto, nome, unidade_medida, quantidade, estoque_minimo,
                   custo_unitario, id_fornecedor, ativo
            FROM produto
            WHERE id_produto = %s;
            """,
            (id_produto,)
        )
        return cursor.fetchone()

    except Exception as erro:
        print(f"Erro ao buscar produto: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def editar_produto(id_produto, nome=None, unidade_medida=None, estoque_minimo=None,
                   custo_unitario=None, id_fornecedor=None):
    """
    Atualiza dados cadastrais do produto. NÃO altera a quantidade — o saldo só
    muda via registrar_entrada / registrar_saida (para manter o histórico).
    """
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            UPDATE produto
            SET nome = COALESCE(%s, nome),
                unidade_medida = COALESCE(%s, unidade_medida),
                estoque_minimo = COALESCE(%s, estoque_minimo),
                custo_unitario = COALESCE(%s, custo_unitario),
                id_fornecedor = COALESCE(%s, id_fornecedor),
                atualizado_em = NOW()
            WHERE id_produto = %s;
            """,
            (nome, unidade_medida, estoque_minimo, custo_unitario,
             id_fornecedor, id_produto)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao editar produto: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def desativar_produto(id_produto):
    """Desativa um produto (soft delete)."""
    return _set_ativo(id_produto, False)


def reativar_produto(id_produto):
    """Reativa um produto previamente desativado."""
    return _set_ativo(id_produto, True)


def _set_ativo(id_produto, ativo):
    conexao = conectar()
    if not conexao:
        return False
    try:
        cursor = conexao.cursor()
        cursor.execute(
            "UPDATE produto SET ativo = %s, atualizado_em = NOW() WHERE id_produto = %s;",
            (ativo, id_produto)
        )
        conexao.commit()
        return cursor.rowcount > 0
    except Exception as erro:
        print(f"Erro ao alterar status do produto: {erro}")
        conexao.rollback()
        return False
    finally:
        cursor.close()
        conexao.close()


# ----------------------------------------------------------------
# Movimentações (atualizam o saldo na mesma transação)
# ----------------------------------------------------------------

def registrar_entrada(id_produto, quantidade, observacao=None):
    """
    Registra entrada de estoque: soma 'quantidade' ao saldo do produto e grava
    a movimentação. Tudo numa transação. Retorna o novo saldo, ou None em erro.
    """
    if quantidade is None or quantidade <= 0:
        print("Quantidade de entrada deve ser maior que zero.")
        return None

    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()

        cursor.execute(
            """
            UPDATE produto
            SET quantidade = quantidade + %s, atualizado_em = NOW()
            WHERE id_produto = %s
            RETURNING quantidade;
            """,
            (quantidade, id_produto)
        )
        linha = cursor.fetchone()
        if not linha:
            print(f"Produto {id_produto} não encontrado.")
            conexao.rollback()
            return None
        novo_saldo = linha[0]

        cursor.execute(
            """
            INSERT INTO movimentacao_estoque (id_produto, tipo, quantidade, observacao)
            VALUES (%s, 'entrada', %s, %s);
            """,
            (id_produto, quantidade, observacao)
        )

        conexao.commit()
        return novo_saldo

    except Exception as erro:
        print(f"Erro ao registrar entrada: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def registrar_saida(id_produto, quantidade, observacao=None):
    """
    Registra saída/consumo de estoque: subtrai 'quantidade' do saldo (se houver
    saldo suficiente) e grava a movimentação. Tudo numa transação.
    Retorna o novo saldo, ou None em erro/saldo insuficiente.
    """
    if quantidade is None or quantidade <= 0:
        print("Quantidade de saída deve ser maior que zero.")
        return None

    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()

        # FOR UPDATE trava ESTA linha do produto até o commit/rollback. Sem isso, duas
        # saídas simultâneas poderiam ler o mesmo saldo e ambas subtrair, deixando o
        # estoque negativo (condição de corrida). Com a trava, a 2ª espera a 1ª terminar.
        cursor.execute(
            "SELECT quantidade FROM produto WHERE id_produto = %s FOR UPDATE;",
            (id_produto,)
        )
        linha = cursor.fetchone()
        if not linha:
            print(f"Produto {id_produto} não encontrado.")
            conexao.rollback()
            return None

        # Recusa a saída se não há saldo — nunca deixa a quantidade ficar negativa.
        saldo_atual = linha[0]
        if saldo_atual < quantidade:
            print(f"Saldo insuficiente: disponível {saldo_atual}, solicitado {quantidade}.")
            conexao.rollback()
            return None

        cursor.execute(
            """
            UPDATE produto
            SET quantidade = quantidade - %s, atualizado_em = NOW()
            WHERE id_produto = %s
            RETURNING quantidade;
            """,
            (quantidade, id_produto)
        )
        novo_saldo = cursor.fetchone()[0]

        cursor.execute(
            """
            INSERT INTO movimentacao_estoque (id_produto, tipo, quantidade, observacao)
            VALUES (%s, 'saida', %s, %s);
            """,
            (id_produto, quantidade, observacao)
        )

        conexao.commit()
        return novo_saldo

    except Exception as erro:
        print(f"Erro ao registrar saída: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def historico_movimentacoes(id_produto, limite=50):
    """Lista as movimentações de um produto, da mais recente para a mais antiga."""
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT id_movimentacao, tipo, quantidade, observacao, data_mov
            FROM movimentacao_estoque
            WHERE id_produto = %s
            ORDER BY data_mov DESC
            LIMIT %s;
            """,
            (id_produto, limite)
        )
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar histórico: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


def produtos_abaixo_minimo():
    """
    Retorna os produtos ativos cujo saldo está no nível mínimo ou abaixo
    (alerta de reposição). Tuplas: (id_produto, nome, quantidade, estoque_minimo).
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT id_produto, nome, quantidade, estoque_minimo
            FROM produto
            WHERE ativo = TRUE AND quantidade <= estoque_minimo
            ORDER BY nome;
            """
        )
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar produtos abaixo do mínimo: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


# ================================================================
# TESTE RÁPIDO (rode este arquivo diretamente para testar)
# ================================================================
if __name__ == "__main__":
    print("Cadastrando produto de teste...")
    pid = inserir_produto(
        nome="Shampoo Automotivo",
        unidade_medida="L",
        quantidade=10,
        estoque_minimo=5,
        custo_unitario=18.50
    )
    print(f"Produto criado: {pid}")

    if pid:
        print("\nEntrada de 5 L ->", registrar_entrada(pid, 5))      # 15
        print("Saída de 8 L    ->", registrar_saida(pid, 8))         # 7
        print("Saída de 100 L  ->", registrar_saida(pid, 100))       # None (insuficiente)

        print("\nHistórico de movimentações:")
        for m in historico_movimentacoes(pid):
            print(" ", m)

        print("\nProdutos abaixo do mínimo (saldo 7, mínimo 5 -> não deve listar este):")
        for p in produtos_abaixo_minimo():
            print(" ", p)
