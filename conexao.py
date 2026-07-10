"""
Modulo de conexao com o banco de dados PostgreSQL.
Sistema de gestão para lava-jato.
Autor: Lucas Ribeiro Nepomuceno de Almeida (RINEAL Analytics).

As credenciais são lidas de variáveis de ambiente (arquivo .env, que NÃO vai
para o git). Veja .env.example para os nomes esperados.
"""

import os
import psycopg2
from psycopg2 import OperationalError


def _carregar_env():
    """
    Carregador mínimo de .env (sem dependências externas).
    Lê o arquivo .env ao lado deste script e popula os.environ com as chaves que
    ainda não estiverem definidas. Linhas em branco e começadas por # são ignoradas.
    """
    caminho = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(caminho):
        return
    with open(caminho, "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, valor = linha.split("=", 1)
            os.environ.setdefault(chave.strip(), valor.strip())


_carregar_env()

# ================================================================
# CONFIGURAÇÃO DA CONEXÃO (lida do ambiente / .env)
# ================================================================

# Os .get(chave, padrao) garantem valores default se o .env não existir; a senha
# é o único campo sem default seguro (vazio) — precisa vir do .env.
DB_config = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', '5432')),
    'database': os.environ.get('DB_NAME', 'lavajato_db'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'client_encoding': 'utf8',
    # Força as mensagens de erro do Postgres em inglês (locale C). No Windows, sem
    # isso o psycopg2 pode quebrar com UnicodeDecodeError ao ler um erro em português
    # (Win-1252). '-c lc_messages=C' é passado ao servidor via libpq no connect.
    'options': '-c lc_messages=C',
}


def conectar():
    """
    Abre e retorna uma conexão com o banco lavajato_db.
    Use sempre dentro de um try/except ao chamar esta função.
    """
    try:
        conexao = psycopg2.connect(**DB_config)
        return conexao
    except OperationalError as erro:
        print(f"Erro ao conectar no banco de dados: {erro}")
        return None


def testar_conexao():
    """
    Testa se a conexão com o banco está funcionando.
    Útil para rodar uma vez e confirmar que tudo está certo.
    """
    conexao = conectar()
    if conexao:
        print("Conexão com lavajato_db estabelecida com sucesso!")
        conexao.close()
        return True
    else:
        print("Falha ao conectar com lavajato_db.")
        return False


# Permite testar este arquivo isoladamente: python conexao.py
if __name__ == "__main__":
    testar_conexao()
