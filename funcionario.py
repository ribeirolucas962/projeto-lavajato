"""
Módulo de Funcionário
Sistema: Lava-Jato
Autor: RINEAL Analytics

CRUD da tabela funcionario, com autenticação por login/senha (hash bcrypt)
e consulta de produtividade (serviços executados).

A senha NUNCA é guardada em texto puro — só o hash bcrypt em senha_hash.
"""

import bcrypt
from conexao import conectar

# Valores aceitos pelo CHECK de funcao no banco.
FUNCOES_VALIDAS = ('lavador', 'caixa', 'gerente')


# ----------------------------------------------------------------
# Senha (hash / verificação)
# ----------------------------------------------------------------

def gerar_hash(senha):
    """Gera o hash bcrypt de uma senha em texto puro. Retorna str."""
    # gensalt() cria um sal aleatório novo a cada chamada; o bcrypt embute esse sal
    # DENTRO do próprio hash. Por isso a mesma senha gera hashes diferentes toda vez,
    # e não precisamos guardar o sal separado. Guardamos o hash como texto (str).
    return bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verificar_senha(senha, senha_hash):
    """Confere se a senha em texto puro corresponde ao hash. Retorna bool."""
    if not senha_hash:
        return False
    try:
        # checkpw reextrai o sal de dentro do hash e recompara — nunca "descriptografa"
        # (bcrypt é mão única). except: hash malformado/None não derruba o login.
        return bcrypt.checkpw(senha.encode('utf-8'), senha_hash.encode('utf-8'))
    except (ValueError, TypeError):
        return False


# ----------------------------------------------------------------
# CRUD
# ----------------------------------------------------------------

def inserir_funcionario(nome, funcao='lavador', login=None, senha=None,
                        comissao_percentual=0, data_admissao=None):
    """
    Insere um funcionário. A senha (se informada) é gravada como hash bcrypt.
    Retorna o id_funcionario criado, ou None em caso de erro.
    """
    if funcao not in FUNCOES_VALIDAS:
        print(f"Função inválida: {funcao}. Use uma de: {', '.join(FUNCOES_VALIDAS)}")
        return None

    senha_hash = gerar_hash(senha) if senha else None

    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            INSERT INTO funcionario (nome, funcao, login, senha_hash,
                                     comissao_percentual, data_admissao)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id_funcionario;
            """,
            (nome, funcao, login, senha_hash, comissao_percentual, data_admissao)
        )
        id_funcionario = cursor.fetchone()[0]
        conexao.commit()
        return id_funcionario

    except Exception as erro:
        print(f"Erro ao inserir funcionário: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def buscar_funcionarios(termo=None, funcao=None, apenas_ativos=True):
    """
    Lista funcionários (sem expor o hash da senha). Filtros opcionais por
    nome (parcial) e por função.
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()

        query = """
            SELECT id_funcionario, nome, funcao, login,
                   comissao_percentual, data_admissao, ativo
            FROM funcionario
            WHERE 1=1
        """
        parametros = []

        if apenas_ativos:
            query += " AND ativo = TRUE"
        if termo:
            query += " AND nome ILIKE %s"
            parametros.append(f"%{termo}%")
        if funcao:
            query += " AND funcao = %s"
            parametros.append(funcao)

        query += " ORDER BY nome;"

        cursor.execute(query, parametros)
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar funcionários: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


def buscar_funcionario_por_id(id_funcionario):
    """Busca um funcionário pelo id (sem expor o hash da senha)."""
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT id_funcionario, nome, funcao, login,
                   comissao_percentual, data_admissao, ativo
            FROM funcionario
            WHERE id_funcionario = %s;
            """,
            (id_funcionario,)
        )
        return cursor.fetchone()

    except Exception as erro:
        print(f"Erro ao buscar funcionário: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def editar_funcionario(id_funcionario, nome=None, funcao=None, login=None,
                       comissao_percentual=None, data_admissao=None):
    """
    Atualiza dados de um funcionário (exceto a senha — use alterar_senha).
    Apenas os campos informados são atualizados.
    """
    if funcao is not None and funcao not in FUNCOES_VALIDAS:
        print(f"Função inválida: {funcao}. Use uma de: {', '.join(FUNCOES_VALIDAS)}")
        return False

    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            UPDATE funcionario
            SET nome = COALESCE(%s, nome),
                funcao = COALESCE(%s, funcao),
                login = COALESCE(%s, login),
                comissao_percentual = COALESCE(%s, comissao_percentual),
                data_admissao = COALESCE(%s, data_admissao),
                atualizado_em = NOW()
            WHERE id_funcionario = %s;
            """,
            (nome, funcao, login, comissao_percentual, data_admissao, id_funcionario)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao editar funcionário: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def alterar_senha(id_funcionario, nova_senha):
    """Define/atualiza a senha de um funcionário (gravada como hash bcrypt)."""
    senha_hash = gerar_hash(nova_senha)

    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            "UPDATE funcionario SET senha_hash = %s, atualizado_em = NOW() WHERE id_funcionario = %s;",
            (senha_hash, id_funcionario)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao alterar senha: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def autenticar(login, senha):
    """
    Verifica login + senha de um funcionário ATIVO.
    Retorna (id_funcionario, nome, funcao) se válido, ou None se inválido.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT id_funcionario, nome, funcao, senha_hash
            FROM funcionario
            WHERE login = %s AND ativo = TRUE;
            """,
            (login,)
        )
        funcionario = cursor.fetchone()
        # funcionario[3] = senha_hash. Só é buscado aqui (as listagens NÃO trazem o
        # hash). Se a senha confere, devolve (id, nome, funcao) — o [:3] descarta o
        # hash para ele nunca sair desta função. É essa tupla que o app.py usa na sessão.
        if funcionario and verificar_senha(senha, funcionario[3]):
            return funcionario[:3]   # sem o hash
        return None

    except Exception as erro:
        print(f"Erro ao autenticar: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def desativar_funcionario(id_funcionario):
    """Desativa um funcionário (soft delete via ativo = FALSE)."""
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            "UPDATE funcionario SET ativo = FALSE, atualizado_em = NOW() WHERE id_funcionario = %s;",
            (id_funcionario,)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao desativar funcionário: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def reativar_funcionario(id_funcionario):
    """Reativa um funcionário previamente desativado."""
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            "UPDATE funcionario SET ativo = TRUE, atualizado_em = NOW() WHERE id_funcionario = %s;",
            (id_funcionario,)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao reativar funcionário: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def produtividade(id_funcionario, data_inicio=None, data_fim=None):
    """
    Conta quantos serviços (itens de comanda) o funcionário executou,
    opcionalmente dentro de um período (datas 'YYYY-MM-DD' sobre a entrada da comanda).
    Retorna um inteiro.
    """
    conexao = conectar()
    if not conexao:
        return 0

    try:
        cursor = conexao.cursor()

        query = """
            SELECT COUNT(*)
            FROM ordem_servico_item i
            JOIN ordem_servico o ON o.id_ordem = i.id_ordem
            WHERE i.id_funcionario = %s
        """
        parametros = [id_funcionario]

        if data_inicio:
            query += " AND o.entrada_em >= %s"
            parametros.append(data_inicio)
        if data_fim:
            query += " AND o.entrada_em < (%s::date + 1)"
            parametros.append(data_fim)

        cursor.execute(query, parametros)
        return cursor.fetchone()[0]

    except Exception as erro:
        print(f"Erro ao consultar produtividade: {erro}")
        return 0

    finally:
        cursor.close()
        conexao.close()


# ----------------------------------------------------------------
# Comissão (fechamento do mês)
# ----------------------------------------------------------------
#
# Quem executou cada serviço está em ordem_servico_item.id_funcionario ("Quem
# lavou", escolhido na comanda). O percentual de cada um está em
# funcionario.comissao_percentual. Estas funções cruzam os dois.
#
# Três decisões que valem para as duas consultas abaixo:
#
# 1. QUAIS COMANDAS CONTAM: status 'finalizado' ou 'entregue', por entrada_em —
#    o MESMO critério de faturamento do dashboard.py e da ficha do cliente.
#    É o que faz os números baterem entre as telas. Cancelada não paga comissão.
#
# 2. SOBRE QUAL VALOR: sobre o que a comanda cobrou de fato, não sobre a tabela
#    de preços. Desconto e acréscimo vivem na COMANDA (não no item), então são
#    rateados proporcionalmente entre os itens pelo 'fator' abaixo: numa comanda
#    de R$ 100 fechada por R$ 90, o serviço de R$ 100 entra como R$ 90 na base.
#    Sem isso, o dono daria 10% de desconto e pagaria comissão cheia.
#
# 3. SÓ SERVIÇO: itens de produto (venda de balcão na comanda) ficam de fora —
#    comissão aqui é sobre mão de obra. Daí o 'i.id_servico IS NOT NULL'.
#
# O valor do item é quantidade * preco_aplicado (preco_aplicado é UNITÁRIO).
# Hoje todo item nasce com quantidade = 1, então dá na mesma; a multiplicação
# está aqui para continuar certo quando a venda de produto na comanda existir.

# Comandas que pagam comissão + o fator de rateio do desconto/acréscimo.
# NULLIF evita divisão por zero em comanda de valor_total 0 (aí o fator vira 1,
# via COALESCE: sem base para ratear, não invento desconto).
_CTE_COMANDAS = """
    WITH comanda AS (
        SELECT o.id_ordem,
               COALESCE(
                   (o.valor_total - COALESCE(o.desconto, 0) + COALESCE(o.acrescimo, 0))
                   / NULLIF(o.valor_total, 0),
                   1
               ) AS fator
        FROM ordem_servico o
        WHERE o.status IN ('finalizado', 'entregue')
          {filtro_datas}
    )
"""


def _filtro_datas(data_inicio, data_fim, parametros, prefixo="o"):
    """Monta o recorte de período sobre entrada_em (mesmo padrão de produtividade)."""
    filtro = ""
    if data_inicio:
        filtro += f" AND {prefixo}.entrada_em >= %s"
        parametros.append(data_inicio)
    if data_fim:
        filtro += f" AND {prefixo}.entrada_em < (%s::date + 1)"
        parametros.append(data_fim)
    return filtro


def comissao_periodo(data_inicio=None, data_fim=None, id_funcionario=None):
    """
    Fechamento de comissão do período — quanto cada um tem a receber.

    Datas em 'YYYY-MM-DD' (sobre a entrada da comanda). id_funcionario filtra um só.
    Só aparece quem executou ao menos um serviço no período (quem não lavou não
    entra na folha); inclui funcionário inativo que trabalhou antes de sair.

    Retorna dict:
      {'funcionarios': [ {id, nome, funcao, ativo, percentual, servicos,
                          comandas, bruto, base, comissao}, ... ],
       'total_bruto', 'total_base', 'total_comissao',
       'sem_responsavel': {'servicos', 'valor'}}

    'bruto' = preço cheio dos serviços; 'base' = já com desconto/acréscimo
    rateado; 'comissao' = base * percentual / 100.

    'sem_responsavel' são os serviços que ninguém marcou como executor: NÃO
    entram na comissão de ninguém e por isso são devolvidos à parte — é o aviso
    de que faltou preencher "Quem lavou" na comanda.
    """
    conexao = conectar()
    if not conexao:
        return {'funcionarios': [], 'total_bruto': 0, 'total_base': 0,
                'total_comissao': 0, 'sem_responsavel': {'servicos': 0, 'valor': 0}}

    try:
        cursor = conexao.cursor()

        parametros = []
        cte = _CTE_COMANDAS.format(
            filtro_datas=_filtro_datas(data_inicio, data_fim, parametros)
        )

        query = cte + """
            SELECT f.id_funcionario,
                   f.nome,
                   f.funcao,
                   f.ativo,
                   COALESCE(f.comissao_percentual, 0)                AS percentual,
                   COUNT(*)                                          AS servicos,
                   COUNT(DISTINCT i.id_ordem)                        AS comandas,
                   ROUND(SUM(i.quantidade * i.preco_aplicado), 2)           AS bruto,
                   ROUND(SUM(i.quantidade * i.preco_aplicado * c.fator), 2) AS base,
                   ROUND(SUM(i.quantidade * i.preco_aplicado * c.fator
                             * COALESCE(f.comissao_percentual, 0) / 100), 2) AS comissao
            FROM ordem_servico_item i
            JOIN comanda c     ON c.id_ordem = i.id_ordem
            JOIN funcionario f ON f.id_funcionario = i.id_funcionario
            WHERE i.id_servico IS NOT NULL
        """
        if id_funcionario:
            query += " AND f.id_funcionario = %s"
            parametros.append(id_funcionario)

        query += """
            GROUP BY f.id_funcionario, f.nome, f.funcao, f.ativo, f.comissao_percentual
            ORDER BY comissao DESC, f.nome;
        """

        cursor.execute(query, parametros)

        funcionarios = [
            {'id': l[0], 'nome': l[1], 'funcao': l[2], 'ativo': l[3],
             'percentual': l[4], 'servicos': l[5], 'comandas': l[6],
             'bruto': l[7] or 0, 'base': l[8] or 0, 'comissao': l[9] or 0}
            for l in cursor.fetchall()
        ]

        # Serviços órfãos (sem "Quem lavou"): mesma janela, mas id_funcionario NULL.
        parametros_orfaos = []
        cte_orfaos = _CTE_COMANDAS.format(
            filtro_datas=_filtro_datas(data_inicio, data_fim, parametros_orfaos)
        )
        cursor.execute(
            cte_orfaos + """
            SELECT COUNT(*),
                   ROUND(COALESCE(SUM(i.quantidade * i.preco_aplicado * c.fator), 0), 2)
            FROM ordem_servico_item i
            JOIN comanda c ON c.id_ordem = i.id_ordem
            WHERE i.id_servico IS NOT NULL
              AND i.id_funcionario IS NULL;
            """,
            parametros_orfaos
        )
        orfaos = cursor.fetchone()

        return {
            'funcionarios': funcionarios,
            'total_bruto': sum(f['bruto'] for f in funcionarios),
            'total_base': sum(f['base'] for f in funcionarios),
            'total_comissao': sum(f['comissao'] for f in funcionarios),
            'sem_responsavel': {'servicos': orfaos[0], 'valor': orfaos[1]},
        }

    except Exception as erro:
        print(f"Erro ao calcular comissão: {erro}")
        return {'funcionarios': [], 'total_bruto': 0, 'total_base': 0,
                'total_comissao': 0, 'sem_responsavel': {'servicos': 0, 'valor': 0}}

    finally:
        cursor.close()
        conexao.close()


def comissao_detalhe(id_funcionario, data_inicio=None, data_fim=None):
    """
    Serviço a serviço que formou a comissão do funcionário no período — é a
    conferência de "de onde saiu esse valor" quando ele contesta o pagamento.

    Retorna lista de dicts (mais recente primeiro):
      {data, id_ordem, cliente, placa, servico, bruto, base, comissao}
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()

        parametros = []
        cte = _CTE_COMANDAS.format(
            filtro_datas=_filtro_datas(data_inicio, data_fim, parametros)
        )
        parametros.append(id_funcionario)

        cursor.execute(
            cte + """
            SELECT o.entrada_em,
                   o.id_ordem,
                   cli.nome,
                   v.placa,
                   s.nome,
                   ROUND(i.quantidade * i.preco_aplicado, 2)           AS bruto,
                   ROUND(i.quantidade * i.preco_aplicado * c.fator, 2) AS base,
                   ROUND(i.quantidade * i.preco_aplicado * c.fator
                         * COALESCE(f.comissao_percentual, 0) / 100, 2) AS comissao
            FROM ordem_servico_item i
            JOIN comanda c        ON c.id_ordem = i.id_ordem
            JOIN ordem_servico o  ON o.id_ordem = i.id_ordem
            JOIN funcionario f    ON f.id_funcionario = i.id_funcionario
            JOIN cliente cli      ON cli.id_cliente = o.id_cliente
            JOIN veiculo v        ON v.id_veiculo = o.id_veiculo
            LEFT JOIN servico s   ON s.id_servico = i.id_servico
            WHERE i.id_servico IS NOT NULL
              AND i.id_funcionario = %s
            ORDER BY o.entrada_em DESC, i.id_item;
            """,
            parametros
        )

        return [
            {'data': l[0], 'id_ordem': l[1], 'cliente': l[2], 'placa': l[3],
             'servico': l[4], 'bruto': l[5] or 0, 'base': l[6] or 0,
             'comissao': l[7] or 0}
            for l in cursor.fetchall()
        ]

    except Exception as erro:
        print(f"Erro ao detalhar comissão: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


# ================================================================
# TESTE RÁPIDO (rode este arquivo diretamente para testar)
# ================================================================
if __name__ == "__main__":
    print("Inserindo funcionário de teste...")
    fid = inserir_funcionario(
        nome="João Lavador",
        funcao="lavador",
        login="joao",
        senha="senha123",
        comissao_percentual=5,
        data_admissao="2026-06-24"
    )
    print(f"Funcionário inserido com id: {fid}")

    print("\nTestando autenticação:")
    print("  senha correta ->", autenticar("joao", "senha123"))
    print("  senha errada  ->", autenticar("joao", "errada"))

    print("\nFuncionários cadastrados:")
    for f in buscar_funcionarios():
        print(" ", f)

    if fid:
        print(f"\nProdutividade do funcionário {fid}: {produtividade(fid)} serviço(s)")
