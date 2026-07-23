# Sistema de Gestão para Lava-Jato (projeto_daniel)

Sistema de gestão para lava-jato em **Python + psycopg2 + PostgreSQL**, com
interface gráfica em **Flet** (`app.py`).
Dependências: `psycopg2`, `bcrypt` (hash de senha no módulo funcionário), `flet`
(interface), `reportlab` (recibo em PDF). Ver `requirements.txt` (`pip install -r requirements.txt`).
Cliente: **Truck Center Lavação**. Autor: Lucas Ribeiro Nepomuceno de Almeida (RINEAL Analytics).

---

## Repositório

- GitHub (privado): https://github.com/ribeirolucas962/projeto-lavajato
- Branch principal: `main`.
- **Credenciais NÃO são versionadas.** Ao clonar, copie `.env.example` para `.env` e
  preencha a senha do banco. O `conexao.py` lê as variáveis do `.env` (`DB_HOST`,
  `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`).
- Nota Windows: este ambiente precisou de `git config --global http.sslBackend schannel`
  para o push HTTPS funcionar (erro de certificado SSL com o backend OpenSSL).

## Banco de dados

- **Banco EM USO (desde 2026-07-15): PostgreSQL 18.4 no servidor TrueNAS da rede local**
  — host `192.168.1.19:5432`, banco `dados`, user `nepomuceno` (senha no `.env`).
  Migração completa feita em 15/07: 22 tabelas + todos os dados copiados do banco local
  (contagens conferidas tabela a tabela). O `.env` aponta pra lá.
- **Banco local antigo (backup/desenvolvimento):** PostgreSQL 16 em `localhost:5432`,
  banco `lavajato_db` (user `postgres`, senha `123456`). Continua intacto com os dados
  de antes da migração; para voltar a usá-lo, troque o bloco comentado no `.env`.
- Conexão centralizada em `conexao.py` → função `conectar()` retorna a conexão (ou `None`).
  Variáveis de ambiente do terminal **têm prioridade** sobre o `.env` (`os.environ.setdefault`).
- Schema completo em `criar_tabelas.sql` (fonte única da verdade). Recriável com
  `python criar_tabelas.py` — é idempotente (`IF NOT EXISTS` / `ON CONFLICT`).

### ⚠️ Atenção: bancos vizinhos no mesmo servidor
O servidor 5432 hospeda vários projetos: `lavajato_db` (este), `mecanica`,
`oficina_mecanica`, `receita_premium`, `viagem_milhas`, `postgres`.
**Sempre confirmar que estamos no `lavajato_db`.** Já houve confusão com o DBeaver
conectado em `oficina_mecanica` (tabelas no plural `clientes`/`veiculos`, mais
`peca`/`financeiro`) — essas NÃO são do lava-jato. No DBeaver, por padrão a conexão
só mostra o banco digitado; para ver o `lavajato_db` crie uma conexão própria pra ele
ou marque "Show all databases" na conexão existente.

### Pendência conhecida (não aplicada)
No Windows, o psycopg2 pode quebrar com `UnicodeDecodeError` ao ler mensagens de erro
do Postgres em português (Win-1252). Fix sugerido: adicionar `'options': '-c lc_messages=C'`
ao `DB_config` em `conexao.py`.

---

## Convenções de código

- **Nomes de tabela no singular** (`cliente`, `veiculo`, `servico`...).
- **Um módulo `.py` por área de negócio**, contendo as funções de CRUD daquela tabela.
- **Padrão de cada função de banco** (ver `cadastro_cliente.py` / `cadastro_veiculo.py`):
  - abre conexão com `conectar()`, retorna cedo se falhar;
  - `try` (executa + `commit`) / `except` (`print` do erro + `rollback`) / `finally`
    (`cursor.close()` + `conexao.close()`);
  - sempre **queries parametrizadas** (`%s`), nunca f-string com dados do usuário.
- **Soft delete:** coluna `ativo BOOLEAN` — `desativar_*` e `reativar_*` em vez de DELETE.
  - **Exceção (2026-07-16):** `excluir_cliente()`/`excluir_veiculo()` fazem DELETE de
    verdade, **só para cadastro criado errado e sem vínculos** (botão "Excluir de vez",
    lixeira vermelha nas telas Clientes/Veículos). Com histórico, as FKs sem CASCADE
    bloqueiam e a função devolve `'vinculos'` — a tela orienta usar o Desativar.
- **Update parcial:** `SET campo = COALESCE(%s, campo)` — só altera o que vier preenchido.
- **Dinheiro:** `NUMERIC(10,2)`. **Quantidade de estoque:** `NUMERIC(12,3)` (aceita litros).
- **Buscas:** parciais com `ILIKE` e `%termo%`.

---

## Schema por módulo (22 tabelas)

| # | Módulo | Tabelas | Arquivo .py | Status |
|---|--------|---------|-------------|--------|
| 1 | Cliente | `cliente` | `cadastro_cliente.py` | ✅ CRUD + ficha 360° + campanhas |
| 2 | Veículo | `categoria_veiculo`, `veiculo` | `cadastro_veiculo.py` | ✅ CRUD feito |
| 3 | Catálogo (serviços e preços) | `servico`, `servico_preco` | `catalogo_servicos.py` | ✅ CRUD + revisão 21/07 |
| 4 | Agendamento | `agendamento`, `agendamento_servico` | `agendamento.py` | ✅ CRUD feito |
| 5 | Ordem de Serviço (comanda) | `ordem_servico`, `ordem_servico_item` | `ordem_servico.py` | ✅ CRUD feito |
| 6 | Funcionário | `funcionario` | `funcionario.py` | ✅ CRUD feito |
| 7 | Estoque | `produto`, `movimentacao_estoque` | `estoque.py` | ✅ CRUD + revisão 21/07 |
| 8 | Fornecedores | `fornecedor` | `fornecedores.py` | ✅ CRUD + revisão 21/07 |
| 9 | Despesa | `despesa` | `despesa.py` | ✅ CRUD feito |
| 10 | Caixa | `caixa`, `caixa_movimento` | `caixa.py` | ✅ CRUD + revisão 22/07 |
| 11 | Dashboard | *(sem tabela — só consultas)* | `dashboard.py` | ✅ consultas feitas |
| 12 | Fidelidade | `fidelidade_saldo`, `fidelidade_movimento` | `fidelidade.py` | ✅ CRUD feito |
| 13 | Planos e Assinaturas | `plano`, `plano_servico`, `assinatura`, `assinatura_uso` | `planos_assinaturas.py` | ✅ CRUD feito |

A especificação detalhada de cada módulo (finalidade, dados, funcionalidades) está em
`documentacao_modulos_lavajato.txt`. A ordem de implementação segue a numeração acima.

### Decisões de modelagem
- **Cliente com aniversário e origem:** `cliente.data_nascimento` (DATE) e
  `cliente.como_conheceu` (VARCHAR 40 — "Indicação de amigo", "Instagram",
  "Passou na frente"…), via `ALTER TABLE ... IF NOT EXISTS`. Sustentam a campanha
  de parabéns no WhatsApp e a leitura de marketing (de onde vêm os clientes).
  ⚠️ Colunas novas entram **no fim do SELECT** de `buscar_clientes()`: as outras
  telas leem a tupla por posição (`c[0]`, `c[1]`, `c[3]`) e continuam intactas.
- **`editar_cliente()` não usa mais COALESCE:** o `SET campo = COALESCE(%s, campo)`
  tornava **impossível apagar** um campo (limpar o e-mail e salvar trazia o valor
  velho de volta). Agora o SET é montado dinamicamente com o sentinela
  `MANTER`: campo não passado = não mexe; campo passado como `None` = grava NULL
  (apaga). Os nomes das colunas vêm de um dict interno e os valores seguem como
  `%s` — sem risco de SQL injection. O `nome` (NOT NULL) é ignorado se vier vazio.
- **Categoria de veículo normalizada:** porte é FK (`veiculo.id_categoria` →
  `categoria_veiculo`), não texto livre. Categorias seed: Moto, Pequeno, Médio,
  Grande, SUV, Caminhonete, Caminhão.
- **Financeiro da comanda em `ordem_servico`:** `desconto`, `acrescimo`, `parcelas`,
  `valor_pago`, `data_pagamento`, `data_vencimento` (upgrade via `ALTER TABLE ... IF NOT EXISTS`
  no `criar_tabelas.sql`). `valor_final` (total − desconto + acréscimo) e `valor_pendente`
  são **calculados na exibição**, não armazenados. Atualização via `salvar_financeiro()`.
- **Preço por porte:** `servico_preco` é a matriz serviço × categoria
  (`UNIQUE(id_servico, id_categoria)`), em vez de colunas fixas por porte.
- **Relações N:N** via tabelas de ligação: `agendamento_servico`,
  `ordem_servico_item`, `plano_servico`.
- **`ordem_servico_item.preco_aplicado`** congela o preço cobrado na comanda
  (histórico imune a reajustes futuros).
- **Quem lavou por serviço:** `ordem_servico_item.id_funcionario` grava o executor
  de cada item (não só o responsável da comanda). Escolhido no dropdown "Quem lavou"
  ao adicionar o serviço; aparece por item na tela e como coluna **Lavador** no recibo.
- **Vistoria de entrada:** `ordem_servico.avarias` (danos observados na chegada — protege
  contra reclamação de dano pré-existente) e `ordem_servico.observacoes` (anotações gerais).
  Colunas TEXT via `ALTER TABLE ... IF NOT EXISTS`; salvas por `salvar_observacoes()`
  (atribuição direta, não COALESCE — o form envia os dois juntos e '' limpa). As avarias
  saem no recibo PDF como comprovante.
- **`funcionario.senha_hash`**: nunca senha em texto puro.
- **Caixa e Fidelidade** com tabela de movimento separada (entradas/saídas,
  acúmulo/resgate), preservando histórico em vez de só um saldo.

---

## Arquivos principais

- `conexao.py` — conexão única com o banco.
- `criar_tabelas.sql` / `criar_tabelas.py` — schema e criação das tabelas.
- `cadastro_cliente.py`, `cadastro_veiculo.py` — módulos já implementados (referência de padrão).
- `validadores.py` — **sem banco**: máscaras (CPF/CNPJ, telefone, data) e validação
  (CPF/CNPJ por dígito verificador, e-mail, telefone, data). `python validadores.py` testa.
- `whatsapp.py` — **sem banco**: monta o link `wa.me/<numero>?text=<msg>` e os 6 modelos
  de mensagem (veículo pronto, feliz aniversário, promoção, sentimos sua falta, em
  andamento, lembrete de pagamento). **Não é API**: o link abre a conversa com o texto
  já digitado e o atendente aperta enviar — de graça, sem token nem número verificado.
- `dashboard.py` — consultas somente leitura dos indicadores do Dashboard.
- `app.py` — **interface gráfica (Flet)**: login + 13 telas reaproveitando os módulos de CRUD.
  Rodar com `python app.py`. Logo da marca em `imagen/trucka car.png`.
- `requirements.txt` — dependências (psycopg2, bcrypt, flet, reportlab).
- `documentacao_modulos_lavajato.txt` — especificação funcional dos 13 módulos.

---

## Estado atual / Próximos passos

- Schema completo já criado no `lavajato_db` (22 tabelas, FKs íntegras).
- **Backend dos 13 módulos completo** (CRUD nos módulos 1–10, 12 e 13; consultas de
  indicadores no 11 — `dashboard.py`).
- Dados de teste no banco: `categoria_veiculo` (7 portes), `cliente` (id 1), `servico` (id 1 com preços),
  `veiculo` (id 1), `agendamento` (id 1), `ordem_servico` (id 1), `funcionario` (id 1),
  `produto` (id 1), `fornecedor` (id 1), `despesa` (id 1 paga, id 2 em aberto), `caixa` (id 1 fechado),
  `fidelidade_saldo` (cliente 1, 6 pontos), `plano` (id 1) + `assinatura` (id 1).
- **Módulo 11 (Dashboard): implementado como cards de KPI.** `dashboard.py` concentra as
  consultas (somente leitura): `faturamento('hoje'/'mes')`, `ticket_medio(dias)`,
  `servicos_mais_vendidos(dias, limite)`, `taxa_retorno(dias)`, `tempo_medio_servico(dias)`
  e `horarios_pico(dias)` — `python dashboard.py` imprime todos (teste rápido).
  Faturamento/ticket usam o **valor final** (valor_total − desconto + acréscimo).
  A tela Dashboard do `app.py` mostra 11 cards (via `mod_dash`); **gráficos ficaram para
  depois** (avaliar no decorrer da construção — `horarios_pico`/`servicos_mais_vendidos`
  já devolvem séries prontas para virar barras).
- **Frontend feito em Flet (`app.py`)** — stack escolhida: Flet (Python puro, `flet==0.85.3`).
  Login real via `autenticar()` + 13 telas reaproveitando os módulos, sem alterar o backend.
  Telas com CRUD: Clientes, Veículos, Serviços (+preços por porte), Agendamentos, Comandas,
  Funcionários, Fornecedores, Estoque (+movimentações), Despesas, Fidelidade, Planos/Assinaturas,
  Caixa; + Dashboard com KPIs reais. Identidade visual da marca (logo + paleta azul-marinho/azul-claro).
  - ⚠️ Flet 0.85 tem API nova: `ft.Colors`/`ft.Icons`, `ft.Alignment.CENTER`, `ft.Padding.symmetric`,
    `ft.BoxFit`, `page.show_dialog()`/`pop_dialog()`, `ft.run(main)`, `ft.Image(src=bytes)`,
    `TextField(prefix=/suffix=/helper=Control)` (não `*_text`).
- **Financeiro da comanda + recibo:** a tela de Comandas tem formulário de pagamento
  (desconto, acréscimo/juros, forma, parcelas, valor pago, datas de pagamento/vencimento)
  via `salvar_financeiro()`, e gera recibo em PDF (`gerar_recibo_pdf()` com reportlab),
  salvo em `recibos/` (pasta ignorada pelo git). O recibo lista **Serviço · Lavador · Valor**
  e traz seção **Vistoria de entrada** (avarias) quando preenchida.
- **Integração Comanda → Caixa (2026-07-16):** salvar o pagamento da comanda agora
  lança a entrada no caixa aberto automaticamente. A tela chama a nova
  `caixa.total_entradas_da_ordem(id_ordem)` (soma de `caixa_movimento` por `id_ordem`,
  tipo entrada) e registra só a **diferença** para o valor pago — re-salvar o pagamento
  não duplica, e pagar o resto depois lança só o resto. Sem caixa aberto: o pagamento
  é salvo mesmo assim e um aviso manda abrir o caixa e salvar de novo (aí o delta entra).
  Valor pago menor que o já lançado: aviso sugere registrar saída manual na tela Caixa.
  O movimento fica rastreável (grava `id_ordem` + descrição "Comanda #N — cliente (placa)").
  Desde 22/07 a entrada leva junto a **forma de pagamento** — ver [Módulo 10 (Caixa)].
- **Reabrir comanda para correção (2026-07-16):** comanda entregue/cancelada fica
  travada na tela (edição desabilitada); o botão **"Reabrir p/ correção"** (só aparece
  nesses status, com diálogo de confirmação) destrava: entregue volta a `finalizado`
  (continua contando no faturamento) e cancelada volta a `em_execucao`. Os horários
  originais não mudam (`alterar_status` só grava `inicio_em`/`finalizacao_em` na 1ª vez).
  Correção de pagamento após reabrir usa a integração com o caixa (lança só a diferença).
- **Quem lavou + vistoria (na comanda):** dropdown "Quem lavou" ao adicionar serviço
  (grava `ordem_servico_item.id_funcionario`; item mostra "Lavou: …" ou "Sem responsável"),
  e seção "Vistoria de entrada / Observações" com `avarias`/`observacoes` via
  `salvar_observacoes()`. Ver [Decisões de modelagem].
- **Correção (fechamento de caixa):** `caixa.fechar_caixa()` quebrava com `TypeError`
  (`float − Decimal`) ao calcular a diferença — o caixa até fechava no banco (o `commit`
  vinha antes), mas o erro fazia a função devolver `None` e o app mostrava "não foi possível
  fechar". Corrigido convertendo o `saldo_real` para `Decimal` no início da função
  (`Decimal(str(saldo_real))`). Coberto pelo teste E2E do backend.
- **UI:** menu lateral com fonte/ícones maiores (ícones 28, texto 18) para melhor legibilidade.
- **Módulo 1 (Cliente) turbinado — 2026-07-12.** A tela de Clientes deixou de ser um
  cadastro isolado e virou a ferramenta de relacionamento:
  - **WhatsApp** (ícone verde na lista e botão na ficha): abre a conversa com a mensagem
    pronta escolhida num menu (ver `whatsapp.py`). O veículo do cliente entra no texto
    ("seu Fiat Toro (ABC-1234) está pronto"). `page.launch_url(link)`.
  - **Ficha do cliente** (ícone do crachá): visão 360° num diálogo — KPIs (visitas, total
    gasto, ticket médio, pontos, valor em aberto), dados de cadastro, veículos, serviços
    preferidos e histórico das 20 últimas comandas. Vem tudo de `mod_cli.ficha_cliente()`,
    que usa o **mesmo critério de faturamento do `dashboard.py`** (status finalizado/entregue,
    valor final) — por isso os números batem entre as telas.
  - **Listas de campanha** (dropdown "Lista"): Aniversariantes do mês / Sumidos (60+ dias) /
    Top 10 que mais gastam. Cada modo filtra a tabela, acrescenta uma coluna com a
    informação relevante e **sugere a mensagem de WhatsApp** correspondente.
  - **Máscaras e validação** no formulário: CPF/CNPJ, telefone e data se formatam sozinhos
    ao digitar; CPF/CNPJ é conferido por dígito verificador; e-mail e telefone validados.
    Erro aparece embaixo do campo.
  - **Anti-duplicidade:** ao salvar, avisa se já existe cliente com o mesmo telefone,
    documento ou nome — mas não bloqueia (marido e mulher podem dividir o telefone).
  - **Exportar CSV** da lista que está na tela (respeita busca e filtro) → pasta
    `exportacoes/` (ignorada pelo git), em `utf-8-sig` + `;` para o Excel BR abrir certo.
- ⚠️ **Mais armadilhas do Flet 0.85** (achadas neste módulo): o aviso de erro do campo é
  `TextField(error=ft.Text(...))` — um **Control** —, **não** `error_text="..."` (a API
  antiga é ignorada em silêncio: o erro nunca aparece). E o rótulo do botão fica em
  `.content`, não em `.text`.
- ⚠️ **Armadilha Flet 0.85 (diálogos): nunca chame `pop_dialog` duas vezes no mesmo
  handler.** Os diálogos ficam numa pilha; `pop_dialog` só marca `open=False` no de
  cima e a remoção real acontece depois da animação (async). Pop duplo + push no mesmo
  clique dessincroniza o Python do Flutter e deixa um diálogo "fantasma" preso na tela,
  impossível de fechar (bug real no "Reabrir p/ correção", 16/07). Receita: **um diálogo
  aberto por vez** — feche o atual ANTES de abrir o próximo (ver `confirmar_reabrir`).
- **Fix do WhatsApp (`app.py`, `menu_whatsapp`):** `page.launch_url()` **não abre nada** nesta
  versão do Flet — virou corrotina (async) e, chamada de um handler comum, devolve uma corrotina
  que ninguém aguarda; falha em silêncio (só o `RuntimeWarning "coroutine was never awaited"` no
  terminal). Trocado por `webbrowser.open(link)` (síncrono, biblioteca padrão, abre o navegador
  do Windows — que é onde o WhatsApp Web roda). Testado e funcionando.

### Módulo 2 (Veículo) — turbinado (backlog de 2026-07-13, concluído em 2026-07-18)
A tela de Veículos era CRUD + busca + histórico de comandas. Backlog acordado, **na ordem**:

**✅ Fase 1 — bugs e validação (feita em 2026-07-14)**
1. **Placa duplicada** — nova `buscar_veiculo_por_placa()` (em `cadastro_veiculo.py`, normaliza
   caixa e traço: `abc1234` acha `ABC-1234`; traz inativos também). A tela checa **antes** de
   inserir/editar e avisa *"Placa ABC-1234 já cadastrada: Fiat Uno do cliente Fulano"* em vez do
   antigo *"verifique a conexão"*. Na edição, ignora o próprio veículo.
2. **`editar_veiculo()` agora usa o sentinela `MANTER`** (COALESCE removido): campo não passado
   fica como está; passado como `None` **apaga** (grava NULL). `id_cliente`/`id_categoria`/`placa`
   são NOT NULL → vazios são ignorados (nunca viram NULL). Mesma receita do `cadastro_cliente.py`.
   Coberto por teste de round-trip contra o banco (apagar cor e restaurar).
3. **Placa e ano validados no `validadores.py`:** `mascara_placa()` (formata `ABC-1234`/`ABC1D23`
   ao digitar), `validar_placa()` (antigo `[A-Z]{3}[0-9]{4}` ou Mercosul `[A-Z]{3}[0-9][A-Z][0-9]{2}`)
   e `validar_ano_veiculo()` (1900 até o ano que vem — barra 1800/3050). A tela aplica máscara no
   `on_change` da placa, só-dígitos no ano, e valida no salvar.
4. **Dropdown de Cliente com busca:** `enable_filter=True` + `hint_text` (mesmo padrão já usado em
   Comandas/Agendamentos) — digita o nome pra filtrar em vez de rolar centenas.

**✅ Fase 2 — "raio-x do carro" (feita em 2026-07-18)**
5. **WhatsApp na linha do veículo:** `menu_whatsapp`/`botao_whatsapp` ganharam o parâmetro
   `veiculo_pref` (placa) — o carro daquela linha já vem selecionado no dropdown da
   mensagem ("seu Fiat Uno (ABC-1234) está pronto"), com o modelo "Veículo pronto" sugerido.
6. **Coluna "Última lavagem"** na tabela: `buscar_veiculos()` ganhou `c.telefone` e a
   subquery `ultima_lavagem` (MAX de `entrada_em`, só finalizado/entregue — mesmo critério
   do dashboard) **no fim do SELECT** (13 colunas; índices antigos preservados).
7. **Ficha do veículo 360°:** `ficha_veiculo()` em `cadastro_veiculo.py` (dict com veiculo/
   resumo/servicos/comandas/avarias, mesmo critério de faturamento do dashboard) + diálogo
   `abrir_ficha_veiculo` — KPIs, dados do carro, serviços preferidos, **vistorias de entrada
   (avarias)** e histórico de comandas. **Substituiu o antigo diálogo "Histórico"** (o
   histórico agora vive dentro da ficha; ícone `ASSIGNMENT` na linha).
8. **Botão "Novo veículo" na ficha do cliente:** o `form_veiculo` foi **extraído para o
   escopo do `main()`** (compartilhado) com `cliente_fixo` (dono pré-selecionado) e
   `ao_salvar` (callback pós-salvar: a tela de Veículos passa o `atualizar` dela; a ficha
   do cliente reabre a si mesma para mostrar o carro novo). Fecha a ficha ANTES de abrir
   o formulário (regra de um diálogo por vez).
9. **Exportar CSV** da lista (respeita busca e filtro de inativos) → `exportacoes/`,
   `utf-8-sig` + `;`, mesmo padrão de Clientes.

### Módulo 4 (Agendamento) — turbinando (combinado em 2026-07-19)
Diagnóstico de 19/07: backend sólido (conflito de box com matemática de sobreposição,
transação única no criar, ponte "Gerar comanda" que copia serviços com preço do porte
e marca o agendamento como em_execucao). Backlog acordado, **na ordem**:

**✅ Fase 1 — básico do dia a dia (feita em 2026-07-19)**
1. **Tela abre filtrada em HOJE** + botões Hoje/Amanhã/Todos + data em dd/mm/aaaa com
   máscara. Digitação parcial não filtra ainda; data completa mas inválida mostra
   "Data inválida" em vez de fingir lista vazia.
2. **Filtro de status:** dropdown "Ativos (agenda viva)" (padrão) / Todos / individuais.
   `buscar_agendamentos()` agora aceita um status OU uma lista (`= ANY(%s)`).
3. **Máscara/validação de data e hora** nos forms Novo e Remarcar (dd/mm/aaaa + HH:MM;
   `mascara_hora()` nova no `validadores.py`).
4. **`remarcar()` migrado de COALESCE para o sentinela `MANTER`** (mesmo padrão de
   cliente/veículo): limpar o box ao remarcar agora TIRA o carro do box — antes o
   COALESCE mantinha o box velho em silêncio. A checagem de conflito usa o box/duração
   que valerão DEPOIS do update. Round-trip testado no banco (trocar → limpar → restaurar).
5. **Duração sugerida:** marcar serviços soma `servico.tempo_medio_min` e preenche a
   duração. Operador digitou → sugestão para de mexer; apagou tudo → volta a sugerir.

**🔨 Fase 2 — a agenda vira ferramenta (em andamento)**
6. ✅ **WhatsApp do agendamento (2026-07-19):** modelo novo "Lembrete de agendamento" no
   `whatsapp.py` + botão na linha e no detalhe (`menu_whatsapp` com `veiculo_pref`).
7. ✅ **Aviso de cliente "furão" (2026-07-20):** `historico_faltas(id_cliente)` no
   `agendamento.py` devolve `(faltas, total)` numa passada só (`COUNT(*) FILTER`). O
   detalhe mostra uma faixa **só quando há falta** — âmbar normalmente, **vermelha a
   partir de 1/3 de faltas** (aí sugere confirmar por WhatsApp antes de reservar o box).
   O total vai junto de propósito: 2 faltas em 3 vindas é alerta, 2 em 40 é vida normal.
8. ✅ **Aviso de mesmo veículo agendado 2x no mesmo dia (2026-07-20):**
   `agendamentos_do_veiculo_no_dia(id_veiculo, data_hora, ignorar_id=None)` — compara
   só a DATA (`::date` dos dois lados) e só conta `STATUS_ATIVOS`, então agendamento
   cancelado/furado não gera alarme falso. **Avisa, não bloqueia** (lavagem de manhã +
   polimento à tarde é legítimo): a confirmação é em **dois cliques no próprio botão
   Agendar** (1º mostra o aviso laranja, 2º grava) — de propósito, para **não abrir um
   segundo diálogo por cima do formulário** (ver a armadilha dos diálogos do Flet 0.85).
   Trocar o carro ou a data zera a confirmação (`limpar_avisos`).
9. 🔜 **Editar serviços/observações** de agendamento existente (hoje só remarca
   data/box/duração; trocar serviço exige cancelar e criar de novo). — **próximo**

⚠️ **Pendente de conferência na tela (itens 7 e 8):** o backend das duas funções novas
foi testado contra o banco (inclusive casos-limite: acha o agendamento das 9:00
procurando às 15:00, `ignorar_id` funciona, `nao_compareceu` não gera alarme falso) e o
`app.py` compila, mas **as faixas de aviso ainda não foram vistas rodando**. Para fechar:
- **Item 7:** abrir o **agendamento #1** (cliente 1 tem 1 falta em 1 agendamento = 100%)
  → a faixa deve sair **vermelha**, com "Vale confirmar por WhatsApp antes".
- **Item 8:** em *Novo agendamento*, escolher o veículo do **agendamento #5** na data
  **19/07/2026** → aviso laranja no 1º clique em Agendar, grava só no 2º.

### Módulo 3 (Catálogo de Serviços) — bugs corrigidos em 2026-07-21
Revisão do módulo achou 4 defeitos, todos corrigidos e testados contra o banco:
1. **`editar_servico()` migrado de COALESCE para o sentinela `MANTER`** — era o mesmo
   bug já corrigido em cliente/veículo/agendamento: limpar a descrição (ou o tempo médio)
   e salvar trazia o valor velho de volta. Agora campo não passado = não mexe; passado
   como `None` = apaga. `nome` (NOT NULL) é ignorado se vier vazio.
2. **Nome duplicado avisa com jeitinho** — `servico.nome` é UNIQUE, então o INSERT
   estourava no banco e a tela só dizia "não foi possível salvar". Nova
   `buscar_servico_por_nome()` (normaliza espaços e caixa via `BTRIM(...) ILIKE`, traz
   **inativos** também) checada antes de gravar; se o serviço existente estiver inativo,
   a mensagem manda marcar "Incluir inativos" para reativá-lo.
3. **Fim do "sucesso" falso ao salvar preços** — a tela ignorava o retorno de
   `definir_preco`/`remover_preco` e dizia "Preços atualizados" mesmo quando o banco
   recusava (a tabela tem `CHECK (preco >= 0)`, e nada impedia digitar `-10`). Agora o
   negativo é barrado na validação da tela, `definir_preco()` também recusa valor
   negativo/não numérico **antes** de abrir conexão, e o salvar acumula as falhas e
   nomeia os portes que não gravaram. Tempo médio ficou limitado a 1–1440 min
   (`tempo_medio_min` é SMALLINT).
4. **Fim do N+1 na lista** — `montar_linhas()` chamava `precos_do_servico()` dentro do
   laço (1 + N conexões ao banco **a cada tecla** digitada na busca, que refaz a lista no
   `on_change`). Nova `resumo_precos(apenas_ativos=)` traz `{id_servico: (qtd, mín, máx)}`
   numa consulta só; de quebra a coluna Preços agora mostra a **faixa** praticada
   ("3 porte(s) · R$ 20,00 a R$ 55,50") em vez de só a contagem.

**Ideias levantadas e ainda não feitas** (por ordem de retorno): reajuste de preços em
massa (%/valor, com prévia — hoje um aumento anual é redigitar serviço × porte na mão);
tela "Tabela de preços" usando a `tabela_de_precos()`, que está pronta no backend e
**nunca foi usada** (vira a tabela da casa, exportável/imprimível); ficha do serviço 360°
(vendas, faturamento e **tempo real médio × `tempo_medio_min` cadastrado** — se o
cadastrado mentir, a agenda estoura o dia); duplicar serviço copiando a matriz de preços;
exportar CSV (Clientes e Veículos já têm); filtro "sem preço definido".

### Módulo 7 (Estoque) — bugs corrigidos em 2026-07-21
A base do módulo já era boa (entrada/saída atualizam saldo + histórico na mesma transação,
e a saída usa `SELECT ... FOR UPDATE` contra condição de corrida). A revisão achou 6 defeitos
+ 1 extra, todos corrigidos e testados contra o banco (38 checks):
1. **`editar_produto()` migrado de COALESCE para o sentinela `MANTER`** — quinto módulo com
   o mesmo bug. Sintoma visível: escolher **"(nenhum)"** no fornecedor **não desvinculava**,
   e limpar a unidade de medida trazia o valor velho de volta.
2. **Valores negativos barrados** — `quantidade` e `estoque_minimo` **não têm CHECK** no
   Postgres (só `custo_unitario`/`preco_venda` têm), então dava para cadastrar produto
   nascendo com saldo negativo. Novo helper `_numero_valido()` valida **antes de abrir
   conexão**, e a tela valida antes de chamar o backend (mensagem específica por campo).
3. **Saldo inicial agora vira movimentação** — `inserir_produto()` grava uma entrada
   "Saldo inicial do cadastro" na **mesma transação**. Antes o produto nascia com saldo e
   histórico vazio: a soma das movimentações nunca batia com `produto.quantidade`.
4. **Produto duplicado avisa** — `produto.nome` **não é UNIQUE** (diferente de `servico.nome`),
   então dois "Shampoo Automotivo" dividiam o estoque real em dois cadastros e o alerta de
   mínimo não disparava em nenhum. Nova `buscar_produto_por_nome()` (normaliza espaços/caixa
   com `BTRIM(...) ILIKE`, traz inativos) checada antes de gravar; a mensagem mostra o saldo
   do existente e manda usar Entrada nele.
5. **Fim da 2ª consulta por tecla digitada** — `montar_linhas()` chamava
   `produtos_abaixo_minimo()` além do `buscar_produtos()`; agora o "está no vermelho?" é
   calculado em Python (`quantidade <= mínimo`) com os dados que a lista já trouxe. De quebra
   some um bug: aquela consulta só devolvia **ativos**, então com "Incluir inativos" marcado
   o produto inativo em falta aparecia **sem o alerta vermelho**.
6. **Coluna `preco_venda` deixou de ser órfã** — existia no schema (com comentário "venda de
   balcão") e **nenhuma linha do projeto lia ou escrevia nela**. Agora entra no CRUD (campo no
   formulário + coluna "Venda" na lista, "—" quando zerada). A venda de balcão em si continua
   não implementada — o dado só passou a ser cadastrável.
7. **Extra achado na revisão:** o dropdown de fornecedor lia `produto[6]`, que é o **nome**
   do fornecedor, não o id — na edição ele vinha em branco. Corrigido com `p.id_fornecedor`
   acrescentado **no fim** do SELECT (índice 9; `preco_venda` no 8 — índices antigos intactos).

**Ideias levantadas e ainda não feitas** (por ordem de retorno): baixa automática de produto
ao lançar o serviço na comanda (é o "vincular consumo a serviços" da documentação — hoje a
saída é 100% manual, então na prática o saldo vira ficção); gerar despesa ao dar entrada
(mesma ponte da Comanda→Caixa); ficha do produto 360° (consumo médio/mês e "dura mais ~N dias",
que transforma o estoque mínimo num número pensado em vez de chute); card "dinheiro parado em
estoque" (Σ qtd × custo) + filtro "só os em falta"; movimentação do tipo **ajuste de inventário**
(hoje a contagem física vira uma "saída" mentirosa — exige mexer no `CHECK (tipo IN ...)`);
exportar CSV.

### Módulo 8 (Fornecedores) — bugs corrigidos em 2026-07-21
Era o módulo mais simples (CRUD puro + produtos vinculados) e justamente por isso ficou para
trás: enquanto Clientes ganhou máscara, validação e WhatsApp, aqui **nada disso tinha chegado**.
5 defeitos corrigidos e testados contra o banco (43 checks):
1. **`editar_fornecedor()` migrado de COALESCE para o sentinela `MANTER`** — sexto módulo com
   o mesmo bug: não dava para **apagar** telefone, e-mail, CNPJ nem condições de pagamento.
2. **CNPJ duplicado avisa com jeitinho** — `fornecedor.cnpj` é UNIQUE, então o INSERT estourava
   no banco e a tela só dizia "não foi possível salvar". Nova `buscar_fornecedor_por_cnpj()`
   compara **só os dígitos** dos dois lados (`regexp_replace(cnpj, '[^0-9]', '', 'g')`), então
   acha o cadastro antigo digitado sem máscara; traz **inativos** também.
3. **Máscara e validação na tela** (o mais visível) — a tela não usava **nada** do
   `validadores.py`, que já estava pronto e em uso em Clientes: dava para salvar CNPJ "abc",
   e-mail "xyz" e telefone "123". Agora CNPJ e telefone se formatam ao digitar
   (`mascara_cpf_cnpj`/`mascara_telefone`) e CNPJ (dígito verificador), e-mail e telefone são
   validados no salvar, com o erro embaixo do campo (`error=ft.Text(...)`, nunca `error_text`).
   Campo vazio segue válido — tudo aqui é opcional.
4. **Aviso ao desativar fornecedor com produtos vinculados** — nova
   `contar_produtos_vinculados()` devolve `(ativos, total)` numa passada só (`COUNT FILTER`,
   mesmo padrão do `historico_faltas`). Antes o fornecedor sumia da lista em silêncio e, na
   hora de repor o estoque, ninguém lembrava que ele fora desativado. **Avisa, não bloqueia.**
5. **Histórico de compras — lacuna da própria especificação** ("consultar histórico de compras
   por fornecedor", nunca implementado, embora `despesa.id_fornecedor` já existisse e fosse
   preenchido). Nova `compras_do_fornecedor()` devolve `{'resumo', 'despesas'}` com qtd, total,
   **total pago × total em aberto** (`SUM FILTER` por `data_pagamento IS NULL`) e última compra;
   novo diálogo na tela (ícone `RECEIPT_LONG`) com os 5 mini-cards + a lista das 20 últimas.

**Ideias levantadas e ainda não feitas** (por ordem de retorno): **lista de compras + pedido por
WhatsApp** — abrir os produtos do fornecedor destacando os abaixo do mínimo e montar a mensagem
pronta ("preciso de 20 L de shampoo, 5 un de cera"), juntando Estoque + Fornecedor + WhatsApp,
que já existem; contato rápido (WhatsApp/e-mail na linha, como em Clientes); ficha do fornecedor
360°; exportar CSV.

⚠️ **Pendente de conferência na tela (módulos 3, 7 e 8).** O backend das três revisões foi
testado contra o banco (25 + 38 + 43 checks) e o `app.py` compila, mas **as telas ainda não
foram vistas rodando** — a tentativa de 21/07 foi abortada depois do acidente do caixa (ver
"Testar o app na tela"). Roteiro para fechar, com o operador navegando:
- **Estoque:** "Novo produto" com nome `Shampoo Automotivo` → aviso de duplicado com o saldo
  do existente; custo `-10` → "O custo não pode ser negativo"; **editar** o Shampoo → o
  dropdown Fornecedor deve vir **preenchido** (era o bug do `produto[6]`).
- **Fornecedores:** editar "Central de tolha" (CNPJ `51044074000160`, gravado **sem máscara**)
  → o CNPJ deve se formatar ao digitar; e-mail `xyz` → erro embaixo do campo; ícone de recibo
  na Distribuidora AutoLimp → histórico de compras com os 5 mini-cards.
- **Serviços:** a coluna Preços deve mostrar a **faixa** ("3 porte(s) · R$ 20,00 a R$ 55,50").

### Módulo 10 (Caixa) — forma de pagamento e ponte Despesa→Caixa (2026-07-22)
Revisão do caixa achou 7 problemas; os **2 primeiros foram feitos** (31 checks contra o
banco, dados de teste apagados no fim). A matemática do saldo já estava certa — o
problema era **conceitual**, do tipo que só aparece no balcão.

1. ✅ **O fechamento nunca ia bater.** O saldo esperado era `fundo + TODAS as entradas −
   saídas`, mas a tela pede *"conte o dinheiro na gaveta"*. Pix e cartão entram no caixa
   e vão para o **banco** — cobrá-los da gaveta fazia o app acusar **falta todo dia** em
   que alguém pagasse no cartão, e o pessoal aprenderia a ignorar justamente o aviso que
   existe para detectar dinheiro sumindo. Correções:
   - `caixa_movimento.forma_pagamento` (VARCHAR 20, via `ALTER TABLE ... IF NOT EXISTS`),
     copiada da comanda/despesa que originou o movimento. **NULL = dinheiro** (regra em
     `FORMAS_EM_ESPECIE` + `_em_especie()`), então os 6 movimentos antigos seguem valendo.
   - `resumo_por_forma(id_caixa)` — numa consulta só devolve a quebra por forma
     (`GROUP BY`, com `COALESCE(NULLIF(BTRIM(...),''),'dinheiro')` normalizando no banco)
     + `esperado_dinheiro` (**o que está na gaveta**, único número comparável com a
     contagem física) e `esperado_total` (o giro do dia, com pix/cartão).
   - `fechar_caixa()` agora confere contra o **esperado em espécie**; devolve
     `esperado` (=espécie), `esperado_total` e `resumo`. `saldo_esperado()` ficou como
     está (giro total) e não é mais usada pela tela.
   - Tela: painel mostra **"Na gaveta"** (grande) × **"Giro do dia"**, mais chips por
     forma (verde = espécie, cinza com ícone de banco = pix/cartão); coluna **Forma** nos
     movimentos; e o diálogo de fechar traz a faixa âmbar *"Não conte estes — foram para
     o banco"* com os valores de pix/cartão.
2. ✅ **Despesa paga não saía do caixa.** `caixa_movimento.id_despesa` existia no schema e
   `registrar_saida()` aceitava o parâmetro, mas **nenhuma linha do projeto passava** —
   mesma **coluna órfã** do `preco_venda` no Estoque, e a especificação do módulo pedia
   *"Saídas (despesas pagas no dia)"*. A ponte Comanda→Caixa (16/07) nunca ganhou o par.
   Agora "Marcar como paga" lança a saída no caixa aberto, com a mesma receita anti-dupla:
   nova `total_saidas_da_despesa()` (espelho de `total_entradas_da_ordem`) e lançamento
   só do **delta**. Guarda importante: **pagamento com data diferente de hoje NÃO entra
   no caixa de hoje** (o caixa é diário) — a tela avisa. Sem caixa aberto, avisa para
   abrir e marcar de novo.

**Achado e ainda não feito** (por ordem de retorno): **3.** aviso de caixa esquecido
aberto de dias anteriores (hoje as vendas caem no caixa de anteontem em silêncio e o
faturamento dos dois dias se mistura); **4.** estorno de movimento errado (digitou 500 em
vez de 50 → só dá para lançar uma saída falsa que suja o histórico); **5.** conferência no
histórico (a lista mostra fundo e saldo final, mas não o esperado nem a sobra/falta, e não
dá para clicar num dia e ver os movimentos — `movimentos_do_caixa()` já está pronta);
**6.** `caixa.observacoes` é **uma coluna só** para abertura e fechamento, então anotar algo
no fechamento **apaga** a anotação da abertura; **7.** `valor_inicial` sem CHECK no banco e
sem validação em `abrir_caixa()` — dá para abrir caixa com fundo negativo (mesma família de
bug do Estoque); e `abrir_caixa()` tem TOCTOU (checa e insere) — um índice único parcial
`WHERE status='aberto'` tornaria a invariante real no banco.
*Ideias de valor:* comprovante de fechamento em PDF (o "Z do dia", já temos reportlab);
aviso ao fechar de **comandas entregues hoje sem pagamento** (pega carro que saiu sem
cobrar); sangria/suprimento como tipo próprio; resumo do dia no fechamento.

⚠️ **Pendente de conferência na tela.** Backend testado contra o banco e `app.py` compila,
mas as telas não foram vistas rodando. Roteiro (operador navegando):
- **Caixa:** abrir caixa → Entrada de R$ 100 em **Pix** → o painel deve mostrar
  **"Na gaveta"** sem o pix e **"Giro do dia"** com ele, e um chip cinza "Pix +R$ 100,00".
- **Fechar caixa:** a faixa âmbar *"Não conte estes"* deve listar o pix, e contar só o
  dinheiro deve fechar **"bateu certinho"**.
- **Despesas:** marcar uma despesa como paga (data de hoje) → mensagem *"Saída de R$ X
  lançada no caixa"*, e o movimento aparece na tela Caixa com Ref. `desp #N`.

### Dívidas estruturais do projeto (levantadas em 2026-07-21, nada feito)
Diagnóstico pedido pelo Lucas ("esse sistema foi bem estruturado certo?"). Resumo: **a dívida
está toda na camada de cima** — banco e backend, que são a parte cara, estão certos; por isso
dá para refatorar depois sem redesenhar nada.
1. **`app.py` com 5.102 linhas** (45% das 11.442 do projeto), com as 13 telas como funções
   aninhadas dentro de um único `main()`. Sai aos pedaços para uma pasta `telas/`, depois de
   extrair o que é compartilhado (`page`, `sucesso`/`aviso`, `abrir_dialog`, paleta) para um
   `ui_comum.py`. **Custo não cresce com o tempo.**
2. **Telas leem o banco por posição na tupla** (`c[0]`, `p[3]`) — é a origem da regra "colunas
   novas entram no FIM do SELECT". Cura: `RealDictCursor` (vira `p["nome"]`), módulo por módulo.
   ⚠️ **É a única cujo custo cresce a cada tela nova.**
3. **Erros viram `print()` e somem** — a função devolve `False`/`None` e o motivo fica no
   terminal; por isso as telas só conseguem dizer "Não foi possível salvar". É o que está por
   trás de boa parte dos bugs corrigidos em Serviços e Estoque.
   *Menores:* uma conexão nova por chamada (~135 funções, sem pool) e testes como blocos
   `if __name__ == "__main__"` que escrevem no banco real, sem pytest nem banco de teste.

**Decisão:** seguir com funcionalidades agora; atacar as dívidas 1 e 2 depois do `flet pack`,
e melhorar as mensagens de erro (dívida 3) de carona nos módulos que forem sendo mexidos.

- **Depois disso:** mais gráficos no Dashboard (o 1º saiu em 2026-07-20 — "De onde vêm
  os clientes", via `dashboard.origem_clientes()`; `horarios_pico` e
  `servicos_mais_vendidos` já devolvem séries prontas para o mesmo estilo de barras);
  empacotar como executável (`flet pack`); refinos de UX. `app.py` mantém a paleta/logo
  centralizadas no topo.
  - **Padrão de gráfico do projeto:** barras horizontais desenhadas na mão (`ft.Container`
    com largura proporcional ao maior valor), **sem** a API de gráficos do Flet — simples,
    sem dependência nova e imune às trocas de API da 0.85.
    ✅ Conferido rodando em 2026-07-20: "Não informado" cinza (3 · 75%) e "Google" azul
    (1 · 25%), proporções corretas.

### Testar o app na tela (Windows)
`python app.py` abre uma **janela nativa** — o processo do Python fica de pé e a janela
é um processo separado chamado `flet` (título "Truck Center Lavação — Gestão"), que é
por onde se acha o handle. Dá para tirar print via `System.Drawing` + `GetWindowRect`.
⚠️ **Não use `ShowWindow(SW_RESTORE)` antes de capturar:** ele *desmaximiza* a janela e
muda o layout no meio do teste (as coordenadas de clique viram lixo). Use só
`SetForegroundWindow`. E o **primeiro clique depois de trazer a janela para frente é
consumido só para dar foco** — clique duas vezes ou dê foco antes.

⚠️ **A janela MUDA DE TAMANHO sozinha no login** (aprendido na marra em 2026-07-21):
abre em ~1180x740 e **maximiza para o tamanho da tela depois de entrar**. Ela também
**minimiza sozinha ao perder o foco** (aí `GetWindowRect` devolve `-32000,-32000`, que é
o "endereço" de janela minimizada no Windows — se capturar assim, o print sai com 160x28).
Receita segura: **reconferir o rect a cada passo** (`IsIconic` → se minimizada,
`ShowWindow(h, 3)` = maximizar, nunca 9/RESTORE) e **tirar print ANTES de cada clique**
para confirmar o alvo.

🚨 **Clicar às cegas mexe em dados de verdade.** Em 21/07 um clique com coordenada velha
(calculada sobre a janela pequena, depois que ela já tinha maximizado) caiu no botão
"Abrir caixa" e **criou o caixa #5 no banco** — teve de ser apagado na mão. O app não
tem modo de teste: **toda tela grava no banco real do TrueNAS.** Para conferência visual,
o caminho barato e sem risco é o operador navegar e o assistente só capturar a tela.
