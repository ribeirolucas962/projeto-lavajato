"""
Módulo de Fidelidade
Sistema: Lava-Jato
Autor: RINEAL Analytics

Sistema de pontos por cliente: acúmulo (a cada comanda finalizada) e resgate de
benefícios, sempre com histórico em fidelidade_movimento.
O saldo fica em fidelidade_saldo e é atualizado na MESMA transação do movimento.

AS DUAS REGRAS (revisão de 2026-07-25) — antes elas simplesmente não existiam:
  * ACÚMULO  -> fidelidade_regra.pontos_por_lavagem (combinado: 1 ponto por
    lavação). Antes era o default `pontos=1` de um parâmetro Python, que ninguém
    conseguia mudar sem mexer no código.
  * TROCA    -> fidelidade_recompensa (catálogo: o que leva, por quantos pontos).
    Antes o atendente digitava um número qualquer no resgate, ou seja, quanto
    valia um ponto era decisão de quem estava no balcão.
As duas ficam no BANCO e são editáveis pela tela, como a taxa_pagamento do Caixa:
promoção muda, e trocar um número não pode exigir reempacotar o .exe.
"""

from conexao import conectar


# Comandas que geram ponto: o MESMO critério de faturamento do dashboard.py, da
# ficha do cliente e da comissão — é o que faz os números baterem entre as telas.
# Comanda cancelada não vira ponto.
STATUS_PONTUAVEIS = ('finalizado', 'entregue')


# ----------------------------------------------------------------
# Regra de acúmulo (quantos pontos por lavagem)
# ----------------------------------------------------------------

def regra_pontos():
    """
    Pontos ganhos por lavagem. Retorna (pontos_por_lavagem, ativo).
    Cai no padrão (1, True) se a tabela ainda não existir ou estiver vazia —
    assim o módulo funciona mesmo antes de rodar o criar_tabelas.py atualizado.
    """
    conexao = conectar()
    if not conexao:
        return (1, True)

    try:
        cursor = conexao.cursor()
        cursor.execute("SELECT pontos_por_lavagem, ativo FROM fidelidade_regra WHERE id = 1;")
        linha = cursor.fetchone()
        return (linha[0], linha[1]) if linha else (1, True)

    except Exception as erro:
        print(f"Erro ao consultar a regra de pontos: {erro}")
        return (1, True)

    finally:
        cursor.close()
        conexao.close()


def salvar_regra(pontos_por_lavagem, ativo=True):
    """Grava a regra de acúmulo (linha única). Retorna True em caso de sucesso."""
    try:
        pontos = int(str(pontos_por_lavagem).strip())
    except (TypeError, ValueError):
        print("Pontos por lavagem deve ser um número inteiro.")
        return False
    if pontos < 0:
        print("Pontos por lavagem não pode ser negativo.")
        return False

    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            INSERT INTO fidelidade_regra (id, pontos_por_lavagem, ativo)
            VALUES (1, %s, %s)
            ON CONFLICT (id) DO UPDATE
                SET pontos_por_lavagem = EXCLUDED.pontos_por_lavagem,
                    ativo              = EXCLUDED.ativo,
                    atualizado_em      = NOW();
            """,
            (pontos, bool(ativo))
        )
        conexao.commit()
        return True

    except Exception as erro:
        print(f"Erro ao salvar a regra de pontos: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


# ----------------------------------------------------------------
# Catálogo de recompensas (a regra de troca)
# ----------------------------------------------------------------

def recompensas(apenas_ativas=True):
    """
    Catálogo de trocas, da mais barata para a mais cara.
    Tuplas: (id_recompensa, nome, pontos_necessarios, id_servico, nome_servico, ativo).
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()
        query = """
            SELECT r.id_recompensa, r.nome, r.pontos_necessarios,
                   r.id_servico, s.nome, r.ativo
            FROM fidelidade_recompensa r
            LEFT JOIN servico s ON s.id_servico = r.id_servico
            WHERE 1=1
        """
        if apenas_ativas:
            query += " AND r.ativo = TRUE"
        query += " ORDER BY r.pontos_necessarios, r.nome;"
        cursor.execute(query)
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar recompensas: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


def salvar_recompensa(nome, pontos_necessarios, id_servico=None, id_recompensa=None):
    """
    Cria (id_recompensa=None) ou edita uma recompensa do catálogo.
    Retorna o id_recompensa, ou None em caso de erro.
    """
    if not nome or not str(nome).strip():
        print("O nome da recompensa é obrigatório.")
        return None
    try:
        pontos = int(str(pontos_necessarios).strip())
    except (TypeError, ValueError):
        print("Pontos necessários deve ser um número inteiro.")
        return None
    if pontos <= 0:
        print("Pontos necessários deve ser maior que zero.")
        return None

    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        if id_recompensa:
            cursor.execute(
                """
                UPDATE fidelidade_recompensa
                SET nome = BTRIM(%s), pontos_necessarios = %s,
                    id_servico = %s, atualizado_em = NOW()
                WHERE id_recompensa = %s
                RETURNING id_recompensa;
                """,
                (nome, pontos, id_servico, id_recompensa)
            )
        else:
            cursor.execute(
                """
                INSERT INTO fidelidade_recompensa (nome, pontos_necessarios, id_servico)
                VALUES (BTRIM(%s), %s, %s)
                RETURNING id_recompensa;
                """,
                (nome, pontos, id_servico)
            )
        linha = cursor.fetchone()
        conexao.commit()
        return linha[0] if linha else None

    except Exception as erro:
        print(f"Erro ao salvar recompensa: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def definir_status_recompensa(id_recompensa, ativo):
    """Ativa/desativa uma recompensa (soft delete — o histórico de resgates aponta para ela)."""
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            UPDATE fidelidade_recompensa
            SET ativo = %s, atualizado_em = NOW()
            WHERE id_recompensa = %s;
            """,
            (bool(ativo), id_recompensa)
        )
        conexao.commit()
        return cursor.rowcount > 0

    except Exception as erro:
        print(f"Erro ao alterar status da recompensa: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


def saldo_pontos(id_cliente):
    """Retorna o saldo de pontos do cliente (0 se ainda não tiver saldo)."""
    conexao = conectar()
    if not conexao:
        return 0

    try:
        cursor = conexao.cursor()
        cursor.execute(
            "SELECT pontos FROM fidelidade_saldo WHERE id_cliente = %s;",
            (id_cliente,)
        )
        linha = cursor.fetchone()
        return linha[0] if linha else 0

    except Exception as erro:
        print(f"Erro ao consultar saldo de pontos: {erro}")
        return 0

    finally:
        cursor.close()
        conexao.close()


def saldos_pontos(apenas_com_saldo=False):
    """
    {id_cliente: pontos} de todos os clientes, numa consulta só.

    Existe para matar o N+1 da tela: ela chamava saldo_pontos() DENTRO do laço
    de clientes, e a lista é remontada a cada tecla digitada na busca — com 300
    clientes eram 301 conexões ao banco por tecla. Mesmo bug já corrigido em
    Serviços (resumo_precos) e Estoque.
    Quem não tem linha de saldo simplesmente não aparece no dict (a tela usa
    .get(id, 0)).
    """
    conexao = conectar()
    if not conexao:
        return {}

    try:
        cursor = conexao.cursor()
        query = "SELECT id_cliente, pontos FROM fidelidade_saldo"
        if apenas_com_saldo:
            query += " WHERE pontos > 0"
        cursor.execute(query + ";")
        return {linha[0]: linha[1] for linha in cursor.fetchall()}

    except Exception as erro:
        print(f"Erro ao consultar saldos de pontos: {erro}")
        return {}

    finally:
        cursor.close()
        conexao.close()


def acumular_pontos(id_cliente, pontos, id_ordem=None, descricao=None):
    """
    Credita pontos ao cliente: soma ao saldo (criando-o se necessário) e grava
    o movimento de acúmulo. Tudo numa transação. Retorna o novo saldo, ou None.
    """
    if pontos is None or pontos <= 0:
        print("Pontos a acumular devem ser maiores que zero.")
        return None

    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()

        # UPSERT que SOMA (não sobrescreve): se o cliente ainda não tem linha de saldo,
        # cria com 'pontos'; se já tem, ACUMULA (saldo_atual + pontos). Note o
        # "fidelidade_saldo.pontos + EXCLUDED.pontos" — sem esse '+', o saldo seria
        # substituído em vez de somado (compare com definir_preco, que sobrescreve).
        cursor.execute(
            """
            INSERT INTO fidelidade_saldo (id_cliente, pontos)
            VALUES (%s, %s)
            ON CONFLICT (id_cliente)
            DO UPDATE SET pontos = fidelidade_saldo.pontos + EXCLUDED.pontos,
                          atualizado_em = NOW()
            RETURNING pontos;
            """,
            (id_cliente, pontos)
        )
        novo_saldo = cursor.fetchone()[0]

        cursor.execute(
            """
            INSERT INTO fidelidade_movimento (id_cliente, tipo, pontos, id_ordem, descricao)
            VALUES (%s, 'acumulo', %s, %s, %s);
            """,
            (id_cliente, pontos, id_ordem, descricao)
        )

        conexao.commit()
        return novo_saldo

    except Exception as erro:
        print(f"Erro ao acumular pontos: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def resgatar_pontos(id_cliente, pontos, descricao=None, id_ordem=None,
                    id_recompensa=None):
    """
    Resgata pontos do cliente (se houver saldo suficiente): subtrai do saldo e
    grava o movimento de resgate. Tudo numa transação.
    Retorna o novo saldo, ou None em erro/saldo insuficiente.

    id_ordem: em qual comanda o benefício foi usado. A coluna existia desde o
    início e só o acúmulo a preenchia — sem ela não dá para auditar depois "a
    lavagem grátis do dia 20 foi em qual carro?".
    """
    if pontos is None or pontos <= 0:
        print("Pontos a resgatar devem ser maiores que zero.")
        return None

    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()

        # Trava a linha do saldo e confere antes de debitar
        cursor.execute(
            "SELECT pontos FROM fidelidade_saldo WHERE id_cliente = %s FOR UPDATE;",
            (id_cliente,)
        )
        linha = cursor.fetchone()
        saldo_atual = linha[0] if linha else 0

        if saldo_atual < pontos:
            print(f"Saldo de pontos insuficiente: disponível {saldo_atual}, solicitado {pontos}.")
            conexao.rollback()
            return None

        cursor.execute(
            """
            UPDATE fidelidade_saldo
            SET pontos = pontos - %s, atualizado_em = NOW()
            WHERE id_cliente = %s
            RETURNING pontos;
            """,
            (pontos, id_cliente)
        )
        novo_saldo = cursor.fetchone()[0]

        cursor.execute(
            """
            INSERT INTO fidelidade_movimento (id_cliente, tipo, pontos, descricao,
                                              id_ordem, id_recompensa)
            VALUES (%s, 'resgate', %s, %s, %s, %s);
            """,
            (id_cliente, pontos, descricao, id_ordem, id_recompensa)
        )

        conexao.commit()
        return novo_saldo

    except Exception as erro:
        print(f"Erro ao resgatar pontos: {erro}")
        conexao.rollback()
        return None

    finally:
        cursor.close()
        conexao.close()


def resgatar_recompensa(id_cliente, id_recompensa, id_ordem=None):
    """
    Troca pontos por uma recompensa DO CATÁLOGO — este é o resgate "conforme a
    regra configurada" que a documentação pede. O preço em pontos vem da tabela,
    não da cabeça de quem está no balcão.

    Retorna dict (a tela precisa do motivo para explicar ao cliente):
      {'ok': bool, 'motivo': str, 'saldo': int, 'faltam': int, 'recompensa': str}
    """
    conexao = conectar()
    if not conexao:
        return {'ok': False, 'motivo': "Sem conexão com o banco.",
                'saldo': 0, 'faltam': 0, 'recompensa': ''}

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT nome, pontos_necessarios, ativo
            FROM fidelidade_recompensa
            WHERE id_recompensa = %s;
            """,
            (id_recompensa,)
        )
        linha = cursor.fetchone()

    except Exception as erro:
        print(f"Erro ao buscar recompensa: {erro}")
        return {'ok': False, 'motivo': "Erro ao consultar a recompensa.",
                'saldo': 0, 'faltam': 0, 'recompensa': ''}

    finally:
        cursor.close()
        conexao.close()

    if not linha:
        return {'ok': False, 'motivo': "Recompensa não encontrada.",
                'saldo': 0, 'faltam': 0, 'recompensa': ''}

    nome, custo, ativa = linha
    if not ativa:
        return {'ok': False, 'motivo': f"A recompensa '{nome}' está desativada.",
                'saldo': saldo_pontos(id_cliente), 'faltam': 0, 'recompensa': nome}

    saldo = saldo_pontos(id_cliente)
    if saldo < custo:
        faltam = custo - saldo
        return {'ok': False, 'recompensa': nome, 'saldo': saldo, 'faltam': faltam,
                'motivo': f"Faltam {faltam} ponto(s): '{nome}' custa {custo} e o "
                          f"cliente tem {saldo}."}

    # Reusa resgatar_pontos (abre a própria transação e confere o saldo de novo,
    # com FOR UPDATE — a conferência acima é só para a mensagem amigável).
    novo_saldo = resgatar_pontos(id_cliente, custo, descricao=nome,
                                 id_ordem=id_ordem, id_recompensa=id_recompensa)
    if novo_saldo is None:
        return {'ok': False, 'recompensa': nome, 'saldo': saldo, 'faltam': 0,
                'motivo': "Não foi possível registrar o resgate."}

    return {'ok': True, 'recompensa': nome, 'saldo': novo_saldo, 'faltam': 0,
            'motivo': f"'{nome}' resgatada por {custo} ponto(s). "
                      f"Saldo agora: {novo_saldo}."}


def acumular_por_comanda(id_ordem, pontos=None, descricao=None):
    """
    Credita os pontos de UMA comanda. É a ponte Comanda->Fidelidade: sem ela, o
    ponto só entrava se o atendente lembrasse de abrir a tela de Fidelidade e
    digitar — ou seja, o programa de pontos não funcionava.

    'pontos=None' (o normal) usa a regra do banco — hoje 1 ponto por lavação.
    Passar um número força outro valor (promoção pontual).

    Só credita se a comanda estiver FINALIZADA ou ENTREGUE (STATUS_PONTUAVEIS):
    comanda cancelada não vira ponto, e comanda ainda em execução vira ponto
    quando terminar. Antes não havia checagem nenhuma de status.
    Retorna o novo saldo, ou None se não creditou (já creditado, status errado,
    regra desligada ou erro).
    """
    if pontos is None:
        pontos, regra_ativa = regra_pontos()
        if not regra_ativa:
            print("Programa de pontos desligado na regra — nada creditado.")
            return None
    if not pontos or pontos <= 0:
        print("A regra atual não credita pontos (pontos por lavagem = 0).")
        return None

    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            "SELECT id_cliente, status FROM ordem_servico WHERE id_ordem = %s;",
            (id_ordem,)
        )
        linha = cursor.fetchone()
        if not linha:
            print(f"Comanda {id_ordem} não encontrada.")
            return None
        id_cliente, status = linha

        if status not in STATUS_PONTUAVEIS:
            print(f"Comanda {id_ordem} está '{status}' — só gera ponto quando "
                  f"finalizada ou entregue.")
            return None

        # Idempotência: se JÁ existe um movimento de 'acumulo' para esta comanda, não
        # credita de novo. Evita pontos em dobro se a função for chamada 2x pela mesma
        # comanda (ex.: reabrir a comanda para correção). O LIMIT 1 para na 1ª ocorrência.
        cursor.execute(
            """
            SELECT 1 FROM fidelidade_movimento
            WHERE id_ordem = %s AND tipo = 'acumulo' LIMIT 1;
            """,
            (id_ordem,)
        )
        if cursor.fetchone():
            print(f"Comanda {id_ordem} já gerou pontos — ignorando.")
            return None

    except Exception as erro:
        print(f"Erro ao preparar acúmulo por comanda: {erro}")
        return None

    finally:
        cursor.close()
        conexao.close()

    # Reusa acumular_pontos (abre sua própria conexão/transação)
    return acumular_pontos(id_cliente, pontos, id_ordem=id_ordem,
                           descricao=descricao or f"Pontos da comanda {id_ordem}")


def extrato_pontos(id_cliente, limite=50):
    """
    Lista o histórico de movimentos de pontos do cliente, do mais recente ao mais antigo.
    Tuplas: (id_movimento, tipo, pontos, id_ordem, descricao, data_mov, nome_recompensa).

    ⚠️ 'nome_recompensa' entra no FIM da tupla (índice 6) — a tela lê por posição.
    """
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()
        # Desempate por id_movimento: dois lançamentos no mesmo instante (o acúmulo
        # automático da comanda e um manual, por exemplo) saíam em ordem indefinida.
        cursor.execute(
            """
            SELECT m.id_movimento, m.tipo, m.pontos, m.id_ordem, m.descricao,
                   m.data_mov, r.nome
            FROM fidelidade_movimento m
            LEFT JOIN fidelidade_recompensa r ON r.id_recompensa = m.id_recompensa
            WHERE m.id_cliente = %s
            ORDER BY m.data_mov DESC, m.id_movimento DESC
            LIMIT %s;
            """,
            (id_cliente, limite)
        )
        return cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao buscar extrato de pontos: {erro}")
        return []

    finally:
        cursor.close()
        conexao.close()


# ================================================================
# TESTE RÁPIDO (rode este arquivo diretamente para testar)
# ================================================================
if __name__ == "__main__":
    cliente = 1

    pontos_lavagem, ligado = regra_pontos()
    print(f"Regra atual: {pontos_lavagem} ponto(s) por lavagem "
          f"({'ativa' if ligado else 'desligada'})")
    print("Catálogo de trocas:")
    for r in recompensas():
        print(f"   {r[1]} — {r[2]} pontos" + (f" (serviço: {r[4]})" if r[4] else ""))

    print(f"\nSaldo inicial do cliente {cliente}:", saldo_pontos(cliente))

    print("\nAcumulando 10 pontos...")
    print("  novo saldo:", acumular_pontos(cliente, 10, descricao="Bônus inicial"))

    print("\nAcumulando pela comanda 1 (1 ponto)...")
    print("  novo saldo:", acumular_por_comanda(1, pontos=1))

    print("\nTentando de novo pela comanda 1 (deve ignorar):")
    print("  ->", acumular_por_comanda(1, pontos=1))

    print("\nResgatando 5 pontos...")
    print("  novo saldo:", resgatar_pontos(cliente, 5, descricao="Lavagem grátis"))

    print("\nResgatando 999 pontos (deve falhar):")
    print("  ->", resgatar_pontos(cliente, 999))

    print("\nExtrato de pontos:")
    for m in extrato_pontos(cliente):
        print("  ", m)
