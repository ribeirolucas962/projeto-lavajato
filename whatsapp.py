"""
WhatsApp — abrir conversa com o cliente já com a mensagem escrita.
Sistema Lava-Jato. Autor: RINEAL Analytics

COMO FUNCIONA (não é integração, é um LINK):
    O WhatsApp aceita links no formato   https://wa.me/<numero>?text=<mensagem>
    Ao abrir esse link, o WhatsApp (Web ou aplicativo) abre a conversa com aquele
    número e a mensagem JÁ DIGITADA na caixa de texto. Quem aperta "enviar" é o
    atendente — a gente não envia nada sozinho, não precisa de API paga, nem de
    número verificado, nem de token. É de graça e funciona hoje.

    No app.py, abrir o link é `page.launch_url(link_whatsapp(...))`.

Este módulo NÃO acessa o banco: recebe telefone + dados e devolve o link pronto.
Rode `python whatsapp.py` para ver exemplos.
"""

from urllib.parse import quote
import re

# Dados da empresa que aparecem nas mensagens (mudou o nome/telefone? é aqui).
EMPRESA = "Truck Center Lavação"
DDI_PADRAO = "55"          # Brasil
DDD_PADRAO = "47"          # usado quando o telefone foi salvo sem DDD


def normalizar_numero(telefone):
    """
    Transforma o telefone salvo no banco no formato que o WhatsApp exige:
    só números, com código do país na frente.
        '(47) 99999-0000' -> '5547999990000'
    Devolve None se não sobrar um telefone plausível (menos de 10 dígitos).
    """
    d = re.sub(r"\D", "", telefone or "")
    if not d:
        return None

    # Já veio com o 55 na frente (ex.: '5547999990000')? Não duplica.
    if len(d) in (12, 13) and d.startswith(DDI_PADRAO):
        return d
    # Telefone com DDD (10 = fixo, 11 = celular): só falta o código do país.
    if len(d) in (10, 11):
        return DDI_PADRAO + d
    # Sem DDD (8 ou 9 dígitos): assume o DDD da região do lava-jato.
    if len(d) in (8, 9):
        return DDI_PADRAO + DDD_PADRAO + d
    return None


def link_whatsapp(telefone, mensagem=""):
    """
    Monta o link que abre a conversa no WhatsApp com a mensagem pré-escrita.
    Retorna None se o telefone for inválido (aí a tela desabilita o botão).

    quote() codifica a mensagem para caber numa URL (espaço vira %20, acento vira
    %C3%A7 etc.) — sem isso, o texto chegaria cortado ou embaralhado.
    """
    numero = normalizar_numero(telefone)
    if not numero:
        return None
    if not mensagem:
        return f"https://wa.me/{numero}"
    return f"https://wa.me/{numero}?text={quote(mensagem)}"


# ================================================================
# Modelos de mensagem
# ================================================================
# Cada modelo é um texto com "buracos" entre chaves ({cliente}, {veiculo}...)
# que o montar_mensagem() preenche. Para criar uma mensagem nova, basta
# adicionar uma entrada aqui — ela aparece sozinha no menu do botão de WhatsApp
# (o app lê este dicionário; veja MODELOS_MENU no fim do arquivo).
MODELOS = {
    "carro_pronto": {
        "titulo": "Veículo pronto",
        "icone": "check",
        "texto": (
            "Olá, {cliente}! Tudo bem?\n\n"
            "Seu veículo {veiculo} já está pronto e à sua disposição aqui na {empresa}. 🚙✨\n\n"
            "Estamos te esperando!"
        ),
    },
    "aniversario": {
        "titulo": "Feliz aniversário",
        "icone": "cake",
        "texto": (
            "Olá, {cliente}! 🎉\n\n"
            "A equipe da {empresa} deseja um feliz aniversário!\n\n"
            "Para comemorar, preparamos um mimo pra você: traga seu veículo este mês "
            "e ganhe um desconto especial na lavagem. 🎁\n\n"
            "Um abraço e parabéns!"
        ),
    },
    "promocao": {
        "titulo": "Promoção",
        "icone": "promo",
        "texto": (
            "Olá, {cliente}! Tudo bem?\n\n"
            "Passando para avisar da promoção da semana aqui na {empresa}: "
            "condições especiais na lavagem completa. 🚿\n\n"
            "Quer que eu já reserve um horário pra você?"
        ),
    },
    "sentimos_falta": {
        "titulo": "Sentimos sua falta",
        "icone": "saudade",
        "texto": (
            "Olá, {cliente}! Tudo bem?\n\n"
            "Faz um tempinho que seu veículo não aparece aqui na {empresa} e a gente "
            "sentiu falta! 😊\n\n"
            "Que tal agendar uma lavagem? É só me chamar por aqui."
        ),
    },
    "orcamento_pronto": {
        "titulo": "Serviço em andamento",
        "icone": "andamento",
        "texto": (
            "Olá, {cliente}! Tudo bem?\n\n"
            "Seu veículo {veiculo} já está em atendimento aqui na {empresa}. "
            "Assim que estiver pronto eu te aviso por aqui. 👍"
        ),
    },
    "cobranca": {
        "titulo": "Lembrete de pagamento",
        "icone": "cobranca",
        "texto": (
            "Olá, {cliente}, tudo bem?\n\n"
            "Passando um lembrete amigável sobre o valor em aberto do serviço "
            "do veículo {veiculo} aqui na {empresa}.\n\n"
            "Qualquer dúvida é só me chamar. Obrigado!"
        ),
    },
    # {quando} = data/hora do agendamento (ex.: "quinta-feira (24/07) às 09:00").
    # É o único modelo que usa esse campo; os demais ignoram (str.format descarta
    # os parâmetros a mais), e montar_mensagem cai num texto neutro se vier vazio.
    "lembrete_agendamento": {
        "titulo": "Lembrete de agendamento",
        "icone": "agenda",
        "texto": (
            "Olá, {cliente}! Tudo bem?\n\n"
            "Passando para lembrar do seu agendamento aqui na {empresa}: "
            "{quando}, para o veículo {veiculo}. 🗓️🚙\n\n"
            "Está tudo certo para esse horário? Se precisar remarcar, "
            "é só me avisar por aqui!"
        ),
    },
}


def montar_mensagem(modelo, cliente="", veiculo="", empresa=EMPRESA, quando=""):
    """
    Preenche um modelo com os dados do cliente.
    'modelo' é a chave do dicionário MODELOS (ex.: 'carro_pronto').
    Campos não informados viram um texto neutro ("seu veículo") em vez de sumirem.
    'quando' (data/hora) só é usado pelo modelo de lembrete de agendamento; nos
    outros modelos ele é ignorado (str.format descarta parâmetros a mais).
    """
    m = MODELOS.get(modelo)
    if not m:
        return ""
    primeiro_nome = (cliente or "").strip().split(" ")[0] or "cliente"
    return m["texto"].format(
        cliente=primeiro_nome,
        veiculo=(veiculo or "").strip() or "seu veículo",
        empresa=empresa,
        quando=(quando or "").strip() or "o horário combinado",
    )


def link_modelo(telefone, modelo, cliente="", veiculo="", quando=""):
    """Atalho: monta a mensagem a partir do modelo E devolve o link do WhatsApp."""
    return link_whatsapp(telefone, montar_mensagem(modelo, cliente, veiculo, quando=quando))


def modelos_disponiveis():
    """[(chave, titulo), ...] — usado pelo app para montar o menu do botão."""
    return [(chave, m["titulo"]) for chave, m in MODELOS.items()]


# ================================================================
# TESTE RÁPIDO (python whatsapp.py)
# ================================================================
if __name__ == "__main__":
    # O terminal do Windows usa Win-1252 e trava ao imprimir emoji (os 🚙 das
    # mensagens). Forçamos UTF-8 só na SAÍDA do teste — a mensagem em si sempre
    # foi válida; o problema era só exibi-la no console.
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("— Normalização do número —")
    for t in ["(47) 99999-0000", "47 3333-4444", "99999-0000", "5547999990000", "abc"]:
        print(f"  {t!r:20} -> {normalizar_numero(t)}")

    print("\n— Mensagem pronta (veículo pronto) —")
    print(montar_mensagem("carro_pronto", cliente="João da Silva",
                          veiculo="Fiat Toro (ABC-1234)"))

    print("\n— Mensagem pronta (lembrete de agendamento) —")
    print(montar_mensagem("lembrete_agendamento", cliente="Maria Souza",
                          veiculo="Fiat Uno (XYZ-9090)",
                          quando="quinta-feira (24/07) às 09:00"))

    print("\n— Link gerado —")
    print(link_modelo("(47) 99999-0000", "aniversario", cliente="Maria Souza"))

    print("\n— Modelos disponíveis —")
    for chave, titulo in modelos_disponiveis():
        print(f"  {chave:18} {titulo}")
