"""
Backup automático do banco de dados PostgreSQL.
Sistema de gestão para lava-jato.
Autor: Lucas Ribeiro Nepomuceno de Almeida (RINEAL Analytics).

O QUE ESTE SCRIPT FAZ
---------------------
Chama o `pg_dump` (programa que vem junto com o PostgreSQL) para gravar num
arquivo único tudo o que é preciso para recriar o banco do zero: tabelas, dados,
índices e permissões. É uma FOTO COMPLETA do banco naquele instante.

Ele SÓ LÊ do banco — não altera, não apaga e não trava nada lá dentro. Fora do
banco ele escreve em dois lugares: cria o arquivo novo em `backups/` e apaga os
backups antigos gerados por ele mesmo (só os que casam com o padrão de nome).

POR QUE EM PYTHON, E NÃO UM .BAT
--------------------------------
Para reaproveitar o `DB_config` do `conexao.py`: as credenciais continuam vindo
só do `.env`. Se a senha do banco mudar, troca-se no `.env` e o backup acompanha
sozinho — nenhuma credencial é escrita aqui dentro.

COMO USAR
---------
    python backup_banco.py

Para agendar no Windows (roda todo dia às 20h, sem ninguém lembrar), veja o
bloco COMO AGENDAR no fim deste arquivo.

COMO RESTAURAR (o dia em que isto importa)
------------------------------------------
O arquivo sai no formato "custom" do PostgreSQL (comprimido), que se restaura
com `pg_restore` — NÃO com `psql`. Para jogar num banco vazio:

    createdb  -h 192.168.1.18 -U nepomuceno restauracao_teste
    pg_restore -h 192.168.1.18 -U nepomuceno -d restauracao_teste --no-owner ARQUIVO.dump

⚠️ Restaure SEMPRE num banco novo primeiro (como no exemplo acima). Restaurar
por cima do banco em produção é como testar o freio descendo a serra.
"""

import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from glob import glob

# As credenciais vêm do .env, exatamente como no resto do projeto.
from conexao import DB_config

# ================================================================
# CONFIGURAÇÃO
# ================================================================

# Pasta onde os backups são gravados (fica ao lado deste script e é ignorada
# pelo git — são dados reais de clientes, não podem ir para o GitHub).
PASTA_BACKUP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")

# Por quantos dias guardar os backups. Backup mais velho que isso é apagado.
RETENCAO_DIAS = 14

# Rede de segurança da limpeza: nunca deixar menos que isto de backups, mesmo
# que todos estejam vencidos. Sem esta guarda, um relógio errado ou um dia de
# testes poderia varrer o histórico inteiro de uma vez.
MINIMO_MANTER = 5

# Tempo máximo que o pg_dump pode demorar (segundos). Sem isto, um servidor
# fora do ar deixaria a tarefa agendada pendurada para sempre.
TIMEOUT_SEGUNDOS = 600

# Padrão do nome do arquivo. A limpeza só apaga arquivos que casam com ele —
# assim nada que o script não tenha criado corre risco.
PREFIXO = "lavajato_"
SUFIXO = ".dump"
PADRAO_DATA = re.compile(r"^lavajato_(\d{4}-\d{2}-\d{2})_\d{4}\.dump$")


# ================================================================
# LOG
# ================================================================

def texto_seguro(texto):
    """
    Devolve o texto numa versão que o console atual consegue imprimir.

    ⚠️ ISTO NÃO É FRESCURA — sem esta rede o script morre justamente na hora de
    registrar uma FALHA. O console do Windows costuma estar em cp1252, que não
    aceita qualquer caractere; e a mensagem de erro do `pg_dump` chega com bytes
    que viraram `\\ufffd` (o "caractere de substituição") ao serem lidos como
    UTF-8. Resultado sem a proteção: `print` levanta `UnicodeEncodeError`, o
    backup quebra com traceback e o **motivo da falha nunca chega ao log** — no
    dia em que o servidor cai, o log fica mudo.

    É o primo do `lc_messages=C` do `conexao.py`, na direção contrária: lá o
    problema era LER uma mensagem do Postgres, aqui é ESCREVER.
    """
    codec = getattr(sys.stdout, "encoding", None) or "ascii"
    return texto.encode(codec, "replace").decode(codec, "replace")


def registrar(mensagem, tambem_no_arquivo=True):
    """
    Escreve a mensagem na tela e no arquivo backups/backup.log.

    O log existe para você descobrir que o backup parou de funcionar ANTES de
    precisar dele. Tarefa agendada roda calada: sem log, a primeira notícia de
    que estava quebrado há três meses chega no pior dia possível.
    """
    carimbo = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    linha = f"[{carimbo}] {mensagem}"
    try:
        print(linha)
    except UnicodeEncodeError:
        print(texto_seguro(linha))

    if not tambem_no_arquivo:
        return
    try:
        os.makedirs(PASTA_BACKUP, exist_ok=True)
        caminho = os.path.join(PASTA_BACKUP, "backup.log")
        with open(caminho, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except OSError as erro:
        # Falhar ao escrever o log não pode derrubar o backup em si.
        print(f"[aviso] não foi possível escrever no log: {erro}")


# ================================================================
# LOCALIZAR O pg_dump
# ================================================================

def achar_executavel(nome):
    """
    Devolve o caminho do `pg_dump`/`pg_restore` a usar, ou None se não achar.

    ⚠️ REGRA QUE MORDE: o pg_dump precisa ser da MESMA versão maior do servidor
    ou mais novo. O servidor do TrueNAS é PostgreSQL 18; chamar o pg_dump 16
    (que também está instalado nesta máquina) falha com "server version
    mismatch". Por isso a busca varre as instalações e escolhe a MAIOR versão,
    em vez de confiar no que estiver no PATH.

    Para apontar manualmente, defina a variável de ambiente PG_BIN com a pasta
    bin do PostgreSQL desejado (ela também pode ir no .env).
    """
    # 1) Caminho explícito informado pelo usuário (via .env ou ambiente).
    pasta_bin = os.environ.get("PG_BIN")
    if pasta_bin:
        candidato = os.path.join(pasta_bin, nome + (".exe" if os.name == "nt" else ""))
        if os.path.isfile(candidato):
            return candidato
        registrar(f"[aviso] PG_BIN aponta para '{pasta_bin}', mas {nome} não está lá.")

    # 2) Instalações padrão do PostgreSQL no Windows — pega a maior versão.
    if os.name == "nt":
        encontrados = []
        for padrao in (r"C:\Program Files\PostgreSQL\*\bin",
                       r"C:\Program Files (x86)\PostgreSQL\*\bin"):
            for pasta in glob(padrao):
                caminho = os.path.join(pasta, nome + ".exe")
                if os.path.isfile(caminho):
                    # O nome da pasta é a versão maior ("16", "18"...).
                    versao = os.path.basename(os.path.dirname(pasta))
                    encontrados.append((int(versao) if versao.isdigit() else 0, caminho))
        if encontrados:
            encontrados.sort(reverse=True)          # maior versão primeiro
            return encontrados[0][1]

    # 3) Último recurso: o que estiver no PATH (caso Linux/macOS).
    from shutil import which
    return which(nome)


# ================================================================
# BACKUP
# ================================================================

def gerar_backup():
    """
    Roda o pg_dump e devolve o caminho do arquivo gerado, ou None se falhar.
    """
    pg_dump = achar_executavel("pg_dump")
    if not pg_dump:
        registrar("ERRO: pg_dump não encontrado. Instale o PostgreSQL client ou "
                  "defina PG_BIN no .env com a pasta bin correta.")
        return None

    os.makedirs(PASTA_BACKUP, exist_ok=True)
    nome = PREFIXO + datetime.now().strftime("%Y-%m-%d_%H%M") + SUFIXO
    destino = os.path.join(PASTA_BACKUP, nome)

    comando = [
        pg_dump,
        "--host", str(DB_config["host"]),
        "--port", str(DB_config["port"]),
        "--username", str(DB_config["user"]),
        "--dbname", str(DB_config["database"]),
        "--format=custom",   # comprimido e permite restaurar tabelas isoladas
        "--no-password",     # falha na hora em vez de travar pedindo senha
        "--file", destino,
    ]

    # A senha vai por variável de ambiente, NUNCA na linha de comando: argumentos
    # de processo são visíveis para qualquer usuário da máquina (Gerenciador de
    # Tarefas, `ps`). Esta cópia do ambiente vale só para o processo filho.
    ambiente = os.environ.copy()
    ambiente["PGPASSWORD"] = str(DB_config["password"])

    registrar(f"Iniciando backup de '{DB_config['database']}' em "
              f"{DB_config['host']}:{DB_config['port']}")
    registrar(f"Usando: {pg_dump}")

    try:
        resultado = subprocess.run(
            comando, env=ambiente, capture_output=True, text=True,
            timeout=TIMEOUT_SEGUNDOS, encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        registrar(f"ERRO: o pg_dump passou de {TIMEOUT_SEGUNDOS}s e foi cancelado. "
                  "O servidor está no ar?")
        return None
    except OSError as erro:
        registrar(f"ERRO ao executar o pg_dump: {erro}")
        return None

    if resultado.returncode != 0:
        registrar(f"ERRO: pg_dump terminou com código {resultado.returncode}.")
        if resultado.stderr:
            registrar("Mensagem do PostgreSQL: " + resultado.stderr.strip())
        # Dump interrompido costuma deixar um arquivo pela metade: melhor sumir
        # com ele do que guardar um backup que parece bom e não é.
        if os.path.exists(destino):
            os.remove(destino)
        return None

    tamanho_mb = os.path.getsize(destino) / (1024 * 1024)
    registrar(f"Backup gravado: {nome} ({tamanho_mb:.2f} MB)")
    return destino


# ================================================================
# CONFERÊNCIA
# ================================================================

def conferir_backup(caminho):
    """
    Confere se o arquivo gerado é legível, e devolve True/False.

    Um backup que nunca foi testado não é backup — é esperança. Esta checagem
    usa `pg_restore --list`, que apesar do nome NÃO restaura nada: apenas abre o
    arquivo e lista o que existe dentro. Se o dump saiu truncado ou corrompido,
    é aqui que se descobre — hoje, e não no dia do desastre.
    """
    pg_restore = achar_executavel("pg_restore")
    if not pg_restore:
        registrar("[aviso] pg_restore não encontrado; backup NÃO foi conferido.")
        return True   # o dump em si deu certo; só não deu para validar

    try:
        resultado = subprocess.run(
            [pg_restore, "--list", caminho], capture_output=True, text=True,
            timeout=TIMEOUT_SEGUNDOS, encoding="utf-8", errors="replace",
        )
    except (subprocess.TimeoutExpired, OSError) as erro:
        registrar(f"[aviso] não foi possível conferir o backup: {erro}")
        return True

    if resultado.returncode != 0:
        registrar("ERRO: o arquivo de backup está corrompido ou ilegível!")
        if resultado.stderr:
            registrar("Mensagem do PostgreSQL: " + resultado.stderr.strip())
        # Renomeia em vez de apagar: o arquivo ruim fica para diagnóstico, e com
        # outro nome ele não é confundido com um backup bom nem pela limpeza.
        try:
            os.rename(caminho, caminho + ".INVALIDO")
            registrar(f"Arquivo marcado como {os.path.basename(caminho)}.INVALIDO")
        except OSError:
            pass
        return False

    # Cada linha da listagem é um objeto do banco (tabela, índice, sequência...).
    objetos = [l for l in resultado.stdout.splitlines()
               if l.strip() and not l.startswith(";")]
    registrar(f"Conferido: arquivo íntegro, {len(objetos)} objetos no dump.")
    return True


# ================================================================
# LIMPEZA DOS ANTIGOS
# ================================================================

def limpar_antigos():
    """
    Apaga backups mais velhos que RETENCAO_DIAS, respeitando o MINIMO_MANTER.

    Só toca em arquivos cujo nome casa com o padrão do script (PADRAO_DATA);
    qualquer outra coisa que esteja na pasta é ignorada. A data sai do NOME do
    arquivo, não da data de modificação — copiar a pasta para outro disco muda a
    data de modificação e faria a limpeza errar a conta.
    """
    arquivos = []
    for caminho in glob(os.path.join(PASTA_BACKUP, PREFIXO + "*" + SUFIXO)):
        casou = PADRAO_DATA.match(os.path.basename(caminho))
        if not casou:
            continue
        try:
            data = datetime.strptime(casou.group(1), "%Y-%m-%d")
        except ValueError:
            continue
        arquivos.append((data, caminho))

    if not arquivos:
        return

    arquivos.sort(reverse=True)            # mais novo primeiro
    corte = datetime.now() - timedelta(days=RETENCAO_DIAS)

    # A fatia [MINIMO_MANTER:] protege os N mais novos, aconteça o que acontecer.
    apagados = 0
    for data, caminho in arquivos[MINIMO_MANTER:]:
        if data >= corte:
            continue
        try:
            os.remove(caminho)
            apagados += 1
        except OSError as erro:
            registrar(f"[aviso] não consegui apagar {os.path.basename(caminho)}: {erro}")

    if apagados:
        registrar(f"Limpeza: {apagados} backup(s) com mais de {RETENCAO_DIAS} dias "
                  f"removido(s). Restam {len(arquivos) - apagados}.")
    else:
        registrar(f"Limpeza: nada a remover ({len(arquivos)} backup(s) na pasta).")


# ================================================================
# PRINCIPAL
# ================================================================

def main():
    """
    Faz o backup, confere e limpa os antigos.
    Devolve 0 se deu tudo certo e 1 se falhou — o Agendador de Tarefas do
    Windows usa esse código para saber que a tarefa falhou.
    """
    registrar("=" * 60, tambem_no_arquivo=False)

    if not DB_config.get("password"):
        registrar("ERRO: senha do banco não encontrada. Confira o DB_PASSWORD no .env.")
        return 1

    destino = gerar_backup()
    if not destino:
        registrar("BACKUP FALHOU.")
        return 1

    if not conferir_backup(destino):
        registrar("BACKUP FALHOU na conferência.")
        return 1

    limpar_antigos()
    registrar("Backup concluído com sucesso.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ================================================================
# COMO AGENDAR NO WINDOWS (uma vez só)
# ================================================================
#
# Abra o PowerShell COMO ADMINISTRADOR, na pasta do projeto, e rode:
#
#   schtasks /create /tn "Backup Lavajato" /tr "\"C:\caminho\python.exe\" \"C:\Users\Usuario\Documents\projeto_daniel\backup_banco.py\"" /sc daily /st 20:00
#
# Trocando C:\caminho\python.exe pelo resultado de:  (Get-Command python).Source
#
# Depois confira em "Agendador de Tarefas" > Biblioteca. Para testar sem esperar
# o horário:  schtasks /run /tn "Backup Lavajato"
#
# 20h é uma boa hora: depois do movimento do dia e antes de desligar a máquina.
#
# ⚠️ O BACKUP AINDA ESTÁ NO MESMO PRÉDIO. Se o disco do TrueNAS e este PC se
# perderem juntos (raio, furto, incêndio), os dois somem. Quando der, copie a
# pasta `backups/` também para um pendrive ou nuvem — a regra clássica é ter 3
# cópias, em 2 mídias diferentes, com 1 fora do local.
