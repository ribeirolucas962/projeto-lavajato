"""
Módulo de Planos e Assinaturas
Sistema: Lava-Jato
Autor: RINEAL Analytics

Pacotes mensais de serviços (plano + plano_servico) e a assinatura de clientes
(assinatura + assinatura_uso). Controla o uso mensal, bloqueando quando o cliente
atinge o limite de um serviço no mês vigente.

VIGÊNCIA (revisão de 2026-07-25) — três coisas decidem se a assinatura vale HOJE,
e o módulo só olhava a primeira:
  1. ativo = TRUE             -> cancelamento manual;
  2. data_inicio <= hoje      -> contratada para começar depois;
  3. data_vencimento >= hoje  -> deixou de pagar (NULL = sem prazo, vale sempre).
Sem o item 3, o cliente que parou de pagar em maio continuava com as lavagens do
plano para sempre: a coluna existia, aparecia na tela e não decidia nada.
"""

from conexao import conectar


# Sentinela do update parcial (mesmo padrão de cliente/veículo/serviço/produto):
# campo não passado = não mexe; passado como None = grava NULL (apaga).
MANTER = object()

# Situações possíveis de uma assinatura, em ordem de precedência na checagem.
SITUACOES = ('vigente', 'cancelada', 'nao_iniciada', 'vencida')


def _valor_valido(valor, rotulo="valor"):
    """
    Confere que o número é válido e não negativo ANTES de abrir conexão — o banco
    tem CHECK (valor_mensalidade >= 0), mas deixar o erro estourar lá devolve só
    'não foi possível salvar' para a tela. Aceita vírgula decimal ("99,90").
    Retorna (ok, valor_convertido, mensagem).
    """
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return False, None, f"Informe {rotulo}."
    try:
        numero = float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return False, None, f"{rotulo.capitalize()} deve ser um número (ex.: 99,90)."
    if numero < 0:
        return False, None, f"{rotulo.capitalize()} não pode ser negativo."
    return True, numero, ""


# ----------------------------------------------------------------
# CRUD de plano
# ----------------------------------------------------------------

def buscar_plano_por_nome(nome):
    """
    Procura um plano pelo nome, ignorando caixa e espaços das pontas.
    Traz INATIVOS também — 'plano.nome' é UNIQUE no banco, então um plano
    desativado com o mesmo nome continua bloqueando o INSERT.
    Retorna (id_plano, nome, valor_mensalidade, ativo) ou None.
    """
    if not nome or not str(nome).strip():
        return None

    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT id_plano, nome, valor_mensalidade, ativo
            FROM plano
            WHERE BTRIM(nome) ILIKE BTRIM(%s)
            LIMIT 1;
            """,
            (nome,)
        )
        return cursor.fetchone()

    except Exception as erro:
        print(f"Erro ao buscar plano por nome: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def criar_plano(nome, valor_mensalidade):
    """Cria um plano. Retorna o id_plano, ou None em caso de erro."""
    if not nome or not str(nome).strip():
        print("O nome do plano é obrigatório.")
        return None

    ok, valor, mensagem = _valor_valido(valor_mensalidade, "a mensalidade")
    if not ok:
        print(mensagem)
        return None

    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            INSERT INTO plano (nome, valor_mensalidade)
            VALUES (BTRIM(%s), %s)
            RETURNING id_plano;
            """,
            (nome, valor)
        )
        id_plano = cursor.fetchone()[0]
        conexao.commit()
        return id_plano

    except Exception as erro:
        print(f"Erro ao criar plano: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def definir_servico_plano(id_plano, id_servico, quantidade_mes):
    """
    Inclui (ou atualiza a cota de) um serviço no plano. UPSERT em plano_servico.
    Retorna True em caso de sucesso.
    """
    if quantidade_mes is None or quantidade_mes <= 0:
        print("quantidade_mes deve ser maior que zero.")
        return False

    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            INSERT INTO plano_servico (id_plano, id_servico, quantidade_mes)
            VALUES (%s, %s, %s)
            ON CONFLICT (id_plano, id_servico)
            DO UPDATE SET quantidade_mes = EXCLUDED.quantidade_mes;
            """,
            (id_plano, id_servico, quantidade_mes)
        )
        conexao.commit()
        return True

    except Exception as erro:
        print(f"Erro ao definir serviço do plano: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def remover_servico_plano(id_plano, id_servico):
    """Remove um serviço de um plano. Retorna True se removeu."""
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            "DELETE FROM plano_servico WHERE id_plano = %s AND id_servico = %s;",
            (id_plano, id_servico)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao remover serviço do plano: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def buscar_planos(apenas_ativos=True):
    """Lista os planos disponíveis."""
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()
        query = "SELECT id_plano, nome, valor_mensalidade, ativo FROM plano WHERE 1=1"
        if apenas_ativos:
            query += " AND ativo = TRUE"
        query += " ORDER BY nome;"
        cursor.execute(query)
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar planos: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


def buscar_plano_por_id(id_plano):
    """
    Retorna o plano e seus serviços inclusos:
      {'plano': (tupla), 'servicos': [(id_servico, nome, quantidade_mes), ...]}
    Ou None se não encontrado.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            "SELECT id_plano, nome, valor_mensalidade, ativo FROM plano WHERE id_plano = %s;",
            (id_plano,)
        )
        plano = cursor.fetchone()
        if not plano:
            return None

        cursor.execute(
            """
            SELECT ps.id_servico, s.nome, ps.quantidade_mes
            FROM plano_servico ps
            JOIN servico s ON s.id_servico = ps.id_servico
            WHERE ps.id_plano = %s
            ORDER BY s.nome;
            """,
            (id_plano,)
        )
        servicos = cursor.fetchall()
        return {'plano': plano, 'servicos': servicos}

    except Exception as erro:
        print(f"Erro ao buscar plano: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def editar_plano(id_plano, nome=MANTER, valor_mensalidade=MANTER):
    """
    Atualiza nome/valor de um plano. Só mexe no que vier preenchido.
    Usa o sentinela MANTER em vez do antigo COALESCE (mesma receita de
    cliente/veículo/serviço/produto/fornecedor). Aqui as duas colunas são
    NOT NULL, então valor vazio é IGNORADO — nunca vira NULL.
    """
    campos = {}

    if nome is not MANTER:
        if not nome or not str(nome).strip():
            print("O nome do plano é obrigatório — alteração ignorada.")
        else:
            campos['nome'] = str(nome).strip()

    if valor_mensalidade is not MANTER:
        ok, valor, mensagem = _valor_valido(valor_mensalidade, "a mensalidade")
        if not ok:
            print(mensagem)
            return False
        campos['valor_mensalidade'] = valor

    if not campos:
        print("Nada para atualizar no plano.")
        return False

    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        # Nomes das colunas vêm do dict interno acima (nunca do usuário);
        # os valores seguem como %s — sem risco de SQL injection.
        sets = ", ".join(f"{coluna} = %s" for coluna in campos)
        cursor.execute(
            f"UPDATE plano SET {sets}, atualizado_em = NOW() WHERE id_plano = %s;",
            (*campos.values(), id_plano)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao editar plano: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def resumo_servicos_planos(apenas_ativos=False):
    """
    {id_plano: (qtd_servicos, total_usos_mes)} numa consulta só.

    Existe para matar o N+1 da tela: ela chamava buscar_plano_por_id() DENTRO do
    laço só para contar os serviços de cada plano — e essa função faz 2 queries,
    então 10 planos custavam 21 conexões ao banco. Mesmo bug já corrigido em
    Serviços (resumo_precos) e Estoque.
    """
    conexao = conectar()
    if not conexao:
        return {}

    try:
        cursor = conexao.cursor()
        query = """
            SELECT p.id_plano,
                   COUNT(ps.id_servico)                        AS qtd_servicos,
                   COALESCE(SUM(ps.quantidade_mes), 0)         AS usos_mes
            FROM plano p
            LEFT JOIN plano_servico ps ON ps.id_plano = p.id_plano
            WHERE 1=1
        """
        if apenas_ativos:
            query += " AND p.ativo = TRUE"
        query += " GROUP BY p.id_plano;"
        cursor.execute(query)
        return {linha[0]: (linha[1], linha[2]) for linha in cursor.fetchall()}

    except Exception as erro:
        print(f"Erro ao resumir serviços dos planos: {erro}")
        return {}

    finally:
        cursor.close()
        conexao.close()


def desativar_plano(id_plano):
    """Desativa um plano (soft delete)."""
    return _set_ativo_plano(id_plano, False)


def reativar_plano(id_plano):
    """Reativa um plano previamente desativado."""
    return _set_ativo_plano(id_plano, True)


def _set_ativo_plano(id_plano, ativo):
    conexao = conectar()
    if not conexao:
        return False
    try:
        cursor = conexao.cursor()
        cursor.execute(
            "UPDATE plano SET ativo = %s, atualizado_em = NOW() WHERE id_plano = %s;",
            (ativo, id_plano)
        )
        conexao.commit()
        return cursor.rowcount > 0
    except Exception as erro:
        print(f"Erro ao alterar status do plano: {erro}")
        conexao.rollback()
        return False
    finally:
        cursor.close()
        conexao.close()


# ----------------------------------------------------------------
# Assinaturas
# ----------------------------------------------------------------

def assinaturas_vigentes_do_cliente(id_cliente, id_plano=None):
    """
    Assinaturas do cliente que valem HOJE (ativa + já iniciada + não vencida).
    Se id_plano vier, restringe àquele plano.
    Tuplas: (id_assinatura, id_plano, nome_plano, data_inicio, data_vencimento).

    É o que faltava para impedir a assinatura duplicada: não havia UNIQUE no
    banco nem checagem nenhuma, então dois cliques no botão "Assinar" criavam
    duas assinaturas ativas do mesmo plano — cota dobrada, em silêncio.
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()
        query = """
            SELECT a.id_assinatura, a.id_plano, p.nome,
                   a.data_inicio, a.data_vencimento
            FROM assinatura a
            JOIN plano p ON p.id_plano = a.id_plano
            WHERE a.id_cliente = %s
              AND a.ativo = TRUE
              AND a.data_inicio <= CURRENT_DATE
              AND (a.data_vencimento IS NULL OR a.data_vencimento >= CURRENT_DATE)
        """
        parametros = [id_cliente]
        if id_plano:
            query += " AND a.id_plano = %s"
            parametros.append(id_plano)
        query += " ORDER BY a.data_inicio DESC;"

        cursor.execute(query, parametros)
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar assinaturas vigentes do cliente: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


def assinar(id_cliente, id_plano, data_inicio=None, data_vencimento=None,
            data_renovacao=None):
    """
    Vincula um cliente a um plano. data_inicio assume hoje se None.
    Retorna o id_assinatura, ou None em caso de erro.

    RECUSA se o cliente já tem uma assinatura VIGENTE do MESMO plano — isso é
    sempre engano (duplo clique, ou não viram que já existia) e dobraria a cota
    sem ninguém perceber. Assinar planos DIFERENTES continua permitido (mensal
    de lavagem + pacote de polimento é legítimo); nesse caso a tela avisa.
    """
    ja_vigentes = assinaturas_vigentes_do_cliente(id_cliente, id_plano)
    if ja_vigentes:
        id_existente, _idp, nome_plano, inicio, venc = ja_vigentes[0]
        print(f"Cliente já tem a assinatura #{id_existente} vigente do plano "
              f"'{nome_plano}' (desde {inicio}"
              f"{f', vence em {venc}' if venc else ''}).")
        return None

    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            INSERT INTO assinatura (id_cliente, id_plano, data_inicio,
                                    data_vencimento, data_renovacao)
            VALUES (%s, %s, COALESCE(%s, CURRENT_DATE), %s, %s)
            RETURNING id_assinatura;
            """,
            (id_cliente, id_plano, data_inicio, data_vencimento, data_renovacao)
        )
        id_assinatura = cursor.fetchone()[0]
        conexao.commit()
        return id_assinatura

    except Exception as erro:
        print(f"Erro ao criar assinatura: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def situacao_assinatura(id_assinatura):
    """
    Diz se a assinatura vale HOJE e por quê — ver o bloco VIGÊNCIA no topo.
    Retorna dict (ou None se não existir):
      {'id_assinatura', 'id_cliente', 'cliente', 'id_plano', 'plano',
       'data_inicio', 'data_vencimento', 'data_renovacao',
       'vigente': bool, 'situacao': 'vigente'|'cancelada'|'nao_iniciada'|'vencida',
       'dias_para_vencer': int|None,   # negativo = venceu há N dias
       'motivo': str}                  # texto pronto para a tela

    'dias_para_vencer' e a comparação de datas são calculados NO BANCO
    (CURRENT_DATE), e não com o datetime do Python — os dois relógios já
    divergiram antes neste projeto (ver conexao.py).
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT a.id_assinatura, a.id_cliente, c.nome, a.id_plano, p.nome,
                   a.data_inicio, a.data_vencimento, a.data_renovacao, a.ativo,
                   (a.data_inicio > CURRENT_DATE)                       AS nao_iniciada,
                   (a.data_vencimento IS NOT NULL
                    AND a.data_vencimento < CURRENT_DATE)               AS vencida,
                   (a.data_vencimento - CURRENT_DATE)                   AS dias,
                   c.telefone, p.valor_mensalidade
            FROM assinatura a
            JOIN cliente c ON c.id_cliente = a.id_cliente
            JOIN plano p   ON p.id_plano   = a.id_plano
            WHERE a.id_assinatura = %s;
            """,
            (id_assinatura,)
        )
        linha = cursor.fetchone()
        if not linha:
            return None

        (ida, idc, cliente, idp, plano, inicio, venc, renov,
         ativo, nao_iniciada, vencida, dias, telefone, mensalidade) = linha

        if not ativo:
            situacao, motivo = 'cancelada', "Assinatura cancelada."
        elif nao_iniciada:
            situacao, motivo = 'nao_iniciada', f"Assinatura começa em {inicio:%d/%m/%Y}."
        elif vencida:
            atraso = abs(dias) if dias is not None else 0
            situacao = 'vencida'
            motivo = (f"Assinatura venceu em {venc:%d/%m/%Y} "
                      f"(há {atraso} dia{'s' if atraso != 1 else ''}).")
        else:
            situacao = 'vigente'
            if dias is None:
                motivo = "Assinatura em dia (sem data de vencimento)."
            elif dias == 0:
                motivo = "Assinatura vence HOJE."
            else:
                motivo = f"Assinatura em dia — vence em {venc:%d/%m/%Y} ({dias} dia(s))."

        return {
            'id_assinatura': ida, 'id_cliente': idc, 'cliente': cliente,
            'telefone': telefone, 'id_plano': idp, 'plano': plano,
            'mensalidade': mensalidade,
            'data_inicio': inicio, 'data_vencimento': venc, 'data_renovacao': renov,
            'vigente': situacao == 'vigente', 'situacao': situacao,
            'dias_para_vencer': dias, 'motivo': motivo,
        }

    except Exception as erro:
        print(f"Erro ao consultar situação da assinatura: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def assinaturas_a_vencer(dias=7, incluir_vencidas=True):
    """
    Assinaturas que vencem nos próximos N dias (e, por padrão, as já vencidas).
    É o "alertar sobre vencimento e renovação" que a documentação do módulo pede
    e que nunca existiu — sem isso, ninguém descobre que o cliente parou de pagar.
    Tuplas: (id_assinatura, cliente, telefone, plano, data_vencimento, dias_restantes).
    Ordenadas pelas mais atrasadas primeiro.
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()
        limite_inferior = "" if incluir_vencidas else " AND a.data_vencimento >= CURRENT_DATE"
        cursor.execute(
            f"""
            SELECT a.id_assinatura, c.nome, c.telefone, p.nome,
                   a.data_vencimento,
                   (a.data_vencimento - CURRENT_DATE) AS dias
            FROM assinatura a
            JOIN cliente c ON c.id_cliente = a.id_cliente
            JOIN plano p   ON p.id_plano   = a.id_plano
            WHERE a.ativo = TRUE
              AND a.data_vencimento IS NOT NULL
              AND a.data_vencimento <= CURRENT_DATE + %s::int
              {limite_inferior}
            ORDER BY a.data_vencimento ASC;
            """,
            (dias,)
        )
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar assinaturas a vencer: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


def cancelar_assinatura(id_assinatura):
    """Cancela (desativa) uma assinatura."""
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            "UPDATE assinatura SET ativo = FALSE, atualizado_em = NOW() WHERE id_assinatura = %s;",
            (id_assinatura,)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao cancelar assinatura: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def buscar_assinaturas(id_cliente=None, apenas_ativas=True):
    """
    Lista assinaturas, com nome do cliente e do plano.
    Tuplas: (id_assinatura, cliente, plano, data_inicio, data_vencimento,
             data_renovacao, ativo, situacao, dias_para_vencer).

    ⚠️ 'situacao' e 'dias_para_vencer' entram no FIM (índices 7 e 8) — as telas
    leem a tupla por posição. Vêm resolvidos no BANCO (CURRENT_DATE) para a lista
    poder marcar "Vencida" sem uma consulta por linha.
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()
        query = """
            SELECT a.id_assinatura, c.nome, p.nome, a.data_inicio,
                   a.data_vencimento, a.data_renovacao, a.ativo,
                   CASE
                       WHEN NOT a.ativo                     THEN 'cancelada'
                       WHEN a.data_inicio > CURRENT_DATE    THEN 'nao_iniciada'
                       WHEN a.data_vencimento IS NOT NULL
                        AND a.data_vencimento < CURRENT_DATE THEN 'vencida'
                       ELSE 'vigente'
                   END AS situacao,
                   (a.data_vencimento - CURRENT_DATE) AS dias_para_vencer
            FROM assinatura a
            JOIN cliente c ON c.id_cliente = a.id_cliente
            JOIN plano p   ON p.id_plano   = a.id_plano
            WHERE 1=1
        """
        parametros = []
        if id_cliente:
            query += " AND a.id_cliente = %s"
            parametros.append(id_cliente)
        if apenas_ativas:
            query += " AND a.ativo = TRUE"
        query += " ORDER BY a.data_inicio DESC;"

        cursor.execute(query, parametros)
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar assinaturas: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


def uso_no_mes(id_assinatura, id_servico):
    """Conta quantas vezes a assinatura usou um serviço no mês vigente."""
    conexao = conectar()
    if not conexao:
        return 0

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM assinatura_uso
            WHERE id_assinatura = %s AND id_servico = %s
              AND date_trunc('month', data_uso) = date_trunc('month', CURRENT_DATE);
            """,
            (id_assinatura, id_servico)
        )
        return cursor.fetchone()[0]

    except Exception as erro:
        print(f"Erro ao consultar uso no mês: {erro}")
        return 0

    finally:
        cursor.close()
        conexao.close()


def registrar_uso(id_assinatura, id_servico, id_ordem=None):
    """
    Registra o uso de um serviço pela assinatura, respeitando plano e limite mensal:
      - a assinatura precisa estar VIGENTE (ativa, iniciada e não vencida);
      - o serviço precisa fazer parte do plano da assinatura;
      - bloqueia se o cliente já usou a cota do serviço no mês vigente.

    Retorna um DICT (não mais só o id/None), porque a tela precisa saber POR QUE
    foi recusado para explicar ao cliente no balcão — "não foi possível" não serve
    quando alguém está esperando uma lavagem de graça:
      {'ok': bool, 'id_uso': int|None, 'motivo': str,
       'usado': int, 'cota': int, 'restante': int, 'situacao': str}

    A checagem de vencimento é a correção principal da revisão de 25/07: antes,
    assinatura vencida em maio continuava liberando serviço para sempre.
    """
    recusa = lambda motivo, **extra: {
        'ok': False, 'id_uso': None, 'motivo': motivo,
        'usado': extra.get('usado', 0), 'cota': extra.get('cota', 0),
        'restante': extra.get('restante', 0),
        'situacao': extra.get('situacao', 'erro'),
    }

    conexao = conectar()
    if not conexao:
        return recusa("Sem conexão com o banco.")

    try:
        cursor = conexao.cursor()

        # Assinatura + vigência, resolvida no BANCO (CURRENT_DATE) — nunca com o
        # datetime do Python: os dois relógios já divergiram neste projeto.
        cursor.execute(
            """
            SELECT id_plano, ativo,
                   (data_inicio > CURRENT_DATE) AS nao_iniciada,
                   (data_vencimento IS NOT NULL
                    AND data_vencimento < CURRENT_DATE) AS vencida,
                   data_vencimento, data_inicio
            FROM assinatura
            WHERE id_assinatura = %s;
            """,
            (id_assinatura,)
        )
        linha = cursor.fetchone()
        if not linha:
            return recusa(f"Assinatura {id_assinatura} não encontrada.")

        id_plano, ativa, nao_iniciada, vencida, venc, inicio = linha

        if not ativa:
            return recusa("Assinatura cancelada — cobre o serviço normalmente.",
                          situacao='cancelada')
        if nao_iniciada:
            return recusa(f"Assinatura só começa em {inicio:%d/%m/%Y}.",
                          situacao='nao_iniciada')
        if vencida:
            return recusa(f"Assinatura venceu em {venc:%d/%m/%Y} — renove antes de usar "
                          f"o plano, ou cobre o serviço normalmente.",
                          situacao='vencida')

        # O serviço faz parte do plano? Qual a cota mensal?
        cursor.execute(
            "SELECT quantidade_mes FROM plano_servico WHERE id_plano = %s AND id_servico = %s;",
            (id_plano, id_servico)
        )
        cota = cursor.fetchone()
        if not cota:
            return recusa("Este serviço não faz parte do plano do cliente.",
                          situacao='fora_do_plano')
        quantidade_mes = cota[0]

        # Quanto já usou NESTE mês. date_trunc('month', data) zera o dia/hora, deixando
        # só ano-mês; comparar as duas versões trunca = "estão no mesmo mês/ano".
        # A cota é mensal e reinicia sozinha ao virar o mês (não precisa "resetar" nada).
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM assinatura_uso
            WHERE id_assinatura = %s AND id_servico = %s
              AND date_trunc('month', data_uso) = date_trunc('month', CURRENT_DATE);
            """,
            (id_assinatura, id_servico)
        )
        usado = cursor.fetchone()[0]

        # Bloqueia se já bateu a cota do mês (usado >= cota). É a regra central do módulo.
        if usado >= quantidade_mes:
            return recusa(f"Cota do mês esgotada: {usado} de {quantidade_mes} já usados. "
                          f"Cobre o serviço normalmente.",
                          usado=usado, cota=quantidade_mes, restante=0,
                          situacao='cota_esgotada')

        cursor.execute(
            """
            INSERT INTO assinatura_uso (id_assinatura, id_servico, id_ordem)
            VALUES (%s, %s, %s)
            RETURNING id_uso;
            """,
            (id_assinatura, id_servico, id_ordem)
        )
        id_uso = cursor.fetchone()[0]
        conexao.commit()

        restante = quantidade_mes - (usado + 1)
        return {
            'ok': True, 'id_uso': id_uso, 'situacao': 'vigente',
            'usado': usado + 1, 'cota': quantidade_mes, 'restante': restante,
            'motivo': f"Incluso no plano — {usado + 1} de {quantidade_mes} usados "
                      f"neste mês ({restante} restante(s)).",
        }

    except Exception as erro:
        print(f"Erro ao registrar uso da assinatura: {erro}")
        conexao.rollback()
        return recusa("Erro ao registrar o uso do plano.")

    finally:
        cursor.close()
        conexao.close()


def saldo_servicos_mes(id_assinatura):
    """
    Mostra, para cada serviço do plano da assinatura, a cota mensal, o quanto já
    foi usado no mês vigente e o restante.
    Tuplas: (id_servico, nome, cota, usado, restante).
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()
        # ⚠️ Detalhe importante: o filtro de mês está na condição do LEFT JOIN (ON ...),
        # NÃO no WHERE. Isso é proposital: mantém na lista TODOS os serviços do plano,
        # inclusive os com 0 uso no mês (usado=0, restante=cota). Se esse filtro fosse
        # para o WHERE, os serviços nunca usados desapareceriam do resumo.
        # COUNT(u.id_uso) conta só os usos que casaram no JOIN (do mês vigente).
        cursor.execute(
            """
            SELECT ps.id_servico, s.nome, ps.quantidade_mes,
                   COUNT(u.id_uso) AS usado,
                   ps.quantidade_mes - COUNT(u.id_uso) AS restante
            FROM assinatura a
            JOIN plano_servico ps ON ps.id_plano = a.id_plano
            JOIN servico s        ON s.id_servico = ps.id_servico
            LEFT JOIN assinatura_uso u
                   ON u.id_assinatura = a.id_assinatura
                  AND u.id_servico = ps.id_servico
                  AND date_trunc('month', u.data_uso) = date_trunc('month', CURRENT_DATE)
            WHERE a.id_assinatura = %s
            GROUP BY ps.id_servico, s.nome, ps.quantidade_mes
            ORDER BY s.nome;
            """,
            (id_assinatura,)
        )
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao consultar saldo de serviços: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


# ================================================================
# TESTE RÁPIDO (rode este arquivo diretamente para testar)
# ================================================================
if __name__ == "__main__":
    print("Criando plano 'Mensal 2 Lavagens'...")
    pid = criar_plano("Mensal 2 Lavagens", 99.90)
    print(f"Plano criado: {pid}")

    if pid:
        # Serviço 1 (Lavagem Simples), 2 usos por mês
        definir_servico_plano(pid, 1, 2)
        print("Plano com serviços:", buscar_plano_por_id(pid))

        print("\nAssinando cliente 1 ao plano...")
        aid = assinar(id_cliente=1, id_plano=pid, data_vencimento="2026-07-24")
        print(f"Assinatura criada: {aid}")

        if aid:
            print("\nSituação da assinatura:", situacao_assinatura(aid)['motivo'])

            print("\nRegistrando usos do serviço 1 (cota = 2):")
            for n in (1, 2, 3):   # o 3º deve ser bloqueado pelo limite
                r = registrar_uso(aid, 1)
                print(f"  uso {n} -> ok={r['ok']} | {r['motivo']}")

            print("\nSaldo de serviços no mês:")
            for s in saldo_servicos_mes(aid):
                print("  ", s)

            print("\nAssinar o MESMO plano de novo (deve recusar):")
            print("  ->", assinar(id_cliente=1, id_plano=pid))
