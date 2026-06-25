-- ================================================================
-- SISTEMA LAVA-JATO — SCHEMA DO BANCO DE DADOS (PostgreSQL)
-- Autor: RINEAL Analytics
-- ================================================================
-- Este arquivo cresce conforme cada módulo é desenvolvido.
-- Ordem de criação segue a ordem de dependência entre tabelas.
-- ================================================================
 
 
-- ================================================================
-- MÓDULO: CADASTRO DE CLIENTE
-- ================================================================


CREATE TABLE cliente (
    id              SERIAL PRIMARY KEY,
    nome            VARCHAR(150) NOT NULL,
    cpf_cnpj        VARCHAR(18) UNIQUE NOT NULL,
    telefone        VARCHAR(20) NOT NULL,
    email           VARCHAR(150),
    endereco        TEXT,
    observacoes     TEXT,
    ativo           BOOLEAN DEFAULT TRUE,
    criado_em       TIMESTAMP DEFAULT NOW(),
    atualizado_em   TIMESTAMP DEFAULT NOW()
);
