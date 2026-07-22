"""
Módulo de Fornecedores
Sistema: Lava-Jato
Autor: RINEAL Analytics

CRUD da tabela fornecedor. Os produtos de cada fornecedor são consultados
via produto.id_fornecedor (módulo de estoque) e as compras via despesa.id_fornecedor
(módulo de despesa).

CRUD idêntico ao padrão do cadastro_cliente.py (transação, %s, sentinela MANTER,
soft delete — veja lá os comentários). Os extras são produtos_do_fornecedor() e
compras_do_fornecedor(), que fazem o caminho inverso: dado um fornecedor, listam o
que aponta para ele.
"""

from conexao import conectar

# Sentinela do editar_fornecedor (mesma ideia de cadastro_cliente/cadastro_veiculo/
# agendamento/catalogo_servicos/estoque): campo NÃO passado = mantém como está;
# campo passado como None = apaga (grava NULL). O COALESCE antigo tornava
# impossível limpar o telefone, o e-mail ou as condições de pagamento.
MANTER = object()


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


def buscar_fornecedor_por_cnpj(cnpj):
    """
    Procura um fornecedor pelo CNPJ, comparando **só os dígitos** dos dois lados —
    então '12345678000190' acha '12.345.678/0001-90' e vice-versa (o cadastro antigo
    pode ter sido digitado sem máscara).

    Serve pra avisar, ANTES de gravar, que o CNPJ já está em uso: a coluna
    fornecedor.cnpj é UNIQUE, então o banco recusaria de qualquer jeito e a tela só
    conseguiria mostrar um erro genérico.

    Traz também fornecedores inativos (o CNPJ continua ocupado mesmo desativado — e
    é o caso mais confuso, porque o fornecedor nem aparece na lista).
    Retorna (id_fornecedor, nome_razao_social, cnpj, ativo), ou None.
    """
    digitos = "".join(c for c in (cnpj or "") if c.isdigit())
    if not digitos:
        return None

    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT id_fornecedor, nome_razao_social, cnpj, ativo
            FROM fornecedor
            WHERE regexp_replace(COALESCE(cnpj, ''), '[^0-9]', '', 'g') = %s
            LIMIT 1;
            """,
            (digitos,)
        )
        return cursor.fetchone()

    except Exception as erro:
        print(f"Erro ao buscar fornecedor por CNPJ: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def contar_produtos_vinculados(id_fornecedor):
    """
    Conta quantos produtos apontam para este fornecedor: (ativos, total).

    Usado para avisar antes de desativar — sem isso o fornecedor sumia da lista em
    silêncio e, na hora de repor o estoque, ninguém lembrava que ele fora desativado.
    Uma consulta só (COUNT FILTER), mesmo padrão do historico_faltas do agendamento.
    """
    conexao = conectar()
    if not conexao:
        return (0, 0)

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FILTER (WHERE ativo = TRUE), COUNT(*)
            FROM produto
            WHERE id_fornecedor = %s;
            """,
            (id_fornecedor,)
        )
        linha = cursor.fetchone()
        return (linha[0] or 0, linha[1] or 0)

    except Exception as erro:
        print(f"Erro ao contar produtos do fornecedor: {erro}")
        return (0, 0)

    finally:
        cursor.close()
        conexao.close()


def compras_do_fornecedor(id_fornecedor, limite=20):
    """
    Histórico de compras feitas deste fornecedor — o "consultar histórico de compras
    por fornecedor" previsto na especificação do módulo. Vem das despesas lançadas
    com este fornecedor (despesa.id_fornecedor).

    Retorna um dict:
        {'resumo':   {'qtd', 'total', 'total_pago', 'total_aberto', 'ultima'},
         'despesas': [(id, descricao, categoria, valor, vencimento, pagamento), ...]}
    'total' soma tudo; 'total_aberto' é o que ainda não foi pago (data_pagamento NULL).
    """
    vazio = {'resumo': {'qtd': 0, 'total': 0, 'total_pago': 0,
                        'total_aberto': 0, 'ultima': None},
             'despesas': []}
    conexao = conectar()
    if not conexao:
        return vazio

    try:
        cursor = conexao.cursor()

        # COALESCE nos totais: sem nenhuma despesa, SUM devolve NULL em vez de 0.
        cursor.execute(
            """
            SELECT COUNT(*),
                   COALESCE(SUM(valor), 0),
                   COALESCE(SUM(valor) FILTER (WHERE data_pagamento IS NOT NULL), 0),
                   COALESCE(SUM(valor) FILTER (WHERE data_pagamento IS NULL), 0),
                   MAX(COALESCE(data_pagamento, data_vencimento))
            FROM despesa
            WHERE id_fornecedor = %s;
            """,
            (id_fornecedor,)
        )
        qtd, total, pago, aberto, ultima = cursor.fetchone()

        cursor.execute(
            """
            SELECT id_despesa, descricao, categoria, valor,
                   data_vencimento, data_pagamento
            FROM despesa
            WHERE id_fornecedor = %s
            ORDER BY COALESCE(data_pagamento, data_vencimento) DESC NULLS LAST,
                     id_despesa DESC
            LIMIT %s;
            """,
            (id_fornecedor, limite)
        )
        despesas = cursor.fetchall()

        return {'resumo': {'qtd': qtd or 0, 'total': total, 'total_pago': pago,
                           'total_aberto': aberto, 'ultima': ultima},
                'despesas': despesas}

    except Exception as erro:
        print(f"Erro ao buscar compras do fornecedor: {erro}")
        return vazio

    finally:
        cursor.close()
        conexao.close()


def editar_fornecedor(id_fornecedor, nome_razao_social=MANTER, cnpj=MANTER,
                      telefone=MANTER, email=MANTER, condicoes_pagamento=MANTER):
    """
    Atualiza dados de um fornecedor.

    Campo que você NÃO passar fica como está (o padrão é o sentinela MANTER).
    Campo passado como None é APAGADO (vira NULL no banco). Era isso que o COALESCE
    antigo impedia: limpar o telefone/e-mail/condições e salvar trazia o valor velho
    de volta — mesmo bug já corrigido em cliente, veículo, agendamento, serviço e
    produto.

    Exceção (coluna NOT NULL): 'nome_razao_social' não pode virar NULL. Se vier
    vazio/None, é simplesmente ignorado (em vez de estourar erro no Postgres).

    Retorna True se alguma linha foi atualizada, False caso contrário.
    """
    conexao = conectar()
    if not conexao:
        return False

    # Monta o SET dinamicamente: só entram na query os campos realmente enviados.
    # Os NOMES das colunas vêm daqui de dentro (nunca do usuário) e os VALORES
    # seguem como %s — continua sem risco de SQL injection.
    campos = {
        "nome_razao_social": nome_razao_social,
        "cnpj": cnpj,
        "telefone": telefone,
        "email": email,
        "condicoes_pagamento": condicoes_pagamento,
    }
    partes, valores = [], []
    for coluna, valor in campos.items():
        if valor is MANTER:
            continue                                 # não foi enviado -> não mexe
        if coluna == "nome_razao_social" and not valor:
            continue                                 # NOT NULL: nunca apaga
        partes.append(f"{coluna} = %s")
        valores.append(valor)

    if not partes:
        conexao.close()
        return False   # ninguém pediu mudança nenhuma

    partes.append("atualizado_em = NOW()")
    valores.append(id_fornecedor)

    try:
        cursor = conexao.cursor()
        cursor.execute(
            f"UPDATE fornecedor SET {', '.join(partes)} WHERE id_fornecedor = %s;",
            valores
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

        print("\nProdutos vinculados (ativos, total):", contar_produtos_vinculados(fid))

        print("\nCNPJ já cadastrado? (procura só pelos dígitos)")
        print(" ", buscar_fornecedor_por_cnpj("12345678000190"))

        compras = compras_do_fornecedor(fid)
        print(f"\nCompras (via despesa.id_fornecedor): {compras['resumo']}")
        for d in compras['despesas']:
            print(" ", d)
