-- ================================================================
-- Script de criação das tabelas - Sistema Lava-Jato (lavajato_db)
-- Autor: RINEAL Analytics
--
-- Execute com:  python criar_tabelas.py
-- ou:           psql -U postgres -d lavajato_db -f criar_tabelas.sql
--
-- É seguro rodar mais de uma vez (usa IF NOT EXISTS / ON CONFLICT).
-- As tabelas estão na ordem de dependência das chaves estrangeiras.
-- ============================================================1===


-- ================================================================
-- MÓDULO 1 - CLIENTE
-- ================================================================
CREATE TABLE IF NOT EXISTS cliente (
    id_cliente      SERIAL PRIMARY KEY,
    nome            VARCHAR(150) NOT NULL,
    cpf_cnpj        VARCHAR(18) UNIQUE,
    telefone        VARCHAR(20),
    email           VARCHAR(120),
    endereco        TEXT,
    observacoes     TEXT,
    data_nascimento DATE,               -- aniversário: base da campanha de parabéns
    como_conheceu   VARCHAR(40),        -- origem: indicação, Instagram, passou na frente...
    ativo           BOOLEAN     NOT NULL DEFAULT TRUE,
    criado_em       TIMESTAMP   NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMP   NOT NULL DEFAULT NOW()
);

-- Upgrade de bancos já existentes: aniversário e origem do cliente.
ALTER TABLE cliente ADD COLUMN IF NOT EXISTS data_nascimento DATE;
ALTER TABLE cliente ADD COLUMN IF NOT EXISTS como_conheceu   VARCHAR(40);

CREATE INDEX IF NOT EXISTS idx_cliente_nome     ON cliente (nome);
CREATE INDEX IF NOT EXISTS idx_cliente_telefone ON cliente (telefone);

COMMENT ON COLUMN cliente.data_nascimento IS 'Aniversário do cliente (usado na campanha de parabéns por WhatsApp)';
COMMENT ON COLUMN cliente.como_conheceu   IS 'Como o cliente chegou até o lava-jato (marketing)';


-- ================================================================
-- MÓDULO 2 - VEÍCULO (+ categoria_veiculo)
-- ================================================================
CREATE TABLE IF NOT EXISTS categoria_veiculo (
    id_categoria  SERIAL PRIMARY KEY,
    nome          VARCHAR(30) NOT NULL UNIQUE,
    ordem         SMALLINT DEFAULT 0   -- ordena na interface (menor -> maior porte)
);

INSERT INTO categoria_veiculo (nome, ordem) VALUES
    ('Moto', 1),
    ('Pequeno', 2),
    ('Médio', 3),
    ('Grande', 4),
    ('SUV', 5),
    ('Caminhonete', 6),
    ('Caminhão', 7)
ON CONFLICT (nome) DO NOTHING;

CREATE TABLE IF NOT EXISTS veiculo (
    id_veiculo      SERIAL PRIMARY KEY,
    id_cliente      INTEGER NOT NULL REFERENCES cliente(id_cliente),
    id_categoria    INTEGER NOT NULL REFERENCES categoria_veiculo(id_categoria),
    placa           VARCHAR(8) NOT NULL UNIQUE,
    marca           VARCHAR(50),
    modelo          VARCHAR(50),
    ano             SMALLINT,
    cor             VARCHAR(30),
    ativo           BOOLEAN   DEFAULT TRUE,
    criado_em       TIMESTAMP DEFAULT NOW(),
    atualizado_em   TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_veiculo_placa   ON veiculo(placa);
CREATE INDEX IF NOT EXISTS idx_veiculo_cliente ON veiculo(id_cliente);

COMMENT ON TABLE  veiculo              IS 'Armazena os veículos cadastrados, vinculados a um cliente e a uma categoria de porte';
COMMENT ON COLUMN veiculo.placa        IS 'Placa do veículo, suporta padrão antigo (ABC1234) e Mercosul (ABC1D23)';
COMMENT ON COLUMN veiculo.id_categoria IS 'Define o porte do veículo, usado para calcular o preço dos serviços';
COMMENT ON COLUMN veiculo.ativo        IS 'Permite desativar veículo sem excluir o histórico (soft delete)';


-- ================================================================
-- MÓDULO 3 - CATÁLOGO (serviços e preços)
-- ================================================================
CREATE TABLE IF NOT EXISTS servico (
    id_servico       SERIAL PRIMARY KEY,
    nome             VARCHAR(100) NOT NULL UNIQUE,
    descricao        TEXT,
    tempo_medio_min  SMALLINT,            -- tempo médio de execução, em minutos
    ativo            BOOLEAN   DEFAULT TRUE,
    criado_em        TIMESTAMP DEFAULT NOW(),
    atualizado_em    TIMESTAMP DEFAULT NOW()
);

-- Matriz de preços: um preço por combinação (serviço, categoria de porte)
CREATE TABLE IF NOT EXISTS servico_preco (
    id_preco      SERIAL PRIMARY KEY,
    id_servico    INTEGER NOT NULL REFERENCES servico(id_servico) ON DELETE CASCADE,
    id_categoria  INTEGER NOT NULL REFERENCES categoria_veiculo(id_categoria),
    preco         NUMERIC(10,2) NOT NULL CHECK (preco >= 0),
    UNIQUE (id_servico, id_categoria)
);

CREATE INDEX IF NOT EXISTS idx_servico_preco_servico ON servico_preco(id_servico);

COMMENT ON TABLE servico       IS 'Catálogo de serviços oferecidos pelo lava-jato';
COMMENT ON TABLE servico_preco IS 'Matriz de preços: um preço por (serviço, categoria de porte)';


-- ================================================================
-- MÓDULO 6 - FUNCIONÁRIO
-- (criado antes de agendamento/ordem por ser referenciado por eles)
-- ================================================================
CREATE TABLE IF NOT EXISTS funcionario (
    id_funcionario    SERIAL PRIMARY KEY,
    nome              VARCHAR(150) NOT NULL,
    funcao            VARCHAR(20) NOT NULL DEFAULT 'lavador'
                          CHECK (funcao IN ('lavador','caixa','gerente')),
    login             VARCHAR(50) UNIQUE,
    senha_hash        VARCHAR(255),          -- nunca guardar senha em texto puro
    comissao_percentual NUMERIC(5,2) DEFAULT 0 CHECK (comissao_percentual >= 0),
    data_admissao     DATE,
    ativo             BOOLEAN   DEFAULT TRUE,
    criado_em         TIMESTAMP DEFAULT NOW(),
    atualizado_em     TIMESTAMP DEFAULT NOW()
);

COMMENT ON COLUMN funcionario.senha_hash IS 'Hash da senha (ex.: bcrypt), nunca a senha em texto puro';


-- ================================================================
-- MÓDULO 8 - FORNECEDORES
-- (criado antes de estoque/despesa por ser referenciado por eles)
-- ================================================================
CREATE TABLE IF NOT EXISTS fornecedor (
    id_fornecedor        SERIAL PRIMARY KEY,
    nome_razao_social    VARCHAR(150) NOT NULL,
    cnpj                 VARCHAR(18) UNIQUE,
    telefone             VARCHAR(20),
    email                VARCHAR(120),
    condicoes_pagamento  TEXT,
    ativo                BOOLEAN   DEFAULT TRUE,
    criado_em            TIMESTAMP DEFAULT NOW(),
    atualizado_em        TIMESTAMP DEFAULT NOW()
);


-- ================================================================
-- MÓDULO 7 - ESTOQUE (produto + movimentação)
-- ================================================================
CREATE TABLE IF NOT EXISTS produto (
    id_produto       SERIAL PRIMARY KEY,
    nome             VARCHAR(120) NOT NULL,
    unidade_medida   VARCHAR(15),           -- ex.: L, ml, un, kg
    quantidade       NUMERIC(12,3) NOT NULL DEFAULT 0,
    estoque_minimo   NUMERIC(12,3) DEFAULT 0,
    custo_unitario   NUMERIC(10,2) DEFAULT 0 CHECK (custo_unitario >= 0),
    preco_venda      NUMERIC(10,2) DEFAULT 0 CHECK (preco_venda >= 0),  -- preço cobrado do cliente (venda de balcão)
    id_fornecedor    INTEGER REFERENCES fornecedor(id_fornecedor),
    ativo            BOOLEAN   DEFAULT TRUE,
    criado_em        TIMESTAMP DEFAULT NOW(),
    atualizado_em    TIMESTAMP DEFAULT NOW()
);

-- Upgrade de bancos já existentes: preço de venda do produto (venda de balcão).
ALTER TABLE produto ADD COLUMN IF NOT EXISTS preco_venda NUMERIC(10,2) DEFAULT 0 CHECK (preco_venda >= 0);

CREATE TABLE IF NOT EXISTS movimentacao_estoque (
    id_movimentacao  SERIAL PRIMARY KEY,
    id_produto       INTEGER NOT NULL REFERENCES produto(id_produto),
    tipo             VARCHAR(7) NOT NULL CHECK (tipo IN ('entrada','saida')),
    quantidade       NUMERIC(12,3) NOT NULL CHECK (quantidade > 0),
    observacao       TEXT,
    data_mov         TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mov_estoque_produto ON movimentacao_estoque(id_produto);

COMMENT ON TABLE produto IS 'Produtos/insumos usados na prestação dos serviços';
COMMENT ON COLUMN produto.estoque_minimo IS 'Nível para alerta de reposição';


-- ================================================================
-- MÓDULO 4 - AGENDAMENTO (+ serviços desejados)
-- ================================================================
CREATE TABLE IF NOT EXISTS agendamento (
    id_agendamento    SERIAL PRIMARY KEY,
    id_cliente        INTEGER NOT NULL REFERENCES cliente(id_cliente),
    id_veiculo        INTEGER NOT NULL REFERENCES veiculo(id_veiculo),
    data_hora         TIMESTAMP NOT NULL,
    duracao_estimada_min SMALLINT,
    box               VARCHAR(20),
    status            VARCHAR(15) NOT NULL DEFAULT 'agendado'
                          CHECK (status IN ('agendado','confirmado','em_espera',
                                            'em_execucao','concluido','cancelado','nao_compareceu')),
    origem            VARCHAR(15) DEFAULT 'manual'
                          CHECK (origem IN ('manual','whatsapp','telefone','app')),
    observacoes       TEXT,
    criado_em         TIMESTAMP DEFAULT NOW(),
    atualizado_em     TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agendamento_data    ON agendamento(data_hora);
CREATE INDEX IF NOT EXISTS idx_agendamento_cliente ON agendamento(id_cliente);

-- Serviços desejados em cada agendamento (N serviços por agendamento)
CREATE TABLE IF NOT EXISTS agendamento_servico (
    id_agendamento  INTEGER NOT NULL REFERENCES agendamento(id_agendamento) ON DELETE CASCADE,
    id_servico      INTEGER NOT NULL REFERENCES servico(id_servico),
    PRIMARY KEY (id_agendamento, id_servico)
);


-- ================================================================
-- MÓDULO 5 - ORDEM DE SERVIÇO / COMANDA (+ itens)
-- ================================================================
CREATE TABLE IF NOT EXISTS ordem_servico (
    id_ordem         SERIAL PRIMARY KEY,          -- número da comanda
    id_cliente       INTEGER NOT NULL REFERENCES cliente(id_cliente),
    id_veiculo       INTEGER NOT NULL REFERENCES veiculo(id_veiculo),
    id_funcionario   INTEGER REFERENCES funcionario(id_funcionario),  -- responsável
    id_agendamento   INTEGER REFERENCES agendamento(id_agendamento),  -- origem (opcional)
    status           VARCHAR(12) NOT NULL DEFAULT 'aguardando'
                          CHECK (status IN ('aguardando','em_execucao','finalizado','entregue','cancelado')),
    forma_pagamento  VARCHAR(20),
    valor_total      NUMERIC(10,2) DEFAULT 0 CHECK (valor_total >= 0),
    -- Financeiro da OS (valor_final e valor_pendente são calculados no app):
    desconto         NUMERIC(10,2) DEFAULT 0 CHECK (desconto >= 0),
    acrescimo        NUMERIC(10,2) DEFAULT 0 CHECK (acrescimo >= 0),   -- acréscimo / juros
    parcelas         SMALLINT      DEFAULT 1 CHECK (parcelas >= 1),
    valor_pago       NUMERIC(10,2) DEFAULT 0 CHECK (valor_pago >= 0),
    data_pagamento   DATE,
    data_vencimento  DATE,
    avarias          TEXT,              -- vistoria de entrada: danos observados na chegada
    observacoes      TEXT,              -- observações gerais da comanda
    entrada_em       TIMESTAMP DEFAULT NOW(),
    inicio_em        TIMESTAMP,
    finalizacao_em   TIMESTAMP,
    criado_em        TIMESTAMP DEFAULT NOW(),
    atualizado_em    TIMESTAMP DEFAULT NOW()
);

-- Upgrade de bancos já existentes: adiciona as colunas financeiras se faltarem.
ALTER TABLE ordem_servico ADD COLUMN IF NOT EXISTS desconto        NUMERIC(10,2) DEFAULT 0;
ALTER TABLE ordem_servico ADD COLUMN IF NOT EXISTS acrescimo       NUMERIC(10,2) DEFAULT 0;
ALTER TABLE ordem_servico ADD COLUMN IF NOT EXISTS parcelas        SMALLINT      DEFAULT 1;
ALTER TABLE ordem_servico ADD COLUMN IF NOT EXISTS valor_pago      NUMERIC(10,2) DEFAULT 0;
ALTER TABLE ordem_servico ADD COLUMN IF NOT EXISTS data_pagamento  DATE;
ALTER TABLE ordem_servico ADD COLUMN IF NOT EXISTS data_vencimento DATE;
ALTER TABLE ordem_servico ADD COLUMN IF NOT EXISTS avarias         TEXT;
ALTER TABLE ordem_servico ADD COLUMN IF NOT EXISTS observacoes     TEXT;

CREATE INDEX IF NOT EXISTS idx_ordem_status  ON ordem_servico(status);
CREATE INDEX IF NOT EXISTS idx_ordem_cliente ON ordem_servico(id_cliente);

-- Itens de cada comanda, com o preço aplicado no momento.
-- Cada item é OU um serviço OU um produto de balcão (toalha, shampoo...), nunca os dois.
CREATE TABLE IF NOT EXISTS ordem_servico_item (
    id_item         SERIAL PRIMARY KEY,
    id_ordem        INTEGER NOT NULL REFERENCES ordem_servico(id_ordem) ON DELETE CASCADE,
    id_servico      INTEGER REFERENCES servico(id_servico),
    id_produto      INTEGER REFERENCES produto(id_produto),           -- venda de produto na comanda
    id_funcionario  INTEGER REFERENCES funcionario(id_funcionario),   -- quem executou (serviço)
    quantidade      NUMERIC(12,3) NOT NULL DEFAULT 1 CHECK (quantidade > 0),
    preco_aplicado  NUMERIC(10,2) NOT NULL CHECK (preco_aplicado >= 0),  -- preço UNITÁRIO congelado
    CONSTRAINT ordem_servico_item_tipo_check CHECK (
        (id_servico IS NOT NULL AND id_produto IS NULL)
     OR (id_servico IS NULL AND id_produto IS NOT NULL)
    )
);

-- Upgrade de bancos já existentes: permite itens de PRODUTO na comanda.
ALTER TABLE ordem_servico_item ALTER COLUMN id_servico DROP NOT NULL;
ALTER TABLE ordem_servico_item ADD COLUMN IF NOT EXISTS id_produto INTEGER REFERENCES produto(id_produto);
ALTER TABLE ordem_servico_item ADD COLUMN IF NOT EXISTS quantidade NUMERIC(12,3) NOT NULL DEFAULT 1;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ordem_servico_item_tipo_check') THEN
        ALTER TABLE ordem_servico_item ADD CONSTRAINT ordem_servico_item_tipo_check CHECK (
            (id_servico IS NOT NULL AND id_produto IS NULL)
         OR (id_servico IS NULL AND id_produto IS NOT NULL));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_ordem_item_ordem   ON ordem_servico_item(id_ordem);
CREATE INDEX IF NOT EXISTS idx_ordem_item_produto ON ordem_servico_item(id_produto);

COMMENT ON COLUMN ordem_servico_item.preco_aplicado IS 'Preço UNITÁRIO cobrado no momento da comanda (histórico imune a reajustes futuros)';
COMMENT ON COLUMN ordem_servico_item.quantidade IS 'Quantidade do item (serviço geralmente 1; produto pode ser N unidades)';


-- ================================================================
-- MÓDULO 9 - DESPESA
-- ================================================================
CREATE TABLE IF NOT EXISTS despesa (
    id_despesa       SERIAL PRIMARY KEY,
    descricao        VARCHAR(200) NOT NULL,
    categoria        VARCHAR(30),       -- produto, salario, aluguel, energia, manutencao...
    valor            NUMERIC(10,2) NOT NULL CHECK (valor >= 0),
    data_vencimento  DATE,
    data_pagamento   DATE,              -- NULL enquanto não paga
    id_fornecedor    INTEGER REFERENCES fornecedor(id_fornecedor),
    forma_pagamento  VARCHAR(20),
    criado_em        TIMESTAMP DEFAULT NOW(),
    atualizado_em    TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_despesa_vencimento ON despesa(data_vencimento);


-- ================================================================
-- MÓDULO 10 - CAIXA (+ movimentações)
-- ================================================================
CREATE TABLE IF NOT EXISTS caixa (
    id_caixa         SERIAL PRIMARY KEY,
    data_abertura    TIMESTAMP NOT NULL DEFAULT NOW(),
    data_fechamento  TIMESTAMP,         -- NULL enquanto o caixa está aberto
    valor_inicial    NUMERIC(10,2) NOT NULL DEFAULT 0,  -- fundo de caixa
    saldo_final      NUMERIC(10,2),     -- preenchido no fechamento
    id_funcionario   INTEGER REFERENCES funcionario(id_funcionario),  -- responsável
    status           VARCHAR(8) NOT NULL DEFAULT 'aberto'
                          CHECK (status IN ('aberto','fechado')),
    observacoes      TEXT
);

CREATE TABLE IF NOT EXISTS caixa_movimento (
    id_movimento  SERIAL PRIMARY KEY,
    id_caixa      INTEGER NOT NULL REFERENCES caixa(id_caixa) ON DELETE CASCADE,
    tipo          VARCHAR(7) NOT NULL CHECK (tipo IN ('entrada','saida')),
    valor         NUMERIC(10,2) NOT NULL CHECK (valor >= 0),
    descricao     VARCHAR(200),
    id_ordem      INTEGER REFERENCES ordem_servico(id_ordem),  -- entrada vinda de comanda
    id_despesa    INTEGER REFERENCES despesa(id_despesa),      -- saída vinda de despesa
    data_mov      TIMESTAMP DEFAULT NOW()
);

-- Como o dinheiro entrou/saiu (dinheiro, pix, cartao_credito...). Copiada da comanda
-- ou da despesa que originou o movimento. Serve para separar, no fechamento, o que
-- está DE FATO na gaveta do que caiu no banco (pix/cartão) — sem ela o caixa acusa
-- falta todo dia em que alguém pagou no cartão. NULL = dinheiro (movimento antigo,
-- lançado antes desta coluna existir).
ALTER TABLE caixa_movimento ADD COLUMN IF NOT EXISTS forma_pagamento VARCHAR(20);

CREATE INDEX IF NOT EXISTS idx_caixa_movimento_caixa ON caixa_movimento(id_caixa);
-- A ponte Despesa→Caixa consulta por id_despesa para não lançar a saída duas vezes.
CREATE INDEX IF NOT EXISTS idx_caixa_movimento_despesa ON caixa_movimento(id_despesa);


-- ================================================================
-- MÓDULO 12 - FIDELIDADE (saldo + movimentações de pontos)
-- ================================================================
CREATE TABLE IF NOT EXISTS fidelidade_saldo (
    id_cliente        INTEGER PRIMARY KEY REFERENCES cliente(id_cliente),
    pontos            INTEGER NOT NULL DEFAULT 0 CHECK (pontos >= 0),
    atualizado_em     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fidelidade_movimento (
    id_movimento  SERIAL PRIMARY KEY,
    id_cliente    INTEGER NOT NULL REFERENCES cliente(id_cliente),
    tipo          VARCHAR(8) NOT NULL CHECK (tipo IN ('acumulo','resgate')),
    pontos        INTEGER NOT NULL CHECK (pontos > 0),
    id_ordem      INTEGER REFERENCES ordem_servico(id_ordem),  -- comanda que gerou o ponto
    descricao     VARCHAR(200),
    data_mov      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fidelidade_mov_cliente ON fidelidade_movimento(id_cliente);


-- ================================================================
-- MÓDULO 13 - PLANOS E ASSINATURAS
-- ================================================================
CREATE TABLE IF NOT EXISTS plano (
    id_plano          SERIAL PRIMARY KEY,
    nome              VARCHAR(100) NOT NULL UNIQUE,
    valor_mensalidade NUMERIC(10,2) NOT NULL CHECK (valor_mensalidade >= 0),
    ativo             BOOLEAN   DEFAULT TRUE,
    criado_em         TIMESTAMP DEFAULT NOW(),
    atualizado_em     TIMESTAMP DEFAULT NOW()
);

-- Serviços inclusos no plano e a quantidade permitida por mês
CREATE TABLE IF NOT EXISTS plano_servico (
    id_plano        INTEGER NOT NULL REFERENCES plano(id_plano) ON DELETE CASCADE,
    id_servico      INTEGER NOT NULL REFERENCES servico(id_servico),
    quantidade_mes  SMALLINT NOT NULL CHECK (quantidade_mes > 0),
    PRIMARY KEY (id_plano, id_servico)
);

CREATE TABLE IF NOT EXISTS assinatura (
    id_assinatura    SERIAL PRIMARY KEY,
    id_cliente       INTEGER NOT NULL REFERENCES cliente(id_cliente),
    id_plano         INTEGER NOT NULL REFERENCES plano(id_plano),
    data_inicio      DATE NOT NULL DEFAULT CURRENT_DATE,
    data_vencimento  DATE,
    data_renovacao   DATE,
    ativo            BOOLEAN   DEFAULT TRUE,
    criado_em        TIMESTAMP DEFAULT NOW(),
    atualizado_em    TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assinatura_cliente ON assinatura(id_cliente);

-- Consumo de serviços do plano (para controlar o limite mensal)
CREATE TABLE IF NOT EXISTS assinatura_uso (
    id_uso         SERIAL PRIMARY KEY,
    id_assinatura  INTEGER NOT NULL REFERENCES assinatura(id_assinatura) ON DELETE CASCADE,
    id_servico     INTEGER NOT NULL REFERENCES servico(id_servico),
    id_ordem       INTEGER REFERENCES ordem_servico(id_ordem),
    data_uso       TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assinatura_uso_assinatura ON assinatura_uso(id_assinatura);


-- ================================================================
-- MÓDULO 11 - DASHBOARD
-- Não possui tabelas próprias: é composto por consultas/relatórios
-- (faturamento, ticket médio, serviço mais vendido, fila atual, etc.)
-- sobre as tabelas acima.
-- ================================================================
