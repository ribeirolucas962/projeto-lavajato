"""
Módulo: Dashboard (módulo 11)
Sistema: Lava-Jato
Autor: RINEAL Analytics

Indicadores do Dashboard — SOMENTE LEITURA (o módulo não tem tabela própria;
tudo aqui é consulta sobre as tabelas dos outros módulos, principalmente
ordem_servico / ordem_servico_item).

Segue o padrão de conexão do cadastro_cliente.py (conectar + try/finally),
mas sem commit/rollback: nenhuma função escreve no banco.

Convenções dos indicadores:
  - "Faturamento" = comandas com status 'finalizado' ou 'entregue', pelo VALOR
    FINAL (valor_total - desconto + acrescimo) — o que foi cobrado de fato.
  - Períodos em dias são parâmetros (%s) via INTERVAL '1 day' * N.
  - Comandas 'cancelado' ficam de fora de tudo.
  - Em caso de falha de conexão/consulta, cada função devolve um valor "vazio"
    (0.0 / [] / None) para o app não quebrar.
"""

from conexao import conectar

# Expressão do valor final da comanda (reutilizada nas consultas de dinheiro).
_VALOR_FINAL = "(valor_total - COALESCE(desconto, 0) + COALESCE(acrescimo, 0))"


def faturamento(periodo="hoje"):
    """
    Soma o valor final das comandas finalizadas/entregues no período:
    'hoje' (dia corrente) ou 'mes' (mês corrente). Retorna float (0.0 se vazio).
    """
    conexao = conectar()
    if not conexao:
        return 0.0

    try:
        cursor = conexao.cursor()
        # 'filtro' é escolhido pelo código (nunca vem do usuário) — por isso pode
        # entrar na query por f-string sem risco de injection.
        if periodo == "hoje":
            filtro = "entrada_em::date = CURRENT_DATE"
        else:
            filtro = "date_trunc('month', entrada_em) = date_trunc('month', CURRENT_DATE)"
        cursor.execute(
            f"""
            SELECT COALESCE(SUM({_VALOR_FINAL}), 0)
            FROM ordem_servico
            WHERE status IN ('finalizado', 'entregue') AND {filtro};
            """
        )
        return float(cursor.fetchone()[0] or 0)

    except Exception as erro:
        print(f"Erro ao calcular faturamento: {erro}")
        return 0.0

    finally:
        cursor.close()
        conexao.close()


def ticket_medio(dias=30):
    """
    Valor final médio das comandas finalizadas/entregues nos últimos 'dias'.
    Retorna float (0.0 se não houver comanda no período).
    """
    conexao = conectar()
    if not conexao:
        return 0.0

    try:
        cursor = conexao.cursor()
        cursor.execute(
            f"""
            SELECT AVG({_VALOR_FINAL})
            FROM ordem_servico
            WHERE status IN ('finalizado', 'entregue')
              AND entrada_em >= NOW() - INTERVAL '1 day' * %s;
            """,
            (dias,)
        )
        return float(cursor.fetchone()[0] or 0)

    except Exception as erro:
        print(f"Erro ao calcular ticket médio: {erro}")
        return 0.0

    finally:
        cursor.close()
        conexao.close()


def servicos_mais_vendidos(dias=30, limite=5):
    """
    Ranking de serviços nos últimos 'dias' (comandas finalizadas/entregues).
    Retorna lista de tuplas (nome, quantidade, total_faturado) — a mais vendida
    primeiro. O total usa preco_aplicado (preço congelado na comanda).
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT s.nome, COUNT(*) AS qtd, SUM(i.preco_aplicado) AS total
            FROM ordem_servico_item i
            JOIN servico s        ON s.id_servico = i.id_servico
            JOIN ordem_servico o  ON o.id_ordem   = i.id_ordem
            WHERE o.status IN ('finalizado', 'entregue')
              AND o.entrada_em >= NOW() - INTERVAL '1 day' * %s
            GROUP BY s.nome
            ORDER BY qtd DESC, total DESC
            LIMIT %s;
            """,
            (dias, limite)
        )
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar serviços mais vendidos: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


def taxa_retorno(dias=90):
    """
    % de clientes que RETORNARAM no período: entre os clientes com ao menos uma
    comanda (não cancelada) nos últimos 'dias', quantos têm duas ou mais.
    Retorna float de 0 a 100 (0.0 se não houver clientes no período).
    """
    conexao = conectar()
    if not conexao:
        return 0.0

    try:
        cursor = conexao.cursor()
        # Subconsulta: comandas por cliente no período. Fora: proporção com >= 2.
        # NULLIF evita divisão por zero quando não há nenhum cliente no período.
        cursor.execute(
            """
            SELECT COUNT(*) FILTER (WHERE qtd >= 2)::numeric
                   / NULLIF(COUNT(*), 0) * 100
            FROM (
                SELECT id_cliente, COUNT(*) AS qtd
                FROM ordem_servico
                WHERE status <> 'cancelado'
                  AND entrada_em >= NOW() - INTERVAL '1 day' * %s
                GROUP BY id_cliente
            ) comandas_por_cliente;
            """,
            (dias,)
        )
        return float(cursor.fetchone()[0] or 0)

    except Exception as erro:
        print(f"Erro ao calcular taxa de retorno: {erro}")
        return 0.0

    finally:
        cursor.close()
        conexao.close()


def tempo_medio_servico(dias=30):
    """
    Tempo médio de execução (inicio_em -> finalizacao_em), em MINUTOS, das
    comandas finalizadas/entregues nos últimos 'dias'.
    Retorna float ou None se nenhuma comanda do período tiver os dois horários.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT AVG(EXTRACT(EPOCH FROM (finalizacao_em - inicio_em)) / 60.0)
            FROM ordem_servico
            WHERE status IN ('finalizado', 'entregue')
              AND inicio_em IS NOT NULL
              AND finalizacao_em IS NOT NULL
              AND entrada_em >= NOW() - INTERVAL '1 day' * %s;
            """,
            (dias,)
        )
        resultado = cursor.fetchone()[0]
        return float(resultado) if resultado is not None else None

    except Exception as erro:
        print(f"Erro ao calcular tempo médio de serviço: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()


def horarios_pico(dias=30):
    """
    Movimento por hora do dia nos últimos 'dias' (comandas não canceladas,
    pela hora de entrada). Retorna lista de tuplas (hora 0-23, quantidade),
    ordenada por hora — pronta para virar gráfico de barras.
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT EXTRACT(HOUR FROM entrada_em)::int AS hora, COUNT(*) AS qtd
            FROM ordem_servico
            WHERE status <> 'cancelado'
              AND entrada_em >= NOW() - INTERVAL '1 day' * %s
            GROUP BY hora
            ORDER BY hora;
            """,
            (dias,)
        )
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao calcular horários de pico: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


# ================================================================
# Teste rápido: python dashboard.py imprime todos os indicadores
# ================================================================
if __name__ == "__main__":
    print("Faturamento hoje....:", faturamento("hoje"))
    print("Faturamento no mês..:", faturamento("mes"))
    print("Ticket médio (30d)..:", ticket_medio(30))
    print("Mais vendidos (30d).:", servicos_mais_vendidos(30))
    print("Taxa de retorno (90d):", taxa_retorno(90))
    print("Tempo médio (30d)...:", tempo_medio_servico(30))
    print("Horários de pico (30d):", horarios_pico(30))
