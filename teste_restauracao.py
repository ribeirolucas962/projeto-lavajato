"""
Teste de restauração do backup — prova que o dump volta mesmo.
Sistema de gestão para lava-jato.
Autor: Lucas Ribeiro Nepomuceno de Almeida (RINEAL Analytics).

POR QUE ISTO EXISTE
-------------------
O `backup_banco.py` já confere o arquivo com `pg_restore --list`, mas isso só prova
que o arquivo é LEGÍVEL. Legível não é o mesmo que restaurável com os dados certos.
Este script fecha essa distância: restaura o dump de verdade num banco descartável e
compara a contagem de linhas de cada tabela com o banco real. Se as 25 tabelas
baterem, o backup presta.

Backup que nunca foi restaurado é esperança, não backup. Vale rodar isto de vez em
quando — e sobretudo depois de mudar de servidor ou de versão do PostgreSQL.

O QUE ELE ENCOSTA NO SERVIDOR
-----------------------------
O banco real é apenas LIDO (só COUNT). A única escrita é criar e apagar o banco
temporário `restauracao_teste`, que é derrubado no `finally` mesmo se algo falhar
no meio. Antes de qualquer coisa o script confere que o nome do banco de teste é
diferente do nome do banco real e aborta se forem iguais.

COMO USAR
---------
    python teste_restauracao.py backups\\lavajato_2026-07-31_2228.dump

Sem argumento, ele pega o backup mais recente da pasta `backups/`.
"""

import os
import subprocess
import sys
from glob import glob

import psycopg2

from conexao import DB_config
from backup_banco import achar_executavel, texto_seguro, PASTA_BACKUP, PREFIXO, SUFIXO

# Nome do banco descartável criado para o teste.
BANCO_TESTE = "restauracao_teste"
BANCO_REAL = DB_config["database"]


def conectar_em(nome_banco, autocommit=False):
    """Abre conexão no mesmo servidor, trocando só o nome do banco."""
    cfg = dict(DB_config)
    cfg["database"] = nome_banco
    con = psycopg2.connect(**cfg)
    con.autocommit = autocommit
    return con


def contar_linhas(nome_banco):
    """Devolve {tabela: nº de linhas} de todas as tabelas do schema public."""
    con = conectar_em(nome_banco)
    try:
        cur = con.cursor()
        cur.execute("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' ORDER BY tablename
        """)
        tabelas = [linha[0] for linha in cur.fetchall()]

        contagens = {}
        for tabela in tabelas:
            # O nome vem do catálogo do próprio Postgres, não do usuário — mas vai
            # entre aspas de identificador por higiene.
            cur.execute(f'SELECT COUNT(*) FROM public."{tabela}"')
            contagens[tabela] = cur.fetchone()[0]
        cur.close()
        return contagens
    finally:
        con.close()


def backup_mais_recente():
    """Caminho do .dump mais novo da pasta backups/, ou None se não houver."""
    arquivos = glob(os.path.join(PASTA_BACKUP, PREFIXO + "*" + SUFIXO))
    return max(arquivos, key=os.path.getmtime) if arquivos else None


def apagar_banco_teste():
    """Derruba o banco temporário. Chamado sempre, mesmo se o teste falhar."""
    admin = conectar_em("postgres", autocommit=True)
    try:
        cur = admin.cursor()
        # Sem derrubar as conexões penduradas, o DROP DATABASE trava esperando.
        cur.execute("""
            SELECT pg_terminate_backend(pid) FROM pg_stat_activity
            WHERE datname = %s AND pid <> pg_backend_pid()
        """, (BANCO_TESTE,))
        cur.execute(f'DROP DATABASE IF EXISTS "{BANCO_TESTE}"')
        cur.close()
    finally:
        admin.close()


def main():
    # Trava de segurança: se os nomes coincidirem, o DROP mataria o banco real.
    if BANCO_TESTE.lower() == BANCO_REAL.lower():
        print(f"ABORTADO: o banco de teste tem o mesmo nome do real ({BANCO_REAL}).")
        return 1

    dump = sys.argv[1] if len(sys.argv) > 1 else backup_mais_recente()
    if not dump or not os.path.isfile(dump):
        print("Nenhum backup encontrado. Rode antes: python backup_banco.py")
        return 1

    if not achar_executavel("pg_restore"):
        print("ERRO: pg_restore não encontrado. Defina PG_BIN no .env.")
        return 1

    print(f"Banco real: {BANCO_REAL} em {DB_config['host']}")
    print(f"Dump testado: {os.path.basename(dump)}\n")

    print("[1/5] Contando as linhas do banco real...")
    real = contar_linhas(BANCO_REAL)
    print(f"      {len(real)} tabelas, {sum(real.values())} linhas.\n")

    print(f"[2/5] Criando o banco temporario '{BANCO_TESTE}'...")
    admin = conectar_em("postgres", autocommit=True)
    try:
        cur = admin.cursor()
        cur.execute(f'DROP DATABASE IF EXISTS "{BANCO_TESTE}"')
        cur.execute(f'CREATE DATABASE "{BANCO_TESTE}"')
        cur.close()
    finally:
        admin.close()
    print("      criado.\n")

    try:
        print("[3/5] Restaurando o dump...")
        ambiente = os.environ.copy()
        # Mesma regra do backup: senha por variável de ambiente, nunca no comando.
        ambiente["PGPASSWORD"] = str(DB_config["password"])
        resultado = subprocess.run(
            [achar_executavel("pg_restore"),
             "--host", str(DB_config["host"]),
             "--port", str(DB_config["port"]),
             "--username", str(DB_config["user"]),
             "--dbname", BANCO_TESTE,
             "--no-owner", "--no-password", dump],
            env=ambiente, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=600,
        )
        if resultado.returncode != 0:
            print(f"      pg_restore terminou com codigo {resultado.returncode}")
            if resultado.stderr:
                # texto_seguro: a mensagem do pg_restore pode trazer caracteres
                # que o console do Windows nao imprime (ver backup_banco.py).
                print("      " + texto_seguro(resultado.stderr.strip()[:2000]))
        else:
            print("      restaurado sem erros.\n")

        print("[4/5] Comparando com o banco real...")
        restaurado = contar_linhas(BANCO_TESTE)

        divergentes = []
        for tabela in sorted(set(real) | set(restaurado)):
            a, b = real.get(tabela), restaurado.get(tabela)
            if a != b:
                divergentes.append(tabela)
            print(f"      {'OK ' if a == b else '!! '}{tabela:<28} "
                  f"real={a!s:>5}  restaurado={b!s:>5}")

        print()
        if divergentes:
            print(f"RESULTADO: {len(divergentes)} tabela(s) DIVERGENTE(S): "
                  + ", ".join(divergentes))
            return 1
        print(f"RESULTADO: todas as {len(real)} tabelas bateram "
              f"({sum(real.values())} linhas). O backup presta.")
        return 0

    finally:
        print(f"\n[5/5] Apagando o banco temporario '{BANCO_TESTE}'...")
        apagar_banco_teste()
        print("      apagado. Servidor de volta ao estado original.")


if __name__ == "__main__":
    sys.exit(main())
