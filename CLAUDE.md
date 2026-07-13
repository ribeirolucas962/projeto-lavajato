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

- **SGBD:** PostgreSQL 16, em `localhost:5432`.
- **Banco do projeto:** `lavajato_db` (user `postgres`, senha `123456`).
- Conexão centralizada em `conexao.py` → função `conectar()` retorna a conexão (ou `None`).
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
- **Update parcial:** `SET campo = COALESCE(%s, campo)` — só altera o que vier preenchido.
- **Dinheiro:** `NUMERIC(10,2)`. **Quantidade de estoque:** `NUMERIC(12,3)` (aceita litros).
- **Buscas:** parciais com `ILIKE` e `%termo%`.

---

## Schema por módulo (22 tabelas)

| # | Módulo | Tabelas | Arquivo .py | Status |
|---|--------|---------|-------------|--------|
| 1 | Cliente | `cliente` | `cadastro_cliente.py` | ✅ CRUD + ficha 360° + campanhas |
| 2 | Veículo | `categoria_veiculo`, `veiculo` | `cadastro_veiculo.py` | ✅ CRUD feito |
| 3 | Catálogo (serviços e preços) | `servico`, `servico_preco` | `catalogo_servicos.py` | ✅ CRUD feito |
| 4 | Agendamento | `agendamento`, `agendamento_servico` | `agendamento.py` | ✅ CRUD feito |
| 5 | Ordem de Serviço (comanda) | `ordem_servico`, `ordem_servico_item` | `ordem_servico.py` | ✅ CRUD feito |
| 6 | Funcionário | `funcionario` | `funcionario.py` | ✅ CRUD feito |
| 7 | Estoque | `produto`, `movimentacao_estoque` | `estoque.py` | ✅ CRUD feito |
| 8 | Fornecedores | `fornecedor` | `fornecedores.py` | ✅ CRUD feito |
| 9 | Despesa | `despesa` | `despesa.py` | ✅ CRUD feito |
| 10 | Caixa | `caixa`, `caixa_movimento` | `caixa.py` | ✅ CRUD feito |
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
- **Próximos passos possíveis:** Dashboard com gráficos (hoje são KPIs em cards); empacotar como
  executável (`flet pack`); refinos de UX. `app.py` mantém a paleta/logo centralizadas no topo.
