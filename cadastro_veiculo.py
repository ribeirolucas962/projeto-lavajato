"""
Módulo de Cadastro de Veículo
Sistema: Lava-Jato
Autor: RINEAL Analytics

Funções de CRUD (Criar, Ler, Atualizar, Desativar) para a tabela veiculo.
Cada veículo pertence a um cliente (id_cliente) e a uma categoria de porte
(id_categoria, FK para a tabela categoria_veiculo).

Segue o mesmo padrão do cadastro_cliente.py (transação try/commit/rollback/finally,
%s parametrizado, COALESCE no update, soft delete). Veja lá os comentários do padrão;
aqui só comentamos o que é próprio de veículo (JOINs e a ordem das colunas).
"""

from conexao import conectar


def listar_categorias():
    """
    Lista as categorias de porte disponíveis (catálogo categoria_veiculo).
    Retorna lista de tuplas (id_categoria, nome, ordem), ordenada por 'ordem'.
    Útil para preencher um dropdown na interface.
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()
        cursor.execute(
            "SELECT id_categoria, nome, ordem FROM categoria_veiculo ORDER BY ordem, nome;"
        )
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao listar categorias: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


def inserir_veiculo(id_cliente, id_categoria, placa, marca=None,
                    modelo=None, ano=None, cor=None):
    """
    Insere um novo veículo no banco de dados.
    Retorna o id_veiculo criado, ou None em caso de erro.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            INSERT INTO veiculo (id_cliente, id_categoria, placa, marca,
                                 modelo, ano, cor)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id_veiculo;
            """,
            (id_cliente, id_categoria, placa, marca, modelo, ano, cor)
        )
        id_veiculo = cursor.fetchone()[0]
        conexao.commit()
        return id_veiculo

    except Exception as erro:
        print(f"Erro ao inserir veículo: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def buscar_veiculos(termo=None, apenas_ativos=True):
    """
    Busca veículos pela placa, modelo ou nome do cliente (busca parcial).
    Se termo for None, retorna todos os veículos.
    Traz o nome do cliente dono e o nome da categoria de porte (JOINs).
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()

        # JOINs trazem o NOME do cliente (c.nome) e o NOME do porte (cat.nome) junto,
        # para a tela mostrar texto legível sem fazer consultas extras por linha.
        # ⚠️ Ordem das 11 colunas = tupla desempacotada em app.py.pagina_veiculos:
        #    (idv, idc, cli_nome, idcat, cat_nome, placa, marca, modelo, ano, cor, ativo)
        query = """
            SELECT v.id_veiculo, v.id_cliente, c.nome, v.id_categoria,
                   cat.nome, v.placa, v.marca, v.modelo, v.ano, v.cor, v.ativo
            FROM veiculo v
            JOIN cliente c             ON c.id_cliente   = v.id_cliente
            JOIN categoria_veiculo cat ON cat.id_categoria = v.id_categoria
            WHERE 1=1
        """
        parametros = []

        if apenas_ativos:
            query += " AND v.ativo = TRUE"

        if termo:
            query += " AND (v.placa ILIKE %s OR v.modelo ILIKE %s OR c.nome ILIKE %s)"
            parametros.extend([f"%{termo}%", f"%{termo}%", f"%{termo}%"])

        query += " ORDER BY v.placa;"

        cursor.execute(query, parametros)
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar veículos: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


def buscar_veiculo_por_id(id_veiculo):
    """
    Busca um único veículo pelo id_veiculo.
    Retorna uma tupla com os dados, ou None se não encontrado.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        # ⚠️ ATENÇÃO: aqui a ordem é DIFERENTE de buscar_veiculos() — sem os JOINs de
        # nome, com id_categoria (não o nome). São 9 colunas:
        #    (id_veiculo, id_cliente, id_categoria, placa, marca, modelo, ano, cor, ativo)
        # No app.py isto é lido como vei[1]=id_cliente e vei[3]=placa. Não confunda
        # os índices desta função com os de buscar_veiculos().
        cursor.execute(
            """
            SELECT id_veiculo, id_cliente, id_categoria, placa, marca,
                   modelo, ano, cor, ativo
            FROM veiculo
            WHERE id_veiculo = %s;
            """,
            (id_veiculo,)
        )
        return cursor.fetchone()

    except Exception as erro:
        print(f"Erro ao buscar veículo: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def buscar_veiculos_por_cliente(id_cliente, apenas_ativos=True):
    """
    Lista todos os veículos de um cliente específico.
    Útil para a tela de histórico do cliente.
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()

        query = """
            SELECT v.id_veiculo, v.id_cliente, v.id_categoria, cat.nome,
                   v.placa, v.marca, v.modelo, v.ano, v.cor, v.ativo
            FROM veiculo v
            JOIN categoria_veiculo cat ON cat.id_categoria = v.id_categoria
            WHERE v.id_cliente = %s
        """
        parametros = [id_cliente]

        if apenas_ativos:
            query += " AND v.ativo = TRUE"

        query += " ORDER BY v.placa;"

        cursor.execute(query, parametros)
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar veículos do cliente: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


def editar_veiculo(id_veiculo, id_cliente=None, id_categoria=None, placa=None,
                   marca=None, modelo=None, ano=None, cor=None):
    """
    Atualiza os dados de um veículo existente.
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
            UPDATE veiculo
            SET id_cliente = COALESCE(%s, id_cliente),
                id_categoria = COALESCE(%s, id_categoria),
                placa = COALESCE(%s, placa),
                marca = COALESCE(%s, marca),
                modelo = COALESCE(%s, modelo),
                ano = COALESCE(%s, ano),
                cor = COALESCE(%s, cor),
                atualizado_em = NOW()
            WHERE id_veiculo = %s;
            """,
            (id_cliente, id_categoria, placa, marca, modelo, ano, cor, id_veiculo)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao editar veículo: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def desativar_veiculo(id_veiculo):
    """
    Desativa um veículo (soft delete) — não exclui o registro do banco,
    apenas marca ativo = FALSE para preservar histórico.
    """
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            "UPDATE veiculo SET ativo = FALSE, atualizado_em = NOW() WHERE id_veiculo = %s;",
            (id_veiculo,)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao desativar veículo: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def reativar_veiculo(id_veiculo):
    """
    Reativa um veículo que havia sido desativado.
    """
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            "UPDATE veiculo SET ativo = TRUE, atualizado_em = NOW() WHERE id_veiculo = %s;",
            (id_veiculo,)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao reativar veículo: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


# ================================================================
# TESTE RÁPIDO (rode este arquivo diretamente para testar o CRUD)
# ================================================================
if __name__ == "__main__":
    print("Categorias disponíveis:")
    categorias = listar_categorias()
    for cat in categorias:
        print(" ", cat)

    if categorias:
        primeira_categoria = categorias[0][0]  # id_categoria da primeira
        print(f"\nTestando inserção de veículo (cliente 1, categoria {primeira_categoria})...")
        novo_id = inserir_veiculo(
            id_cliente=1,
            id_categoria=primeira_categoria,
            placa="ABC1D23",
            marca="Fiat",
            modelo="Uno",
            ano=2015,
            cor="Prata"
        )
        print(f"Veículo inserido com id: {novo_id}")
    else:
        print("\nNenhuma categoria cadastrada — popule categoria_veiculo antes de inserir veículos.")

    print("\nTestando busca de todos os veículos...")
    for v in buscar_veiculos():
        print(v)
