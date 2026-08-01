"""
Teste do sistema de backup — foco nos CAMINHOS DE FALHA.
Sistema de gestão para lava-jato.
Autor: Lucas Ribeiro Nepomuceno de Almeida (RINEAL Analytics).

POR QUE ESTE TESTE EXISTE
-------------------------
O `teste_restauracao.py` prova o caminho feliz: o dump gera e volta com os dados
certos. Mas um backup só tem valor no dia em que algo deu errado — e é justamente
esse comportamento que ninguém testa. As perguntas aqui são outras:

  - Se o dump sair corrompido, o script detecta ou guarda um arquivo inútil
    achando que está tudo bem?
  - Se a senha do banco mudar, ele falha na hora ou fica pendurado esperando
    alguém digitar? (numa tarefa agendada isso trava para sempre)
  - A limpeza dos 14 dias apaga o que deve — e só o que é dela?
  - Os códigos de saída estão certos? O Agendador do Windows só sabe que a
    tarefa falhou por causa deles.

Foi este teste que achou o bug do `UnicodeEncodeError` no `registrar()`
(ver seção G e o `texto_seguro()` no `backup_banco.py`): o script morria com
traceback ao imprimir a mensagem de erro do `pg_dump`, e o motivo da falha nunca
chegava ao log — exatamente no dia em que o servidor caía.

SEGURANÇA
---------
A `PASTA_BACKUP` é desviada para um diretório temporário, então os backups reais
nunca são tocados. O banco é apenas LIDO, e só em dois checks (o do dump íntegro
e o do backup bem-sucedido); o resto nem chega a conectar.

COMO USAR
---------
    python testar_backup.py

Sai com código 0 se tudo passar, 1 se algo falhar.
"""

import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta

import backup_banco as bb
import teste_restauracao as tr

# Guardado ANTES de desviar a pasta, para achar um dump real de referência.
PASTA_REAL = bb.PASTA_BACKUP

CHECKS = []


def check(nome, condicao, detalhe=""):
    CHECKS.append((nome, bool(condicao), detalhe))
    print(f"  {'OK ' if condicao else '!! '}{nome}"
          + (f"  [{detalhe}]" if detalhe and not condicao else ""))


def nome_dump(dias_atras, hora="1200"):
    data = (datetime.now() - timedelta(days=dias_atras)).strftime("%Y-%m-%d")
    return f"lavajato_{data}_{hora}.dump"


def criar(pasta, nome, conteudo=b"x"):
    caminho = os.path.join(pasta, nome)
    with open(caminho, "wb") as f:
        f.write(conteudo)
    return caminho


def arquivos_em(pasta):
    return sorted(n for n in os.listdir(pasta) if n != "backup.log")


def e_backup_valido(nome):
    """Casa o padrão do script E tem data que existe de verdade."""
    casou = bb.PADRAO_DATA.match(nome)
    if not casou:
        return False
    try:
        datetime.strptime(casou.group(1), "%Y-%m-%d")
        return True
    except ValueError:
        return False


# ============================================================================
print("\n=== A. Escolha do pg_dump (a regra que morde: versao do servidor) ===")

exe = bb.achar_executavel("pg_dump")
check("acha o pg_dump", exe is not None)
# Esta maquina tem PostgreSQL 13, 16, 17 e 18. O servidor e 18: pegar o 16
# falharia com "server version mismatch" — e so no dia do backup.
check("escolhe a MAIOR versao instalada, nao a do PATH",
      exe and os.sep + "18" + os.sep in exe, f"escolheu: {exe}")

os.environ["PG_BIN"] = r"C:\pasta\que\nao\existe"
check("PG_BIN invalido avisa e cai no criterio seguinte, sem quebrar",
      bb.achar_executavel("pg_dump") is not None)
os.environ.pop("PG_BIN", None)

check("devolve None para executavel inexistente",
      bb.achar_executavel("programa_que_nao_existe_xyz") is None)


# ============================================================================
print("\n=== B. Limpeza dos antigos (a unica parte que APAGA coisas) ===")

pasta = tempfile.mkdtemp(prefix="teste_backup_")
bb.PASTA_BACKUP = pasta          # desvia: backups reais intocados

# B1: muitos vencidos -> o piso protege o historico
for i in range(20):
    criar(pasta, nome_dump(30 + i, hora=f"{1000 + i}"))
bb.limpar_antigos()
restantes = arquivos_em(pasta)
check(f"20 vencidos -> mantem o piso de {bb.MINIMO_MANTER}",
      len(restantes) == bb.MINIMO_MANTER, f"sobraram {len(restantes)}")
check("e os mantidos sao os 5 MAIS NOVOS",
      restantes == sorted(nome_dump(30 + i, hora=f"{1000 + i}") for i in range(5)),
      f"{restantes}")

# B2: abaixo do piso, nao apaga nem os vencidos
shutil.rmtree(pasta); os.makedirs(pasta)
for i in range(3):
    criar(pasta, nome_dump(100 + i, hora=f"{1000 + i}"))
bb.limpar_antigos()
check("3 vencidos (abaixo do piso) -> nao apaga nenhum",
      len(arquivos_em(pasta)) == 3)

# B3: recente nunca e apagado, mesmo passando do piso
shutil.rmtree(pasta); os.makedirs(pasta)
for i in range(10):
    criar(pasta, nome_dump(i, hora=f"{1000 + i}"))
bb.limpar_antigos()
check("10 recentes (dentro dos 14 dias) -> nenhum apagado",
      len(arquivos_em(pasta)) == 10)

# B4: mistura
shutil.rmtree(pasta); os.makedirs(pasta)
for i in range(2):
    criar(pasta, nome_dump(i, hora=f"{1000 + i}"))
for i in range(6):
    criar(pasta, nome_dump(30 + i, hora=f"{2000 + i}"))
bb.limpar_antigos()
restantes = arquivos_em(pasta)
check("2 recentes + 6 vencidos -> sobram 5", len(restantes) == 5, f"{restantes}")
check("os recentes continuam la",
      all(nome_dump(i, hora=f"{1000 + i}") in restantes for i in range(2)))

# B5: nao pode encostar em arquivo que nao e dele
shutil.rmtree(pasta); os.makedirs(pasta)
intrusos = [
    "outro_sistema.dump",                      # nome alheio
    "lavajato_semdata.dump",                   # nao casa o padrao
    "lavajato_2026-13-45_1200.dump",           # casa o regex, data impossivel
    "lavajato_2020-01-01_1200.dump.INVALIDO",  # dump ruim guardado p/ diagnostico
    "notas_do_dono.txt",
]
for nome in intrusos:
    criar(pasta, nome)
for i in range(10):
    criar(pasta, nome_dump(50 + i, hora=f"{1000 + i}"))
bb.limpar_antigos()
restantes = arquivos_em(pasta)
check("nenhum arquivo alheio foi apagado",
      all(n in restantes for n in intrusos),
      f"sumiram: {[n for n in intrusos if n not in restantes]}")
check("mas os proprios vencidos foram limpos",
      len([n for n in restantes if e_backup_valido(n)]) == bb.MINIMO_MANTER)
check("arquivo com data impossivel (2026-13-45) e ignorado, nao apagado",
      "lavajato_2026-13-45_1200.dump" in restantes)

# B6
shutil.rmtree(pasta); os.makedirs(pasta)
try:
    bb.limpar_antigos()
    check("pasta vazia nao quebra", True)
except Exception as erro:
    check("pasta vazia nao quebra", False, str(erro))


# ============================================================================
print("\n=== C. Deteccao de dump corrompido (o check que mais importa) ===")

dump_real = next((os.path.join(PASTA_REAL, n) for n in sorted(os.listdir(PASTA_REAL))
                  if n.endswith(".dump")), None) if os.path.isdir(PASTA_REAL) else None

if not dump_real:
    check("existe um dump real de referencia (rode antes: python backup_banco.py)",
          False)
else:
    copia_boa = os.path.join(pasta, "lavajato_2026-01-01_1200.dump")
    shutil.copy(dump_real, copia_boa)
    check("dump integro passa na conferencia", bb.conferir_backup(copia_boa) is True)

    # O caso real: disco encheu ou a rede caiu no meio do dump.
    truncado = os.path.join(pasta, "lavajato_2026-01-02_1200.dump")
    with open(dump_real, "rb") as f:
        dados = f.read()
    with open(truncado, "wb") as f:
        f.write(dados[:len(dados) // 3])
    check("dump truncado e REPROVADO", bb.conferir_backup(truncado) is False)
    check("dump truncado vira .INVALIDO", os.path.exists(truncado + ".INVALIDO"),
          "ficou com nome de backup bom!")
    check("e nao sobra com nome de dump valido", not os.path.exists(truncado))

    lixo = criar(pasta, "lavajato_2026-01-03_1200.dump", b"isto nao e um dump" * 100)
    check("arquivo de lixo e REPROVADO", bb.conferir_backup(lixo) is False)

    vazio = criar(pasta, "lavajato_2026-01-04_1200.dump", b"")
    check("arquivo vazio (0 bytes) e REPROVADO", bb.conferir_backup(vazio) is False)


# ============================================================================
print("\n=== D. Falhas de conexao (tarefa agendada nao pode ficar pendurada) ===")

original = dict(bb.DB_config)

shutil.rmtree(pasta); os.makedirs(pasta)
bb.DB_config = dict(original, host="127.0.0.1", port=9)   # porta 9: nada escuta
inicio = datetime.now()
resultado = bb.gerar_backup()
demora = (datetime.now() - inicio).total_seconds()
check("servidor inacessivel -> devolve None", resultado is None)
check("nao deixa arquivo .dump pela metade",
      not [n for n in arquivos_em(pasta) if n.endswith(".dump")],
      f"sobrou: {arquivos_em(pasta)}")
check(f"falha rapido, nao fica pendurado ({demora:.1f}s)", demora < 30)

# O --no-password existe para isto: sem ele o pg_dump abriria um prompt e a
# tarefa agendada ficaria travada para sempre, sem ninguem para digitar.
bb.DB_config = dict(original, password="senha_propositalmente_errada")
inicio = datetime.now()
resultado = bb.gerar_backup()
demora = (datetime.now() - inicio).total_seconds()
check("senha errada -> devolve None", resultado is None)
check(f"NAO trava pedindo senha ({demora:.1f}s)", demora < 30)
check("nao deixa arquivo pela metade",
      not [n for n in arquivos_em(pasta) if n.endswith(".dump")])

bb.DB_config = dict(original, database="banco_que_nao_existe_xyz")
check("banco inexistente -> devolve None", bb.gerar_backup() is None)


# ============================================================================
print("\n=== E. Codigos de saida (e como o Agendador sabe que falhou) ===")

bb.DB_config = dict(original, password="")
check("sem senha no .env -> main() devolve 1", bb.main() == 1)

bb.DB_config = dict(original, host="127.0.0.1", port=9)
check("servidor fora -> main() devolve 1", bb.main() == 1)

# A falha tem de CHEGAR AO LOG. Era isto que o bug do UnicodeEncodeError
# destruia: o script morria ao imprimir a mensagem do pg_dump e o log ficava
# mudo justamente no dia em que o servidor caiu.
caminho_log = os.path.join(pasta, "backup.log")
log_txt = ""
if os.path.exists(caminho_log):
    with open(caminho_log, encoding="utf-8") as f:
        log_txt = f.read()
check("a falha fica REGISTRADA no log", "BACKUP FALHOU" in log_txt)
check("o log guarda a mensagem de erro do PostgreSQL",
      "Mensagem do PostgreSQL" in log_txt)

# Caminho feliz (unica vez que encosta no banco de verdade, so leitura).
bb.DB_config = original
shutil.rmtree(pasta); os.makedirs(pasta)
check("backup bem-sucedido -> main() devolve 0", bb.main() == 0)
check("gerou exatamente 1 arquivo de dump",
      len([n for n in arquivos_em(pasta) if n.endswith(".dump")]) == 1)
check("gravou o log", os.path.exists(caminho_log))

with open(caminho_log, encoding="utf-8") as f:
    log_txt = f.read()
check("log abre em UTF-8 com acentos corretos",
      "concluído" in log_txt or "íntegro" in log_txt,
      "acentuacao corrompida no log")


# ============================================================================
print("\n=== F. Regressao do bug que este teste achou ===")

# O pg_dump devolve a mensagem de erro em bytes que, lidos como UTF-8, viram
# U+FFFD. Imprimir isso num console cp1252 levantava UnicodeEncodeError e
# derrubava o backup — no exato momento em que ele registrava uma falha.
try:
    bb.registrar("ERRO simulado: \ufffd servidor n\ufffdo aceita conex\ufffdes")
    check("registrar() aguenta caractere que o console nao imprime", True)
except UnicodeEncodeError as erro:
    check("registrar() aguenta caractere que o console nao imprime", False, str(erro))

check("texto_seguro() devolve string sem levantar excecao",
      isinstance(bb.texto_seguro("\ufffd abc \ufffd"), str))

with open(caminho_log, encoding="utf-8") as f:
    check("a mensagem problematica foi gravada no log", "ERRO simulado" in f.read())


# ============================================================================
print("\n=== G. Travas do teste_restauracao ===")

# A trava que impede o DROP DATABASE cair no banco real.
tr.BANCO_REAL = tr.BANCO_TESTE
check("aborta se o banco de teste tiver o nome do real", tr.main() == 1)
tr.BANCO_REAL = original["database"]

tr.PASTA_BACKUP = pasta
antigo = criar(pasta, "lavajato_2020-01-01_1200.dump")
os.utime(antigo, (0, 0))
check("backup_mais_recente() pega o mais novo, nao o mais velho",
      tr.backup_mais_recente() != antigo)

vazia = tempfile.mkdtemp(prefix="teste_vazio_")
tr.PASTA_BACKUP = vazia
check("pasta sem backup -> backup_mais_recente() devolve None",
      tr.backup_mais_recente() is None)


# ============================================================================
shutil.rmtree(pasta, ignore_errors=True)
shutil.rmtree(vazia, ignore_errors=True)

falhas = [c for c in CHECKS if not c[1]]
print("\n" + "=" * 70)
if falhas:
    print(f"RESULTADO: {len(CHECKS) - len(falhas)}/{len(CHECKS)} checks passaram, "
          f"{len(falhas)} FALHA(S):")
    for nome, _, detalhe in falhas:
        print(f"   !! {nome}" + (f"  [{detalhe}]" if detalhe else ""))
else:
    print(f"RESULTADO: {len(CHECKS)}/{len(CHECKS)} checks passaram, 0 falhas.")
print("=" * 70)

sys.exit(1 if falhas else 0)
