"""
Cria as tabelas do banco lavajato_db a partir do arquivo criar_tabelas.sql.
Sistema de gestão para lava-jato.
Autor: RINEAL Analytics.

Uso:  python criar_tabelas.py
"""

import os
from conexao import conectar

SQL_FILE = os.path.join(os.path.dirname(__file__), "criar_tabelas.sql")


def criar_tabelas():
    """Lê criar_tabelas.sql e executa no banco. Retorna True se deu certo."""
    conexao = conectar()
    if not conexao:
        return False

    try:
        # Lê o script inteiro e executa de uma vez. O criar_tabelas.sql é idempotente
        # (CREATE TABLE IF NOT EXISTS / ON CONFLICT), então rodar de novo não quebra
        # nem duplica dados — pode reexecutar à vontade para recriar o schema.
        with open(SQL_FILE, "r", encoding="utf-8") as f:
            sql = f.read()

        cursor = conexao.cursor()
        cursor.execute(sql)
        conexao.commit()
        print("Tabelas criadas/atualizadas com sucesso!")
        return True

    except Exception as erro:
        print(f"Erro ao criar tabelas: {erro}")
        conexao.rollback()
        return False

    finally:
        cursor.close()
        conexao.close()


if __name__ == "__main__":
    criar_tabelas()
