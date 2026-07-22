"""
Módulo de Estoque
Sistema: Lava-Jato
Autor: RINEAL Analytics

CRUD da tabela produto + movimentações (movimentacao_estoque).
Cada entrada/saída grava o histórico E atualiza produto.quantidade na MESMA
transação, mantendo o saldo sempre coerente. Saída valida saldo suficiente.
"""

from conexao import conectar

# Sentinela do editar_produto (mesma ideia de cadastro_cliente/cadastro_veiculo/
# agendamento/catalogo_servicos): campo NÃO passado = mantém como está; campo
# passado como None = apaga (grava NULL). O COALESCE antigo tornava impossível
# desvincular o fornecedor ou limpar a unidade de medida.
MANTER = object()


def _numero_valido(valor, rotulo, permite_none=True):
    """
    Confere que 'valor' é um número >= 0 ANTES de abrir conexão com o banco.

    Existe porque parte dessas colunas não tem CHECK no Postgres (quantidade e
    estoque_minimo aceitariam negativo em silêncio, deixando o estoque nascer
    no vermelho) e as que têm (custo_unitario, preco_venda) só estouram lá no
    banco, devolvendo um erro genérico que não ajuda o operador.

    Retorna (ok: bool, mensagem: str) — mensagem vazia quando está tudo certo.
    """
    if valor is None:
        return (True, "") if permite_none else (False, f"{rotulo} é obrigatório.")
    try:
        if float(valor) < 0:
            return False, f"{rotulo} não pode ser negativo."
    except (TypeError, ValueError):
        return False, f"{rotulo} deve ser um número."
    return True, ""


# ----------------------------------------------------------------
# CRUD de produto
# ----------------------------------------------------------------

def inserir_produto(nome, unidade_medida=None, quantidade=0, estoque_minimo=0,
                    custo_unitario=0, id_fornecedor=None, preco_venda=0):
    """
    Cadastra um produto/insumo. 'quantidade' é o saldo inicial.

    O saldo inicial (quando maior que zero) também é gravado como uma
    movimentação de entrada "Saldo inicial", na MESMA transação. Sem isso o
    produto nascia com saldo mas com histórico vazio, e a soma das
    movimentações nunca batia com a quantidade em estoque.

    Retorna o id_produto criado, ou None em caso de erro/valor inválido.
    """
    for valor, rotulo in ((quantidade, "Quantidade"), (estoque_minimo, "Estoque mínimo"),
                          (custo_unitario, "Custo unitário"), (preco_venda, "Preço de venda")):
        ok, msg = _numero_valido(valor, rotulo)
        if not ok:
            print(f"Erro ao inserir produto: {msg}")
            return None

    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            INSERT INTO produto (nome, unidade_medida, quantidade, estoque_minimo,
                                 custo_unitario, id_fornecedor, preco_venda)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id_produto;
            """,
            (nome, unidade_medida, quantidade or 0, estoque_minimo,
             custo_unitario, id_fornecedor, preco_venda)
        )
        id_produto = cursor.fetchone()[0]

        # Mesma transação: ou nascem os dois (produto + histórico), ou nenhum.
        if quantidade and float(quantidade) > 0:
            cursor.execute(
                """
                INSERT INTO movimentacao_estoque (id_produto, tipo, quantidade, observacao)
                VALUES (%s, 'entrada', %s, 'Saldo inicial do cadastro');
                """,
                (id_produto, quantidade)
            )

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
        # ⚠️ Colunas novas entram sempre no FIM do SELECT: a tela lê a tupla por
        # posição (p[0], p[3]...), então mexer na ordem quebraria a lista inteira.
        query = """
            SELECT p.id_produto, p.nome, p.unidade_medida, p.quantidade,
                   p.estoque_minimo, p.custo_unitario, f.nome_razao_social, p.ativo,
                   p.preco_venda, p.id_fornecedor
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
                   custo_unitario, id_fornecedor, ativo, preco_venda
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


def buscar_produto_por_nome(nome):
    """
    Procura um produto pelo nome EXATO (ignora maiúsc/minúsc e espaços sobrando,
    então '  shampoo automotivo ' acha 'Shampoo Automotivo').

    Serve pra avisar, ANTES de cadastrar, que já existe um produto com esse nome.
    Diferente de servico.nome, produto.nome NÃO é UNIQUE no banco — nada impediria
    dois "Shampoo Automotivo", e aí o estoque real fica dividido entre dois
    cadastros (8 L num, 3 L noutro) e o alerta de mínimo não dispara em nenhum.

    Traz também produtos inativos (é o caso mais confuso: o produto nem aparece
    na lista, mas está lá com o saldo dele).
    Retorna a tupla (id_produto, nome, unidade_medida, quantidade, ativo),
    ou None se ninguém usa esse nome.
    """
    conexao = conectar()
    if not conexao:
        return None

    nome_limpo = " ".join((nome or "").split())   # tira espaços duplos e das pontas
    if not nome_limpo:
        conexao.close()
        return None

    try:
        cursor = conexao.cursor()
        # BTRIM normaliza o que está gravado; ILIKE sem % compara o texto inteiro
        # ignorando maiúsculas/minúsculas.
        cursor.execute(
            """
            SELECT id_produto, nome, unidade_medida, quantidade, ativo
            FROM produto
            WHERE BTRIM(nome) ILIKE %s
            LIMIT 1;
            """,
            (nome_limpo,)
        )
        return cursor.fetchone()

    except Exception as erro:
        print(f"Erro ao buscar produto por nome: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def editar_produto(id_produto, nome=MANTER, unidade_medida=MANTER, estoque_minimo=MANTER,
                   custo_unitario=MANTER, id_fornecedor=MANTER, preco_venda=MANTER):
    """
    Atualiza dados cadastrais do produto. NÃO altera a quantidade — o saldo só
    muda via registrar_entrada / registrar_saida (para manter o histórico).

    Campo que você NÃO passar fica como está (o padrão é o sentinela MANTER).
    Campo passado como None é APAGADO (vira NULL no banco). Era isso que o COALESCE
    antigo impedia: escolher "(nenhum)" no fornecedor não desvinculava nada, e
    limpar a unidade de medida trazia o valor velho de volta — mesmo bug já
    corrigido em cliente, veículo, agendamento e serviço.

    Exceção (coluna NOT NULL): 'nome' não pode virar NULL. Se vier vazio/None, é
    simplesmente ignorado (em vez de estourar erro no Postgres).

    Retorna True se alguma linha foi atualizada, False caso contrário.
    """
    for valor, rotulo in ((estoque_minimo, "Estoque mínimo"),
                          (custo_unitario, "Custo unitário"),
                          (preco_venda, "Preço de venda")):
        if valor is MANTER:
            continue
        ok, msg = _numero_valido(valor, rotulo)
        if not ok:
            print(f"Erro ao editar produto: {msg}")
            return False

    conexao = conectar()
    if not conexao:
        return False

    # Monta o SET dinamicamente: só entram na query os campos realmente enviados.
    # Os NOMES das colunas vêm daqui de dentro (nunca do usuário) e os VALORES
    # seguem como %s — continua sem risco de SQL injection.
    campos = {
        "nome": nome,
        "unidade_medida": unidade_medida,
        "estoque_minimo": estoque_minimo,
        "custo_unitario": custo_unitario,
        "id_fornecedor": id_fornecedor,
        "preco_venda": preco_venda,
    }
    partes, valores = [], []
    for coluna, valor in campos.items():
        if valor is MANTER:
            continue                                 # não foi enviado -> não mexe
        if coluna == "nome" and not valor:
            continue                                 # NOT NULL: nunca apaga
        partes.append(f"{coluna} = %s")
        valores.append(valor)

    if not partes:
        conexao.close()
        return False   # ninguém pediu mudança nenhuma

    partes.append("atualizado_em = NOW()")
    valores.append(id_produto)

    try:
        cursor = conexao.cursor()
        cursor.execute(
            f"UPDATE produto SET {', '.join(partes)} WHERE id_produto = %s;",
            valores
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
        custo_unitario=18.50,
        preco_venda=29.90
    )
    print(f"Produto criado: {pid}")

    print("Valor negativo é recusado ->", inserir_produto("Teste negativo", quantidade=-5))

    if pid:
        print("\nEntrada de 5 L ->", registrar_entrada(pid, 5))      # 15
        print("Saída de 8 L    ->", registrar_saida(pid, 8))         # 7
        print("Saída de 100 L  ->", registrar_saida(pid, 100))       # None (insuficiente)

        # 3 lançamentos: o "Saldo inicial" (10) entra junto com o cadastro, então a
        # soma das movimentações sempre bate com o saldo do produto.
        print("\nHistórico de movimentações:")
        for m in historico_movimentacoes(pid):
            print(" ", m)

        print("\nProdutos abaixo do mínimo (saldo 7, mínimo 5 -> não deve listar este):")
        for p in produtos_abaixo_minimo():
            print(" ", p)
