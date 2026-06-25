# Sistema de Gestão para Lava-Jato (projeto_daniel)

Sistema de gestão para lava-jato em **Python + psycopg2 + PostgreSQL**.
Dependências: `psycopg2`, `bcrypt` (hash de senha no módulo funcionário).
Cliente: **Truck Center Lavação**. Autor: Lucas Ribeiro Nepomuceno de Almeida (RINEAL Analytics).

---

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
| 1 | Cliente | `cliente` | `cadastro_cliente.py` | ✅ CRUD feito |
| 2 | Veículo | `categoria_veiculo`, `veiculo` | `cadastro_veiculo.py` | ✅ CRUD feito |
| 3 | Catálogo (serviços e preços) | `servico`, `servico_preco` | `catalogo_servicos.py` | ✅ CRUD feito |
| 4 | Agendamento | `agendamento`, `agendamento_servico` | `agendamento.py` | ✅ CRUD feito |
| 5 | Ordem de Serviço (comanda) | `ordem_servico`, `ordem_servico_item` | `ordem_servico.py` | ✅ CRUD feito |
| 6 | Funcionário | `funcionario` | `funcionario.py` | ✅ CRUD feito |
| 7 | Estoque | `produto`, `movimentacao_estoque` | `estoque.py` | ✅ CRUD feito |
| 8 | Fornecedores | `fornecedor` | `fornecedores.py` | ✅ CRUD feito |
| 9 | Despesa | `despesa` | `despesa.py` | ✅ CRUD feito |
| 10 | Caixa | `caixa`, `caixa_movimento` | `caixa.py` | ✅ CRUD feito |
| 11 | Dashboard | *(sem tabela — só consultas)* | `dashboard.py` | ⬜ vazio |
| 12 | Fidelidade | `fidelidade_saldo`, `fidelidade_movimento` | `fidelidade.py` | ✅ CRUD feito |
| 13 | Planos e Assinaturas | `plano`, `plano_servico`, `assinatura`, `assinatura_uso` | `planos_assinaturas.py` | ✅ CRUD feito |

A especificação detalhada de cada módulo (finalidade, dados, funcionalidades) está em
`documentacao_modulos_lavajato.txt`. A ordem de implementação segue a numeração acima.

### Decisões de modelagem
- **Categoria de veículo normalizada:** porte é FK (`veiculo.id_categoria` →
  `categoria_veiculo`), não texto livre. Categorias seed: Moto, Pequeno, Médio,
  Grande, SUV, Caminhonete.
- **Preço por porte:** `servico_preco` é a matriz serviço × categoria
  (`UNIQUE(id_servico, id_categoria)`), em vez de colunas fixas por porte.
- **Relações N:N** via tabelas de ligação: `agendamento_servico`,
  `ordem_servico_item`, `plano_servico`.
- **`ordem_servico_item.preco_aplicado`** congela o preço cobrado na comanda
  (histórico imune a reajustes futuros).
- **`funcionario.senha_hash`**: nunca senha em texto puro.
- **Caixa e Fidelidade** com tabela de movimento separada (entradas/saídas,
  acúmulo/resgate), preservando histórico em vez de só um saldo.

---

## Arquivos principais

- `conexao.py` — conexão única com o banco.
- `criar_tabelas.sql` / `criar_tabelas.py` — schema e criação das tabelas.
- `cadastro_cliente.py`, `cadastro_veiculo.py` — módulos já implementados (referência de padrão).
- `documentacao_modulos_lavajato.txt` — especificação funcional dos 13 módulos.

---

## Estado atual / Próximos passos

- Schema completo já criado no `lavajato_db` (22 tabelas, FKs íntegras).
- Módulos com CRUD implementado: 1 a 10, 12 e 13. **Falta só o módulo 11 — Dashboard.**
- Dados de teste no banco: `categoria_veiculo` (6 portes), `cliente` (id 1), `servico` (id 1 com preços),
  `veiculo` (id 1), `agendamento` (id 1), `ordem_servico` (id 1), `funcionario` (id 1),
  `produto` (id 1), `fornecedor` (id 1), `despesa` (id 1 paga, id 2 em aberto), `caixa` (id 1 fechado),
  `fidelidade_saldo` (cliente 1, 6 pontos), `plano` (id 1) + `assinatura` (id 1).
- **Módulo 11 (Dashboard): ADIADO** por decisão do usuário — será feito junto com o frontend
  (os indicadores viram gráficos). Indicadores previstos: faturamento por período, serviço mais
  vendido, ticket médio, taxa de retorno, tempo médio por serviço, horários de pico, fila atual.
- **Backend de CRUD essencialmente completo** (12 de 13 módulos). Próxima grande etapa provável:
  escolher a stack de frontend (desktop CustomTkinter/Flet vs web Flask/FastAPI) e montar as telas
  reaproveitando as funções dos módulos. `autenticar()` (funcionario) já serve de base p/ login.
