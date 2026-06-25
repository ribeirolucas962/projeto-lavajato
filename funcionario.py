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
    return bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verificar_senha(senha, senha_hash):
    """Confere se a senha em texto puro corresponde ao hash. Retorna bool."""
    if not senha_hash:
        return False
    try:
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
