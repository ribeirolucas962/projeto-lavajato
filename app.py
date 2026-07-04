"""
Interface gráfica (protótipo) — Sistema de Gestão Truck Center Lavação.
Stack: Flet (Python puro). Reaproveita as funções de CRUD dos módulos do backend.
Autor: Lucas Ribeiro Nepomuceno de Almeida (RINEAL Analytics).

Como rodar:
    python app.py

Login: usa funcionario.autenticar(login, senha). Cadastre um funcionário com login/senha
(ex.: rode `python funcionario.py` uma vez) ou use o botão "Entrar como demonstração".

------------------------------------------------------------------------------
GUIA DE LEITURA (mapa do arquivo, de cima para baixo)
------------------------------------------------------------------------------
1. Paleta/identidade visual (COR_*) e helpers de formatação (brl, fmt_dt, ...).
2. gerar_recibo_pdf()  -> monta o recibo da comanda em PDF (reportlab).
   (os indicadores do Dashboard são calculados em dashboard.py -> mod_dash)
3. main(page)          -> TODA a aplicação vive aqui dentro (closures aninhados):
     - helpers de UI (abrir/fechar diálogo, aviso, cabeçalho de diálogo);
     - tela_login();
     - "shell" principal (sidebar + área de conteúdo) e navegação entre telas;
     - componentes reutilizáveis (cabecalho, card_kpi, card_tabela);
     - uma função pagina_*() por tela (Dashboard, Clientes, Veículos, ...);
     - registrar_paginas() -> mapeia nome do menu -> (ícone, função da tela).

PADRÃO DE CADA TELA (pagina_*): todas seguem a MESMA receita, então entender uma
(a de Clientes está comentada como referência) é entender todas:
    montar_linhas()      -> lê do backend e devolve a DataTable (ou aviso de vazio);
    atualizar()          -> re-renderiza a tabela após uma mudança;
    confirmar_desativar()-> diálogo de confirmação do soft delete;
    form_*()             -> diálogo de cadastro/edição (valida e chama o backend);
    return ft.Column(...)-> layout final da tela (cabeçalho + filtros + tabela).

⚠️ DUAS CONVENÇÕES FRÁGEIS (é aqui que a maioria dos bugs aparece):
  (a) DESEMPACOTAMENTO POR ÍNDICE: as linhas vêm do backend como TUPLAS e são
      abertas por posição, ex.: `(idc, nome, cpf, tel, ...) = c`. Se a ordem das
      colunas no SELECT do módulo mudar, os campos aqui saem trocados SEM erro.
      Cada tela anota, no loop, o layout da tupla que espera — confira contra o .py.
  (b) CAPTURA EM CLOSURE DENTRO DE LOOP: nos on_click usamos `lambda e, i=idc: ...`.
      O `i=idc` "congela" o valor daquela iteração. Sem esse argumento padrão,
      TODOS os botões usariam o último id do loop (bug clássico de Python).
"""

import os
from datetime import datetime
import flet as ft

import funcionario as mod_func
import cadastro_cliente as mod_cli
import cadastro_veiculo as mod_veic
import catalogo_servicos as mod_serv
import ordem_servico as mod_os
import agendamento as mod_ag
import estoque as mod_estoque
import fornecedores as mod_forn
import planos_assinaturas as mod_planos
import caixa as mod_caixa
import dashboard as mod_dash

# ================================================================
# Paleta / identidade visual — cores da marca Truck Center Lavação
# ================================================================
COR_PRIMARIA = "#1B3B6F"          # azul-marinho da marca (botões, títulos)
COR_PRIMARIA_ESCURA = "#0A1730"   # azul-marinho profundo (gradiente)
COR_ACENTO = "#5BA9DC"            # azul-claro da marca (gotas/"LAVAÇÃO")
COR_FUNDO = ft.Colors.GREY_100
COR_CARD = ft.Colors.WHITE
COR_SIDEBAR = "#0D1B3E"           # azul-marinho da sidebar
COR_TEXTO_CLARO = ft.Colors.WHITE


def _carregar_logo():
    """Lê o PNG da logo como bytes (o Image do Flet 0.85 aceita src=bytes)."""
    caminho = os.path.join(os.path.dirname(__file__), "imagen", "trucka car.png")
    try:
        with open(caminho, "rb") as f:
            return f.read()
    except Exception:
        return None


LOGO_BYTES = _carregar_logo()


def brl(valor):
    """Formata um número como moeda brasileira: 1234.5 -> 'R$ 1.234,50'."""
    try:
        v = float(valor or 0)
    except (TypeError, ValueError):
        v = 0.0
    inteiro, dec = f"{v:,.2f}".split(".")
    inteiro = inteiro.replace(",", ".")
    return f"R$ {inteiro},{dec}"


def fmt_dt(dt):
    """Formata um datetime como 'dd/mm/aaaa HH:MM'. Tolerante a None."""
    try:
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return "—"


def fmt_date(d):
    """Formata uma data como 'dd/mm/aaaa'. Tolerante a None."""
    try:
        return d.strftime("%d/%m/%Y")
    except Exception:
        return "—"


def qtd_fmt(v):
    """Formata quantidade (NUMERIC) sem zeros à toa: 10.000 -> '10', 7.5 -> '7,5'."""
    try:
        return f"{float(v):g}".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def gerar_recibo_pdf(caminho, ctx):
    """
    Gera o recibo de uma comanda em PDF (reportlab) com a identidade da Truck Center.
    'ctx' é um dict com os dados já formatados. Lança exceção se reportlab faltar.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                    TableStyle, Image)
    from datetime import datetime as _dt

    NAVY = colors.HexColor("#1B3B6F")
    styles = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=styles["Title"], textColor=NAVY, fontSize=18, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=styles["Normal"], textColor=colors.grey,
                         fontSize=10, spaceAfter=2)
    secao = ParagraphStyle("secao", parent=styles["Heading3"], textColor=NAVY,
                           spaceBefore=12, spaceAfter=4)

    doc = SimpleDocTemplate(caminho, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm,
                            leftMargin=20 * mm, rightMargin=20 * mm,
                            title=f"Recibo Comanda {ctx['id_ordem']}")
    elems = []

    if ctx.get("logo") and os.path.exists(ctx["logo"]):
        try:
            img = Image(ctx["logo"], width=38 * mm, height=38 * mm)
            img.hAlign = "CENTER"
            elems.append(img)
        except Exception:
            pass
    elems.append(Paragraph("Truck Center Lavação", h))
    elems.append(Paragraph("Recibo de Serviço", sub))
    elems.append(Spacer(1, 6))

    info = [["Comanda:", f"#{ctx['id_ordem']}", "Data:", ctx['data']],
            ["Cliente:", ctx['cli_nome'], "", ""],
            ["Veículo:", ctx['placa'], "", ""]]
    t_info = Table(info, colWidths=[24 * mm, 70 * mm, 22 * mm, 44 * mm])
    t_info.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elems.append(t_info)

    elems.append(Paragraph("Serviços", secao))
    # ctx["itens"] = [(nome_servico, nome_lavador|None, preco), ...]
    serv_rows = [["Serviço", "Lavador", "Valor"]] + \
                [[n, (lav or "—"), brl(p)] for n, lav, p in ctx["itens"]]
    if len(serv_rows) == 1:
        serv_rows.append(["(nenhum)", "", ""])
    t_serv = Table(serv_rows, colWidths=[86 * mm, 44 * mm, 30 * mm])
    t_serv.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6FB")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elems.append(t_serv)

    elems.append(Paragraph("Valores", secao))
    t_val = Table([["Valor Total", brl(ctx['total'])],
                   ["Desconto", brl(ctx['desconto'])],
                   ["Acréscimo/Juros", brl(ctx['acrescimo'])],
                   ["Valor Final", brl(ctx['valor_final'])]],
                  colWidths=[120 * mm, 40 * mm])
    t_val.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.6, NAVY),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, -1), (-1, -1), NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elems.append(t_val)

    elems.append(Paragraph("Pagamento", secao))
    t_pag = Table([["Forma de pagamento", ctx['forma']],
                   ["Parcelas", str(ctx['parcelas'])],
                   ["Valor Pago", brl(ctx['valor_pago'])],
                   ["Valor Pendente", brl(ctx['valor_pendente'])],
                   ["Status", ctx['pag_status']],
                   ["Data do pagamento", ctx['data_pag']],
                   ["Vencimento", ctx['data_venc']]],
                  colWidths=[120 * mm, 40 * mm])
    t_pag.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elems.append(t_pag)

    # Vistoria de entrada: só sai no recibo se houver avarias registradas. Serve de
    # comprovante de que o dano já existia na chegada do veículo.
    if ctx.get("avarias"):
        elems.append(Paragraph("Vistoria de entrada", secao))
        elems.append(Paragraph(str(ctx["avarias"]),
                               ParagraphStyle("avar", parent=styles["Normal"], fontSize=10)))

    elems.append(Spacer(1, 16))
    elems.append(Paragraph(
        f"Emitido em {_dt.now().strftime('%d/%m/%Y %H:%M')} — Truck Center Lavação",
        ParagraphStyle("foot", parent=styles["Normal"], fontSize=8,
                       textColor=colors.grey, alignment=1)))
    doc.build(elems)


# ================================================================
# Aplicação
# ================================================================

def main(page: ft.Page):
    page.title = "Truck Center Lavação — Gestão"
    page.bgcolor = COR_FUNDO
    page.padding = 0
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window.width = 1180
    page.window.height = 740
    page.window.min_width = 920
    page.window.min_height = 600

    # Estado da sessão (funcionário logado)
    sessao = {"id": None, "nome": None, "funcao": None}

    # ------------------------------------------------------------
    # Helpers de UI
    # ------------------------------------------------------------
    def abrir_dialog(dlg):
        page.show_dialog(dlg)

    def fechar_dialog():
        page.pop_dialog()

    def cabecalho_dialog(texto, icone):
        """Cabeçalho colorido (cores da marca) para os diálogos de formulário."""
        return ft.Container(
            bgcolor=COR_PRIMARIA, border_radius=8,
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            content=ft.Row(spacing=10, controls=[
                ft.Icon(icone, color=COR_ACENTO, size=22),
                ft.Text(texto, color=ft.Colors.WHITE, size=18, weight=ft.FontWeight.BOLD),
            ]),
        )

    def aviso(titulo, mensagem):
        abrir_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text(titulo),
            content=ft.Text(mensagem),
            actions=[ft.TextButton("OK", on_click=lambda e: fechar_dialog())],
        ))

    # ============================================================
    # TELA DE LOGIN
    # ============================================================
    def tela_login():
        campo_login = ft.TextField(
            label="Login", width=300, autofocus=True,
            prefix_icon=ft.Icons.PERSON,
        )
        campo_senha = ft.TextField(
            label="Senha", width=300, password=True, can_reveal_password=True,
            prefix_icon=ft.Icons.LOCK,
        )
        erro = ft.Text("", color=ft.Colors.RED_400, size=13)

        def entrar(e=None):
            login = (campo_login.value or "").strip()
            senha = campo_senha.value or ""
            if not login or not senha:
                erro.value = "Informe login e senha."
                page.update()
                return
            resultado = mod_func.autenticar(login, senha)
            if resultado:
                sessao["id"], sessao["nome"], sessao["funcao"] = resultado
                montar_app()
            else:
                erro.value = "Login ou senha inválidos."
                page.update()

        def entrar_demo(e=None):
            # Acesso de demonstração (sem banco) — só pra navegar pelas telas.
            sessao["id"], sessao["nome"], sessao["funcao"] = (0, "Demonstração", "gerente")
            montar_app()

        campo_senha.on_submit = entrar

        cartao = ft.Container(
            width=380,
            padding=40,
            bgcolor=COR_CARD,
            border_radius=16,
            shadow=ft.BoxShadow(blur_radius=24, color=ft.Colors.with_opacity(0.2, ft.Colors.BLACK)),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=18,
                controls=[
                    ft.Container(
                        bgcolor=COR_SIDEBAR, border_radius=14, padding=12,
                        content=ft.Image(src=LOGO_BYTES, height=160, fit=ft.BoxFit.CONTAIN)
                    ) if LOGO_BYTES else ft.Icon(ft.Icons.LOCAL_CAR_WASH, size=56, color=COR_PRIMARIA),
                    ft.Text("Sistema de Gestão", size=14, color=ft.Colors.GREY_600,
                            weight=ft.FontWeight.W_500),
                    ft.Container(height=6),
                    campo_login,
                    campo_senha,
                    erro,
                    ft.FilledButton(
                        "Entrar", width=300, height=44, on_click=entrar,
                        style=ft.ButtonStyle(bgcolor=COR_PRIMARIA),
                    ),
                    ft.TextButton("Entrar como demonstração", on_click=entrar_demo),
                ],
            ),
        )

        page.controls.clear()
        page.add(
            ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                gradient=ft.LinearGradient(
                    begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                    colors=[COR_PRIMARIA, COR_PRIMARIA_ESCURA],
                ),
                content=cartao,
            )
        )
        page.update()

    # ============================================================
    # SHELL PRINCIPAL (sidebar + conteúdo)
    # ============================================================
    # Container onde a tela atual é desenhada (à direita da sidebar). Trocar de
    # menu só substitui o .content deste container — a sidebar permanece.
    area_conteudo = ft.Container(expand=True, padding=24)

    # Registro das telas: nome do menu -> (ícone, função que CONSTRÓI a tela).
    # Preenchido por registrar_paginas() no login. A função é chamada a cada
    # navegação (a tela é reconstruída do zero, relendo dados frescos do banco).
    paginas = {}

    def item_menu(nome, icone, selecionado):
        def ir(e):
            navegar(nome)
        return ft.Container(
            on_click=ir,
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=14, vertical=11),
            bgcolor=ft.Colors.with_opacity(0.16, COR_ACENTO) if selecionado else None,
            content=ft.Row(spacing=12, controls=[
                ft.Icon(icone, size=20,
                        color=COR_ACENTO if selecionado else ft.Colors.BLUE_GREY_200),
                ft.Text(nome, size=14,
                        weight=ft.FontWeight.W_600 if selecionado else ft.FontWeight.NORMAL,
                        color=COR_TEXTO_CLARO if selecionado else ft.Colors.BLUE_GREY_100),
            ]),
        )

    selecionado_atual = {"nome": "Dashboard"}

    def construir_sidebar():
        itens = [item_menu(nome, icone, nome == selecionado_atual["nome"])
                 for nome, (icone, _) in paginas.items()]
        return ft.Container(
            width=230,
            bgcolor=COR_SIDEBAR,
            padding=ft.Padding.symmetric(horizontal=14, vertical=20),
            content=ft.Column(
                expand=True,
                controls=[
                    ft.Container(
                        alignment=ft.Alignment.CENTER, padding=ft.Padding.only(bottom=4),
                        content=ft.Image(src=LOGO_BYTES, height=130, fit=ft.BoxFit.CONTAIN),
                    ) if LOGO_BYTES else ft.Row(spacing=10, controls=[
                        ft.Icon(ft.Icons.LOCAL_CAR_WASH, color=COR_TEXTO_CLARO, size=28),
                        ft.Column(spacing=0, controls=[
                            ft.Text("Truck Center", color=COR_TEXTO_CLARO,
                                    weight=ft.FontWeight.BOLD, size=15),
                            ft.Text("Lavação", color=ft.Colors.BLUE_GREY_200, size=11),
                        ]),
                    ]),
                    ft.Divider(color=ft.Colors.BLUE_GREY_700, height=24),
                    ft.Column(controls=itens, spacing=4, expand=True,
                              scroll=ft.ScrollMode.AUTO),
                    ft.Divider(color=ft.Colors.BLUE_GREY_700, height=12),
                    ft.Row(spacing=10, controls=[
                        ft.CircleAvatar(
                            content=ft.Text((sessao["nome"] or "?")[0].upper()),
                            bgcolor=COR_PRIMARIA, color=COR_TEXTO_CLARO,
                        ),
                        ft.Column(spacing=0, controls=[
                            ft.Text(sessao["nome"] or "", color=COR_TEXTO_CLARO, size=13,
                                    weight=ft.FontWeight.W_600),
                            ft.Text((sessao["funcao"] or "").capitalize(),
                                    color=ft.Colors.BLUE_GREY_200, size=11),
                        ]),
                    ]),
                    ft.TextButton(
                        "Sair", icon=ft.Icons.LOGOUT,
                        on_click=lambda e: tela_login(),
                        style=ft.ButtonStyle(color=ft.Colors.BLUE_GREY_100),
                    ),
                ],
            ),
        )

    sidebar_container = ft.Container()

    def navegar(nome):
        # Clique num item do menu: marca o item, redesenha a sidebar (para o
        # destaque de selecionado) e reconstrói a tela chamando paginas[nome][1]().
        selecionado_atual["nome"] = nome
        sidebar_container.content = construir_sidebar()
        area_conteudo.content = paginas[nome][1]()
        page.update()

    def montar_app():
        # Chamado logo após o login: troca a tela de login pelo layout principal
        # (sidebar + conteúdo) e abre a tela inicial (selecionado_atual, "Dashboard").
        registrar_paginas()
        sidebar_container.content = construir_sidebar()
        area_conteudo.content = paginas[selecionado_atual["nome"]][1]()
        page.controls.clear()
        page.add(ft.Row(expand=True, spacing=0, controls=[sidebar_container, area_conteudo]))
        page.update()

    # ============================================================
    # COMPONENTES REUTILIZÁVEIS
    # ============================================================
    def cabecalho(titulo, subtitulo=None, acao=None):
        # Título grande + subtítulo opcional à esquerda; 'acao' (ex.: botão "Novo")
        # vai à direita. Usado no topo de todas as telas.
        col = [ft.Text(titulo, size=26, weight=ft.FontWeight.BOLD)]
        if subtitulo:
            col.append(ft.Text(subtitulo, size=13, color=ft.Colors.GREY_600))
        linha = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[ft.Column(col, spacing=2)],
        )
        if acao:
            linha.controls.append(acao)
        return linha

    def card_kpi(titulo, valor, icone, cor, tamanho=24):
        # Cartão de indicador do Dashboard: rótulo + número grande + ícone colorido.
        # 'tamanho' menor serve para valores em texto (ex.: nome do serviço campeão).
        return ft.Container(
            width=250, padding=20, bgcolor=COR_CARD, border_radius=12,
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK)),
            content=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ft.Column(spacing=4, expand=True, controls=[
                    ft.Text(titulo, size=13, color=ft.Colors.GREY_600),
                    ft.Text(str(valor), size=tamanho, weight=ft.FontWeight.BOLD),
                ]),
                ft.Container(
                    width=48, height=48, border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.15, cor),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icone, color=cor, size=26),
                ),
            ]),
        )

    def card_tabela(titulo, tabela):
        # "Moldura" branca padrão em volta de uma tabela (título + divisor + corpo
        # rolável). 'tabela' costuma ser o corpo_tabela dinâmico de cada tela.
        return ft.Container(
            expand=True, padding=20, bgcolor=COR_CARD, border_radius=12,
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK)),
            content=ft.Column(expand=True, controls=[
                ft.Text(titulo, size=16, weight=ft.FontWeight.BOLD),
                ft.Divider(height=12),
                ft.Column([tabela], expand=True, scroll=ft.ScrollMode.AUTO),
            ]),
        )

    # ============================================================
    # PÁGINA: DASHBOARD
    # ============================================================
    def pagina_dashboard():
        # Cada KPI é uma consulta independente ao backend; aqui só contamos/somamos
        # os resultados. Sem tabela própria — o Dashboard vive só de leitura
        # (os indicadores calculados no banco ficam em dashboard.py -> mod_dash).
        clientes = mod_cli.buscar_clientes()
        servicos = mod_serv.buscar_servicos()
        comandas_abertas = mod_os.buscar_comandas(somente_abertas=True)
        abaixo_min = mod_estoque.produtos_abaixo_minimo()   # produtos no vermelho
        caixa = mod_caixa.caixa_aberto()                    # None se não há caixa aberto
        fat_hoje = mod_dash.faturamento("hoje")
        fat_mes = mod_dash.faturamento("mes")
        ticket = mod_dash.ticket_medio(30)
        mais_vendidos = mod_dash.servicos_mais_vendidos(30)  # [(nome, qtd, total), ...]
        taxa = mod_dash.taxa_retorno(90)
        tempo = mod_dash.tempo_medio_servico(30)             # minutos, ou None sem dados
        horas = mod_dash.horarios_pico(30)                   # [(hora, qtd), ...]
        # Hora com mais entradas de comanda no período (None se não houve movimento).
        hora_pico = max(horas, key=lambda h: h[1])[0] if horas else None

        kpis = ft.Row(wrap=True, spacing=16, run_spacing=16, controls=[
            card_kpi("Faturamento hoje", brl(fat_hoje), ft.Icons.TODAY, ft.Colors.GREEN_600),
            card_kpi("Faturamento no mês", brl(fat_mes), ft.Icons.CALENDAR_MONTH, ft.Colors.BLUE_600),
            card_kpi("Ticket médio (30 dias)", brl(ticket), ft.Icons.PRICE_CHECK, ft.Colors.CYAN_700),
            card_kpi("Serviço mais vendido (30 dias)",
                     mais_vendidos[0][0] if mais_vendidos else "—",
                     ft.Icons.STAR, ft.Colors.AMBER_700, tamanho=17),
            card_kpi("Taxa de retorno (90 dias)", f"{taxa:.0f}%", ft.Icons.REPLAY, ft.Colors.INDIGO_600),
            card_kpi("Tempo médio de serviço (30 dias)",
                     f"{tempo:.0f} min" if tempo is not None else "—",
                     ft.Icons.TIMER, ft.Colors.BROWN_600),
            card_kpi("Horário de pico (30 dias)",
                     f"{hora_pico:02d}h" if hora_pico is not None else "—",
                     ft.Icons.SCHEDULE, ft.Colors.DEEP_ORANGE_600),
            card_kpi("Comandas abertas", len(comandas_abertas), ft.Icons.RECEIPT_LONG, ft.Colors.ORANGE_700),
            card_kpi("Clientes ativos", len(clientes), ft.Icons.PEOPLE, ft.Colors.PURPLE_600),
            card_kpi("Serviços no catálogo", len(servicos), ft.Icons.LOCAL_CAR_WASH, ft.Colors.TEAL_600),
            card_kpi("Estoque abaixo do mínimo", len(abaixo_min), ft.Icons.WARNING_AMBER,
                     ft.Colors.RED_600 if abaixo_min else ft.Colors.GREY_500),
        ])

        status_caixa = ("Aberto" if caixa else "Fechado")
        cor_caixa = ft.Colors.GREEN_600 if caixa else ft.Colors.GREY_500
        faixa_caixa = ft.Container(
            padding=16, bgcolor=COR_CARD, border_radius=12,
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK)),
            content=ft.Row(spacing=12, controls=[
                ft.Icon(ft.Icons.POINT_OF_SALE, color=cor_caixa),
                ft.Text(f"Caixa: {status_caixa}", weight=ft.FontWeight.W_600),
            ]),
        )

        return ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=20, controls=[
            cabecalho("Dashboard", f"Bem-vindo, {sessao['nome']}!"),
            kpis,
            faixa_caixa,
        ])

    # ============================================================
    # PÁGINA: CLIENTES (CRUD completo — vitrine)
    # ============================================================
    def pagina_clientes():
        # ===== TELA DE REFERÊNCIA =====
        # Esta é a tela mais comentada de propósito: todas as outras pagina_*()
        # seguem exatamente esta estrutura (busca -> montar_linhas -> atualizar ->
        # confirmar_desativar -> form_* -> return Column). Entenda esta e entendeu
        # as demais; lá só comentamos o que difere.

        # Campo de busca e checkbox de filtro. Ambos disparam atualizar() no on_change
        # (ligados mais abaixo), refazendo a consulta ao vivo enquanto o usuário digita.
        campo_busca = ft.TextField(
            hint_text="Buscar por nome ou telefone...", expand=True,
            prefix_icon=ft.Icons.SEARCH, height=44,
        )
        mostrar_inativos = ft.Checkbox(label="Incluir inativos", value=False)
        # Coluna "viva": seu conteúdo é trocado por atualizar() sem reconstruir a tela.
        corpo_tabela = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

        def montar_linhas():
            # Lê os clientes do banco conforme o filtro e devolve a DataTable pronta.
            termo = (campo_busca.value or "").strip() or None
            clientes = mod_cli.buscar_clientes(
                termo=termo, apenas_ativos=not mostrar_inativos.value)
            if not clientes:
                return ft.Container(
                    padding=30, alignment=ft.Alignment.CENTER,
                    content=ft.Text("Nenhum cliente encontrado.", color=ft.Colors.GREY_500))
            linhas = []
            for c in clientes:
                # ⚠️ Ordem da tupla = ordem do SELECT em cadastro_cliente.buscar_clientes().
                # Se mudar lá, ajuste aqui (senão os campos saem trocados sem erro).
                (idc, nome, cpf, tel, email, end, obs, ativo) = c
                badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=2), border_radius=20,
                    bgcolor=ft.Colors.GREEN_100 if ativo else ft.Colors.GREY_300,
                    content=ft.Text("Ativo" if ativo else "Inativo", size=11,
                                    color=ft.Colors.GREEN_900 if ativo else ft.Colors.GREY_700),
                )
                # Cliente ativo -> botão de desativar; inativo -> botão de reativar.
                # `i=idc` / `cc=c`: congela o valor DESTA iteração no closure (ver nota
                # (b) no topo do arquivo). Sem isso, todo botão usaria o último cliente.
                if ativo:
                    acao = ft.IconButton(ft.Icons.BLOCK, icon_color=ft.Colors.RED_400,
                                         tooltip="Desativar",
                                         on_click=lambda e, i=idc: confirmar_desativar(i))
                else:
                    acao = ft.IconButton(ft.Icons.RESTORE, icon_color=ft.Colors.GREEN_500,
                                         tooltip="Reativar",
                                         on_click=lambda e, i=idc: (mod_cli.reativar_cliente(i), atualizar()))
                linhas.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(idc))),
                    ft.DataCell(ft.Text(nome or "")),
                    ft.DataCell(ft.Text(tel or "—")),
                    ft.DataCell(ft.Text(email or "—")),
                    ft.DataCell(badge),
                    ft.DataCell(ft.Row(spacing=0, controls=[
                        # Editar passa a tupla inteira (cc=c) para o formulário preencher os campos.
                        ft.IconButton(ft.Icons.EDIT, icon_color=COR_PRIMARIA, tooltip="Editar",
                                      on_click=lambda e, cc=c: form_cliente(cc)),
                        acao,
                    ])),
                ]))
            return ft.DataTable(
                expand=True,
                heading_row_color=ft.Colors.GREY_50,
                columns=[
                    ft.DataColumn(ft.Text("ID")),
                    ft.DataColumn(ft.Text("Nome")),
                    ft.DataColumn(ft.Text("Telefone")),
                    ft.DataColumn(ft.Text("E-mail")),
                    ft.DataColumn(ft.Text("Status")),
                    ft.DataColumn(ft.Text("Ações")),
                ],
                rows=linhas,
            )

        def atualizar(e=None):
            # Refaz só a tabela (relê o banco) e repinta a tela. Aceita `e=None`
            # para servir tanto como callback de evento quanto chamada direta.
            corpo_tabela.controls = [montar_linhas()]
            page.update()

        # Liga os filtros à atualização ao vivo.
        campo_busca.on_change = atualizar
        mostrar_inativos.on_change = atualizar

        def confirmar_desativar(idc):
            # Soft delete: pede confirmação e chama desativar_cliente (não apaga o
            # registro; só marca ativo=FALSE, preservando o histórico).
            def sim(e):
                mod_cli.desativar_cliente(idc)
                fechar_dialog()
                atualizar()
            abrir_dialog(ft.AlertDialog(
                modal=True,
                title=ft.Text("Desativar cliente"),
                content=ft.Text("Tem certeza? O cliente fica inativo, mas o histórico é preservado."),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Desativar", on_click=sim,
                                    style=ft.ButtonStyle(bgcolor=ft.Colors.RED_500)),
                ],
            ))

        def form_cliente(cliente=None):
            # Um único formulário serve para CRIAR (cliente=None) e EDITAR (recebe a
            # tupla vinda da tabela). `editando` alterna rótulos e qual função do
            # backend é chamada no salvar(). Os índices cliente[1..6] seguem a mesma
            # ordem da tupla desempacotada em montar_linhas().
            editando = cliente is not None
            f_nome = ft.TextField(label="Nome *", value=cliente[1] if editando else "", width=420)
            f_cpf = ft.TextField(label="CPF / CNPJ", value=(cliente[2] or "") if editando else "", width=200)
            f_tel = ft.TextField(label="Telefone", value=(cliente[3] or "") if editando else "", width=200)
            f_email = ft.TextField(label="E-mail", value=(cliente[4] or "") if editando else "", width=420)
            f_end = ft.TextField(label="Endereço", value=(cliente[5] or "") if editando else "", width=420)
            f_obs = ft.TextField(label="Observações", value=(cliente[6] or "") if editando else "",
                                 width=420, multiline=True, min_lines=2, max_lines=3)
            erro_form = ft.Text("", color=ft.Colors.RED_400, size=12)

            def salvar(e):
                # Valida o obrigatório, normaliza vazios para None (campos opcionais)
                # e chama editar/inserir conforme o modo. `strip() or None` evita
                # gravar strings vazias no lugar de NULL.
                if not (f_nome.value or "").strip():
                    erro_form.value = "O nome é obrigatório."
                    page.update()
                    return
                vals = dict(
                    nome=f_nome.value.strip(),
                    cpf_cnpj=(f_cpf.value or "").strip() or None,
                    telefone=(f_tel.value or "").strip() or None,
                    email=(f_email.value or "").strip() or None,
                    endereco=(f_end.value or "").strip() or None,
                    observacoes=(f_obs.value or "").strip() or None,
                )
                if editando:
                    ok = mod_cli.editar_cliente(cliente[0], **vals)  # cliente[0] = id
                else:
                    ok = mod_cli.inserir_cliente(**vals) is not None
                fechar_dialog()
                if ok:
                    atualizar()
                else:
                    aviso("Erro", "Não foi possível salvar. Verifique a conexão com o banco.")

            abrir_dialog(ft.AlertDialog(
                modal=True,
                title_padding=0,
                title=cabecalho_dialog(
                    "Editar cliente" if editando else "Novo cliente",
                    ft.Icons.PERSON if editando else ft.Icons.PERSON_ADD),
                content=ft.Container(width=460, content=ft.Column(tight=True, spacing=12, controls=[
                    f_nome,
                    ft.Row([f_cpf, f_tel], spacing=20),
                    f_email, f_end, f_obs, erro_form,
                ])),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Salvar", on_click=salvar,
                                    style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)),
                ],
            ))

        botao_novo = ft.FilledButton(
            "Novo cliente", icon=ft.Icons.ADD, on_click=lambda e: form_cliente(),
            style=ft.ButtonStyle(bgcolor=COR_PRIMARIA))

        corpo_tabela.controls = [montar_linhas()]

        return ft.Column(expand=True, spacing=20, controls=[
            cabecalho("Clientes", "Cadastro e gestão de clientes", acao=botao_novo),
            ft.Row([campo_busca, mostrar_inativos], spacing=16),
            card_tabela("Lista de clientes", corpo_tabela),
        ])

    # ============================================================
    # PÁGINA: SERVIÇOS (CRUD + matriz de preços por porte)
    # ============================================================
    def pagina_servicos():
        campo_busca = ft.TextField(
            hint_text="Buscar serviço...", expand=True,
            prefix_icon=ft.Icons.SEARCH, height=44)
        mostrar_inativos = ft.Checkbox(label="Incluir inativos", value=False)
        corpo_tabela = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

        def montar_linhas():
            termo = (campo_busca.value or "").strip() or None
            servicos = mod_serv.buscar_servicos(
                termo=termo, apenas_ativos=not mostrar_inativos.value)
            if not servicos:
                return ft.Container(
                    padding=30, alignment=ft.Alignment.CENTER,
                    content=ft.Text("Nenhum serviço encontrado.", color=ft.Colors.GREY_500))
            linhas = []
            for s in servicos:
                # Tupla = SELECT de catalogo_servicos.buscar_servicos().
                (ids, nome, descricao, tempo, ativo) = s
                # Quantos portes já têm preço definido (0 = serviço não pode ser
                # cobrado ainda; a badge fica vermelha para chamar atenção).
                n_precos = len(mod_serv.precos_do_servico(ids))
                badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=2), border_radius=20,
                    bgcolor=ft.Colors.GREEN_100 if ativo else ft.Colors.GREY_300,
                    content=ft.Text("Ativo" if ativo else "Inativo", size=11,
                                    color=ft.Colors.GREEN_900 if ativo else ft.Colors.GREY_700))
                if ativo:
                    acao = ft.IconButton(ft.Icons.BLOCK, icon_color=ft.Colors.RED_400,
                                         tooltip="Desativar",
                                         on_click=lambda e, i=ids: confirmar_desativar(i))
                else:
                    acao = ft.IconButton(ft.Icons.RESTORE, icon_color=ft.Colors.GREEN_500,
                                         tooltip="Reativar",
                                         on_click=lambda e, i=ids: (mod_serv.reativar_servico(i), atualizar()))
                cor_precos = ft.Colors.GREEN_700 if n_precos else ft.Colors.RED_500
                linhas.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(ids))),
                    ft.DataCell(ft.Text(nome or "")),
                    ft.DataCell(ft.Text(descricao or "—")),
                    ft.DataCell(ft.Text(f"{tempo} min" if tempo else "—")),
                    ft.DataCell(ft.Text(f"{n_precos} porte(s)", color=cor_precos, size=12)),
                    ft.DataCell(badge),
                    ft.DataCell(ft.Row(spacing=0, controls=[
                        ft.IconButton(ft.Icons.ATTACH_MONEY, icon_color=COR_ACENTO,
                                      tooltip="Preços por porte",
                                      on_click=lambda e, ss=s: form_precos(ss)),
                        ft.IconButton(ft.Icons.EDIT, icon_color=COR_PRIMARIA, tooltip="Editar",
                                      on_click=lambda e, ss=s: form_servico(ss)),
                        acao,
                    ])),
                ]))
            return ft.DataTable(
                expand=True, heading_row_color=ft.Colors.GREY_50,
                columns=[
                    ft.DataColumn(ft.Text("ID")),
                    ft.DataColumn(ft.Text("Serviço")),
                    ft.DataColumn(ft.Text("Descrição")),
                    ft.DataColumn(ft.Text("Tempo médio")),
                    ft.DataColumn(ft.Text("Preços")),
                    ft.DataColumn(ft.Text("Status")),
                    ft.DataColumn(ft.Text("Ações")),
                ],
                rows=linhas,
            )

        def atualizar(e=None):
            corpo_tabela.controls = [montar_linhas()]
            page.update()

        campo_busca.on_change = atualizar
        mostrar_inativos.on_change = atualizar

        def confirmar_desativar(ids):
            def sim(e):
                mod_serv.desativar_servico(ids)
                fechar_dialog()
                atualizar()
            abrir_dialog(ft.AlertDialog(
                modal=True,
                title=ft.Text("Desativar serviço"),
                content=ft.Text("Tem certeza? O serviço fica inativo, mas o histórico "
                                "de comandas é preservado."),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Desativar", on_click=sim,
                                    style=ft.ButtonStyle(bgcolor=ft.Colors.RED_500)),
                ],
            ))

        def form_servico(servico=None):
            editando = servico is not None
            f_nome = ft.TextField(label="Nome *", value=servico[1] if editando else "", width=420)
            f_desc = ft.TextField(label="Descrição", value=(servico[2] or "") if editando else "",
                                  width=420, multiline=True, min_lines=2, max_lines=3)
            f_tempo = ft.TextField(label="Tempo médio (min)", width=180,
                                   value=(str(servico[3]) if editando and servico[3] else ""))
            erro_form = ft.Text("", color=ft.Colors.RED_400, size=12)

            def salvar(e):
                if not (f_nome.value or "").strip():
                    erro_form.value = "O nome é obrigatório."
                    page.update(); return
                tempo_txt = (f_tempo.value or "").strip()
                if tempo_txt and not tempo_txt.isdigit():
                    erro_form.value = "Tempo médio deve ser um número (minutos)."
                    page.update(); return
                tempo_val = int(tempo_txt) if tempo_txt else None
                desc = (f_desc.value or "").strip() or None
                if editando:
                    ok = mod_serv.editar_servico(servico[0], nome=f_nome.value.strip(),
                                                 descricao=desc, tempo_medio_min=tempo_val)
                else:
                    ok = mod_serv.inserir_servico(f_nome.value.strip(), descricao=desc,
                                                  tempo_medio_min=tempo_val) is not None
                fechar_dialog()
                if ok:
                    atualizar()
                else:
                    aviso("Erro", "Não foi possível salvar o serviço.")

            abrir_dialog(ft.AlertDialog(
                modal=True, title_padding=0,
                title=cabecalho_dialog("Editar serviço" if editando else "Novo serviço",
                                       ft.Icons.LOCAL_CAR_WASH),
                content=ft.Container(width=460, content=ft.Column(tight=True, spacing=12, controls=[
                    f_nome, f_desc, f_tempo, erro_form,
                ])),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Salvar", on_click=salvar,
                                    style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)),
                ],
            ))

        def form_precos(servico):
            # Editor da matriz preço × porte: mostra um campo por categoria de veículo,
            # já preenchido com o preço atual (se houver). Deixar em branco = remover o
            # preço daquele porte (o serviço deixa de ser cobrável nele).
            id_servico, nome_serv = servico[0], servico[1]
            categorias = mod_veic.listar_categorias()
            # {id_categoria: preco} com os preços que já existem hoje, para pré-preencher.
            precos_atuais = {cat_id: preco
                             for (cat_id, _cat_nome, preco) in mod_serv.precos_do_servico(id_servico)}
            campos = {}  # id_categoria -> TextField (para ler os valores no salvar)
            linhas_precos = []
            for (cat_id, cat_nome, _ordem) in categorias:
                atual = precos_atuais.get(cat_id)
                f = ft.TextField(
                    width=140, prefix=ft.Text("R$ "),
                    value=(f"{float(atual):.2f}".replace(".", ",") if atual is not None else ""),
                    hint_text="—")
                campos[cat_id] = f
                linhas_precos.append(ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[ft.Text(cat_nome, size=14, weight=ft.FontWeight.W_500), f]))
            erro_form = ft.Text("", color=ft.Colors.RED_400, size=12)

            def salvar(e):
                # 1ª passada: valida TUDO antes de tocar no banco (aceita vírgula
                # decimal). Assim não gravamos metade e abortamos no meio.
                novos = {}
                for cat_id, f in campos.items():
                    txt = (f.value or "").strip().replace(",", ".")
                    if not txt:
                        novos[cat_id] = None  # vazio = marcar para remover
                        continue
                    try:
                        novos[cat_id] = float(txt)
                    except ValueError:
                        erro_form.value = "Preços devem ser números (ex.: 35,00)."
                        page.update(); return
                # 2ª passada: grava. Só remove o que já existia (evita DELETE à toa).
                for cat_id, val in novos.items():
                    if val is None:
                        if cat_id in precos_atuais:
                            mod_serv.remover_preco(id_servico, cat_id)
                    else:
                        mod_serv.definir_preco(id_servico, cat_id, val)  # upsert
                fechar_dialog()
                atualizar()

            abrir_dialog(ft.AlertDialog(
                modal=True, title_padding=0,
                title=cabecalho_dialog(f"Preços — {nome_serv}", ft.Icons.ATTACH_MONEY),
                content=ft.Container(width=420, content=ft.Column(
                    tight=True, spacing=10, scroll=ft.ScrollMode.AUTO, controls=[
                        ft.Text("Defina o preço por porte (deixe vazio para não cobrar nesse porte):",
                                size=12, color=ft.Colors.GREY_600),
                        *linhas_precos,
                        erro_form,
                    ])),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Salvar preços", on_click=salvar,
                                    style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)),
                ],
            ))

        botao_novo = ft.FilledButton(
            "Novo serviço", icon=ft.Icons.ADD, on_click=lambda e: form_servico(),
            style=ft.ButtonStyle(bgcolor=COR_PRIMARIA))

        corpo_tabela.controls = [montar_linhas()]

        return ft.Column(expand=True, spacing=20, controls=[
            cabecalho("Catálogo de Serviços", "Serviços e preços por porte de veículo",
                      acao=botao_novo),
            ft.Row([campo_busca, mostrar_inativos], spacing=16),
            card_tabela("Serviços", corpo_tabela),
        ])

    # ============================================================
    # PÁGINA: COMANDAS / ORDEM DE SERVIÇO (CRUD + fluxo de atendimento)
    # ============================================================
    # Cores e rótulos dos status da comanda
    CORES_STATUS = {
        "aguardando": (ft.Colors.ORANGE_100, ft.Colors.ORANGE_900),
        "em_execucao": (ft.Colors.BLUE_100, ft.Colors.BLUE_900),
        "finalizado": (ft.Colors.GREEN_100, ft.Colors.GREEN_900),
        "entregue": (ft.Colors.TEAL_100, ft.Colors.TEAL_900),
        "cancelado": (ft.Colors.RED_100, ft.Colors.RED_900),
    }
    FORMAS_PAGAMENTO = [
        ("dinheiro", "Dinheiro"), ("pix", "Pix"),
        ("cartao_credito", "Cartão de crédito"), ("cartao_debito", "Cartão de débito"),
        ("transferencia", "Transferência"),
    ]

    def badge_status(status):
        status = status or ""
        bg, fg = CORES_STATUS.get(status, (ft.Colors.GREY_200, ft.Colors.GREY_800))
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=3), border_radius=20,
            bgcolor=bg,
            content=ft.Text(status.replace("_", " ").capitalize(), size=11, color=fg,
                            weight=ft.FontWeight.W_600),
        )

    def pagina_comandas():
        # Duas peças além da lista: form_nova_comanda() (abre a comanda a partir de um
        # veículo) e abrir_detalhe() (painel completo: itens, status, valores, pgto).
        filtro_abertas = ft.Checkbox(label="Somente abertas (fila)", value=True)
        corpo_tabela = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

        def montar_linhas():
            comandas = mod_os.buscar_comandas(somente_abertas=filtro_abertas.value)
            if not comandas:
                # Mensagem contextual: distingue "não há nenhuma" de "filtro escondendo".
                if filtro_abertas.value and mod_os.buscar_comandas():
                    msg = ("Nenhuma comanda aberta no momento.\n"
                           "Desmarque \"Somente abertas\" para ver o histórico.")
                else:
                    msg = "Nenhuma comanda registrada. Clique em \"Nova comanda\" para começar."
                return ft.Container(
                    padding=30, alignment=ft.Alignment.CENTER,
                    content=ft.Text(msg, color=ft.Colors.GREY_500,
                                    text_align=ft.TextAlign.CENTER))
            linhas = []
            for c in comandas:
                # Tupla = SELECT de ordem_servico.buscar_comandas() (resumo p/ a lista).
                (ido, cli_nome, placa, status, total, forma, entrada) = c
                linhas.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(f"#{ido}", weight=ft.FontWeight.BOLD)),
                    ft.DataCell(ft.Text(cli_nome or "")),
                    ft.DataCell(ft.Text(placa or "—")),
                    ft.DataCell(badge_status(status)),
                    ft.DataCell(ft.Text(brl(total))),
                    ft.DataCell(ft.Text(dict(FORMAS_PAGAMENTO).get(forma, forma or "—"))),
                    ft.DataCell(ft.Text(fmt_dt(entrada))),
                    ft.DataCell(ft.IconButton(
                        ft.Icons.OPEN_IN_NEW, icon_color=COR_PRIMARIA, tooltip="Abrir comanda",
                        on_click=lambda e, i=ido: abrir_detalhe(i))),
                ]))
            return ft.DataTable(
                expand=True, heading_row_color=ft.Colors.GREY_50,
                columns=[
                    ft.DataColumn(ft.Text("Comanda")),
                    ft.DataColumn(ft.Text("Cliente")),
                    ft.DataColumn(ft.Text("Placa")),
                    ft.DataColumn(ft.Text("Status")),
                    ft.DataColumn(ft.Text("Total")),
                    ft.DataColumn(ft.Text("Pagamento")),
                    ft.DataColumn(ft.Text("Entrada")),
                    ft.DataColumn(ft.Text("")),
                ],
                rows=linhas,
            )

        def atualizar(e=None):
            corpo_tabela.controls = [montar_linhas()]
            page.update()

        filtro_abertas.on_change = atualizar

        # -------- Nova comanda (escolhe o veículo; o cliente vem dele) --------
        def form_nova_comanda():
            veiculos = mod_veic.buscar_veiculos()  # já traz nome do cliente e placa
            dd_vei = ft.Dropdown(
                label="Veículo *", width=440,
                hint_text="Busque pela placa ou cliente", enable_filter=True,
                options=[ft.dropdown.Option(
                    key=str(v[0]),
                    text=f"{v[5]} — {v[2]}" + (f" ({v[7]})" if v[7] else ""))  # placa — cliente (modelo)
                    for v in veiculos])
            erro = ft.Text("", color=ft.Colors.RED_400, size=12)
            if not veiculos:
                erro.value = "Nenhum veículo cadastrado. Cadastre em Veículos primeiro."

            def criar(e):
                # A comanda é aberta pelo VEÍCULO; o cliente é deduzido dele
                # (vinfo[1] = id_cliente), pois todo veículo pertence a um cliente.
                if not dd_vei.value:
                    erro.value = "Selecione o veículo."; page.update(); return
                vinfo = mod_veic.buscar_veiculo_por_id(int(dd_vei.value))
                if not vinfo:
                    erro.value = "Veículo não encontrado."; page.update(); return
                id_cliente = vinfo[1]
                ido = mod_os.abrir_comanda(id_cliente, int(dd_vei.value),
                                           id_funcionario=sessao["id"] or None)
                fechar_dialog()
                if ido:
                    atualizar()
                    abrir_detalhe(ido)
                else:
                    aviso("Erro", "Não foi possível abrir a comanda.")

            abrir_dialog(ft.AlertDialog(
                modal=True, title_padding=0,
                title=cabecalho_dialog("Nova comanda", ft.Icons.RECEIPT_LONG),
                content=ft.Container(width=470, content=ft.Column(tight=True, spacing=12, controls=[
                    ft.Text("Escolha o veículo (o cliente é identificado automaticamente):",
                            size=12, color=ft.Colors.GREY_600),
                    dd_vei, erro,
                ])),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Abrir comanda", on_click=criar,
                                    style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)),
                ],
            ))

        # -------- Painel de detalhe da comanda --------
        def abrir_detalhe(id_ordem):
            # Diálogo grande com TUDO da comanda: dados, itens, mudança de status,
            # valores e pagamento. É reaberto (via refrescar) após cada alteração.
            dados = mod_os.buscar_comanda_por_id(id_ordem)
            if not dados:
                aviso("Erro", "Comanda não encontrada.")
                return
            comanda = dados["comanda"]
            itens = dados["itens"]
            # ⚠️ Aqui a tupla 'comanda' é lida por índices soltos (1,2,5,6,7,8 e 11..16
            # mais abaixo). Esses números seguem a ordem do SELECT em
            # ordem_servico.buscar_comanda_por_id() — confira lá se algo sair errado.
            id_cliente, id_veiculo = comanda[1], comanda[2]
            status, forma, total, entrada = comanda[5], comanda[6], comanda[7], comanda[8]
            avarias_atual = comanda[17]      # vistoria de entrada (danos na chegada)
            obs_atual = comanda[18]          # observações gerais da comanda
            # Comanda entregue/cancelada é "travada": desabilita edição de itens/status.
            finalizada = status in ("entregue", "cancelado")

            cli = mod_cli.buscar_cliente_por_id(id_cliente)
            vei = mod_veic.buscar_veiculo_por_id(id_veiculo)
            cli_nome = cli[1] if cli else "—"
            placa = vei[3] if vei else "—"

            def refrescar():
                fechar_dialog()
                atualizar()
                abrir_detalhe(id_ordem)

            # Itens
            if itens:
                linhas_itens = []
                for (id_item, nome_serv, preco, exec_nome) in itens:
                    # Serviço + quem executou (lavador). Sem responsável fica em laranja
                    # para chamar atenção de que ninguém foi atribuído àquele serviço.
                    col_serv = ft.Column(spacing=0, expand=True, controls=[
                        ft.Text(nome_serv),
                        ft.Text(f"Lavou: {exec_nome}" if exec_nome else "Sem responsável",
                                size=11,
                                color=ft.Colors.GREY_500 if exec_nome else ft.Colors.ORANGE_700),
                    ])
                    linhas_itens.append(ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            col_serv,
                            ft.Text(brl(preco)),
                            ft.IconButton(
                                ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_400,
                                icon_size=18, tooltip="Remover", disabled=finalizada,
                                on_click=lambda e, it=id_item: (mod_os.remover_item(it), refrescar())),
                        ]))
                bloco_itens = ft.Column(linhas_itens, spacing=2)
            else:
                bloco_itens = ft.Text("Nenhum serviço adicionado.", color=ft.Colors.GREY_500,
                                      italic=True)

            # Adicionar serviço
            servicos = mod_serv.buscar_servicos()
            dd_serv = ft.Dropdown(
                label="Adicionar serviço", expand=True,
                options=[ft.dropdown.Option(key=str(s[0]), text=s[1]) for s in servicos])
            # Quem vai lavar: lista de funcionários ativos. Já vem pré-selecionado o
            # usuário logado (o mais comum é quem está no balcão lançar o próprio serviço).
            funcionarios = mod_func.buscar_funcionarios(apenas_ativos=True)
            dd_func = ft.Dropdown(
                label="Quem lavou", width=200,
                value=str(sessao["id"]) if sessao["id"] else None,
                options=[ft.dropdown.Option(key=str(f[0]), text=f[1]) for f in funcionarios])

            def add_serv(e):
                # adicionar_servico devolve None quando o serviço não tem preço para o
                # PORTE deste veículo (a matriz preço×porte não cobre essa combinação).
                # Nesse caso avisamos em vez de adicionar um item sem valor.
                if not dd_serv.value:
                    return
                # Funcionário escolhido no dropdown (cai no logado se nada for selecionado).
                id_func = int(dd_func.value) if dd_func.value else (sessao["id"] or None)
                r = mod_os.adicionar_servico(id_ordem, int(dd_serv.value),
                                             id_funcionario=id_func)
                if r is None:
                    aviso("Sem preço definido",
                          "Esse serviço não tem preço para o porte deste veículo. "
                          "Cadastre o preço no catálogo de serviços.")
                else:
                    refrescar()

            linha_add = ft.Row(spacing=10, controls=[
                dd_serv,
                dd_func,
                ft.FilledButton("Adicionar", icon=ft.Icons.ADD, on_click=add_serv,
                                disabled=finalizada,
                                style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)),
            ])

            # Mudança de status
            def botao_status(rotulo, novo, cor):
                return ft.OutlinedButton(
                    rotulo, disabled=finalizada or status == novo,
                    on_click=lambda e: (mod_os.alterar_status(id_ordem, novo), refrescar()),
                    style=ft.ButtonStyle(color=cor))
            linha_status = ft.Row(wrap=True, spacing=8, controls=[
                botao_status("Em execução", "em_execucao", ft.Colors.BLUE_700),
                botao_status("Finalizado", "finalizado", ft.Colors.GREEN_700),
                botao_status("Entregue", "entregue", ft.Colors.TEAL_700),
                botao_status("Cancelar", "cancelado", ft.Colors.RED_600),
            ])

            # ----- Vistoria de entrada / Observações -----
            # 'avarias' = danos do veículo observados na chegada (protege o lava-jato de
            # reclamação de dano pré-existente). 'observacoes' = anotações gerais.
            f_avarias = ft.TextField(
                label="Avarias na entrada (riscos, amassados, faltando peça...)",
                value=avarias_atual or "", multiline=True, min_lines=2, max_lines=4,
                disabled=finalizada)
            f_obs = ft.TextField(
                label="Observações gerais", value=obs_atual or "",
                multiline=True, min_lines=2, max_lines=3, disabled=finalizada)
            vistoria_msg = ft.Text("", size=12, color=ft.Colors.GREEN_700)

            def salvar_vistoria(e):
                ok = mod_os.salvar_observacoes(
                    id_ordem,
                    avarias=(f_avarias.value or "").strip() or None,
                    observacoes=(f_obs.value or "").strip() or None)
                vistoria_msg.value = "Vistoria salva." if ok else "Não foi possível salvar."
                page.update()

            bloco_vistoria = ft.Column(spacing=8, controls=[
                f_avarias, f_obs,
                ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                    vistoria_msg,
                    ft.OutlinedButton("Salvar vistoria", icon=ft.Icons.FACT_CHECK,
                                      on_click=salvar_vistoria, disabled=finalizada),
                ]),
            ])

            # ----- Financeiro (Valores + Pagamento) -----
            # Valor final = soma dos serviços - desconto + acréscimo/juros.
            total_f = float(total or 0)
            desconto = float(comanda[11] or 0)
            acrescimo = float(comanda[12] or 0)
            parcelas = comanda[13] or 1
            valor_pago = float(comanda[14] or 0)
            data_pag = comanda[15]
            data_venc = comanda[16]
            valor_final = total_f - desconto + acrescimo
            valor_pendente = valor_final - valor_pago
            # Status de pagamento derivado (não vem do banco): a tolerância de 0,005
            # evita marcar "Parcial" por causa de arredondamento de centavos.
            if valor_final <= 0:
                pag_status, pag_cor = "—", ft.Colors.GREY_600
            elif valor_pago >= valor_final - 0.005:
                pag_status, pag_cor = "Pago", ft.Colors.GREEN_700
            elif valor_pago > 0:
                pag_status, pag_cor = "Parcial", ft.Colors.ORANGE_800
            else:
                pag_status, pag_cor = "Pendente", ft.Colors.RED_600

            def form_pagamento(e):
                f_desc = ft.TextField(label="Desconto", width=150, prefix=ft.Text("R$ "),
                                      value=f"{desconto:.2f}".replace('.', ','))
                f_acre = ft.TextField(label="Acréscimo/Juros", width=150, prefix=ft.Text("R$ "),
                                      value=f"{acrescimo:.2f}".replace('.', ','))
                dd_forma = ft.Dropdown(
                    label="Forma de pagamento", width=260, value=forma,
                    options=[ft.dropdown.Option(key=k, text=t) for k, t in FORMAS_PAGAMENTO])
                f_parc = ft.TextField(label="Parcelas", width=110, value=str(parcelas or 1))
                f_pago = ft.TextField(label="Valor pago", width=150, prefix=ft.Text("R$ "),
                                      value=f"{(valor_pago or valor_final):.2f}".replace('.', ','))
                f_dpag = ft.TextField(
                    label="Data pgto (AAAA-MM-DD)", width=210,
                    value=(data_pag.strftime('%Y-%m-%d') if data_pag
                           else datetime.now().strftime('%Y-%m-%d')))
                f_venc = ft.TextField(label="Vencimento (AAAA-MM-DD)", width=210,
                                      value=(data_venc.strftime('%Y-%m-%d') if data_venc else ''))
                erro = ft.Text("", color=ft.Colors.RED_400, size=12)

                def num(campo):
                    # Lê um campo monetário como float (vírgula -> ponto); vazio = 0.0.
                    t = (campo.value or '').strip().replace(',', '.')
                    return float(t) if t else 0.0

                def salvar(e):
                    # Valida números, parcelas (inteiro >= 1) e datas ANTES de gravar.
                    for campo in (f_desc, f_acre, f_pago):
                        t = (campo.value or '').strip().replace(',', '.')
                        if t:
                            try:
                                float(t)
                            except ValueError:
                                erro.value = "Valores devem ser números."; page.update(); return
                    parc_txt = (f_parc.value or '1').strip()
                    if not parc_txt.isdigit() or int(parc_txt) < 1:
                        erro.value = "Parcelas deve ser inteiro maior ou igual a 1."
                        page.update(); return
                    for campo, rot in ((f_dpag, 'Data pgto'), (f_venc, 'Vencimento')):
                        t = (campo.value or '').strip()
                        if t:
                            try:
                                datetime.strptime(t, '%Y-%m-%d')
                            except ValueError:
                                erro.value = f"{rot}: data inválida (AAAA-MM-DD)."
                                page.update(); return
                    mod_os.salvar_financeiro(
                        id_ordem, desconto=num(f_desc), acrescimo=num(f_acre),
                        forma_pagamento=dd_forma.value, parcelas=int(parc_txt),
                        valor_pago=num(f_pago),
                        data_pagamento=(f_dpag.value or '').strip() or None,
                        data_vencimento=(f_venc.value or '').strip() or None)
                    refrescar()

                abrir_dialog(ft.AlertDialog(
                    modal=True, title_padding=0,
                    title=cabecalho_dialog(f"Pagamento — Comanda #{id_ordem}", ft.Icons.PAYMENTS),
                    content=ft.Container(width=500, content=ft.Column(
                        tight=True, spacing=12, scroll=ft.ScrollMode.AUTO, controls=[
                            ft.Text(f"Valor total dos serviços: {brl(total_f)}",
                                    weight=ft.FontWeight.BOLD),
                            ft.Row([f_desc, f_acre], spacing=16),
                            dd_forma,
                            ft.Row([f_parc, f_pago], spacing=16),
                            ft.Row([f_dpag, f_venc], spacing=16),
                            erro,
                        ])),
                    actions=[
                        ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                        ft.FilledButton("Salvar", on_click=salvar,
                                        style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)),
                    ]))

            def gerar_recibo(e):
                pasta = os.path.join(os.path.dirname(__file__), "recibos")
                ctx = {
                    "id_ordem": id_ordem, "cli_nome": cli_nome, "placa": placa,
                    "data": fmt_dt(entrada),
                    "itens": [(nome_serv, exec_nome, preco)
                              for (_i, nome_serv, preco, exec_nome) in itens],
                    "avarias": avarias_atual,
                    "total": total_f, "desconto": desconto, "acrescimo": acrescimo,
                    "valor_final": valor_final,
                    "forma": dict(FORMAS_PAGAMENTO).get(forma, forma or "—"),
                    "parcelas": parcelas or 1,
                    "valor_pago": valor_pago, "valor_pendente": valor_pendente,
                    "pag_status": pag_status,
                    "data_pag": fmt_date(data_pag), "data_venc": fmt_date(data_venc),
                    "logo": os.path.join(os.path.dirname(__file__), "imagen", "trucka car.png"),
                }
                try:
                    os.makedirs(pasta, exist_ok=True)
                    caminho = os.path.join(pasta, f"recibo_comanda_{id_ordem}.pdf")
                    gerar_recibo_pdf(caminho, ctx)
                    try:
                        os.startfile(caminho)  # abre o PDF (Windows)
                    except Exception:
                        pass
                    aviso("Recibo gerado", f"Recibo PDF salvo em:\n{caminho}")
                except Exception as err:
                    # Fallback simples em .txt caso o PDF falhe (ex.: sem reportlab)
                    try:
                        caminho = os.path.join(pasta, f"recibo_comanda_{id_ordem}.txt")
                        with open(caminho, "w", encoding="utf-8") as f:
                            f.write(f"Recibo Comanda #{id_ordem}\nCliente: {cli_nome}\n"
                                    f"Veículo: {placa}\nValor final: {brl(valor_final)}\n"
                                    f"Pago: {brl(valor_pago)} | Pendente: {brl(valor_pendente)}\n"
                                    f"Status: {pag_status}\n")
                        aviso("Recibo gerado (.txt)",
                              f"PDF indisponível ({err}). Salvei em texto:\n{caminho}")
                    except Exception as err2:
                        aviso("Erro", f"Não foi possível gerar o recibo: {err2}")

            def linha_info(rotulo, valor):
                return ft.Row(spacing=8, controls=[
                    ft.Text(f"{rotulo}:", size=13, color=ft.Colors.GREY_600, width=80),
                    ft.Text(valor, size=13, weight=ft.FontWeight.W_500),
                ])

            def linha_val(rotulo, valor_txt, bold=False, cor=None):
                return ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                    ft.Text(rotulo, size=13, color=ft.Colors.GREY_700),
                    ft.Text(valor_txt, size=14 if bold else 13,
                            weight=ft.FontWeight.BOLD if bold else ft.FontWeight.W_500, color=cor)])

            bloco_valores = ft.Column(spacing=4, controls=[
                linha_val("Valor Total", brl(total_f)),
                linha_val("Desconto", brl(desconto)),
                linha_val("Acréscimo/Juros", brl(acrescimo)),
                linha_val("Valor Final", brl(valor_final), bold=True, cor=COR_PRIMARIA),
            ])
            bloco_pagamento = ft.Column(spacing=4, controls=[
                linha_val("Forma Pgto", dict(FORMAS_PAGAMENTO).get(forma, forma or "—")),
                linha_val("Parcelas", str(parcelas or 1)),
                linha_val("Valor Pago", brl(valor_pago)),
                linha_val("Valor Pendente", brl(valor_pendente)),
                linha_val("Status", pag_status, bold=True, cor=pag_cor),
                linha_val("Data Pgto", fmt_date(data_pag)),
                linha_val("Vencimento", fmt_date(data_venc)),
            ])
            botoes_fin = ft.Row(spacing=10, wrap=True, controls=[
                ft.FilledButton("Registrar pgto", icon=ft.Icons.PAYMENTS, on_click=form_pagamento,
                                disabled=status == "cancelado",
                                style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_600)),
                ft.OutlinedButton("Gerar recibo", icon=ft.Icons.RECEIPT_LONG,
                                  on_click=gerar_recibo),
            ])

            conteudo = ft.Container(width=600, content=ft.Column(
                tight=True, spacing=14, scroll=ft.ScrollMode.AUTO, controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                        ft.Column(spacing=4, controls=[
                            linha_info("Cliente", cli_nome),
                            linha_info("Veículo", placa),
                            linha_info("Entrada", fmt_dt(entrada)),
                        ]),
                        ft.Column(horizontal_alignment=ft.CrossAxisAlignment.END, spacing=6,
                                  controls=[badge_status(status),
                                            ft.Text(brl(valor_final), size=22,
                                                    weight=ft.FontWeight.BOLD, color=COR_PRIMARIA)]),
                    ]),
                    ft.Divider(),
                    ft.Text("Serviços", weight=ft.FontWeight.BOLD),
                    bloco_itens,
                    linha_add,
                    ft.Divider(),
                    ft.Text("Status do atendimento", weight=ft.FontWeight.BOLD),
                    linha_status,
                    ft.Divider(),
                    ft.Text("Vistoria de entrada / Observações", weight=ft.FontWeight.BOLD),
                    bloco_vistoria,
                    ft.Divider(),
                    ft.Text("Valores", weight=ft.FontWeight.BOLD),
                    bloco_valores,
                    ft.Divider(),
                    ft.Text("Pagamento", weight=ft.FontWeight.BOLD),
                    bloco_pagamento,
                    botoes_fin,
                ]))

            abrir_dialog(ft.AlertDialog(
                modal=True, title_padding=0,
                title=cabecalho_dialog(f"Comanda #{id_ordem}", ft.Icons.RECEIPT_LONG),
                content=conteudo,
                actions=[ft.TextButton("Fechar", on_click=lambda e: fechar_dialog())],
            ))

        botao_nova = ft.FilledButton(
            "Nova comanda", icon=ft.Icons.ADD, on_click=lambda e: form_nova_comanda(),
            style=ft.ButtonStyle(bgcolor=COR_PRIMARIA))

        corpo_tabela.controls = [montar_linhas()]

        return ft.Column(expand=True, spacing=20, controls=[
            cabecalho("Comandas / Ordens de Serviço",
                      "Abertura, serviços, status e pagamento", acao=botao_nova),
            ft.Row([filtro_abertas], spacing=16),
            card_tabela("Comandas", corpo_tabela),
        ])

    # ============================================================
    # PÁGINA: ESTOQUE (CRUD + entrada/saída + histórico + alerta de mínimo)
    # ============================================================
    def pagina_estoque():
        campo_busca = ft.TextField(
            hint_text="Buscar produto...", expand=True,
            prefix_icon=ft.Icons.SEARCH, height=44)
        mostrar_inativos = ft.Checkbox(label="Incluir inativos", value=False)
        corpo_tabela = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

        def montar_linhas():
            termo = (campo_busca.value or "").strip() or None
            produtos = mod_estoque.buscar_produtos(
                termo=termo, apenas_ativos=not mostrar_inativos.value)
            # Conjunto de ids no vermelho, para marcar cada linha em O(1) (evita
            # consultar "abaixo do mínimo" produto a produto dentro do loop).
            abaixo = {p[0] for p in mod_estoque.produtos_abaixo_minimo()}
            if not produtos:
                return ft.Container(
                    padding=30, alignment=ft.Alignment.CENTER,
                    content=ft.Text("Nenhum produto encontrado.", color=ft.Colors.GREY_500))
            linhas = []
            for p in produtos:
                # Tupla = SELECT de estoque.buscar_produtos().
                (idp, nome, unidade, qtd, minimo, custo, forn_nome, ativo) = p
                critico = idp in abaixo   # True = quantidade <= estoque mínimo
                badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=2), border_radius=20,
                    bgcolor=ft.Colors.GREEN_100 if ativo else ft.Colors.GREY_300,
                    content=ft.Text("Ativo" if ativo else "Inativo", size=11,
                                    color=ft.Colors.GREEN_900 if ativo else ft.Colors.GREY_700))
                if ativo:
                    acao = ft.IconButton(ft.Icons.BLOCK, icon_color=ft.Colors.RED_400,
                                         tooltip="Desativar",
                                         on_click=lambda e, i=idp: confirmar_desativar(i))
                else:
                    acao = ft.IconButton(ft.Icons.RESTORE, icon_color=ft.Colors.GREEN_500,
                                         tooltip="Reativar",
                                         on_click=lambda e, i=idp: (mod_estoque.reativar_produto(i), atualizar()))
                cel_qtd = ft.Row(spacing=6, controls=[
                    ft.Text(qtd_fmt(qtd),
                            color=ft.Colors.RED_600 if critico else None,
                            weight=ft.FontWeight.BOLD if critico else None),
                    ft.Icon(ft.Icons.WARNING_AMBER, color=ft.Colors.RED_500, size=16,
                            tooltip="Abaixo do mínimo") if critico else ft.Container(),
                ])
                linhas.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(idp))),
                    ft.DataCell(ft.Text(nome or "")),
                    ft.DataCell(ft.Text(unidade or "—")),
                    ft.DataCell(cel_qtd),
                    ft.DataCell(ft.Text(qtd_fmt(minimo))),
                    ft.DataCell(ft.Text(brl(custo) if custo is not None else "—")),
                    ft.DataCell(ft.Text(forn_nome or "—")),
                    ft.DataCell(badge),
                    ft.DataCell(ft.Row(spacing=0, controls=[
                        ft.IconButton(ft.Icons.SWAP_VERT, icon_color=COR_ACENTO,
                                      tooltip="Entrada / Saída",
                                      on_click=lambda e, pp=p: form_movimentar(pp)),
                        ft.IconButton(ft.Icons.HISTORY, icon_color=ft.Colors.GREY_600,
                                      tooltip="Histórico",
                                      on_click=lambda e, pp=p: ver_historico(pp)),
                        ft.IconButton(ft.Icons.EDIT, icon_color=COR_PRIMARIA, tooltip="Editar",
                                      on_click=lambda e, pp=p: form_produto(pp)),
                        acao,
                    ])),
                ]))
            return ft.DataTable(
                expand=True, heading_row_color=ft.Colors.GREY_50,
                columns=[
                    ft.DataColumn(ft.Text("ID")),
                    ft.DataColumn(ft.Text("Produto")),
                    ft.DataColumn(ft.Text("Un.")),
                    ft.DataColumn(ft.Text("Quantidade")),
                    ft.DataColumn(ft.Text("Mínimo")),
                    ft.DataColumn(ft.Text("Custo unit.")),
                    ft.DataColumn(ft.Text("Fornecedor")),
                    ft.DataColumn(ft.Text("Status")),
                    ft.DataColumn(ft.Text("Ações")),
                ],
                rows=linhas,
            )

        def atualizar(e=None):
            corpo_tabela.controls = [montar_linhas()]
            page.update()

        campo_busca.on_change = atualizar
        mostrar_inativos.on_change = atualizar

        def confirmar_desativar(idp):
            def sim(e):
                mod_estoque.desativar_produto(idp)
                fechar_dialog()
                atualizar()
            abrir_dialog(ft.AlertDialog(
                modal=True,
                title=ft.Text("Desativar produto"),
                content=ft.Text("Tem certeza? O produto fica inativo, mas o histórico "
                                "é preservado."),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Desativar", on_click=sim,
                                    style=ft.ButtonStyle(bgcolor=ft.Colors.RED_500)),
                ],
            ))

        def form_produto(produto=None):
            editando = produto is not None
            fornecedores = mod_forn.buscar_fornecedores()
            f_nome = ft.TextField(label="Nome *", value=produto[1] if editando else "", width=440)
            f_un = ft.TextField(label="Unidade (L, un, kg...)", width=180,
                                value=(produto[2] or "") if editando else "")
            # Quantidade só é editável na CRIAÇÃO. Depois, o saldo muda apenas via
            # Entrada/Saída (que registram no histórico) — por isso fica desabilitado.
            f_qtd = ft.TextField(label="Quantidade inicial", width=180, value="0",
                                 disabled=editando,
                                 helper=ft.Text("Após criar, use Entrada/Saída") if not editando else None)
            f_min = ft.TextField(label="Estoque mínimo", width=180,
                                 value=(qtd_fmt(produto[4]) if editando else "0"))
            f_custo = ft.TextField(label="Custo unitário", width=180, prefix=ft.Text("R$ "),
                                   value=(f"{float(produto[5]):.2f}".replace('.', ',')
                                          if editando and produto[5] is not None else ""))
            dd_forn = ft.Dropdown(
                label="Fornecedor", width=440,
                options=[ft.dropdown.Option(key="", text="(nenhum)")]
                        + [ft.dropdown.Option(key=str(fo[0]), text=fo[1]) for fo in fornecedores],
                value=str(produto[6]) if editando and produto[6] else "")
            erro_form = ft.Text("", color=ft.Colors.RED_400, size=12)

            def num_or(txt, padrao=None):
                txt = (txt or "").strip().replace(",", ".")
                if not txt:
                    return padrao, True
                try:
                    return float(txt), True
                except ValueError:
                    return None, False

            def salvar(e):
                if not (f_nome.value or "").strip():
                    erro_form.value = "O nome é obrigatório."
                    page.update(); return
                minimo, ok1 = num_or(f_min.value, 0)
                custo, ok2 = num_or(f_custo.value, None)
                if not (ok1 and ok2):
                    erro_form.value = "Mínimo e custo devem ser números."
                    page.update(); return
                id_forn = int(dd_forn.value) if dd_forn.value else None
                if editando:
                    ok = mod_estoque.editar_produto(
                        produto[0], nome=f_nome.value.strip(),
                        unidade_medida=(f_un.value or "").strip() or None,
                        estoque_minimo=minimo, custo_unitario=custo, id_fornecedor=id_forn)
                else:
                    qtd_ini, ok3 = num_or(f_qtd.value, 0)
                    if not ok3:
                        erro_form.value = "Quantidade inicial deve ser um número."
                        page.update(); return
                    ok = mod_estoque.inserir_produto(
                        nome=f_nome.value.strip(),
                        unidade_medida=(f_un.value or "").strip() or None,
                        quantidade=qtd_ini or 0, estoque_minimo=minimo or 0,
                        custo_unitario=custo or 0, id_fornecedor=id_forn) is not None
                fechar_dialog()
                if ok:
                    atualizar()
                else:
                    aviso("Erro", "Não foi possível salvar o produto.")

            abrir_dialog(ft.AlertDialog(
                modal=True, title_padding=0,
                title=cabecalho_dialog("Editar produto" if editando else "Novo produto",
                                       ft.Icons.INVENTORY_2),
                content=ft.Container(width=480, content=ft.Column(tight=True, spacing=12, controls=[
                    f_nome,
                    ft.Row([f_un, f_qtd], spacing=20),
                    ft.Row([f_min, f_custo], spacing=20),
                    dd_forn, erro_form,
                ])),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Salvar", on_click=salvar,
                                    style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)),
                ],
            ))

        def form_movimentar(produto):
            id_produto, nome = produto[0], produto[1]
            saldo_atual = produto[3]
            dd_tipo = ft.Dropdown(
                label="Tipo *", width=180, value="entrada",
                options=[ft.dropdown.Option(key="entrada", text="Entrada"),
                         ft.dropdown.Option(key="saida", text="Saída")])
            f_qtd = ft.TextField(label="Quantidade *", width=180)
            f_obs = ft.TextField(label="Observação", width=380)
            info_saldo = ft.Text(f"Saldo atual: {qtd_fmt(saldo_atual)} {produto[2] or ''}",
                                 size=13, color=ft.Colors.GREY_600)
            erro_form = ft.Text("", color=ft.Colors.RED_400, size=12)

            def salvar(e):
                txt = (f_qtd.value or "").strip().replace(",", ".")
                try:
                    qtd = float(txt)
                except ValueError:
                    erro_form.value = "Quantidade deve ser um número."
                    page.update(); return
                if qtd <= 0:
                    erro_form.value = "Quantidade deve ser maior que zero."
                    page.update(); return
                obs = (f_obs.value or "").strip() or None
                # Entrada soma ao saldo; saída subtrai. registrar_saida devolve None
                # quando não há saldo suficiente (o backend recusa deixar negativo).
                if dd_tipo.value == "entrada":
                    res = mod_estoque.registrar_entrada(id_produto, qtd, obs)
                else:
                    res = mod_estoque.registrar_saida(id_produto, qtd, obs)
                if res is None:
                    if dd_tipo.value == "saida":
                        erro_form.value = "Saldo insuficiente para essa saída."
                    else:
                        erro_form.value = "Não foi possível registrar a movimentação."
                    page.update(); return
                fechar_dialog()
                atualizar()

            abrir_dialog(ft.AlertDialog(
                modal=True, title_padding=0,
                title=cabecalho_dialog(f"Movimentar — {nome}", ft.Icons.SWAP_VERT),
                content=ft.Container(width=420, content=ft.Column(tight=True, spacing=12, controls=[
                    info_saldo,
                    ft.Row([dd_tipo, f_qtd], spacing=20),
                    f_obs, erro_form,
                ])),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Registrar", on_click=salvar,
                                    style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)),
                ],
            ))

        def ver_historico(produto):
            movs = mod_estoque.historico_movimentacoes(produto[0])
            if movs:
                linhas = []
                for (_idm, tipo, qtd, obs, data) in movs:
                    entrada = tipo == "entrada"
                    linhas.append(ft.DataRow(cells=[
                        ft.DataCell(ft.Row(spacing=4, controls=[
                            ft.Icon(ft.Icons.ARROW_DOWNWARD if entrada else ft.Icons.ARROW_UPWARD,
                                    size=16,
                                    color=ft.Colors.GREEN_600 if entrada else ft.Colors.RED_500),
                            ft.Text("Entrada" if entrada else "Saída", size=12),
                        ])),
                        ft.DataCell(ft.Text(qtd_fmt(qtd))),
                        ft.DataCell(ft.Text(obs or "—")),
                        ft.DataCell(ft.Text(fmt_dt(data))),
                    ]))
                corpo = ft.DataTable(
                    heading_row_color=ft.Colors.GREY_50,
                    columns=[ft.DataColumn(ft.Text("Tipo")), ft.DataColumn(ft.Text("Qtd")),
                             ft.DataColumn(ft.Text("Observação")), ft.DataColumn(ft.Text("Data"))],
                    rows=linhas)
            else:
                corpo = ft.Text("Sem movimentações registradas.", color=ft.Colors.GREY_500,
                                italic=True)
            abrir_dialog(ft.AlertDialog(
                modal=True, title_padding=0,
                title=cabecalho_dialog(f"Histórico — {produto[1]}", ft.Icons.HISTORY),
                content=ft.Container(width=560, content=ft.Column(
                    tight=True, scroll=ft.ScrollMode.AUTO, controls=[corpo])),
                actions=[ft.TextButton("Fechar", on_click=lambda e: fechar_dialog())],
            ))

        botao_novo = ft.FilledButton(
            "Novo produto", icon=ft.Icons.ADD, on_click=lambda e: form_produto(),
            style=ft.ButtonStyle(bgcolor=COR_PRIMARIA))

        corpo_tabela.controls = [montar_linhas()]

        return ft.Column(expand=True, spacing=20, controls=[
            cabecalho("Estoque", "Produtos, movimentações e níveis de estoque", acao=botao_novo),
            ft.Row([campo_busca, mostrar_inativos], spacing=16),
            card_tabela("Produtos", corpo_tabela),
        ])

    # ============================================================
    # PÁGINA: VEÍCULOS (CRUD completo)
    # ============================================================
    def pagina_veiculos():
        campo_busca = ft.TextField(
            hint_text="Buscar por placa, modelo ou cliente...", expand=True,
            prefix_icon=ft.Icons.SEARCH, height=44,
        )
        mostrar_inativos = ft.Checkbox(label="Incluir inativos", value=False)
        corpo_tabela = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

        def montar_linhas():
            termo = (campo_busca.value or "").strip() or None
            veiculos = mod_veic.buscar_veiculos(
                termo=termo, apenas_ativos=not mostrar_inativos.value)
            if not veiculos:
                return ft.Container(
                    padding=30, alignment=ft.Alignment.CENTER,
                    content=ft.Text("Nenhum veículo encontrado.", color=ft.Colors.GREY_500))
            linhas = []
            for v in veiculos:
                # Tupla = SELECT de cadastro_veiculo.buscar_veiculos() (já traz o nome
                # do cliente e o nome do porte via JOIN, além dos ids idc/idcat).
                (idv, idc, cli_nome, idcat, cat_nome, placa, marca, modelo, ano, cor, ativo) = v
                badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=2), border_radius=20,
                    bgcolor=ft.Colors.GREEN_100 if ativo else ft.Colors.GREY_300,
                    content=ft.Text("Ativo" if ativo else "Inativo", size=11,
                                    color=ft.Colors.GREEN_900 if ativo else ft.Colors.GREY_700),
                )
                if ativo:
                    acao = ft.IconButton(ft.Icons.BLOCK, icon_color=ft.Colors.RED_400,
                                         tooltip="Desativar",
                                         on_click=lambda e, i=idv: confirmar_desativar(i))
                else:
                    acao = ft.IconButton(ft.Icons.RESTORE, icon_color=ft.Colors.GREEN_500,
                                         tooltip="Reativar",
                                         on_click=lambda e, i=idv: (mod_veic.reativar_veiculo(i), atualizar()))
                veiculo_desc = " ".join(p for p in [marca, modelo] if p) or "—"
                linhas.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(placa or "")),
                    ft.DataCell(ft.Text(cli_nome or "")),
                    ft.DataCell(ft.Text(cat_nome or "—")),
                    ft.DataCell(ft.Text(veiculo_desc)),
                    ft.DataCell(ft.Text(str(ano) if ano else "—")),
                    ft.DataCell(ft.Text(cor or "—")),
                    ft.DataCell(badge),
                    ft.DataCell(ft.Row(spacing=0, controls=[
                        ft.IconButton(ft.Icons.HISTORY, icon_color=ft.Colors.GREY_600,
                                      tooltip="Histórico de serviços",
                                      on_click=lambda e, vv=v: ver_historico(vv)),
                        ft.IconButton(ft.Icons.EDIT, icon_color=COR_PRIMARIA, tooltip="Editar",
                                      on_click=lambda e, vv=v: form_veiculo(vv)),
                        acao,
                    ])),
                ]))
            return ft.DataTable(
                expand=True,
                heading_row_color=ft.Colors.GREY_50,
                columns=[
                    ft.DataColumn(ft.Text("Placa")),
                    ft.DataColumn(ft.Text("Cliente")),
                    ft.DataColumn(ft.Text("Porte")),
                    ft.DataColumn(ft.Text("Veículo")),
                    ft.DataColumn(ft.Text("Ano")),
                    ft.DataColumn(ft.Text("Cor")),
                    ft.DataColumn(ft.Text("Status")),
                    ft.DataColumn(ft.Text("Ações")),
                ],
                rows=linhas,
            )

        def atualizar(e=None):
            corpo_tabela.controls = [montar_linhas()]
            page.update()

        campo_busca.on_change = atualizar
        mostrar_inativos.on_change = atualizar

        def confirmar_desativar(idv):
            def sim(e):
                mod_veic.desativar_veiculo(idv)
                fechar_dialog()
                atualizar()
            abrir_dialog(ft.AlertDialog(
                modal=True,
                title=ft.Text("Desativar veículo"),
                content=ft.Text("Tem certeza? O veículo fica inativo, mas o histórico é preservado."),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Desativar", on_click=sim,
                                    style=ft.ButtonStyle(bgcolor=ft.Colors.RED_500)),
                ],
            ))

        def ver_historico(veiculo):
            (idv, idc, cli_nome, idcat, cat_nome, placa, marca, modelo, ano, cor, ativo) = veiculo
            comandas = mod_os.buscar_comandas(id_veiculo=idv)
            veiculo_desc = " ".join(p for p in [marca, modelo] if p) or "—"

            if not comandas:
                lista = ft.Container(
                    content=ft.Text("Nenhuma comanda registrada para este veículo ainda.",
                                    color=ft.Colors.GREY_500))
            else:
                linhas_hist = []
                for c in comandas:
                    (ido, _cli_nome, _placa, status, total, forma, entrada) = c
                    linhas_hist.append(ft.DataRow(cells=[
                        ft.DataCell(ft.Text(f"#{ido}", weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(fmt_dt(entrada))),
                        ft.DataCell(badge_status(status)),
                        ft.DataCell(ft.Text(brl(total))),
                        ft.DataCell(ft.Text(dict(FORMAS_PAGAMENTO).get(forma, forma or "—"))),
                    ]))
                tabela_hist = ft.DataTable(
                    heading_row_color=ft.Colors.GREY_50,
                    columns=[
                        ft.DataColumn(ft.Text("Comanda")),
                        ft.DataColumn(ft.Text("Entrada")),
                        ft.DataColumn(ft.Text("Status")),
                        ft.DataColumn(ft.Text("Total")),
                        ft.DataColumn(ft.Text("Pagamento")),
                    ],
                    rows=linhas_hist,
                )
                lista = ft.Container(
                    height=320,
                    content=ft.Column([tabela_hist], scroll=ft.ScrollMode.AUTO))

            abrir_dialog(ft.AlertDialog(
                modal=True,
                title_padding=0,
                title=cabecalho_dialog(f"Histórico — {placa}", ft.Icons.HISTORY),
                content=ft.Container(width=560, content=ft.Column(tight=True, spacing=12, controls=[
                    ft.Text(f"{cli_nome} — {veiculo_desc}", size=13, color=ft.Colors.GREY_700),
                    ft.Text(
                        f"{len(comandas)} visita" + ("s" if len(comandas) != 1 else "")
                        + " na lavação",
                        size=14, weight=ft.FontWeight.BOLD, color=COR_PRIMARIA),
                    ft.Container(content=lista, height=320 if comandas else None,
                                 padding=ft.Padding.only(top=4)),
                ])),
                actions=[
                    ft.TextButton("Fechar", on_click=lambda e: fechar_dialog()),
                ],
            ))

        def form_veiculo(veiculo=None):
            editando = veiculo is not None
            clientes = mod_cli.buscar_clientes()
            categorias = mod_veic.listar_categorias()

            dd_cliente = ft.Dropdown(
                label="Cliente *", width=420,
                options=[ft.dropdown.Option(key=str(c[0]), text=c[1]) for c in clientes],
                value=str(veiculo[1]) if editando else None,
            )
            dd_categoria = ft.Dropdown(
                label="Porte *", width=200,
                options=[ft.dropdown.Option(key=str(cat[0]), text=cat[1]) for cat in categorias],
                value=str(veiculo[3]) if editando else None,
            )
            f_placa = ft.TextField(label="Placa *", value=veiculo[5] if editando else "", width=200)
            f_marca = ft.TextField(label="Marca", value=(veiculo[6] or "") if editando else "", width=200)
            f_modelo = ft.TextField(label="Modelo", value=(veiculo[7] or "") if editando else "", width=200)
            f_ano = ft.TextField(label="Ano", width=120,
                                 value=(str(veiculo[8]) if editando and veiculo[8] else ""))
            f_cor = ft.TextField(label="Cor", value=(veiculo[9] or "") if editando else "", width=200)
            erro_form = ft.Text("", color=ft.Colors.RED_400, size=12)

            def salvar(e):
                if not dd_cliente.value:
                    erro_form.value = "Selecione o cliente."
                    page.update(); return
                if not dd_categoria.value:
                    erro_form.value = "Selecione o porte."
                    page.update(); return
                if not (f_placa.value or "").strip():
                    erro_form.value = "A placa é obrigatória."
                    page.update(); return
                ano_txt = (f_ano.value or "").strip()
                if ano_txt and not ano_txt.isdigit():
                    erro_form.value = "Ano deve ser um número (ex.: 2015)."
                    page.update(); return
                ano_val = int(ano_txt) if ano_txt else None
                vals = dict(
                    id_cliente=int(dd_cliente.value),
                    id_categoria=int(dd_categoria.value),
                    placa=f_placa.value.strip().upper(),
                    marca=(f_marca.value or "").strip() or None,
                    modelo=(f_modelo.value or "").strip() or None,
                    ano=ano_val,
                    cor=(f_cor.value or "").strip() or None,
                )
                if editando:
                    ok = mod_veic.editar_veiculo(veiculo[0], **vals)
                else:
                    ok = mod_veic.inserir_veiculo(**vals) is not None
                fechar_dialog()
                if ok:
                    atualizar()
                else:
                    aviso("Erro", "Não foi possível salvar. Verifique a conexão com o banco.")

            abrir_dialog(ft.AlertDialog(
                modal=True,
                title_padding=0,
                title=cabecalho_dialog(
                    "Editar veículo" if editando else "Novo veículo",
                    ft.Icons.DIRECTIONS_CAR),
                content=ft.Container(width=460, content=ft.Column(tight=True, spacing=12, controls=[
                    dd_cliente,
                    ft.Row([dd_categoria, f_placa], spacing=20),
                    ft.Row([f_marca, f_modelo], spacing=20),
                    ft.Row([f_ano, f_cor], spacing=20),
                    erro_form,
                ])),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Salvar", on_click=salvar,
                                    style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)),
                ],
            ))

        botao_novo = ft.FilledButton(
            "Novo veículo", icon=ft.Icons.ADD, on_click=lambda e: form_veiculo(),
            style=ft.ButtonStyle(bgcolor=COR_PRIMARIA))

        corpo_tabela.controls = [montar_linhas()]

        return ft.Column(expand=True, spacing=20, controls=[
            cabecalho("Veículos", "Cadastro de veículos por cliente e porte", acao=botao_novo),
            ft.Row([campo_busca, mostrar_inativos], spacing=16),
            card_tabela("Lista de veículos", corpo_tabela),
        ])

    # ============================================================
    # PÁGINA: AGENDAMENTOS (CRUD + conflito de box + virar comanda)
    # ============================================================
    CORES_STATUS_AG = {
        "agendado": (ft.Colors.BLUE_100, ft.Colors.BLUE_900),
        "confirmado": (ft.Colors.GREEN_100, ft.Colors.GREEN_900),
        "em_espera": (ft.Colors.AMBER_100, ft.Colors.AMBER_900),
        "em_execucao": (ft.Colors.CYAN_100, ft.Colors.CYAN_900),
        "concluido": (ft.Colors.TEAL_100, ft.Colors.TEAL_900),
        "cancelado": (ft.Colors.RED_100, ft.Colors.RED_900),
        "nao_compareceu": (ft.Colors.GREY_400, ft.Colors.GREY_900),
    }
    ORIGENS = [("manual", "Manual"), ("whatsapp", "WhatsApp"),
               ("telefone", "Telefone"), ("app", "App")]

    def badge_status_ag(status):
        status = status or ""
        bg, fg = CORES_STATUS_AG.get(status, (ft.Colors.GREY_200, ft.Colors.GREY_800))
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=3), border_radius=20,
            bgcolor=bg,
            content=ft.Text(status.replace("_", " ").capitalize(), size=11, color=fg,
                            weight=ft.FontWeight.W_600))

    def pagina_agendamentos():
        f_filtro_data = ft.TextField(
            label="Filtrar por data (AAAA-MM-DD)", width=240, hint_text="vazio = todas")
        corpo_tabela = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

        def montar_linhas():
            data = (f_filtro_data.value or "").strip() or None
            ags = mod_ag.buscar_agendamentos(data=data)
            if not ags:
                return ft.Container(
                    padding=30, alignment=ft.Alignment.CENTER,
                    content=ft.Text("Nenhum agendamento encontrado.", color=ft.Colors.GREY_500))
            linhas = []
            for a in ags:
                # Tupla = SELECT de agendamento.buscar_agendamentos().
                (ida, data_hora, cli_nome, placa, dur, box, status, origem) = a
                linhas.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(fmt_dt(data_hora), weight=ft.FontWeight.W_600)),
                    ft.DataCell(ft.Text(cli_nome or "")),
                    ft.DataCell(ft.Text(placa or "—")),
                    ft.DataCell(ft.Text(box or "—")),
                    ft.DataCell(ft.Text(f"{dur} min" if dur else "—")),
                    ft.DataCell(badge_status_ag(status)),
                    ft.DataCell(ft.Text(dict(ORIGENS).get(origem, origem or "—"))),
                    ft.DataCell(ft.IconButton(
                        ft.Icons.OPEN_IN_NEW, icon_color=COR_PRIMARIA, tooltip="Abrir",
                        on_click=lambda e, i=ida: abrir_detalhe(i))),
                ]))
            return ft.DataTable(
                expand=True, heading_row_color=ft.Colors.GREY_50,
                columns=[
                    ft.DataColumn(ft.Text("Data / Hora")),
                    ft.DataColumn(ft.Text("Cliente")),
                    ft.DataColumn(ft.Text("Placa")),
                    ft.DataColumn(ft.Text("Box")),
                    ft.DataColumn(ft.Text("Duração")),
                    ft.DataColumn(ft.Text("Status")),
                    ft.DataColumn(ft.Text("Origem")),
                    ft.DataColumn(ft.Text("")),
                ],
                rows=linhas,
            )

        def atualizar(e=None):
            corpo_tabela.controls = [montar_linhas()]
            page.update()

        f_filtro_data.on_change = atualizar

        # ---- Novo agendamento ----
        def form_novo():
            veiculos = mod_veic.buscar_veiculos()  # traz nome do cliente e placa
            dd_vei = ft.Dropdown(
                label="Veículo *", expand=True,
                hint_text="Busque pela placa ou cliente", enable_filter=True,
                options=[ft.dropdown.Option(
                    key=str(v[0]),
                    text=f"{v[5]} — {v[2]}" + (f" ({v[7]})" if v[7] else ""))  # placa — cliente (modelo)
                    for v in veiculos])
            hoje = datetime.now().strftime("%Y-%m-%d")
            f_data = ft.TextField(label="Data (AAAA-MM-DD) *", value=hoje, width=200)
            f_hora = ft.TextField(label="Hora (HH:MM) *", value="09:00", width=140)
            f_dur = ft.TextField(label="Duração (min)", width=140)
            f_box = ft.TextField(label="Box", width=120)
            dd_origem = ft.Dropdown(
                label="Origem", width=200, value="manual",
                options=[ft.dropdown.Option(key=k, text=t) for k, t in ORIGENS])
            f_obs = ft.TextField(label="Observações", multiline=True, min_lines=2, max_lines=3)

            servicos = mod_serv.buscar_servicos()
            chk_servicos = [(s[0], ft.Checkbox(label=s[1])) for s in servicos]
            bloco_serv = ft.Container(
                height=120, border=ft.Border.all(1, ft.Colors.GREY_300), border_radius=8,
                padding=8,
                content=ft.Column(
                    [c for _, c in chk_servicos] or [ft.Text("Nenhum serviço no catálogo.",
                                                             color=ft.Colors.GREY_500)],
                    scroll=ft.ScrollMode.AUTO, spacing=0))
            erro = ft.Text("", color=ft.Colors.RED_400, size=12)

            def salvar(e):
                if not dd_vei.value:
                    erro.value = "Selecione o veículo."; page.update(); return
                vinfo = mod_veic.buscar_veiculo_por_id(int(dd_vei.value))
                id_cliente_sel = vinfo[1] if vinfo else None
                if not id_cliente_sel:
                    erro.value = "Veículo inválido."; page.update(); return
                data_txt = (f_data.value or "").strip()
                hora_txt = (f_hora.value or "").strip()
                try:
                    quando = datetime.strptime(f"{data_txt} {hora_txt}", "%Y-%m-%d %H:%M")
                except ValueError:
                    erro.value = "Data/hora inválida. Use AAAA-MM-DD e HH:MM."
                    page.update(); return
                dur_txt = (f_dur.value or "").strip()
                if dur_txt and not dur_txt.isdigit():
                    erro.value = "Duração deve ser um número (minutos)."
                    page.update(); return
                dur_val = int(dur_txt) if dur_txt else None
                box = (f_box.value or "").strip() or None
                escolhidos = [sid for sid, c in chk_servicos if c.value]

                # Checagem de conflito amigável (antes de tentar gravar): só faz sentido
                # se um box foi informado — dois carros não podem ocupar o mesmo box no
                # mesmo horário. O backend também valida, mas aqui damos erro mais claro.
                if box:
                    conflitos = mod_ag.verificar_conflito(
                        quando.strftime("%Y-%m-%d %H:%M:%S"), dur_val, box)
                    if conflitos:
                        erro.value = (f"Conflito no box {box}: já há agendamento "
                                      f"nesse horário (#{conflitos[0][0]}).")
                        page.update(); return

                novo = mod_ag.criar_agendamento(
                    id_cliente=id_cliente_sel, id_veiculo=int(dd_vei.value),
                    data_hora=quando.strftime("%Y-%m-%d %H:%M:%S"),
                    servicos=escolhidos, duracao_estimada_min=dur_val, box=box,
                    origem=dd_origem.value or "manual",
                    observacoes=(f_obs.value or "").strip() or None)
                fechar_dialog()
                if novo:
                    atualizar()
                    abrir_detalhe(novo)
                else:
                    aviso("Erro", "Não foi possível criar o agendamento.")

            abrir_dialog(ft.AlertDialog(
                modal=True, title_padding=0,
                title=cabecalho_dialog("Novo agendamento", ft.Icons.EVENT),
                content=ft.Container(width=520, content=ft.Column(
                    tight=True, spacing=12, scroll=ft.ScrollMode.AUTO, controls=[
                        dd_vei,
                        ft.Row([f_data, f_hora, f_dur], spacing=12),
                        ft.Row([f_box, dd_origem], spacing=12),
                        ft.Text("Serviços desejados", size=13, color=ft.Colors.GREY_600),
                        bloco_serv,
                        f_obs, erro,
                    ])),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Agendar", on_click=salvar,
                                    style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)),
                ],
            ))

        # ---- Remarcar ----
        def form_remarcar(id_ag, atual):
            data_atual = atual[3]
            f_data = ft.TextField(label="Nova data (AAAA-MM-DD) *", width=200,
                                  value=data_atual.strftime("%Y-%m-%d") if data_atual else "")
            f_hora = ft.TextField(label="Nova hora (HH:MM) *", width=140,
                                  value=data_atual.strftime("%H:%M") if data_atual else "")
            f_box = ft.TextField(label="Box", width=120, value=atual[5] or "")
            f_dur = ft.TextField(label="Duração (min)", width=140,
                                 value=str(atual[4]) if atual[4] else "")
            erro = ft.Text("", color=ft.Colors.RED_400, size=12)

            def salvar(e):
                try:
                    quando = datetime.strptime(
                        f"{(f_data.value or '').strip()} {(f_hora.value or '').strip()}",
                        "%Y-%m-%d %H:%M")
                except ValueError:
                    erro.value = "Data/hora inválida."; page.update(); return
                dur_txt = (f_dur.value or "").strip()
                dur_val = int(dur_txt) if dur_txt.isdigit() else None
                ok = mod_ag.remarcar(
                    id_ag, quando.strftime("%Y-%m-%d %H:%M:%S"),
                    novo_box=(f_box.value or "").strip() or None, nova_duracao_min=dur_val)
                fechar_dialog()
                if ok:
                    atualizar(); abrir_detalhe(id_ag)
                else:
                    aviso("Não remarcado",
                          "Pode haver conflito de horário no box, ou erro de dados.")

            abrir_dialog(ft.AlertDialog(
                modal=True, title_padding=0,
                title=cabecalho_dialog("Remarcar", ft.Icons.EDIT_CALENDAR),
                content=ft.Container(width=480, content=ft.Column(tight=True, spacing=12, controls=[
                    ft.Row([f_data, f_hora], spacing=12),
                    ft.Row([f_box, f_dur], spacing=12),
                    erro,
                ])),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: (fechar_dialog(), abrir_detalhe(id_ag))),
                    ft.FilledButton("Remarcar", on_click=salvar,
                                    style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)),
                ],
            ))

        # ---- Detalhe do agendamento ----
        def abrir_detalhe(id_ag):
            dados = mod_ag.buscar_agendamento_por_id(id_ag)
            if not dados:
                aviso("Erro", "Agendamento não encontrado.")
                return
            ag = dados["agendamento"]
            servicos = dados["servicos"]
            # Tupla = SELECT de agendamento.buscar_agendamento_por_id() (linha "agendamento").
            (ida, id_cliente, id_veiculo, data_hora, dur, box, status, origem, obs) = ag
            # Estados terminais: desabilitam status/remarcar/cancelar no detalhe.
            encerrado = status in ("concluido", "cancelado", "nao_compareceu")

            cli = mod_cli.buscar_cliente_por_id(id_cliente)
            vei = mod_veic.buscar_veiculo_por_id(id_veiculo)
            cli_nome = cli[1] if cli else "—"
            placa = vei[3] if vei else "—"

            def refrescar():
                fechar_dialog(); atualizar(); abrir_detalhe(id_ag)

            def linha_info(rotulo, valor):
                return ft.Row(spacing=8, controls=[
                    ft.Text(f"{rotulo}:", size=13, color=ft.Colors.GREY_600, width=90),
                    ft.Text(valor, size=13, weight=ft.FontWeight.W_500, expand=True),
                ])

            if servicos:
                bloco_serv = ft.Column(
                    [ft.Text(f"• {nome}", size=13) for _, nome in servicos], spacing=2)
            else:
                bloco_serv = ft.Text("Nenhum serviço informado.", color=ft.Colors.GREY_500,
                                     italic=True, size=13)

            def botao_status(rotulo, novo, cor):
                return ft.OutlinedButton(
                    rotulo, disabled=encerrado or status == novo,
                    on_click=lambda e: (mod_ag.alterar_status(id_ag, novo), refrescar()),
                    style=ft.ButtonStyle(color=cor))

            linha_status = ft.Row(wrap=True, spacing=8, controls=[
                botao_status("Confirmar", "confirmado", ft.Colors.GREEN_700),
                botao_status("Em espera", "em_espera", ft.Colors.AMBER_800),
                botao_status("Em execução", "em_execucao", ft.Colors.CYAN_800),
                botao_status("Concluído", "concluido", ft.Colors.TEAL_700),
            ])
            linha_acoes = ft.Row(wrap=True, spacing=8, controls=[
                ft.OutlinedButton("Remarcar", icon=ft.Icons.EDIT_CALENDAR, disabled=encerrado,
                                  on_click=lambda e: (fechar_dialog(), form_remarcar(id_ag, ag))),
                ft.OutlinedButton("Cancelar agend.", icon=ft.Icons.CANCEL, disabled=encerrado,
                                  on_click=lambda e: (mod_ag.cancelar_agendamento(id_ag), refrescar()),
                                  style=ft.ButtonStyle(color=ft.Colors.RED_600)),
                ft.OutlinedButton("Não compareceu", icon=ft.Icons.PERSON_OFF, disabled=encerrado,
                                  on_click=lambda e: (mod_ag.registrar_nao_comparecimento(id_ag), refrescar()),
                                  style=ft.ButtonStyle(color=ft.Colors.GREY_700)),
            ])

            def gerar_comanda(e):
                # Converte o agendamento em comanda (leva cliente, veículo e serviços
                # desejados). É a "ponte" entre a agenda e o atendimento em Comandas.
                ido = mod_os.abrir_de_agendamento(id_ag, id_funcionario=sessao["id"] or None)
                if ido:
                    fechar_dialog(); atualizar()
                    aviso("Comanda gerada",
                          f"Comanda #{ido} criada a partir deste agendamento. "
                          f"Veja na tela de Comandas.")
                else:
                    aviso("Erro", "Não foi possível gerar a comanda.")

            conteudo = ft.Container(width=560, content=ft.Column(
                tight=True, spacing=12, scroll=ft.ScrollMode.AUTO, controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                        ft.Text(fmt_dt(data_hora), size=18, weight=ft.FontWeight.BOLD,
                                color=COR_PRIMARIA),
                        badge_status_ag(status),
                    ]),
                    linha_info("Cliente", cli_nome),
                    linha_info("Veículo", placa),
                    linha_info("Box", box or "—"),
                    linha_info("Duração", f"{dur} min" if dur else "—"),
                    linha_info("Origem", dict(ORIGENS).get(origem, origem or "—")),
                    linha_info("Observações", obs or "—"),
                    ft.Divider(),
                    ft.Text("Serviços desejados", weight=ft.FontWeight.BOLD),
                    bloco_serv,
                    ft.Divider(),
                    ft.Text("Status", weight=ft.FontWeight.BOLD),
                    linha_status,
                    ft.Divider(),
                    ft.Text("Ações", weight=ft.FontWeight.BOLD),
                    linha_acoes,
                    ft.FilledButton("Gerar comanda", icon=ft.Icons.RECEIPT_LONG,
                                    disabled=encerrado, on_click=gerar_comanda,
                                    style=ft.ButtonStyle(bgcolor=COR_ACENTO)),
                ]))

            abrir_dialog(ft.AlertDialog(
                modal=True, title_padding=0,
                title=cabecalho_dialog(f"Agendamento #{id_ag}", ft.Icons.EVENT),
                content=conteudo,
                actions=[ft.TextButton("Fechar", on_click=lambda e: fechar_dialog())],
            ))

        botao_novo = ft.FilledButton(
            "Novo agendamento", icon=ft.Icons.ADD, on_click=lambda e: form_novo(),
            style=ft.ButtonStyle(bgcolor=COR_PRIMARIA))

        corpo_tabela.controls = [montar_linhas()]

        return ft.Column(expand=True, spacing=20, controls=[
            cabecalho("Agendamentos", "Agenda por data, box e serviços", acao=botao_novo),
            ft.Row([f_filtro_data], spacing=16),
            card_tabela("Agendamentos", corpo_tabela),
        ])

    # ============================================================
    # PÁGINA: FUNCIONÁRIOS (CRUD + senha + ativar/desativar)
    # ============================================================
    FUNCOES = [("lavador", "Lavador"), ("caixa", "Caixa"), ("gerente", "Gerente")]
    CORES_FUNCAO = {
        "lavador": (ft.Colors.TEAL_100, ft.Colors.TEAL_900),
        "caixa": (ft.Colors.BLUE_100, ft.Colors.BLUE_900),
        "gerente": (ft.Colors.PURPLE_100, ft.Colors.PURPLE_900),
    }

    def badge_funcao(funcao):
        bg, fg = CORES_FUNCAO.get(funcao, (ft.Colors.GREY_200, ft.Colors.GREY_800))
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=3), border_radius=20, bgcolor=bg,
            content=ft.Text(dict(FUNCOES).get(funcao, funcao or ""), size=11, color=fg,
                            weight=ft.FontWeight.W_600))

    def pagina_funcionarios():
        campo_busca = ft.TextField(
            hint_text="Buscar por nome...", expand=True,
            prefix_icon=ft.Icons.SEARCH, height=44)
        dd_filtro_funcao = ft.Dropdown(
            label="Função", width=180,
            options=[ft.dropdown.Option(key="", text="Todas")]
                    + [ft.dropdown.Option(key=k, text=t) for k, t in FUNCOES],
            value="")
        mostrar_inativos = ft.Checkbox(label="Incluir inativos", value=False)
        corpo_tabela = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

        def montar_linhas():
            termo = (campo_busca.value or "").strip() or None
            funcao = (dd_filtro_funcao.value or "") or None
            funcs = mod_func.buscar_funcionarios(
                termo=termo, funcao=funcao, apenas_ativos=not mostrar_inativos.value)
            if not funcs:
                return ft.Container(
                    padding=30, alignment=ft.Alignment.CENTER,
                    content=ft.Text("Nenhum funcionário encontrado.", color=ft.Colors.GREY_500))
            linhas = []
            for f in funcs:
                # Tupla = SELECT de funcionario.buscar_funcionarios(). NÃO traz a
                # senha_hash — senha nunca circula na interface (só se define/troca).
                (idf, nome, funcao_v, login, comissao, data_adm, ativo) = f
                badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=2), border_radius=20,
                    bgcolor=ft.Colors.GREEN_100 if ativo else ft.Colors.GREY_300,
                    content=ft.Text("Ativo" if ativo else "Inativo", size=11,
                                    color=ft.Colors.GREEN_900 if ativo else ft.Colors.GREY_700))
                if ativo:
                    acao = ft.IconButton(ft.Icons.BLOCK, icon_color=ft.Colors.RED_400,
                                         tooltip="Desativar",
                                         on_click=lambda e, i=idf: confirmar_desativar(i))
                else:
                    acao = ft.IconButton(ft.Icons.RESTORE, icon_color=ft.Colors.GREEN_500,
                                         tooltip="Reativar",
                                         on_click=lambda e, i=idf: (mod_func.reativar_funcionario(i), atualizar()))
                comissao_txt = (f"{float(comissao):g}%" if comissao is not None else "—")
                linhas.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(idf))),
                    ft.DataCell(ft.Text(nome or "")),
                    ft.DataCell(badge_funcao(funcao_v)),
                    ft.DataCell(ft.Text(login or "—")),
                    ft.DataCell(ft.Text(comissao_txt)),
                    ft.DataCell(ft.Text(fmt_date(data_adm))),
                    ft.DataCell(badge),
                    ft.DataCell(ft.Row(spacing=0, controls=[
                        ft.IconButton(ft.Icons.PASSWORD, icon_color=COR_ACENTO,
                                      tooltip="Alterar senha",
                                      on_click=lambda e, ff=f: form_senha(ff)),
                        ft.IconButton(ft.Icons.EDIT, icon_color=COR_PRIMARIA, tooltip="Editar",
                                      on_click=lambda e, ff=f: form_funcionario(ff)),
                        acao,
                    ])),
                ]))
            return ft.DataTable(
                expand=True, heading_row_color=ft.Colors.GREY_50,
                columns=[
                    ft.DataColumn(ft.Text("ID")),
                    ft.DataColumn(ft.Text("Nome")),
                    ft.DataColumn(ft.Text("Função")),
                    ft.DataColumn(ft.Text("Login")),
                    ft.DataColumn(ft.Text("Comissão")),
                    ft.DataColumn(ft.Text("Admissão")),
                    ft.DataColumn(ft.Text("Status")),
                    ft.DataColumn(ft.Text("Ações")),
                ],
                rows=linhas,
            )

        def atualizar(e=None):
            corpo_tabela.controls = [montar_linhas()]
            page.update()

        campo_busca.on_change = atualizar
        dd_filtro_funcao.on_change = atualizar
        mostrar_inativos.on_change = atualizar

        def confirmar_desativar(idf):
            def sim(e):
                mod_func.desativar_funcionario(idf)
                fechar_dialog()
                atualizar()
            abrir_dialog(ft.AlertDialog(
                modal=True,
                title=ft.Text("Desativar funcionário"),
                content=ft.Text("Tem certeza? O funcionário fica inativo e não consegue "
                                "mais fazer login, mas o histórico é preservado."),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Desativar", on_click=sim,
                                    style=ft.ButtonStyle(bgcolor=ft.Colors.RED_500)),
                ],
            ))

        def form_funcionario(func=None):
            editando = func is not None
            f_nome = ft.TextField(label="Nome *", value=func[1] if editando else "", width=420)
            dd_funcao = ft.Dropdown(
                label="Função *", width=200, value=func[2] if editando else "lavador",
                options=[ft.dropdown.Option(key=k, text=t) for k, t in FUNCOES])
            f_login = ft.TextField(label="Login", value=(func[3] or "") if editando else "", width=200)
            f_comissao = ft.TextField(
                label="Comissão (%)", width=160,
                value=(f"{float(func[4]):g}" if editando and func[4] is not None else ""))
            f_adm = ft.TextField(
                label="Admissão (AAAA-MM-DD)", width=220,
                value=(func[5].strftime("%Y-%m-%d") if editando and func[5] else ""))
            f_senha = ft.TextField(label="Senha", width=220, password=True,
                                   can_reveal_password=True)
            erro_form = ft.Text("", color=ft.Colors.RED_400, size=12)

            def salvar(e):
                if not (f_nome.value or "").strip():
                    erro_form.value = "O nome é obrigatório."
                    page.update(); return
                comissao_txt = (f_comissao.value or "").strip().replace(",", ".")
                if comissao_txt:
                    try:
                        comissao_val = float(comissao_txt)
                    except ValueError:
                        erro_form.value = "Comissão deve ser um número (ex.: 5)."
                        page.update(); return
                else:
                    comissao_val = None
                adm_txt = (f_adm.value or "").strip()
                if adm_txt:
                    try:
                        datetime.strptime(adm_txt, "%Y-%m-%d")
                    except ValueError:
                        erro_form.value = "Data de admissão inválida (use AAAA-MM-DD)."
                        page.update(); return
                login = (f_login.value or "").strip() or None
                if editando:
                    ok = mod_func.editar_funcionario(
                        func[0], nome=f_nome.value.strip(), funcao=dd_funcao.value,
                        login=login, comissao_percentual=comissao_val,
                        data_admissao=adm_txt or None)
                else:
                    ok = mod_func.inserir_funcionario(
                        nome=f_nome.value.strip(), funcao=dd_funcao.value, login=login,
                        senha=(f_senha.value or "") or None,
                        comissao_percentual=comissao_val if comissao_val is not None else 0,
                        data_admissao=adm_txt or None) is not None
                fechar_dialog()
                if ok:
                    atualizar()
                else:
                    aviso("Erro", "Não foi possível salvar. O login pode já estar em uso.")

            campos = [
                f_nome,
                ft.Row([dd_funcao, f_login], spacing=20),
                ft.Row([f_comissao, f_adm], spacing=20),
            ]
            # Senha só aparece ao CRIAR. Na edição, trocar senha é ação à parte
            # (form_senha, botão de cadeado na lista) para não mexer nela sem querer.
            if not editando:
                campos.append(f_senha)
            campos.append(erro_form)

            abrir_dialog(ft.AlertDialog(
                modal=True, title_padding=0,
                title=cabecalho_dialog("Editar funcionário" if editando else "Novo funcionário",
                                       ft.Icons.BADGE),
                content=ft.Container(width=470, content=ft.Column(tight=True, spacing=12,
                                                                  controls=campos)),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Salvar", on_click=salvar,
                                    style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)),
                ],
            ))

        def form_senha(func):
            f1 = ft.TextField(label="Nova senha *", width=300, password=True,
                              can_reveal_password=True)
            f2 = ft.TextField(label="Confirmar senha *", width=300, password=True,
                              can_reveal_password=True)
            erro_form = ft.Text("", color=ft.Colors.RED_400, size=12)

            def salvar(e):
                if not (f1.value or ""):
                    erro_form.value = "Informe a nova senha."
                    page.update(); return
                if f1.value != f2.value:
                    erro_form.value = "As senhas não conferem."
                    page.update(); return
                ok = mod_func.alterar_senha(func[0], f1.value)
                fechar_dialog()
                if ok:
                    aviso("Senha alterada", f"A senha de {func[1]} foi atualizada.")
                else:
                    aviso("Erro", "Não foi possível alterar a senha.")

            abrir_dialog(ft.AlertDialog(
                modal=True, title_padding=0,
                title=cabecalho_dialog(f"Senha — {func[1]}", ft.Icons.PASSWORD),
                content=ft.Container(width=340, content=ft.Column(tight=True, spacing=12, controls=[
                    f1, f2, erro_form,
                ])),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Salvar", on_click=salvar,
                                    style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)),
                ],
            ))

        botao_novo = ft.FilledButton(
            "Novo funcionário", icon=ft.Icons.ADD, on_click=lambda e: form_funcionario(),
            style=ft.ButtonStyle(bgcolor=COR_PRIMARIA))

        corpo_tabela.controls = [montar_linhas()]

        return ft.Column(expand=True, spacing=20, controls=[
            cabecalho("Funcionários", "Equipe, funções e acesso ao sistema", acao=botao_novo),
            ft.Row([campo_busca, dd_filtro_funcao, mostrar_inativos], spacing=16),
            card_tabela("Funcionários", corpo_tabela),
        ])

    # ============================================================
    # PÁGINA: FORNECEDORES (CRUD + produtos vinculados)
    # ============================================================
    def pagina_fornecedores():
        campo_busca = ft.TextField(
            hint_text="Buscar por nome ou CNPJ...", expand=True,
            prefix_icon=ft.Icons.SEARCH, height=44)
        mostrar_inativos = ft.Checkbox(label="Incluir inativos", value=False)
        corpo_tabela = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

        def montar_linhas():
            termo = (campo_busca.value or "").strip() or None
            forns = mod_forn.buscar_fornecedores(
                termo=termo, apenas_ativos=not mostrar_inativos.value)
            if not forns:
                return ft.Container(
                    padding=30, alignment=ft.Alignment.CENTER,
                    content=ft.Text("Nenhum fornecedor encontrado.", color=ft.Colors.GREY_500))
            linhas = []
            for f in forns:
                # Tupla = SELECT de fornecedores.buscar_fornecedores().
                (idf, nome, cnpj, tel, email, cond, ativo) = f
                badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=2), border_radius=20,
                    bgcolor=ft.Colors.GREEN_100 if ativo else ft.Colors.GREY_300,
                    content=ft.Text("Ativo" if ativo else "Inativo", size=11,
                                    color=ft.Colors.GREEN_900 if ativo else ft.Colors.GREY_700))
                if ativo:
                    acao = ft.IconButton(ft.Icons.BLOCK, icon_color=ft.Colors.RED_400,
                                         tooltip="Desativar",
                                         on_click=lambda e, i=idf: confirmar_desativar(i))
                else:
                    acao = ft.IconButton(ft.Icons.RESTORE, icon_color=ft.Colors.GREEN_500,
                                         tooltip="Reativar",
                                         on_click=lambda e, i=idf: (mod_forn.reativar_fornecedor(i), atualizar()))
                linhas.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(idf))),
                    ft.DataCell(ft.Text(nome or "")),
                    ft.DataCell(ft.Text(cnpj or "—")),
                    ft.DataCell(ft.Text(tel or "—")),
                    ft.DataCell(ft.Text(email or "—")),
                    ft.DataCell(ft.Text(cond or "—")),
                    ft.DataCell(badge),
                    ft.DataCell(ft.Row(spacing=0, controls=[
                        ft.IconButton(ft.Icons.INVENTORY_2, icon_color=COR_ACENTO,
                                      tooltip="Produtos vinculados",
                                      on_click=lambda e, ff=f: ver_produtos(ff)),
                        ft.IconButton(ft.Icons.EDIT, icon_color=COR_PRIMARIA, tooltip="Editar",
                                      on_click=lambda e, ff=f: form_fornecedor(ff)),
                        acao,
                    ])),
                ]))
            return ft.DataTable(
                expand=True, heading_row_color=ft.Colors.GREY_50,
                columns=[
                    ft.DataColumn(ft.Text("ID")),
                    ft.DataColumn(ft.Text("Razão social")),
                    ft.DataColumn(ft.Text("CNPJ")),
                    ft.DataColumn(ft.Text("Telefone")),
                    ft.DataColumn(ft.Text("E-mail")),
                    ft.DataColumn(ft.Text("Condições")),
                    ft.DataColumn(ft.Text("Status")),
                    ft.DataColumn(ft.Text("Ações")),
                ],
                rows=linhas,
            )

        def atualizar(e=None):
            corpo_tabela.controls = [montar_linhas()]
            page.update()

        campo_busca.on_change = atualizar
        mostrar_inativos.on_change = atualizar

        def confirmar_desativar(idf):
            def sim(e):
                mod_forn.desativar_fornecedor(idf)
                fechar_dialog()
                atualizar()
            abrir_dialog(ft.AlertDialog(
                modal=True,
                title=ft.Text("Desativar fornecedor"),
                content=ft.Text("Tem certeza? O fornecedor fica inativo, mas o histórico "
                                "é preservado."),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Desativar", on_click=sim,
                                    style=ft.ButtonStyle(bgcolor=ft.Colors.RED_500)),
                ],
            ))

        def form_fornecedor(forn=None):
            editando = forn is not None
            f_nome = ft.TextField(label="Razão social / Nome *",
                                  value=forn[1] if editando else "", width=440)
            f_cnpj = ft.TextField(label="CNPJ", value=(forn[2] or "") if editando else "", width=220)
            f_tel = ft.TextField(label="Telefone", value=(forn[3] or "") if editando else "", width=200)
            f_email = ft.TextField(label="E-mail", value=(forn[4] or "") if editando else "", width=440)
            f_cond = ft.TextField(label="Condições de pagamento",
                                  value=(forn[5] or "") if editando else "", width=440,
                                  hint_text="ex.: 30 dias, à vista...")
            erro_form = ft.Text("", color=ft.Colors.RED_400, size=12)

            def salvar(e):
                if not (f_nome.value or "").strip():
                    erro_form.value = "A razão social / nome é obrigatória."
                    page.update(); return
                vals = dict(
                    nome_razao_social=f_nome.value.strip(),
                    cnpj=(f_cnpj.value or "").strip() or None,
                    telefone=(f_tel.value or "").strip() or None,
                    email=(f_email.value or "").strip() or None,
                    condicoes_pagamento=(f_cond.value or "").strip() or None,
                )
                if editando:
                    ok = mod_forn.editar_fornecedor(forn[0], **vals)
                else:
                    ok = mod_forn.inserir_fornecedor(**vals) is not None
                fechar_dialog()
                if ok:
                    atualizar()
                else:
                    aviso("Erro", "Não foi possível salvar o fornecedor.")

            abrir_dialog(ft.AlertDialog(
                modal=True, title_padding=0,
                title=cabecalho_dialog("Editar fornecedor" if editando else "Novo fornecedor",
                                       ft.Icons.LOCAL_SHIPPING),
                content=ft.Container(width=470, content=ft.Column(tight=True, spacing=12, controls=[
                    f_nome,
                    ft.Row([f_cnpj, f_tel], spacing=20),
                    f_email, f_cond, erro_form,
                ])),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Salvar", on_click=salvar,
                                    style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)),
                ],
            ))

        def ver_produtos(forn):
            produtos = mod_forn.produtos_do_fornecedor(forn[0])
            if produtos:
                linhas = [ft.DataRow(cells=[
                    ft.DataCell(ft.Text(nome or "")),
                    ft.DataCell(ft.Text(str(un or "—"))),
                    ft.DataCell(ft.Text(str(qtd if qtd is not None else "—"))),
                    ft.DataCell(ft.Text(brl(custo) if custo is not None else "—")),
                ]) for (_idp, nome, un, qtd, custo) in produtos]
                corpo = ft.DataTable(
                    heading_row_color=ft.Colors.GREY_50,
                    columns=[ft.DataColumn(ft.Text("Produto")), ft.DataColumn(ft.Text("Unidade")),
                             ft.DataColumn(ft.Text("Qtd")), ft.DataColumn(ft.Text("Custo unit."))],
                    rows=linhas)
            else:
                corpo = ft.Text("Nenhum produto vinculado a este fornecedor.",
                                color=ft.Colors.GREY_500, italic=True)
            abrir_dialog(ft.AlertDialog(
                modal=True, title_padding=0,
                title=cabecalho_dialog(f"Produtos — {forn[1]}", ft.Icons.INVENTORY_2),
                content=ft.Container(width=520, content=ft.Column(
                    tight=True, scroll=ft.ScrollMode.AUTO, controls=[corpo])),
                actions=[ft.TextButton("Fechar", on_click=lambda e: fechar_dialog())],
            ))

        botao_novo = ft.FilledButton(
            "Novo fornecedor", icon=ft.Icons.ADD, on_click=lambda e: form_fornecedor(),
            style=ft.ButtonStyle(bgcolor=COR_PRIMARIA))

        corpo_tabela.controls = [montar_linhas()]

        return ft.Column(expand=True, spacing=20, controls=[
            cabecalho("Fornecedores", "Cadastro de fornecedores e produtos vinculados",
                      acao=botao_novo),
            ft.Row([campo_busca, mostrar_inativos], spacing=16),
            card_tabela("Fornecedores", corpo_tabela),
        ])

    # ============================================================
    # PÁGINA: PLANOS E ASSINATURAS (planos padrão + assinatura com resumo)
    # ============================================================
    def resumo_plano_widget(id_plano):
        """Resumo do plano (valor + serviços inclusos) para o cliente ficar ciente."""
        dados = mod_planos.buscar_plano_por_id(id_plano)
        if not dados:
            return ft.Text("Plano não encontrado.", color=ft.Colors.GREY_500)
        plano = dados["plano"]
        servicos = dados["servicos"]
        if servicos:
            itens = [ft.Text(f"• {nome} — {int(qtd)}x/mês", size=13) for (_id, nome, qtd) in servicos]
        else:
            itens = [ft.Text("Nenhum serviço incluso ainda.", size=13, italic=True,
                             color=ft.Colors.GREY_500)]
        return ft.Container(
            bgcolor=ft.Colors.BLUE_50, border_radius=10, padding=14,
            content=ft.Column(spacing=6, controls=[
                ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                    ft.Text(plano[1], weight=ft.FontWeight.BOLD, size=15),
                    ft.Text(f"{brl(plano[2])}/mês", weight=ft.FontWeight.BOLD, color=COR_PRIMARIA),
                ]),
                ft.Divider(height=8),
                ft.Text("Serviços inclusos:", size=12, color=ft.Colors.GREY_700),
                *itens,
            ]))

    def pagina_planos():
        # Tela com DUAS abas internas (Planos / Assinaturas), alternadas pela barra
        # de botões. 'aba' guarda a aba atual; render() redesenha barra + conteúdo.
        # (Padrão diferente das outras telas por causa das sub-seções.)
        aba = {"atual": "Planos"}
        area = ft.Container(expand=True)
        barra = ft.Row(spacing=8)

        def trocar(nome):
            aba["atual"] = nome
            render()

        def render():
            barra.controls = []
            for nm in ("Planos", "Assinaturas"):
                if nm == aba["atual"]:
                    barra.controls.append(ft.FilledButton(
                        nm, on_click=lambda e, n=nm: trocar(n),
                        style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)))
                else:
                    barra.controls.append(ft.OutlinedButton(
                        nm, on_click=lambda e, n=nm: trocar(n)))
            area.content = secao_planos() if aba["atual"] == "Planos" else secao_assinaturas()
            page.update()

        # ---------------- Seção PLANOS ----------------
        def secao_planos():
            corpo = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

            def montar():
                planos = mod_planos.buscar_planos(apenas_ativos=False)
                if not planos:
                    return ft.Container(
                        padding=30, alignment=ft.Alignment.CENTER,
                        content=ft.Text("Nenhum plano cadastrado. Clique em \"Novo plano\".",
                                        color=ft.Colors.GREY_500))
                linhas = []
                for (idp, nome, valor, ativo) in planos:
                    dados = mod_planos.buscar_plano_por_id(idp)
                    n_serv = len(dados["servicos"]) if dados else 0
                    badge = ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=2), border_radius=20,
                        bgcolor=ft.Colors.GREEN_100 if ativo else ft.Colors.GREY_300,
                        content=ft.Text("Ativo" if ativo else "Inativo", size=11,
                                        color=ft.Colors.GREEN_900 if ativo else ft.Colors.GREY_700))
                    if ativo:
                        acao = ft.IconButton(ft.Icons.BLOCK, icon_color=ft.Colors.RED_400,
                                             tooltip="Desativar",
                                             on_click=lambda e, i=idp: (mod_planos.desativar_plano(i), atualizar()))
                    else:
                        acao = ft.IconButton(ft.Icons.RESTORE, icon_color=ft.Colors.GREEN_500,
                                             tooltip="Reativar",
                                             on_click=lambda e, i=idp: (mod_planos.reativar_plano(i), atualizar()))
                    linhas.append(ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(idp))),
                        ft.DataCell(ft.Text(nome or "")),
                        ft.DataCell(ft.Text(f"{brl(valor)}/mês")),
                        ft.DataCell(ft.Text(f"{n_serv} serviço(s)")),
                        ft.DataCell(badge),
                        ft.DataCell(ft.Row(spacing=0, controls=[
                            ft.IconButton(ft.Icons.LIST_ALT, icon_color=COR_ACENTO,
                                          tooltip="Serviços inclusos",
                                          on_click=lambda e, i=idp, n=nome: form_servicos(i, n)),
                            ft.IconButton(ft.Icons.EDIT, icon_color=COR_PRIMARIA, tooltip="Editar",
                                          on_click=lambda e, pl=(idp, nome, valor, ativo): form_plano(pl)),
                            acao,
                        ])),
                    ]))
                return ft.DataTable(
                    expand=True, heading_row_color=ft.Colors.GREY_50,
                    columns=[ft.DataColumn(ft.Text("ID")), ft.DataColumn(ft.Text("Plano")),
                             ft.DataColumn(ft.Text("Mensalidade")), ft.DataColumn(ft.Text("Serviços")),
                             ft.DataColumn(ft.Text("Status")), ft.DataColumn(ft.Text("Ações"))],
                    rows=linhas)

            def atualizar(e=None):
                corpo.controls = [montar()]
                page.update()

            def form_plano(plano=None):
                editando = plano is not None
                f_nome = ft.TextField(label="Nome do plano *",
                                      value=plano[1] if editando else "", width=420)
                f_valor = ft.TextField(label="Mensalidade *", width=200, prefix=ft.Text("R$ "),
                                       value=(f"{float(plano[2]):.2f}".replace('.', ',')
                                              if editando else ""))
                erro = ft.Text("", color=ft.Colors.RED_400, size=12)

                def salvar(e):
                    if not (f_nome.value or "").strip():
                        erro.value = "O nome é obrigatório."; page.update(); return
                    vtxt = (f_valor.value or "").strip().replace(",", ".")
                    try:
                        valor = float(vtxt)
                    except ValueError:
                        erro.value = "Mensalidade deve ser um número (ex.: 99,90)."
                        page.update(); return
                    if editando:
                        ok = mod_planos.editar_plano(plano[0], nome=f_nome.value.strip(),
                                                     valor_mensalidade=valor)
                    else:
                        ok = mod_planos.criar_plano(f_nome.value.strip(), valor) is not None
                    fechar_dialog()
                    if ok:
                        atualizar()
                    else:
                        aviso("Erro", "Não foi possível salvar o plano.")

                abrir_dialog(ft.AlertDialog(
                    modal=True, title_padding=0,
                    title=cabecalho_dialog("Editar plano" if editando else "Novo plano",
                                           ft.Icons.CARD_MEMBERSHIP),
                    content=ft.Container(width=460, content=ft.Column(tight=True, spacing=12,
                                                                     controls=[f_nome, f_valor, erro])),
                    actions=[
                        ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                        ft.FilledButton("Salvar", on_click=salvar,
                                        style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)),
                    ]))

            def form_servicos(id_plano, nome_plano):
                servicos = mod_serv.buscar_servicos()
                dados = mod_planos.buscar_plano_por_id(id_plano)
                cotas_atuais = {sid: int(q) for (sid, _n, q) in (dados["servicos"] if dados else [])}
                campos = {}
                linhas = []
                for s in servicos:
                    sid, snome = s[0], s[1]
                    f = ft.TextField(width=120, value=(str(cotas_atuais[sid]) if sid in cotas_atuais else ""),
                                     hint_text="—", suffix=ft.Text("/mês"))
                    campos[sid] = f
                    linhas.append(ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                         controls=[ft.Text(snome, size=14), f]))
                erro = ft.Text("", color=ft.Colors.RED_400, size=12)

                def salvar(e):
                    novos = {}
                    for sid, f in campos.items():
                        txt = (f.value or "").strip()
                        if not txt:
                            novos[sid] = None
                            continue
                        if not txt.isdigit() or int(txt) <= 0:
                            erro.value = "Quantidades devem ser números inteiros maiores que zero."
                            page.update(); return
                        novos[sid] = int(txt)
                    for sid, q in novos.items():
                        if q is None:
                            if sid in cotas_atuais:
                                mod_planos.remover_servico_plano(id_plano, sid)
                        else:
                            mod_planos.definir_servico_plano(id_plano, sid, q)
                    fechar_dialog()
                    atualizar()

                abrir_dialog(ft.AlertDialog(
                    modal=True, title_padding=0,
                    title=cabecalho_dialog(f"Serviços — {nome_plano}", ft.Icons.LIST_ALT),
                    content=ft.Container(width=440, content=ft.Column(
                        tight=True, spacing=10, scroll=ft.ScrollMode.AUTO, controls=[
                            ft.Text("Defina quantos usos por mês cada serviço dá no plano "
                                    "(vazio = não incluso):", size=12, color=ft.Colors.GREY_600),
                            *linhas, erro])),
                    actions=[
                        ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                        ft.FilledButton("Salvar", on_click=salvar,
                                        style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)),
                    ]))

            corpo.controls = [montar()]
            return ft.Column(expand=True, spacing=16, controls=[
                ft.Row([ft.FilledButton("Novo plano", icon=ft.Icons.ADD,
                                        on_click=lambda e: form_plano(),
                                        style=ft.ButtonStyle(bgcolor=COR_PRIMARIA))]),
                card_tabela("Planos padrão", corpo),
            ])

        # ---------------- Seção ASSINATURAS ----------------
        def secao_assinaturas():
            corpo = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

            def montar():
                assinaturas = mod_planos.buscar_assinaturas(apenas_ativas=False)
                if not assinaturas:
                    return ft.Container(
                        padding=30, alignment=ft.Alignment.CENTER,
                        content=ft.Text("Nenhuma assinatura. Clique em \"Nova assinatura\".",
                                        color=ft.Colors.GREY_500))
                linhas = []
                # Tupla = SELECT de planos_assinaturas.buscar_assinaturas() (cli/plano
                # já vêm como nomes via JOIN; 'renov' = renovação automática).
                for (ida, cli, plano, inicio, venc, renov, ativo) in assinaturas:
                    badge = ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=2), border_radius=20,
                        bgcolor=ft.Colors.GREEN_100 if ativo else ft.Colors.GREY_300,
                        content=ft.Text("Ativa" if ativo else "Cancelada", size=11,
                                        color=ft.Colors.GREEN_900 if ativo else ft.Colors.GREY_700))
                    botoes = [ft.IconButton(ft.Icons.RECEIPT, icon_color=COR_ACENTO,
                                            tooltip="Ver resumo do plano",
                                            on_click=lambda e, i=ida: ver_resumo(i))]
                    if ativo:
                        botoes.append(ft.IconButton(
                            ft.Icons.CANCEL, icon_color=ft.Colors.RED_400, tooltip="Cancelar",
                            on_click=lambda e, i=ida: (mod_planos.cancelar_assinatura(i), atualizar())))
                    linhas.append(ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(ida))),
                        ft.DataCell(ft.Text(cli or "")),
                        ft.DataCell(ft.Text(plano or "")),
                        ft.DataCell(ft.Text(fmt_date(inicio))),
                        ft.DataCell(ft.Text(fmt_date(venc))),
                        ft.DataCell(badge),
                        ft.DataCell(ft.Row(spacing=0, controls=botoes)),
                    ]))
                return ft.DataTable(
                    expand=True, heading_row_color=ft.Colors.GREY_50,
                    columns=[ft.DataColumn(ft.Text("ID")), ft.DataColumn(ft.Text("Cliente")),
                             ft.DataColumn(ft.Text("Plano")), ft.DataColumn(ft.Text("Início")),
                             ft.DataColumn(ft.Text("Vencimento")), ft.DataColumn(ft.Text("Status")),
                             ft.DataColumn(ft.Text("Ações"))],
                    rows=linhas)

            def atualizar(e=None):
                corpo.controls = [montar()]
                page.update()

            def ver_resumo(id_assinatura):
                # Acha a assinatura na lista já carregada (só para exibir cliente/plano).
                ass = next((a for a in mod_planos.buscar_assinaturas(apenas_ativas=False)
                            if a[0] == id_assinatura), None)
                # Descobrir o id do plano dessa assinatura via buscar_plano por nome é frágil;
                # usamos saldo_servicos_mes para montar o resumo real do contratado
                # (cada serviço com cota do mês, quanto já foi usado e quanto resta).
                saldo = mod_planos.saldo_servicos_mes(id_assinatura)
                if saldo:
                    itens = [ft.Text(f"• {nome} — {int(cota)}x/mês "
                                     f"(usado {int(usado)}, restam {int(rest)})", size=13)
                             for (_id, nome, cota, usado, rest) in saldo]
                else:
                    itens = [ft.Text("Plano sem serviços inclusos.", size=13, italic=True,
                                     color=ft.Colors.GREY_500)]
                abrir_dialog(ft.AlertDialog(
                    modal=True, title_padding=0,
                    title=cabecalho_dialog(
                        f"Assinatura — {ass[1] if ass else ''}", ft.Icons.RECEIPT),
                    content=ft.Container(width=440, content=ft.Column(
                        tight=True, spacing=8, scroll=ft.ScrollMode.AUTO, controls=[
                            ft.Text(f"Plano: {ass[2] if ass else ''}", weight=ft.FontWeight.BOLD),
                            ft.Divider(),
                            ft.Text("Serviços inclusos (saldo do mês):", size=12,
                                    color=ft.Colors.GREY_700),
                            *itens])),
                    actions=[ft.TextButton("Fechar", on_click=lambda e: fechar_dialog())]))

            def form_assinatura():
                clientes = mod_cli.buscar_clientes()
                planos = mod_planos.buscar_planos(apenas_ativos=True)
                dd_cli = ft.Dropdown(
                    label="Cliente *", expand=True,
                    options=[ft.dropdown.Option(key=str(c[0]), text=c[1]) for c in clientes])
                dd_plano = ft.Dropdown(
                    label="Plano *", expand=True,
                    options=[ft.dropdown.Option(key=str(p[0]), text=f"{p[1]} ({brl(p[2])}/mês)")
                             for p in planos])
                resumo = ft.Container()
                hoje = datetime.now().strftime("%Y-%m-%d")
                f_inicio = ft.TextField(label="Início (AAAA-MM-DD)", value=hoje, width=200)
                f_venc = ft.TextField(label="Vencimento (AAAA-MM-DD)", width=200,
                                      hint_text="opcional")
                erro = ft.Text("", color=ft.Colors.RED_400, size=12)

                def on_plano(e):
                    # Ao escolher o plano, mostra o resumo (valor + serviços inclusos)
                    # para o cliente ficar ciente do que está contratando antes de assinar.
                    resumo.content = (resumo_plano_widget(int(dd_plano.value))
                                      if dd_plano.value else None)
                    resumo.update()
                dd_plano.on_change = on_plano

                def salvar(e):
                    if not dd_cli.value:
                        erro.value = "Selecione o cliente."; page.update(); return
                    if not dd_plano.value:
                        erro.value = "Selecione o plano."; page.update(); return
                    for campo, rotulo in ((f_inicio, "Início"), (f_venc, "Vencimento")):
                        txt = (campo.value or "").strip()
                        if txt:
                            try:
                                datetime.strptime(txt, "%Y-%m-%d")
                            except ValueError:
                                erro.value = f"{rotulo}: data inválida (AAAA-MM-DD)."
                                page.update(); return
                    novo = mod_planos.assinar(
                        int(dd_cli.value), int(dd_plano.value),
                        data_inicio=(f_inicio.value or "").strip() or None,
                        data_vencimento=(f_venc.value or "").strip() or None)
                    fechar_dialog()
                    if novo:
                        atualizar()
                    else:
                        aviso("Erro", "Não foi possível criar a assinatura.")

                abrir_dialog(ft.AlertDialog(
                    modal=True, title_padding=0,
                    title=cabecalho_dialog("Nova assinatura", ft.Icons.CARD_MEMBERSHIP),
                    content=ft.Container(width=480, content=ft.Column(
                        tight=True, spacing=12, scroll=ft.ScrollMode.AUTO, controls=[
                            dd_cli, dd_plano,
                            ft.Text("Resumo do plano (o cliente fica ciente):", size=12,
                                    color=ft.Colors.GREY_600),
                            resumo,
                            ft.Row([f_inicio, f_venc], spacing=12),
                            erro])),
                    actions=[
                        ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                        ft.FilledButton("Assinar", on_click=salvar,
                                        style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)),
                    ]))

            corpo.controls = [montar()]
            return ft.Column(expand=True, spacing=16, controls=[
                ft.Row([ft.FilledButton("Nova assinatura", icon=ft.Icons.ADD,
                                        on_click=lambda e: form_assinatura(),
                                        style=ft.ButtonStyle(bgcolor=COR_PRIMARIA))]),
                card_tabela("Assinaturas", corpo),
            ])

        # Monta a aba inicial
        for nm in ("Planos", "Assinaturas"):
            if nm == aba["atual"]:
                barra.controls.append(ft.FilledButton(nm, on_click=lambda e, n=nm: trocar(n),
                                                      style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)))
            else:
                barra.controls.append(ft.OutlinedButton(nm, on_click=lambda e, n=nm: trocar(n)))
        area.content = secao_planos()

        return ft.Column(expand=True, spacing=20, controls=[
            cabecalho("Planos e Assinaturas", "Planos padrão e assinaturas de clientes"),
            barra,
            area,
        ])

    # ============================================================
    # PÁGINA: DESPESAS (contas a pagar)
    # ============================================================
    # Import local (não no topo do arquivo) só por organização — mantém o módulo de
    # despesa perto da tela que o usa. Funciona igual; é intencional, não é erro.
    import despesa as mod_desp

    def pagina_despesas():
        dd_categoria = ft.Dropdown(label="Categoria", width=200,
                                   options=[ft.dropdown.Option(key="", text="Todas")], value="")
        so_aberto = ft.Checkbox(label="Somente em aberto", value=False)
        chip_total = ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=8), border_radius=10,
            bgcolor=ft.Colors.RED_50,
            content=ft.Text("", weight=ft.FontWeight.BOLD, color=ft.Colors.RED_700))
        corpo_tabela = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

        def recarregar_categorias():
            # As categorias não são cadastro fixo: são texto livre nas despesas. Aqui
            # remontamos o filtro com as categorias que realmente existem hoje.
            cats = [c[0] for c in mod_desp.total_por_categoria()
                    if c[0] and c[0] != "(sem categoria)"]
            atual = dd_categoria.value
            dd_categoria.options = [ft.dropdown.Option(key="", text="Todas")] + [
                ft.dropdown.Option(key=c, text=c) for c in cats]
            if atual not in [""] + cats:
                dd_categoria.value = ""

        def montar_linhas():
            categoria = (dd_categoria.value or "") or None
            despesas = mod_desp.buscar_despesas(
                categoria=categoria, apenas_em_aberto=so_aberto.value)
            # Total em aberto é SEMPRE o geral (ignora o filtro de categoria/aberto da
            # tabela), pois o chip resume "quanto ainda devo no total". d[3] = valor.
            abertas = mod_desp.buscar_despesas(apenas_em_aberto=True)
            total_aberto = sum(float(d[3] or 0) for d in abertas)
            chip_total.content.value = f"Em aberto: {brl(total_aberto)}  ({len(abertas)} conta(s))"

            if not despesas:
                return ft.Container(
                    padding=30, alignment=ft.Alignment.CENTER,
                    content=ft.Text("Nenhuma despesa encontrada.", color=ft.Colors.GREY_500))
            linhas = []
            for d in despesas:
                # Tupla = SELECT de despesa.buscar_despesas(). 'forn' já é o NOME do
                # fornecedor (via JOIN) — o id vem só de buscar_despesa_por_id (edição).
                (idd, desc, cat, valor, venc, pag, forn, forma) = d
                paga = pag is not None   # tem data de pagamento => já foi paga
                badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=2), border_radius=20,
                    bgcolor=ft.Colors.GREEN_100 if paga else ft.Colors.ORANGE_100,
                    content=ft.Text("Paga" if paga else "Em aberto", size=11,
                                    color=ft.Colors.GREEN_900 if paga else ft.Colors.ORANGE_900,
                                    weight=ft.FontWeight.W_600))
                botoes = []
                if not paga:
                    botoes.append(ft.IconButton(
                        ft.Icons.PAID, icon_color=ft.Colors.GREEN_600, tooltip="Marcar como paga",
                        on_click=lambda e, i=idd: form_pagar(i)))
                botoes.append(ft.IconButton(
                    ft.Icons.EDIT, icon_color=COR_PRIMARIA, tooltip="Editar",
                    on_click=lambda e, dd=d: form_despesa(dd)))
                botoes.append(ft.IconButton(
                    ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_400, tooltip="Excluir",
                    on_click=lambda e, i=idd, ds=desc: confirmar_excluir(i, ds)))
                linhas.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(idd))),
                    ft.DataCell(ft.Text(desc or "")),
                    ft.DataCell(ft.Text(cat or "—")),
                    ft.DataCell(ft.Text(brl(valor))),
                    ft.DataCell(ft.Text(fmt_date(venc))),
                    ft.DataCell(ft.Text(fmt_date(pag) if paga else "—")),
                    ft.DataCell(badge),
                    ft.DataCell(ft.Text(forn or "—")),
                    ft.DataCell(ft.Row(spacing=0, controls=botoes)),
                ]))
            return ft.DataTable(
                expand=True, heading_row_color=ft.Colors.GREY_50,
                columns=[
                    ft.DataColumn(ft.Text("ID")),
                    ft.DataColumn(ft.Text("Descrição")),
                    ft.DataColumn(ft.Text("Categoria")),
                    ft.DataColumn(ft.Text("Valor")),
                    ft.DataColumn(ft.Text("Vencimento")),
                    ft.DataColumn(ft.Text("Pagamento")),
                    ft.DataColumn(ft.Text("Status")),
                    ft.DataColumn(ft.Text("Fornecedor")),
                    ft.DataColumn(ft.Text("Ações")),
                ],
                rows=linhas,
            )

        def atualizar(e=None):
            recarregar_categorias()
            corpo_tabela.controls = [montar_linhas()]
            page.update()

        dd_categoria.on_change = atualizar
        so_aberto.on_change = atualizar

        def confirmar_excluir(idd, desc):
            def sim(e):
                mod_desp.excluir_despesa(idd)
                fechar_dialog()
                atualizar()
            abrir_dialog(ft.AlertDialog(
                modal=True,
                title=ft.Text("Excluir despesa"),
                content=ft.Text(f"Excluir \"{desc}\" definitivamente? Esta ação não pode "
                                f"ser desfeita (a despesa não tem desativação)."),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Excluir", on_click=sim,
                                    style=ft.ButtonStyle(bgcolor=ft.Colors.RED_500)),
                ],
            ))

        def form_pagar(idd):
            hoje = datetime.now().strftime("%Y-%m-%d")
            f_data = ft.TextField(label="Data do pagamento", value=hoje, width=200)
            dd_forma = ft.Dropdown(
                label="Forma de pagamento", width=240,
                options=[ft.dropdown.Option(key=k, text=t) for k, t in FORMAS_PAGAMENTO])
            erro = ft.Text("", color=ft.Colors.RED_400, size=12)

            def salvar(e):
                dtxt = (f_data.value or "").strip()
                if dtxt:
                    try:
                        datetime.strptime(dtxt, "%Y-%m-%d")
                    except ValueError:
                        erro.value = "Data inválida (AAAA-MM-DD)."; page.update(); return
                mod_desp.marcar_como_paga(idd, data_pagamento=dtxt or None,
                                          forma_pagamento=dd_forma.value or None)
                fechar_dialog()
                atualizar()

            abrir_dialog(ft.AlertDialog(
                modal=True, title_padding=0,
                title=cabecalho_dialog("Marcar como paga", ft.Icons.PAID),
                content=ft.Container(width=320, content=ft.Column(tight=True, spacing=12, controls=[
                    f_data, dd_forma, erro])),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Confirmar", on_click=salvar,
                                    style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_600)),
                ],
            ))

        def form_despesa(despesa=None):
            editando = despesa is not None
            fornecedores = mod_forn.buscar_fornecedores()
            f_desc = ft.TextField(label="Descrição *", value=despesa[1] if editando else "", width=440)
            f_valor = ft.TextField(label="Valor *", width=180, prefix=ft.Text("R$ "),
                                   value=(f"{float(despesa[3]):.2f}".replace('.', ',')
                                          if editando else ""))
            f_cat = ft.TextField(label="Categoria", width=220,
                                 value=(despesa[2] or "") if editando else "",
                                 hint_text="ex.: energia, produto, aluguel")
            f_venc = ft.TextField(label="Vencimento (AAAA-MM-DD)", width=220,
                                  value=(despesa[4].strftime("%Y-%m-%d")
                                         if editando and despesa[4] else ""))
            # fornecedor id: na busca vem o nome (índice 6); para edição uso buscar_despesa_por_id
            id_forn_atual = None
            if editando:
                det = mod_desp.buscar_despesa_por_id(despesa[0])
                id_forn_atual = det[6] if det else None
            dd_forn = ft.Dropdown(
                label="Fornecedor", width=440,
                options=[ft.dropdown.Option(key="", text="(nenhum)")]
                        + [ft.dropdown.Option(key=str(fo[0]), text=fo[1]) for fo in fornecedores],
                value=str(id_forn_atual) if id_forn_atual else "")
            erro = ft.Text("", color=ft.Colors.RED_400, size=12)

            def salvar(e):
                if not (f_desc.value or "").strip():
                    erro.value = "A descrição é obrigatória."; page.update(); return
                vtxt = (f_valor.value or "").strip().replace(",", ".")
                try:
                    valor = float(vtxt)
                except ValueError:
                    erro.value = "Valor deve ser um número (ex.: 185,00)."; page.update(); return
                venc_txt = (f_venc.value or "").strip()
                if venc_txt:
                    try:
                        datetime.strptime(venc_txt, "%Y-%m-%d")
                    except ValueError:
                        erro.value = "Vencimento inválido (AAAA-MM-DD)."; page.update(); return
                id_forn = int(dd_forn.value) if dd_forn.value else None
                cat = (f_cat.value or "").strip() or None
                if editando:
                    ok = mod_desp.editar_despesa(
                        despesa[0], descricao=f_desc.value.strip(), categoria=cat, valor=valor,
                        data_vencimento=venc_txt or None, id_fornecedor=id_forn)
                else:
                    ok = mod_desp.inserir_despesa(
                        f_desc.value.strip(), valor, categoria=cat,
                        data_vencimento=venc_txt or None, id_fornecedor=id_forn) is not None
                fechar_dialog()
                if ok:
                    atualizar()
                else:
                    aviso("Erro", "Não foi possível salvar a despesa.")

            abrir_dialog(ft.AlertDialog(
                modal=True, title_padding=0,
                title=cabecalho_dialog("Editar despesa" if editando else "Nova despesa",
                                       ft.Icons.PAYMENTS),
                content=ft.Container(width=470, content=ft.Column(tight=True, spacing=12, controls=[
                    f_desc,
                    ft.Row([f_valor, f_cat], spacing=20),
                    f_venc, dd_forn, erro,
                ])),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Salvar", on_click=salvar,
                                    style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)),
                ],
            ))

        botao_nova = ft.FilledButton(
            "Nova despesa", icon=ft.Icons.ADD, on_click=lambda e: form_despesa(),
            style=ft.ButtonStyle(bgcolor=COR_PRIMARIA))

        recarregar_categorias()
        corpo_tabela.controls = [montar_linhas()]

        return ft.Column(expand=True, spacing=20, controls=[
            cabecalho("Despesas", "Contas a pagar e pagas", acao=botao_nova),
            ft.Row([dd_categoria, so_aberto, chip_total], spacing=16,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            card_tabela("Despesas", corpo_tabela),
        ])

    # ============================================================
    # PÁGINA: CAIXA (estado: aberto/fechado + movimentos + histórico)
    # ============================================================
    def pagina_caixa():
        # Tela de estado (não é uma lista com CRUD): mostra o caixa ABERTO (com seus
        # movimentos e botões) ou o painel de "abrir caixa", + o histórico embaixo.
        # construir() decide qual painel montar conforme houver ou não caixa aberto.
        conteudo = ft.Column(expand=True, spacing=20)

        def render():
            # Reconstrói os painéis do zero (relê caixa_aberto/movimentos) e repinta.
            conteudo.controls = construir()
            page.update()

        # -------- Ações --------
        def form_abrir():
            f_valor = ft.TextField(label="Fundo inicial", width=200, prefix=ft.Text("R$ "),
                                   value="0")
            f_obs = ft.TextField(label="Observações", width=420, multiline=True,
                                 min_lines=2, max_lines=3)
            erro = ft.Text("", color=ft.Colors.RED_400, size=12)

            def salvar(e):
                vtxt = (f_valor.value or "0").strip().replace(",", ".")
                try:
                    valor = float(vtxt)
                except ValueError:
                    erro.value = "Fundo inicial deve ser um número."; page.update(); return
                cid = mod_caixa.abrir_caixa(valor_inicial=valor,
                                            id_funcionario=sessao["id"] or None,
                                            observacoes=(f_obs.value or "").strip() or None)
                fechar_dialog()
                if cid:
                    render()
                else:
                    aviso("Erro", "Não foi possível abrir o caixa (já há um aberto?).")

            abrir_dialog(ft.AlertDialog(
                modal=True, title_padding=0,
                title=cabecalho_dialog("Abrir caixa", ft.Icons.LOCK_OPEN),
                content=ft.Container(width=460, content=ft.Column(tight=True, spacing=12,
                                                                 controls=[f_valor, f_obs, erro])),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Abrir", on_click=salvar,
                                    style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)),
                ]))

        def form_movimento(tipo):
            entrada = tipo == "entrada"
            f_valor = ft.TextField(label="Valor *", width=200, prefix=ft.Text("R$ "))
            f_desc = ft.TextField(label="Descrição", width=420)
            erro = ft.Text("", color=ft.Colors.RED_400, size=12)

            def salvar(e):
                vtxt = (f_valor.value or "").strip().replace(",", ".")
                try:
                    valor = float(vtxt)
                except ValueError:
                    erro.value = "Valor deve ser um número."; page.update(); return
                if valor <= 0:
                    erro.value = "Valor deve ser maior que zero."; page.update(); return
                desc = (f_desc.value or "").strip() or None
                res = (mod_caixa.registrar_entrada(valor, desc) if entrada
                       else mod_caixa.registrar_saida(valor, desc))
                fechar_dialog()
                if res:
                    render()
                else:
                    aviso("Erro", "Não foi possível registrar o movimento.")

            cor = ft.Colors.GREEN_600 if entrada else ft.Colors.RED_500
            abrir_dialog(ft.AlertDialog(
                modal=True, title_padding=0,
                title=cabecalho_dialog("Registrar entrada" if entrada else "Registrar saída",
                                       ft.Icons.ADD if entrada else ft.Icons.REMOVE),
                content=ft.Container(width=460, content=ft.Column(tight=True, spacing=12,
                                                                 controls=[f_valor, f_desc, erro])),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Registrar", on_click=salvar,
                                    style=ft.ButtonStyle(bgcolor=cor)),
                ]))

        def form_fechar(id_caixa):
            esperado = mod_caixa.saldo_esperado(id_caixa)
            f_real = ft.TextField(label="Saldo real contado *", width=220, prefix=ft.Text("R$ "))
            f_obs = ft.TextField(label="Observações", width=420, multiline=True,
                                 min_lines=2, max_lines=3)
            erro = ft.Text("", color=ft.Colors.RED_400, size=12)

            def salvar(e):
                vtxt = (f_real.value or "").strip().replace(",", ".")
                try:
                    real = float(vtxt)
                except ValueError:
                    erro.value = "Saldo real deve ser um número."; page.update(); return
                res = mod_caixa.fechar_caixa(saldo_real=real,
                                             id_funcionario=sessao["id"] or None,
                                             observacoes=(f_obs.value or "").strip() or None)
                fechar_dialog()
                if res:
                    # diferenca = saldo real contado - saldo esperado pelo sistema.
                    # >0 sobra, <0 falta, ~0 bateu (tolerância p/ arredondamento).
                    dif = res["diferenca"]
                    if dif is None:
                        msg = "Caixa fechado."
                    elif abs(float(dif)) < 0.005:
                        msg = "Caixa fechado e bateu certinho! ✅"
                    elif float(dif) > 0:
                        msg = f"Caixa fechado. Sobra de {brl(dif)} (mais que o esperado)."
                    else:
                        msg = f"Caixa fechado. Falta de {brl(abs(float(dif)))} (menos que o esperado)."
                    aviso("Caixa fechado",
                          f"Esperado: {brl(res['esperado'])}\nReal: {brl(res['real'])}\n\n{msg}")
                    render()
                else:
                    aviso("Erro", "Não foi possível fechar o caixa.")

            abrir_dialog(ft.AlertDialog(
                modal=True, title_padding=0,
                title=cabecalho_dialog("Fechar caixa", ft.Icons.LOCK),
                content=ft.Container(width=460, content=ft.Column(tight=True, spacing=12, controls=[
                    ft.Container(
                        bgcolor=ft.Colors.BLUE_50, border_radius=8, padding=12,
                        content=ft.Text(f"Saldo esperado (sistema): {brl(esperado)}",
                                        weight=ft.FontWeight.BOLD, color=COR_PRIMARIA)),
                    ft.Text("Conte o dinheiro na gaveta e informe o valor real:",
                            size=12, color=ft.Colors.GREY_600),
                    f_real, f_obs, erro,
                ])),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Fechar caixa", on_click=salvar,
                                    style=ft.ButtonStyle(bgcolor=ft.Colors.RED_500)),
                ]))

        # -------- Blocos visuais --------
        def info(rotulo, valor, cor=None, grande=False):
            return ft.Column(spacing=2, controls=[
                ft.Text(rotulo, size=12, color=ft.Colors.GREY_600),
                ft.Text(valor, size=22 if grande else 15,
                        weight=ft.FontWeight.BOLD, color=cor),
            ])

        def painel_aberto(aberto):
            # 'aberto' = tupla de caixa.caixa_aberto(): (id, abertura, fundo, id_func).
            id_caixa, data_ab, valor_ini, id_func = aberto
            # Saldo esperado = fundo inicial + entradas - saídas (calculado no backend).
            esperado = mod_caixa.saldo_esperado(id_caixa)
            func = mod_func.buscar_funcionario_por_id(id_func) if id_func else None
            resp = func[1] if func else "—"
            movs = mod_caixa.movimentos_do_caixa(id_caixa)

            cabecalho_painel = ft.Container(
                padding=20, bgcolor=COR_CARD, border_radius=12,
                shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK)),
                content=ft.Column(spacing=16, controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                        ft.Row(spacing=10, controls=[
                            ft.Icon(ft.Icons.LOCK_OPEN, color=ft.Colors.GREEN_600),
                            ft.Text("Caixa aberto", size=18, weight=ft.FontWeight.BOLD),
                        ]),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=10, vertical=3), border_radius=20,
                            bgcolor=ft.Colors.GREEN_100,
                            content=ft.Text(f"#{id_caixa}", size=12, color=ft.Colors.GREEN_900)),
                    ]),
                    ft.Row(spacing=40, wrap=True, controls=[
                        info("Aberto em", fmt_dt(data_ab)),
                        info("Fundo inicial", brl(valor_ini)),
                        info("Responsável", resp),
                        info("Saldo esperado", brl(esperado), cor=COR_PRIMARIA, grande=True),
                    ]),
                    ft.Row(spacing=10, controls=[
                        ft.FilledButton("Entrada", icon=ft.Icons.ADD,
                                        on_click=lambda e: form_movimento("entrada"),
                                        style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_600)),
                        ft.FilledButton("Saída", icon=ft.Icons.REMOVE,
                                        on_click=lambda e: form_movimento("saida"),
                                        style=ft.ButtonStyle(bgcolor=ft.Colors.RED_500)),
                        ft.FilledButton("Fechar caixa", icon=ft.Icons.LOCK,
                                        on_click=lambda e: form_fechar(id_caixa),
                                        style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)),
                    ]),
                ]))

            if movs:
                linhas = []
                # Cada movimento pode referenciar uma comanda (id_ordem) OU uma despesa
                # (id_desp) OU nenhum (entrada/saída avulsa). Só um deles vem preenchido.
                for (_idm, tipo, valor, desc, id_ordem, id_desp, data) in movs:
                    entrada = tipo == "entrada"
                    linhas.append(ft.DataRow(cells=[
                        ft.DataCell(ft.Row(spacing=4, controls=[
                            ft.Icon(ft.Icons.ARROW_DOWNWARD if entrada else ft.Icons.ARROW_UPWARD,
                                    size=16,
                                    color=ft.Colors.GREEN_600 if entrada else ft.Colors.RED_500),
                            ft.Text("Entrada" if entrada else "Saída", size=12)])),
                        ft.DataCell(ft.Text(brl(valor),
                                            color=ft.Colors.GREEN_700 if entrada else ft.Colors.RED_600)),
                        ft.DataCell(ft.Text(desc or "—")),
                        ft.DataCell(ft.Text(f"#{id_ordem}" if id_ordem else
                                            (f"desp #{id_desp}" if id_desp else "—"))),
                        ft.DataCell(ft.Text(fmt_dt(data))),
                    ]))
                tabela_movs = ft.DataTable(
                    expand=True, heading_row_color=ft.Colors.GREY_50,
                    columns=[ft.DataColumn(ft.Text("Tipo")), ft.DataColumn(ft.Text("Valor")),
                             ft.DataColumn(ft.Text("Descrição")), ft.DataColumn(ft.Text("Ref.")),
                             ft.DataColumn(ft.Text("Data"))],
                    rows=linhas)
            else:
                tabela_movs = ft.Text("Nenhum movimento ainda.", color=ft.Colors.GREY_500,
                                      italic=True)
            return ft.Column(spacing=20, controls=[
                cabecalho_painel,
                card_tabela("Movimentos do caixa", ft.Column([tabela_movs], expand=True,
                                                             scroll=ft.ScrollMode.AUTO)),
            ])

        def painel_fechado():
            return ft.Container(
                padding=40, bgcolor=COR_CARD, border_radius=12,
                shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK)),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=14, controls=[
                        ft.Icon(ft.Icons.LOCK, size=56, color=ft.Colors.GREY_400),
                        ft.Text("Nenhum caixa aberto", size=18, weight=ft.FontWeight.W_600),
                        ft.Text("Abra o caixa com o fundo inicial para começar a registrar "
                                "entradas e saídas do dia.", size=13, color=ft.Colors.GREY_600,
                                text_align=ft.TextAlign.CENTER),
                        ft.FilledButton("Abrir caixa", icon=ft.Icons.LOCK_OPEN,
                                        on_click=lambda e: form_abrir(),
                                        style=ft.ButtonStyle(bgcolor=COR_PRIMARIA)),
                    ]))

        def card_historico():
            caixas = mod_caixa.historico_caixas()
            if caixas:
                linhas = []
                # Tupla = SELECT de caixa.historico_caixas(): id, abertura, fechamento,
                # fundo inicial, saldo final, status. 'fe'/'sfinal' são None se aberto.
                for (idc, ab, fe, vini, sfinal, status) in caixas:
                    aberto_s = status == "aberto"
                    badge = ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=2), border_radius=20,
                        bgcolor=ft.Colors.GREEN_100 if aberto_s else ft.Colors.GREY_300,
                        content=ft.Text("Aberto" if aberto_s else "Fechado", size=11,
                                        color=ft.Colors.GREEN_900 if aberto_s else ft.Colors.GREY_700))
                    linhas.append(ft.DataRow(cells=[
                        ft.DataCell(ft.Text(f"#{idc}")),
                        ft.DataCell(ft.Text(fmt_dt(ab))),
                        ft.DataCell(ft.Text(fmt_dt(fe) if fe else "—")),
                        ft.DataCell(ft.Text(brl(vini))),
                        ft.DataCell(ft.Text(brl(sfinal) if sfinal is not None else "—")),
                        ft.DataCell(badge),
                    ]))
                corpo = ft.DataTable(
                    expand=True, heading_row_color=ft.Colors.GREY_50,
                    columns=[ft.DataColumn(ft.Text("Caixa")), ft.DataColumn(ft.Text("Abertura")),
                             ft.DataColumn(ft.Text("Fechamento")), ft.DataColumn(ft.Text("Fundo")),
                             ft.DataColumn(ft.Text("Saldo final")), ft.DataColumn(ft.Text("Status"))],
                    rows=linhas)
            else:
                corpo = ft.Text("Nenhum caixa no histórico.", color=ft.Colors.GREY_500)
            return card_tabela("Histórico de caixas",
                               ft.Column([corpo], expand=True, scroll=ft.ScrollMode.AUTO))

        def construir():
            aberto = mod_caixa.caixa_aberto()
            blocos = [painel_aberto(aberto) if aberto else painel_fechado()]
            blocos.append(card_historico())
            return blocos

        conteudo.controls = construir()
        return ft.Column(expand=True, spacing=20, scroll=ft.ScrollMode.AUTO, controls=[
            cabecalho("Caixa", "Abertura, movimentos e fechamento do caixa"),
            conteudo,
        ])

    # ============================================================
    # PÁGINA: FIDELIDADE (pontos por cliente: acúmulo/resgate + extrato)
    # ============================================================
    # Import local (igual ao de despesa acima): intencional, não é erro.
    import fidelidade as mod_fid

    def pagina_fidelidade():
        campo_busca = ft.TextField(
            hint_text="Buscar cliente...", expand=True,
            prefix_icon=ft.Icons.SEARCH, height=44)
        corpo_tabela = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

        def montar_linhas():
            termo = (campo_busca.value or "").strip() or None
            clientes = mod_cli.buscar_clientes(termo=termo)
            if not clientes:
                return ft.Container(
                    padding=30, alignment=ft.Alignment.CENTER,
                    content=ft.Text("Nenhum cliente encontrado.", color=ft.Colors.GREY_500))
            linhas = []
            for c in clientes:
                # Reaproveita a tupla de clientes; pega só id(0), nome(1) e telefone(3)
                # — pula cpf_cnpj(2). Saldo de pontos vem de fidelidade.saldo_pontos().
                idc, nome, tel = c[0], c[1], c[3]
                saldo = mod_fid.saldo_pontos(idc)
                chip = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=3), border_radius=20,
                    bgcolor=ft.Colors.AMBER_100,
                    content=ft.Row(spacing=4, tight=True, controls=[
                        ft.Icon(ft.Icons.STARS, size=14, color=ft.Colors.AMBER_800),
                        ft.Text(f"{saldo} pts", size=12, color=ft.Colors.AMBER_900,
                                weight=ft.FontWeight.BOLD)]))
                linhas.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(idc))),
                    ft.DataCell(ft.Text(nome or "")),
                    ft.DataCell(ft.Text(tel or "—")),
                    ft.DataCell(chip),
                    ft.DataCell(ft.Row(spacing=0, controls=[
                        ft.IconButton(ft.Icons.ADD_CIRCLE_OUTLINE, icon_color=ft.Colors.GREEN_600,
                                      tooltip="Acumular pontos",
                                      on_click=lambda e, i=idc, n=nome: form_pontos(i, n, "acumular")),
                        ft.IconButton(ft.Icons.REDEEM, icon_color=COR_PRIMARIA,
                                      tooltip="Resgatar pontos",
                                      on_click=lambda e, i=idc, n=nome, s=saldo: form_pontos(i, n, "resgatar", s)),
                        ft.IconButton(ft.Icons.HISTORY, icon_color=ft.Colors.GREY_600,
                                      tooltip="Extrato",
                                      on_click=lambda e, i=idc, n=nome: ver_extrato(i, n)),
                    ])),
                ]))
            return ft.DataTable(
                expand=True, heading_row_color=ft.Colors.GREY_50,
                columns=[
                    ft.DataColumn(ft.Text("ID")),
                    ft.DataColumn(ft.Text("Cliente")),
                    ft.DataColumn(ft.Text("Telefone")),
                    ft.DataColumn(ft.Text("Saldo")),
                    ft.DataColumn(ft.Text("Ações")),
                ],
                rows=linhas,
            )

        def atualizar(e=None):
            corpo_tabela.controls = [montar_linhas()]
            page.update()

        campo_busca.on_change = atualizar

        def form_pontos(id_cliente, nome, modo, saldo_atual=None):
            # Mesmo formulário para acumular e resgatar (modo decide). No resgate
            # passamos saldo_atual para mostrar quanto o cliente tem; o backend
            # recusa (devolve None) se os pontos a resgatar excederem o saldo.
            acumular = modo == "acumular"
            f_pontos = ft.TextField(label="Pontos *", width=160)
            f_desc = ft.TextField(label="Descrição", width=400,
                                  hint_text="ex.: Bônus / Lavagem grátis")
            info = (ft.Text(f"Saldo atual: {saldo_atual} pts", size=13, color=ft.Colors.GREY_600)
                    if not acumular else ft.Container())
            erro = ft.Text("", color=ft.Colors.RED_400, size=12)

            def salvar(e):
                txt = (f_pontos.value or "").strip()
                if not txt.isdigit() or int(txt) <= 0:
                    erro.value = "Pontos deve ser um número inteiro maior que zero."
                    page.update(); return
                pts = int(txt)
                desc = (f_desc.value or "").strip() or None
                if acumular:
                    res = mod_fid.acumular_pontos(id_cliente, pts, descricao=desc)
                else:
                    res = mod_fid.resgatar_pontos(id_cliente, pts, descricao=desc)
                if res is None:
                    erro.value = ("Saldo de pontos insuficiente." if not acumular
                                  else "Não foi possível acumular os pontos.")
                    page.update(); return
                fechar_dialog()
                atualizar()

            cor = ft.Colors.GREEN_600 if acumular else COR_PRIMARIA
            abrir_dialog(ft.AlertDialog(
                modal=True, title_padding=0,
                title=cabecalho_dialog(
                    f"{'Acumular' if acumular else 'Resgatar'} pontos — {nome}",
                    ft.Icons.ADD_CIRCLE_OUTLINE if acumular else ft.Icons.REDEEM),
                content=ft.Container(width=420, content=ft.Column(tight=True, spacing=12, controls=[
                    info, f_pontos, f_desc, erro])),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: fechar_dialog()),
                    ft.FilledButton("Acumular" if acumular else "Resgatar", on_click=salvar,
                                    style=ft.ButtonStyle(bgcolor=cor)),
                ]))

        def ver_extrato(id_cliente, nome):
            movs = mod_fid.extrato_pontos(id_cliente)
            saldo = mod_fid.saldo_pontos(id_cliente)
            if movs:
                linhas = []
                # Tupla = SELECT de fidelidade.extrato_pontos(). id_ordem preenchido
                # quando os pontos vieram de uma comanda; None se lançamento manual.
                for (_idm, tipo, pts, id_ordem, desc, data) in movs:
                    acum = tipo == "acumulo"   # senão é "resgate"
                    linhas.append(ft.DataRow(cells=[
                        ft.DataCell(ft.Row(spacing=4, controls=[
                            ft.Icon(ft.Icons.ADD if acum else ft.Icons.REMOVE, size=16,
                                    color=ft.Colors.GREEN_600 if acum else ft.Colors.RED_500),
                            ft.Text("Acúmulo" if acum else "Resgate", size=12)])),
                        ft.DataCell(ft.Text(f"{'+' if acum else '-'}{pts}",
                                            color=ft.Colors.GREEN_700 if acum else ft.Colors.RED_600,
                                            weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(f"#{id_ordem}" if id_ordem else "—")),
                        ft.DataCell(ft.Text(desc or "—")),
                        ft.DataCell(ft.Text(fmt_dt(data))),
                    ]))
                corpo = ft.DataTable(
                    expand=True, heading_row_color=ft.Colors.GREY_50,
                    columns=[ft.DataColumn(ft.Text("Tipo")), ft.DataColumn(ft.Text("Pontos")),
                             ft.DataColumn(ft.Text("Comanda")), ft.DataColumn(ft.Text("Descrição")),
                             ft.DataColumn(ft.Text("Data"))],
                    rows=linhas)
            else:
                corpo = ft.Text("Sem movimentações de pontos.", color=ft.Colors.GREY_500,
                                italic=True)
            abrir_dialog(ft.AlertDialog(
                modal=True, title_padding=0,
                title=cabecalho_dialog(f"Extrato — {nome}", ft.Icons.STARS),
                content=ft.Container(width=560, content=ft.Column(
                    tight=True, spacing=10, scroll=ft.ScrollMode.AUTO, controls=[
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                            border_radius=8, bgcolor=ft.Colors.AMBER_100,
                            content=ft.Text(f"Saldo atual: {saldo} pontos",
                                            weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_900)),
                        corpo])),
                actions=[ft.TextButton("Fechar", on_click=lambda e: fechar_dialog())]))

        corpo_tabela.controls = [montar_linhas()]

        return ft.Column(expand=True, spacing=20, controls=[
            cabecalho("Fidelidade", "Pontos por cliente: acúmulo e resgate"),
            ft.Row([campo_busca], spacing=16),
            card_tabela("Clientes e pontos", corpo_tabela),
        ])

    # ============================================================
    # PÁGINA: placeholder "em construção"
    # ============================================================
    def pagina_em_construcao(nome):
        # Fábrica de tela placeholder: recebe o nome e DEVOLVE a função construtora
        # (_build), para casar com o formato esperado em paginas[nome] = (icone, func).
        # Hoje nenhuma tela usa isto (todas foram implementadas), mas fica de reserva.
        def _build():
            return ft.Column(expand=True, spacing=20, controls=[
                cabecalho(nome),
                ft.Container(
                    expand=True, alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12, controls=[
                            ft.Icon(ft.Icons.CONSTRUCTION, size=64, color=ft.Colors.GREY_400),
                            ft.Text("Tela em construção", size=18, color=ft.Colors.GREY_600),
                            ft.Text(f"O backend de '{nome}' já está pronto — falta plugar a interface.",
                                    size=13, color=ft.Colors.GREY_500),
                        ]),
                ),
            ])
        return _build

    # ------------------------------------------------------------
    # Registro das páginas (ordem do menu)
    # ------------------------------------------------------------
    def registrar_paginas():
        paginas.clear()
        # Ordem do menu segue o fluxo operacional do dia a dia
        paginas["Dashboard"] = (ft.Icons.DASHBOARD, pagina_dashboard)
        paginas["Clientes"] = (ft.Icons.PEOPLE, pagina_clientes)
        paginas["Veículos"] = (ft.Icons.DIRECTIONS_CAR, pagina_veiculos)
        paginas["Agendamentos"] = (ft.Icons.EVENT, pagina_agendamentos)
        paginas["Comandas"] = (ft.Icons.RECEIPT_LONG, pagina_comandas)
        paginas["Serviços"] = (ft.Icons.LOCAL_CAR_WASH, pagina_servicos)
        paginas["Estoque"] = (ft.Icons.INVENTORY_2, pagina_estoque)
        paginas["Fornecedores"] = (ft.Icons.LOCAL_SHIPPING, pagina_fornecedores)
        paginas["Caixa"] = (ft.Icons.POINT_OF_SALE, pagina_caixa)
        paginas["Despesas"] = (ft.Icons.PAYMENTS, pagina_despesas)
        paginas["Fidelidade"] = (ft.Icons.STARS, pagina_fidelidade)
        paginas["Planos"] = (ft.Icons.CARD_MEMBERSHIP, pagina_planos)
        paginas["Funcionários"] = (ft.Icons.BADGE, pagina_funcionarios)

    # Ponto de partida da aplicação: a primeira coisa que aparece é o login.
    # Só depois de autenticar (montar_app) a sidebar e as telas são construídas.
    tela_login()


if __name__ == "__main__":
    # ft.run recebe main(page) e abre a janela do app (API do Flet 0.85).
    ft.run(main)
