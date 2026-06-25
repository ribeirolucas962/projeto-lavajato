"""
Módulo de Planos e Assinaturas
Sistema: Lava-Jato
Autor: RINEAL Analytics

Pacotes mensais de serviços (plano + plano_servico) e a assinatura de clientes
(assinatura + assinatura_uso). Controla o uso mensal, bloqueando quando o cliente
atinge o limite de um serviço no mês vigente.
"""

from conexao import conectar


# ----------------------------------------------------------------
# CRUD de plano
# ----------------------------------------------------------------

def criar_plano(nome, valor_mensalidade):
    """Cria um plano. Retorna o id_plano, ou None em caso de erro."""
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            INSERT INTO plano (nome, valor_mensalidade)
            VALUES (%s, %s)
            RETURNING id_plano;
            """,
            (nome, valor_mensalidade)
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


def editar_plano(id_plano, nome=None, valor_mensalidade=None):
    """Atualiza nome/valor de um plano. Apenas os campos informados."""
    conexao = conectar()
    if not conexao:
        return False

    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            UPDATE plano
            SET nome = COALESCE(%s, nome),
                valor_mensalidade = COALESCE(%s, valor_mensalidade),
                atualizado_em = NOW()
            WHERE id_plano = %s;
            """,
            (nome, valor_mensalidade, id_plano)
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

def assinar(id_cliente, id_plano, data_inicio=None, data_vencimento=None,
            data_renovacao=None):
    """
    Vincula um cliente a um plano. data_inicio assume hoje se None.
    Retorna o id_assinatura, ou None em caso de erro.
    """
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
    """Lista assinaturas, com nome do cliente e do plano."""
    conexao = conectar()
    if not conexao:
        return []

    try:
        cursor = conexao.cursor()
        query = """
            SELECT a.id_assinatura, c.nome, p.nome, a.data_inicio,
                   a.data_vencimento, a.data_renovacao, a.ativo
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
    Registra o uso de um serviço pela assinatura, respeitando o limite mensal:
      - o serviço precisa fazer parte do plano da assinatura;
      - bloqueia se o cliente já usou a cota do serviço no mês vigente.
    Retorna o id_uso criado, ou None se bloqueado/erro.
    """
    conexao = conectar()
    if not conexao:
        return None

    try:
        cursor = conexao.cursor()

        # Assinatura ativa + plano
        cursor.execute(
            "SELECT id_plano, ativo FROM assinatura WHERE id_assinatura = %s;",
            (id_assinatura,)
        )
        linha = cursor.fetchone()
        if not linha:
            print(f"Assinatura {id_assinatura} não encontrada.")
            return None
        id_plano, ativa = linha
        if not ativa:
            print(f"Assinatura {id_assinatura} está inativa.")
            return None

        # O serviço faz parte do plano? Qual a cota mensal?
        cursor.execute(
            "SELECT quantidade_mes FROM plano_servico WHERE id_plano = %s AND id_servico = %s;",
            (id_plano, id_servico)
        )
        cota = cursor.fetchone()
        if not cota:
            print(f"Serviço {id_servico} não faz parte do plano {id_plano}.")
            return None
        quantidade_mes = cota[0]

        # Quanto já usou neste mês
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

        if usado >= quantidade_mes:
            print(f"Limite mensal atingido para o serviço {id_servico}: "
                  f"{usado}/{quantidade_mes} usados.")
            return None

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
        return id_uso

    except Exception as erro:
        print(f"Erro ao registrar uso da assinatura: {erro}")
        conexao.rollback()
        return None

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
            print("\nRegistrando usos do serviço 1 (cota = 2):")
            print("  uso 1 ->", registrar_uso(aid, 1))   # ok
            print("  uso 2 ->", registrar_uso(aid, 1))   # ok
            print("  uso 3 ->", registrar_uso(aid, 1))   # bloqueado (limite)

            print("\nSaldo de serviços no mês:")
            for s in saldo_servicos_mes(aid):
                print("  ", s)
