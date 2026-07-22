"""
Módulo de Catálogo de Serviços e Preços
Sistema: Lava-Jato
Autor: RINEAL Analytics

CRUD da tabela servico (catálogo de serviços) + gestão da matriz de preços
em servico_preco (um preço por combinação serviço x categoria de porte).

O CRUD de servico segue o padrão do cadastro_cliente.py (veja lá os comentários do
padrão comum). A parte específica deste módulo é a MATRIZ DE PREÇOS: em vez de uma
coluna de preço por porte, cada par (serviço, categoria) é uma linha em servico_preco
com UNIQUE(id_servico, id_categoria). Assim dá para ter preços diferentes por porte
sem alterar o schema quando surge um porte novo.
"""

from conexao import conectar

# Sentinela do editar_servico (mesma ideia de cadastro_cliente/cadastro_veiculo/agendamento):
# campo NÃO passado = mantém como está; campo passado como None = apaga (grava NULL).
# O COALESCE antigo tornava impossível apagar a descrição ou o tempo médio.
MANTER = object()


# ================================================================
# CRUD DE SERVIÇO
# ================================================================

def inserir_servico(nome, descricao=None, tempo_medio_min=None):
    """
    Insere um novo serviço no catálogo.
    Retorna o id_servico criado, ou None em caso de erro.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            INSERT INTO servico (nome, descricao, tempo_medio_min)
            VALUES (%s, %s, %s)
            RETURNING id_servico;
            """,
            (nome, descricao, tempo_medio_min)
        )
        id_servico = cursor.fetchone()[0]
        conexao.commit()
        return id_servico

    except Exception as erro:
        print(f"Erro ao inserir serviço: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def buscar_servicos(termo=None, apenas_ativos=True):
    """
    Busca serviços pelo nome (busca parcial).
    Se termo for None, retorna todos os serviços.
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()

        query = """
            SELECT id_servico, nome, descricao, tempo_medio_min, ativo
            FROM servico
            WHERE 1=1
        """
        parametros = []

        if apenas_ativos:
            query += " AND ativo = TRUE"

        if termo:
            query += " AND nome ILIKE %s"
            parametros.append(f"%{termo}%")

        query += " ORDER BY nome;"

        cursor.execute(query, parametros)
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar serviços: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


def buscar_servico_por_id(id_servico):
    """
    Busca um único serviço pelo id_servico.
    Retorna uma tupla com os dados, ou None se não encontrado.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT id_servico, nome, descricao, tempo_medio_min, ativo
            FROM servico
            WHERE id_servico = %s;
            """,
            (id_servico,)
        )
        return cursor.fetchone()

    except Exception as erro:
        print(f"Erro ao buscar serviço: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def buscar_servico_por_nome(nome):
    """
    Procura um serviço pelo nome EXATO (ignora maiúsc/minúsc e espaços sobrando, então
    '  lavagem simples ' acha 'Lavagem Simples'). Serve pra avisar, ANTES de tentar
    cadastrar, que o nome já existe — a coluna servico.nome é UNIQUE, então o banco
    recusaria o INSERT de qualquer jeito; melhor avisar com jeitinho.

    Traz também serviços inativos (o nome continua ocupado mesmo desativado — e é o
    caso mais confuso pro operador, porque o serviço nem aparece na lista).
    Retorna a tupla (id_servico, nome, descricao, tempo_medio_min, ativo),
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
        # Normaliza dos dois lados: BTRIM tira os espaços do que está gravado e o
        # ILIKE (sem % nenhum) compara o texto inteiro ignorando maiúsc/minúsc.
        cursor.execute(
            """
            SELECT id_servico, nome, descricao, tempo_medio_min, ativo
            FROM servico
            WHERE BTRIM(nome) ILIKE %s
            LIMIT 1;
            """,
            (nome_limpo,)
        )
        return cursor.fetchone()

    except Exception as erro:
        print(f"Erro ao buscar serviço por nome: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def editar_servico(id_servico, nome=MANTER, descricao=MANTER, tempo_medio_min=MANTER):
    """
    Atualiza os dados de um serviço existente.

    Campo que você NÃO passar fica como está (o padrão é o sentinela MANTER).
    Campo passado como None é APAGADO (vira NULL no banco). Era isso que o COALESCE
    antigo impedia: limpar a descrição/tempo médio e salvar trazia o valor velho de
    volta — mesmo bug já corrigido em cliente, veículo e agendamento.

    Exceção (coluna NOT NULL): 'nome' não pode virar NULL. Se vier vazio/None, é
    simplesmente ignorado (em vez de estourar erro no Postgres).

    Retorna True se alguma linha foi atualizada, False caso contrário.
    """
    conexao = conectar()
    if not conexao:
        return False

    # Monta o SET dinamicamente: só entram na query os campos realmente enviados.
    # Os NOMES das colunas vêm daqui de dentro (nunca do usuário) e os VALORES seguem
    # como %s — continua sem risco de SQL injection.
    campos = {
        "nome": nome,
        "descricao": descricao,
        "tempo_medio_min": tempo_medio_min,
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
    valores.append(id_servico)

    try:
        cursor = conexao.cursor()
        cursor.execute(
            f"UPDATE servico SET {', '.join(partes)} WHERE id_servico = %s;",
            valores
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao editar serviço: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def desativar_servico(id_servico):
    """
    Desativa um serviço (soft delete) — não exclui o registro,
    apenas marca ativo = FALSE para preservar o histórico de comandas.
    """
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            "UPDATE servico SET ativo = FALSE, atualizado_em = NOW() WHERE id_servico = %s;",
            (id_servico,)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao desativar serviço: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def reativar_servico(id_servico):
    """
    Reativa um serviço que havia sido desativado.
    """
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            "UPDATE servico SET ativo = TRUE, atualizado_em = NOW() WHERE id_servico = %s;",
            (id_servico,)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao reativar serviço: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


# ================================================================
# GESTÃO DE PREÇOS (matriz servico x categoria)
# ================================================================

def definir_preco(id_servico, id_categoria, preco):
    """
    Define (ou atualiza) o preço de um serviço para uma categoria de porte.
    Faz UPSERT: insere se não existir, atualiza se já existir.
    Retorna True em caso de sucesso, False caso contrário.
    """
    # Barra o preço inválido aqui: a tabela tem CHECK (preco >= 0), então um valor
    # negativo viraria erro do Postgres no meio do laço de quem chama. Recusando
    # antes, quem chama recebe um False limpo e sabe que nada foi gravado.
    try:
        if preco is None or float(preco) < 0:
            print(f"Erro ao definir preço: valor inválido ({preco!r}) — deve ser >= 0.")
            return False
    except (TypeError, ValueError):
        print(f"Erro ao definir preço: valor não numérico ({preco!r}).")
        return False

    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        # UPSERT: tenta inserir; se já existe o par (id_servico, id_categoria) — a
        # constraint UNIQUE dispara o ON CONFLICT — atualiza o preço em vez de duplicar.
        # EXCLUDED.preco é o valor que teria sido inserido (o novo preço passado).
        cursor.execute(
            """
            INSERT INTO servico_preco (id_servico, id_categoria, preco)
            VALUES (%s, %s, %s)
            ON CONFLICT (id_servico, id_categoria)
            DO UPDATE SET preco = EXCLUDED.preco;
            """,
            (id_servico, id_categoria, preco)
        )
        conexao.commit()
        return True

    except Exception as erro:
        print(f"Erro ao definir preço: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def buscar_preco(id_servico, id_categoria):
    """
    Retorna o preço (Decimal) de um serviço para uma categoria de porte,
    ou None se ainda não houver preço definido para essa combinação.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT preco
            FROM servico_preco
            WHERE id_servico = %s AND id_categoria = %s;
            """,
            (id_servico, id_categoria)
        )
        resultado = cursor.fetchone()
        return resultado[0] if resultado else None

    except Exception as erro:
        print(f"Erro ao buscar preço: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def remover_preco(id_servico, id_categoria):
    """
    Remove o preço de um serviço para uma categoria de porte específica.
    Retorna True se algo foi removido, False caso contrário.
    """
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            "DELETE FROM servico_preco WHERE id_servico = %s AND id_categoria = %s;",
            (id_servico, id_categoria)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao remover preço: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def precos_do_servico(id_servico):
    """
    Lista os preços de um serviço em todas as categorias que já têm preço.
    Retorna tuplas (id_categoria, nome_categoria, preco), ordenadas por porte.
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()
        # Só retorna as categorias que JÁ têm preço (parte de servico_preco). Portes
        # sem preço não aparecem — é assim que o app.py conta "quantos portes têm preço".
        cursor.execute(
            """
            SELECT cat.id_categoria, cat.nome, sp.preco
            FROM servico_preco sp
            JOIN categoria_veiculo cat ON cat.id_categoria = sp.id_categoria
            WHERE sp.id_servico = %s
            ORDER BY cat.ordem, cat.nome;
            """,
            (id_servico,)
        )
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar preços do serviço: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


def resumo_precos(apenas_ativos=True):
    """
    Resumo dos preços de TODOS os serviços numa consulta só.
    Retorna um dict {id_servico: (quantidade_de_portes, preco_minimo, preco_maximo)}.

    Existe para a lista de serviços da interface não chamar precos_do_servico()
    dentro do laço: eram 1 + N conexões ao banco (uma por linha da tabela) a cada
    tecla digitada na busca. Serviço sem preço nenhum simplesmente não aparece no
    dict — quem lê usa .get(id, (0, None, None)).
    """
    conexao = conectar()
    if not conexao:
        return {}

    try:
        cursor = conexao.cursor()
        query = """
            SELECT sp.id_servico, COUNT(*), MIN(sp.preco), MAX(sp.preco)
            FROM servico_preco sp
            JOIN servico s ON s.id_servico = sp.id_servico
            WHERE 1=1
        """
        if apenas_ativos:
            query += " AND s.ativo = TRUE"
        query += " GROUP BY sp.id_servico;"

        cursor.execute(query)
        return {linha[0]: (linha[1], linha[2], linha[3]) for linha in cursor.fetchall()}

    except Exception as erro:
        print(f"Erro ao resumir preços: {erro}")
        return {}

    finally:
        cursor.close()
        conexao.close()


def tabela_de_precos(apenas_ativos=True):
    """
    Retorna a tabela de preços vigente: cada linha é uma combinação
    (serviço, categoria) com preço definido.
    Tuplas: (id_servico, nome_servico, id_categoria, nome_categoria, preco).
    Serve de base para exibir a matriz serviço x porte na interface.
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()

        query = """
            SELECT s.id_servico, s.nome, cat.id_categoria, cat.nome, sp.preco
            FROM servico_preco sp
            JOIN servico s            ON s.id_servico   = sp.id_servico
            JOIN categoria_veiculo cat ON cat.id_categoria = sp.id_categoria
            WHERE 1=1
        """
        if apenas_ativos:
            query += " AND s.ativo = TRUE"

        query += " ORDER BY s.nome, cat.ordem, cat.nome;"

        cursor.execute(query)
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao montar tabela de preços: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


# ================================================================
# TESTE RÁPIDO (rode este arquivo diretamente para testar o CRUD)
# ================================================================
if __name__ == "__main__":
    print("Inserindo serviço de teste...")
    id_serv = inserir_servico(
        nome="Lavagem Simples",
        descricao="Lavagem externa com shampoo automotivo",
        tempo_medio_min=30
    )
    print(f"Serviço inserido com id: {id_serv}")

    if id_serv:
        # Define preços para Moto (1) e Pequeno (2) — ids das categorias seed
        print("\nDefinindo preços por porte...")
        definir_preco(id_serv, 1, 20.00)   # Moto
        definir_preco(id_serv, 2, 35.00)   # Pequeno
        definir_preco(id_serv, 2, 40.00)   # Pequeno de novo -> deve ATUALIZAR para 40

        print("Preços do serviço:")
        for p in precos_do_servico(id_serv):
            print(" ", p)

    print("\nTabela de preços vigente:")
    for linha in tabela_de_precos():
        print(" ", linha)
