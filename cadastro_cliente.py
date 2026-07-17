"""
Módulo de Cadastro de Cliente
Sistema: Lava-Jato
Autor: RINEAL Analytics

Funções de CRUD (Criar, Ler, Atualizar, Desativar) para a tabela cliente.

------------------------------------------------------------------------------
MÓDULO DE REFERÊNCIA — o padrão comentado aqui vale para TODOS os módulos backend
------------------------------------------------------------------------------
Toda função de banco segue a mesma "receita" (veja também o CLAUDE.md):
  1. conexao = conectar(); se falhar (None), retorna cedo um valor "vazio"
     (None / [] / False) — nunca segue sem conexão.
  2. try:    executa a query e dá commit() (nas escritas);
     except: imprime o erro e faz rollback() (desfaz escrita pela metade);
     finally: cursor.close() + conexao.close() (sempre libera a conexão).
  3. Queries SEMPRE parametrizadas com %s (nunca f-string com dado do usuário)
     — é a proteção contra SQL injection.
  4. Soft delete: desativar_*/reativar_* trocam a coluna 'ativo' em vez de DELETE,
     preservando o histórico.
  5. Update parcial: editar_cliente() só mexe nos campos que você PASSAR
     (ver o sentinela MANTER, logo abaixo).

⚠️ A ORDEM das colunas nos SELECT abaixo é a MESMA ordem em que o app.py desempacota
as tuplas (ex.: `(idc, nome, cpf, tel, ...) = c`). Mudou a coluna aqui? Ajuste lá.
   Colunas NOVAS entram sempre NO FIM do SELECT — assim as telas que leem por
   posição (c[0], c[1], c[3]...) continuam funcionando sem alteração.

Além do CRUD, este módulo traz as consultas que dão INTELIGÊNCIA ao cadastro:
  ficha_cliente()       -> retrato completo (veículos, histórico, quanto gastou)
  aniversariantes_mes() -> quem faz aniversário no mês (campanha de parabéns)
  clientes_inativos()   -> quem sumiu há X dias (campanha de retorno)
  top_clientes()        -> quem mais gasta
  possiveis_duplicados()-> evita cadastrar o mesmo cliente duas vezes
"""

import psycopg2

from conexao import conectar

# Sentinela do update parcial. Precisamos distinguir três intenções:
#   editar_cliente(1, nome="Ana")     -> muda o nome, NÃO MEXE no resto  (MANTER)
#   editar_cliente(1, email=None)     -> APAGA o e-mail (grava NULL)
#   editar_cliente(1, email="a@b.c")  -> grava o novo e-mail
# Com o antigo COALESCE(%s, campo) era impossível apagar: None significava
# "mantenha o que está lá". Agora o "mantenha" é este objeto MANTER (o valor
# padrão dos parâmetros) e o None volta a significar "vazio" de verdade.
MANTER = object()

# Faturamento de uma comanda = o que foi REALMENTE cobrado. Mesma regra do
# dashboard.py: só comanda finalizada/entregue, pelo valor final.
_VALOR_FINAL = "(valor_total - COALESCE(desconto, 0) + COALESCE(acrescimo, 0))"


def inserir_cliente(nome, cpf_cnpj=None, telefone=None, email=None,
                     endereco=None, observacoes=None,
                     data_nascimento=None, como_conheceu=None):
    """
    Insere um novo cliente no banco de dados.
    'data_nascimento' é um date do Python — use validadores.parse_data_br() para
    converter o texto 'dd/mm/aaaa' digitado na tela.
    Retorna o id_cliente criado, ou None em caso de erro.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            INSERT INTO cliente (nome, cpf_cnpj, telefone, email, endereco,
                                 observacoes, data_nascimento, como_conheceu)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id_cliente;
            """,
            (nome, cpf_cnpj, telefone, email, endereco, observacoes,
             data_nascimento, como_conheceu)
        )
        # RETURNING devolve o id gerado (SERIAL) na mesma query — evita um SELECT extra.
        id_cliente = cursor.fetchone()[0]
        conexao.commit()   # confirma a escrita; sem isso o INSERT seria descartado
        return id_cliente

    except Exception as erro:
        # Qualquer falha desfaz a transação inteira (não deixa registro pela metade).
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

        # "WHERE 1=1" é um truque para montar o filtro dinamicamente: cada condição
        # opcional vira só um "AND ..." sem precisar checar se é a primeira cláusula.
        # Colunas novas (data_nascimento, como_conheceu) vão NO FIM: as telas que
        # leem por posição (c[0]=id, c[1]=nome, c[3]=telefone) seguem intactas.
        query = ("SELECT id_cliente, nome, cpf_cnpj, telefone, email, endereco, "
                 "observacoes, ativo, data_nascimento, como_conheceu "
                 "FROM cliente WHERE 1=1")
        parametros = []

        if apenas_ativos:
            query += " AND ativo = TRUE"

        if termo:
            # ILIKE = busca parcial e sem diferenciar maiúsculas; %termo% casa em qualquer
            # posição. O termo entra como PARÂMETRO (%s), não concatenado — sem injection.
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
            SELECT id_cliente, nome, cpf_cnpj, telefone, email, endereco,
                   observacoes, ativo, data_nascimento, como_conheceu
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


def editar_cliente(id_cliente, nome=MANTER, cpf_cnpj=MANTER, telefone=MANTER,
                    email=MANTER, endereco=MANTER, observacoes=MANTER,
                    data_nascimento=MANTER, como_conheceu=MANTER):
    """
    Atualiza os dados de um cliente existente.

    Campo que você NÃO passar fica como está (o padrão é o sentinela MANTER).
    Campo passado como None é APAGADO (vira NULL no banco) — era isso que o
    COALESCE antigo impedia: apagar o e-mail de um cliente era impossível, o
    valor velho voltava sozinho.

    Exceção: o 'nome' é NOT NULL no banco. Passar nome=None/'' seria um erro do
    chamador, então nesse caso o nome simplesmente não é alterado (em vez de
    estourar uma exceção do Postgres).

    Retorna True se alguma linha foi atualizada, False caso contrário.
    """
    conexao = conectar()
    if not conexao:
        return False

    # Monta o SET dinamicamente: só entram na query os campos realmente enviados.
    # Os NOMES das colunas vêm daqui de dentro (nunca do usuário) e os VALORES
    # continuam indo como parâmetro %s — segue sem risco de SQL injection.
    campos = {
        "nome": nome,
        "cpf_cnpj": cpf_cnpj,
        "telefone": telefone,
        "email": email,
        "endereco": endereco,
        "observacoes": observacoes,
        "data_nascimento": data_nascimento,
        "como_conheceu": como_conheceu,
    }
    partes, valores = [], []
    for coluna, valor in campos.items():
        if valor is MANTER:
            continue                                  # não foi enviado -> não mexe
        if coluna == "nome" and not (valor or "").strip():
            continue                                  # nome é obrigatório -> ignora
        partes.append(f"{coluna} = %s")
        valores.append(valor)

    if not partes:
        conexao.close()
        return False   # ninguém pediu mudança nenhuma

    partes.append("atualizado_em = NOW()")
    valores.append(id_cliente)

    try:
        cursor = conexao.cursor()
        cursor.execute(
            f"UPDATE cliente SET {', '.join(partes)} WHERE id_cliente = %s;",
            valores
        )
        conexao.commit()
        # rowcount > 0 => alguma linha foi afetada (id existia). False => id inexistente.
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
        # Soft delete: apenas marca ativo=FALSE. O registro continua no banco (e nas
        # comandas/histórico); some só das listas que filtram por apenas_ativos=True.
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


def excluir_cliente(id_cliente):
    """
    Exclui o cliente DE VEZ (DELETE) — só para cadastro criado errado
    (teste, duplicado), SEM nada vinculado. Se o cliente tiver qualquer
    histórico (veículo, comanda, agendamento, fidelidade, assinatura),
    o banco BLOQUEIA a exclusão (FKs sem CASCADE) e devolvemos 'vinculos'
    — nesse caso o caminho certo é desativar (soft delete).
    Retorna: True = excluído | 'vinculos' = tem histórico | False = erro/não achou.
    """
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            "DELETE FROM cliente WHERE id_cliente = %s;",
            (id_cliente,)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except psycopg2.errors.ForeignKeyViolation:
        # Alguma tabela ainda aponta para este cliente — histórico existe.
        conexao.rollback()
        return 'vinculos'

    except Exception as erro:
        print(f"Erro ao excluir cliente: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


# ================================================================
# ANTI-DUPLICIDADE
# ================================================================
def possiveis_duplicados(nome=None, telefone=None, cpf_cnpj=None, ignorar_id=None):
    """
    Procura clientes que PARECEM ser a mesma pessoa antes de cadastrar de novo.
    Casa por telefone igual, documento igual ou nome idêntico (ignorando
    maiúsculas). Não bloqueia nada: só devolve a lista para a tela perguntar
    "já existe este cliente, quer mesmo cadastrar outro?".

    'ignorar_id' exclui o próprio cliente da busca (na edição, ele não é
    duplicata de si mesmo).
    Retorna [(id_cliente, nome, telefone, cpf_cnpj, motivo), ...].
    """
    import re
    conexao = conectar()
    if not conexao:
        return []

    # Compara só os DÍGITOS do telefone/documento: '(47) 99999-0000' e
    # '47999990000' são o mesmo número, mas seriam textos diferentes no ILIKE.
    # regexp_replace(coluna, '\D', '', 'g') faz no banco o mesmo que so_digitos().
    tel_d = re.sub(r"\D", "", telefone or "")
    doc_d = re.sub(r"\D", "", cpf_cnpj or "")
    nome_l = (nome or "").strip()

    condicoes, parametros = [], []
    if tel_d:
        condicoes.append("regexp_replace(COALESCE(telefone, ''), '\\D', '', 'g') = %s")
        parametros.append(tel_d)
    if doc_d:
        condicoes.append("regexp_replace(COALESCE(cpf_cnpj, ''), '\\D', '', 'g') = %s")
        parametros.append(doc_d)
    if nome_l:
        condicoes.append("LOWER(TRIM(nome)) = LOWER(%s)")
        parametros.append(nome_l)

    if not condicoes:
        conexao.close()
        return []

    query = f"""
        SELECT id_cliente, nome, telefone, cpf_cnpj,
               CASE
                 WHEN regexp_replace(COALESCE(cpf_cnpj, ''), '\\D', '', 'g') = %s
                      AND %s <> '' THEN 'mesmo CPF/CNPJ'
                 WHEN regexp_replace(COALESCE(telefone, ''), '\\D', '', 'g') = %s
                      AND %s <> '' THEN 'mesmo telefone'
                 ELSE 'mesmo nome'
               END AS motivo
        FROM cliente
        WHERE ({' OR '.join(condicoes)})
    """
    # Os 4 primeiros %s são do CASE (que roda para cada linha encontrada).
    valores = [doc_d, doc_d, tel_d, tel_d] + parametros

    if ignorar_id:
        query += " AND id_cliente <> %s"
        valores.append(ignorar_id)
    query += " ORDER BY nome;"

    try:
        cursor = conexao.cursor()
        cursor.execute(query, valores)
        return cursor.fetchall()
    except Exception as erro:
        print(f"Erro ao checar duplicidade: {erro}")
        return []
    finally:
        cursor.close()
        conexao.close()


# ================================================================
# FICHA DO CLIENTE (visão 360°)
# ================================================================
def ficha_cliente(id_cliente):
    """
    O retrato completo do cliente numa única chamada. Junta o que hoje está
    espalhado por 4 telas (Veículos, Comandas, Fidelidade, Planos).

    Retorna um DICIONÁRIO (não uma tupla — aqui são muitos dados, e nome de
    chave é mais legível que posição) ou None se o cliente não existir:

      {
        'cliente':   tupla do buscar_cliente_por_id(),
        'veiculos':  [(id, placa, marca, modelo, ano, cor, categoria), ...],
        'comandas':  [(id_ordem, entrada_em, placa, status, valor_final, valor_pago), ...],
        'servicos':  [(nome_servico, vezes), ...]   # os preferidos dele
        'pontos':    int,                            # saldo de fidelidade
        'plano':     (nome, mensalidade, data_inicio) ou None,
        'resumo':    {'visitas', 'total_gasto', 'ticket_medio',
                      'primeira_visita', 'ultima_visita', 'dias_sem_vir', 'em_aberto'}
      }
    """
    cliente = buscar_cliente_por_id(id_cliente)
    if not cliente:
        return None

    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()

        # --- Veículos do cliente (com o nome do porte, não o id) ---
        cursor.execute(
            """
            SELECT v.id_veiculo, v.placa, v.marca, v.modelo, v.ano, v.cor, c.nome
            FROM veiculo v
            JOIN categoria_veiculo c ON c.id_categoria = v.id_categoria
            WHERE v.id_cliente = %s AND v.ativo = TRUE
            ORDER BY v.placa;
            """,
            (id_cliente,)
        )
        veiculos = cursor.fetchall()

        # --- Histórico de comandas (as 20 mais recentes) ---
        cursor.execute(
            f"""
            SELECT o.id_ordem, o.entrada_em, v.placa, o.status,
                   {_VALOR_FINAL} AS valor_final,
                   COALESCE(o.valor_pago, 0) AS valor_pago
            FROM ordem_servico o
            JOIN veiculo v ON v.id_veiculo = o.id_veiculo
            WHERE o.id_cliente = %s
            ORDER BY o.entrada_em DESC
            LIMIT 20;
            """,
            (id_cliente,)
        )
        comandas = cursor.fetchall()

        # --- Resumo financeiro: só comandas que viraram dinheiro de verdade ---
        # NULLIF evita divisão por zero no ticket médio (cliente sem visita).
        cursor.execute(
            f"""
            SELECT COUNT(*)                                   AS visitas,
                   COALESCE(SUM({_VALOR_FINAL}), 0)           AS total_gasto,
                   COALESCE(SUM({_VALOR_FINAL}), 0)
                       / NULLIF(COUNT(*), 0)                  AS ticket_medio,
                   MIN(o.entrada_em)                          AS primeira,
                   MAX(o.entrada_em)                          AS ultima,
                   COALESCE(SUM({_VALOR_FINAL} - COALESCE(o.valor_pago, 0)), 0) AS em_aberto
            FROM ordem_servico o
            WHERE o.id_cliente = %s
              AND o.status IN ('finalizado', 'entregue');
            """,
            (id_cliente,)
        )
        visitas, total_gasto, ticket, primeira, ultima, em_aberto = cursor.fetchone()

        # --- Serviços preferidos (o que ele mais pede) ---
        cursor.execute(
            """
            SELECT s.nome, COUNT(*) AS vezes
            FROM ordem_servico_item i
            JOIN ordem_servico o ON o.id_ordem = i.id_ordem
            JOIN servico s       ON s.id_servico = i.id_servico
            WHERE o.id_cliente = %s AND i.id_servico IS NOT NULL
            GROUP BY s.nome
            ORDER BY vezes DESC, s.nome
            LIMIT 5;
            """,
            (id_cliente,)
        )
        servicos = cursor.fetchall()

        # --- Fidelidade (pode não ter linha ainda: cliente sem ponto nenhum) ---
        cursor.execute(
            "SELECT pontos FROM fidelidade_saldo WHERE id_cliente = %s;",
            (id_cliente,)
        )
        linha = cursor.fetchone()
        pontos = linha[0] if linha else 0

        # --- Plano assinado (o mais recente ativo) ---
        cursor.execute(
            """
            SELECT p.nome, p.valor_mensalidade, a.data_inicio
            FROM assinatura a
            JOIN plano p ON p.id_plano = a.id_plano
            WHERE a.id_cliente = %s AND a.ativo = TRUE
            ORDER BY a.data_inicio DESC
            LIMIT 1;
            """,
            (id_cliente,)
        )
        plano = cursor.fetchone()

        dias_sem_vir = None
        if ultima:
            from datetime import datetime
            dias_sem_vir = (datetime.now() - ultima).days

        return {
            "cliente": cliente,
            "veiculos": veiculos,
            "comandas": comandas,
            "servicos": servicos,
            "pontos": pontos,
            "plano": plano,
            "resumo": {
                "visitas": visitas or 0,
                "total_gasto": total_gasto or 0,
                "ticket_medio": ticket or 0,
                "primeira_visita": primeira,
                "ultima_visita": ultima,
                "dias_sem_vir": dias_sem_vir,
                "em_aberto": em_aberto or 0,
            },
        }

    except Exception as erro:
        print(f"Erro ao montar a ficha do cliente: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


# ================================================================
# CAMPANHAS (listas para o operador agir — todas viram WhatsApp na tela)
# ================================================================
def aniversariantes_mes(mes=None):
    """
    Clientes que fazem aniversário no mês (padrão: o mês atual).
    EXTRACT(MONTH FROM data_nascimento) pega só o mês da data, ignorando o ano.
    Retorna [(id, nome, telefone, data_nascimento, dia), ...] ordenado pelo dia.
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT id_cliente, nome, telefone, data_nascimento,
                   EXTRACT(DAY FROM data_nascimento)::int AS dia
            FROM cliente
            WHERE ativo = TRUE
              AND data_nascimento IS NOT NULL
              AND EXTRACT(MONTH FROM data_nascimento) =
                  COALESCE(%s, EXTRACT(MONTH FROM CURRENT_DATE))
            ORDER BY dia, nome;
            """,
            (mes,)
        )
        return cursor.fetchall()
    except Exception as erro:
        print(f"Erro ao buscar aniversariantes: {erro}")
        return []
    finally:
        cursor.close()
        conexao.close()


def clientes_inativos(dias=60):
    """
    Clientes que não aparecem há mais de X dias — os candidatos à mensagem
    "sentimos sua falta". Inclui quem NUNCA veio (cadastrou e sumiu):
    o LEFT JOIN mantém o cliente mesmo sem comanda, e o MAX(entrada_em) vira NULL.

    Retorna [(id, nome, telefone, ultima_visita, dias_sem_vir), ...],
    do que sumiu há mais tempo para o mais recente.
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT c.id_cliente, c.nome, c.telefone,
                   MAX(o.entrada_em) AS ultima_visita,
                   (CURRENT_DATE - MAX(o.entrada_em)::date) AS dias_sem_vir
            FROM cliente c
            LEFT JOIN ordem_servico o
                   ON o.id_cliente = c.id_cliente
                  AND o.status IN ('finalizado', 'entregue')
            WHERE c.ativo = TRUE
            GROUP BY c.id_cliente, c.nome, c.telefone
            HAVING MAX(o.entrada_em) IS NULL
                OR MAX(o.entrada_em) < CURRENT_DATE - %s::int
            ORDER BY ultima_visita ASC NULLS FIRST, c.nome;
            """,
            (dias,)
        )
        return cursor.fetchall()
    except Exception as erro:
        print(f"Erro ao buscar clientes inativos: {erro}")
        return []
    finally:
        cursor.close()
        conexao.close()


def top_clientes(limite=10, dias=None):
    """
    Ranking dos clientes que mais gastaram (os que merecem tratamento VIP).
    'dias' limita o período (ex.: 90 = últimos 3 meses); None = desde sempre.
    Retorna [(id, nome, telefone, visitas, total_gasto), ...] do maior ao menor.
    """
    conexao = conectar()
    if not conexao:
        return []

    filtro_periodo = ""
    parametros = []
    if dias:
        filtro_periodo = "AND o.entrada_em >= CURRENT_DATE - %s::int"
        parametros.append(dias)
    parametros.append(limite)

    try:
        cursor = conexao.cursor()
        cursor.execute(
            f"""
            SELECT c.id_cliente, c.nome, c.telefone,
                   COUNT(*)                          AS visitas,
                   COALESCE(SUM({_VALOR_FINAL}), 0)  AS total_gasto
            FROM cliente c
            JOIN ordem_servico o ON o.id_cliente = c.id_cliente
            WHERE o.status IN ('finalizado', 'entregue') {filtro_periodo}
            GROUP BY c.id_cliente, c.nome, c.telefone
            ORDER BY total_gasto DESC, visitas DESC
            LIMIT %s;
            """,
            parametros
        )
        return cursor.fetchall()
    except Exception as erro:
        print(f"Erro ao buscar o top de clientes: {erro}")
        return []
    finally:
        cursor.close()
        conexao.close()


# ================================================================
# TESTE RÁPIDO (rode este arquivo diretamente para testar o CRUD)
# ================================================================
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # acentos no terminal do Windows
    except Exception:
        pass

    print("=== Clientes cadastrados ===")
    for c in buscar_clientes():
        print(f"  [{c[0]}] {c[1]:<25} tel: {c[3] or '—':<18} nasc: {c[8] or '—'}")

    print("\n=== Ficha do cliente 1 ===")
    f = ficha_cliente(1)
    if f:
        r = f["resumo"]
        print(f"  Nome        : {f['cliente'][1]}")
        print(f"  Veículos    : {len(f['veiculos'])}")
        print(f"  Visitas     : {r['visitas']}")
        print(f"  Total gasto : R$ {r['total_gasto']}")
        print(f"  Ticket médio: R$ {r['ticket_medio']:.2f}" if r['visitas'] else "  Ticket médio: —")
        print(f"  Última visita: {r['ultima_visita']} ({r['dias_sem_vir']} dias atrás)"
              if r['ultima_visita'] else "  Última visita: nunca veio")
        print(f"  Em aberto   : R$ {r['em_aberto']}")
        print(f"  Pontos      : {f['pontos']}")
        print(f"  Plano       : {f['plano'][0] if f['plano'] else '—'}")
        print(f"  Preferidos  : {[s[0] for s in f['servicos']] or '—'}")
    else:
        print("  (cliente 1 não encontrado)")

    print("\n=== Aniversariantes do mês ===")
    for a in aniversariantes_mes() or [("—", "nenhum", "", "", "")]:
        print(f"  {a[1]}")

    print("\n=== Clientes sumidos (60+ dias) ===")
    for c in clientes_inativos(60)[:5] or [("—", "nenhum", "", "", "")]:
        print(f"  {c[1]:<25} há {c[4] if c[4] is not None else '∞'} dias")

    print("\n=== Top clientes ===")
    for t in top_clientes(5) or [("—", "nenhum", "", 0, 0)]:
        print(f"  {t[1]:<25} {t[3]} visita(s)  R$ {t[4]}")
