"""
Módulo de Cadastro de Cliente
Sistema: Lava-Jato
Autor: RINEAL Analytics

Funções de CRUD (Criar, Ler, Atualizar, Desativar) para a tabela cliente.
"""

from conexao import conectar


def inserir_cliente(nome, cpf_cnpj=None, telefone=None, email=None,
                     endereco=None, observacoes=None):
    """
    Insere um novo cliente no banco de dados.
    Retorna o id_cliente criado, ou None em caso de erro.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            INSERT INTO cliente (nome, cpf_cnpj, telefone, email, endereco, observacoes)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id_cliente;
            """,
            (nome, cpf_cnpj, telefone, email, endereco, observacoes)
        )
        id_cliente = cursor.fetchone()[0]
        conexao.commit()
        return id_cliente

    except Exception as erro:
        print(f"Erro ao inserir cliente: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def buscar_clientes(termo=None, apenas_ativos=True):
    """
    Busca clientes pelo nome ou telefone (busca parcial).
    Se termo for None, retorna todos os clientes.
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()

        query = "SELECT id_cliente, nome, cpf_cnpj, telefone, email, endereco, observacoes, ativo FROM cliente WHERE 1=1"
        parametros = []

        if apenas_ativos:
            query += " AND ativo = TRUE"

        if termo:
            query += " AND (nome ILIKE %s OR telefone ILIKE %s)"
            parametros.extend([f"%{termo}%", f"%{termo}%"])

        query += " ORDER BY nome;"

        cursor.execute(query, parametros)
        resultados = cursor.fetchall()
        return resultados

    except Exception as erro:
        print(f"Erro ao buscar clientes: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


def buscar_cliente_por_id(id_cliente):
    """
    Busca um único cliente pelo id_cliente.
    Retorna uma tupla com os dados, ou None se não encontrado.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT id_cliente, nome, cpf_cnpj, telefone, email, endereco, observacoes, ativo
            FROM cliente
            WHERE id_cliente = %s;
            """,
            (id_cliente,)
        )
        resultado = cursor.fetchone()
        return resultado

    except Exception as erro:
        print(f"Erro ao buscar cliente: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def editar_cliente(id_cliente, nome=None, cpf_cnpj=None, telefone=None,
                    email=None, endereco=None, observacoes=None):
    """
    Atualiza os dados de um cliente existente.
    Apenas os campos informados (diferentes de None) são atualizados.
    Retorna True se a atualização foi bem-sucedida, False caso contrário.
    """
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            UPDATE cliente
            SET nome = COALESCE(%s, nome),
                cpf_cnpj = COALESCE(%s, cpf_cnpj),
                telefone = COALESCE(%s, telefone),
                email = COALESCE(%s, email),
                endereco = COALESCE(%s, endereco),
                observacoes = COALESCE(%s, observacoes),
                atualizado_em = NOW()
            WHERE id_cliente = %s;
            """,
            (nome, cpf_cnpj, telefone, email, endereco, observacoes, id_cliente)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao editar cliente: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def desativar_cliente(id_cliente):
    """
    Desativa um cliente (soft delete) — não exclui o registro do banco,
    apenas marca ativo = FALSE para preservar histórico.
    """
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            "UPDATE cliente SET ativo = FALSE, atualizado_em = NOW() WHERE id_cliente = %s;",
            (id_cliente,)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao desativar cliente: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def reativar_cliente(id_cliente):
    """
    Reativa um cliente que havia sido desativado.
    """
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            "UPDATE cliente SET ativo = TRUE, atualizado_em = NOW() WHERE id_cliente = %s;",
            (id_cliente,)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao reativar cliente: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


# ================================================================
# TESTE RÁPIDO (rode este arquivo diretamente para testar o CRUD)
# ================================================================
if __name__ == "__main__":
    print("Testando inserção de cliente...")
    novo_id = inserir_cliente(
        nome="Cliente Teste",
        cpf_cnpj="123.456.789-00",
        telefone="(47) 99999-0000",
        email="teste@email.com"
    )
    print(f"Cliente inserido com id: {novo_id}")

    print("\nTestando busca de todos os clientes...")
    clientes = buscar_clientes()
    for c in clientes:
        print(c)
