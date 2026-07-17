"""
Módulo de Cadastro de Veículo
Sistema: Lava-Jato
Autor: RINEAL Analytics

Funções de CRUD (Criar, Ler, Atualizar, Desativar) para a tabela veiculo.
Cada veículo pertence a um cliente (id_cliente) e a uma categoria de porte
(id_categoria, FK para a tabela categoria_veiculo).

Segue o mesmo padrão do cadastro_cliente.py (transação try/commit/rollback/finally,
%s parametrizado, sentinela MANTER no update — ver editar_veiculo, soft delete). Veja
lá os comentários do padrão; aqui só comentamos o que é próprio de veículo (JOINs e a
ordem das colunas).
"""

import psycopg2

from conexao import conectar

# Sentinela do editar_veiculo (mesma ideia do cadastro_cliente.py):
# campo NÃO passado = mantém como está; campo passado como None = apaga (grava NULL).
# O COALESCE antigo tornava impossível apagar cor/marca/modelo/ano — ver editar_veiculo.
MANTER = object()


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


def buscar_veiculo_por_placa(placa):
    """
    Procura um veículo pela placa EXATA (ignora maiúsc/minúsc e o traço, então
    'abc1234' acha 'ABC-1234'). Serve pra avisar, ANTES de tentar cadastrar, que
    a placa já existe e de quem é o carro — a coluna veiculo.placa é UNIQUE, então
    o banco recusaria o INSERT de qualquer jeito; melhor avisar com jeitinho.

    Traz também veículos inativos (a placa continua ocupada mesmo desativada).
    Retorna a tupla (id_veiculo, placa, marca, modelo, cliente_nome, ativo),
    ou None se ninguém usa essa placa.
    """
    conexao = conectar()
    if not conexao:
        return None

    # Normaliza dos dois lados (banco e busca): só letras/números, em maiúsculo.
    # REPLACE tira o traço da placa gravada; UPPER cuida do caixa. Assim 'ABC-1234'
    # no banco casa com 'abc1234' digitado.
    import re
    placa_limpa = re.sub(r"[^A-Za-z0-9]", "", placa or "").upper()
    if not placa_limpa:
        conexao.close()
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT v.id_veiculo, v.placa, v.marca, v.modelo, c.nome, v.ativo
            FROM veiculo v
            JOIN cliente c ON c.id_cliente = v.id_cliente
            WHERE UPPER(REPLACE(v.placa, '-', '')) = %s;
            """,
            (placa_limpa,)
        )
        return cursor.fetchone()

    except Exception as erro:
        print(f"Erro ao buscar veículo por placa: {erro}")
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


def editar_veiculo(id_veiculo, id_cliente=MANTER, id_categoria=MANTER, placa=MANTER,
                   marca=MANTER, modelo=MANTER, ano=MANTER, cor=MANTER):
    """
    Atualiza os dados de um veículo existente.

    Campo que você NÃO passar fica como está (o padrão é o sentinela MANTER).
    Campo passado como None é APAGADO (vira NULL no banco). Era isso que o COALESCE
    antigo impedia: limpar a cor/marca/modelo/ano e salvar trazia o valor velho de
    volta — mesmo bug já corrigido no cadastro_cliente.py.

    Exceções (colunas NOT NULL / obrigatórias no banco): id_cliente, id_categoria e
    placa não podem virar NULL. Se vierem vazios/None, são simplesmente ignorados
    (em vez de estourar erro no Postgres).

    Retorna True se alguma linha foi atualizada, False caso contrário.
    """
    conexao = conectar()
    if not conexao:
        return False

    # Monta o SET dinamicamente: só entram na query os campos realmente enviados.
    # Os NOMES das colunas vêm daqui de dentro (nunca do usuário) e os VALORES seguem
    # como %s — continua sem risco de SQL injection.
    campos = {
        "id_cliente": id_cliente,
        "id_categoria": id_categoria,
        "placa": placa,
        "marca": marca,
        "modelo": modelo,
        "ano": ano,
        "cor": cor,
    }
    obrigatorios = ("id_cliente", "id_categoria", "placa")   # NOT NULL: nunca apagam
    partes, valores = [], []
    for coluna, valor in campos.items():
        if valor is MANTER:
            continue                                 # não foi enviado -> não mexe
        if coluna in obrigatorios and not valor:
            continue                                 # obrigatório vazio -> ignora
        partes.append(f"{coluna} = %s")
        valores.append(valor)

    if not partes:
        conexao.close()
        return False   # ninguém pediu mudança nenhuma

    partes.append("atualizado_em = NOW()")
    valores.append(id_veiculo)

    try:
        cursor = conexao.cursor()
        cursor.execute(
            f"UPDATE veiculo SET {', '.join(partes)} WHERE id_veiculo = %s;",
            valores
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


def excluir_veiculo(id_veiculo):
    """
    Exclui o veículo DE VEZ (DELETE) — só para cadastro criado errado
    (teste, duplicado), SEM nada vinculado. Se o veículo tiver histórico
    (comanda ou agendamento), o banco BLOQUEIA a exclusão (FKs sem CASCADE)
    e devolvemos 'vinculos' — nesse caso o caminho certo é desativar.
    Retorna: True = excluído | 'vinculos' = tem histórico | False = erro/não achou.
    """
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            "DELETE FROM veiculo WHERE id_veiculo = %s;",
            (id_veiculo,)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except psycopg2.errors.ForeignKeyViolation:
        # Alguma comanda/agendamento ainda aponta para este veículo.
        conexao.rollback()
        return 'vinculos'

    except Exception as erro:
        print(f"Erro ao excluir veículo: {erro}")
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
