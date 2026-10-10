
-- =====================================================
-- Sistema de Gestão de Associações
-- Bases de Dados II - Ficha 3
-- =====================================================

-- ==========================================
-- TABELA LOCALIDADE
-- ==========================================

CREATE TABLE localidade (
    id_localidade INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome_localidade VARCHAR(150) NOT NULL UNIQUE
);


-- ==========================================
-- TABELA ASSOCIACAO
-- ==========================================

CREATE TABLE associacao (
    id_associacao INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nipc VARCHAR(9) NOT NULL UNIQUE,
    nome VARCHAR(150) NOT NULL,
    data_fundacao DATE,
    email VARCHAR(150),
    telefone VARCHAR(20),
    password_hash VARCHAR(255) NOT NULL,

    tipo_via VARCHAR(30),
    nome_via VARCHAR(150),
    numero_porta VARCHAR(20),
    andar VARCHAR(20),
    codigo_postal VARCHAR(8),
    id_localidade INTEGER,

    CONSTRAINT fk_associacao_localidade
        FOREIGN KEY (id_localidade)
        REFERENCES localidade(id_localidade)
);


-- ==========================================
-- TABELA ASSOCIADO
-- ==========================================

CREATE TABLE associado (
    id_associado INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numero_associado INTEGER NOT NULL UNIQUE,
    nome VARCHAR(150) NOT NULL,
    nif VARCHAR(9),
    data_nascimento DATE,
    email VARCHAR(150),
    telefone VARCHAR(20),
    data_adesao DATE NOT NULL,
    data_saida DATE,
    estado VARCHAR(30) NOT NULL,

    tipo_via VARCHAR(30),
    nome_via VARCHAR(150),
    numero_porta VARCHAR(20),
    andar VARCHAR(20),
    codigo_postal VARCHAR(8),
    id_localidade INTEGER,

    id_associacao INTEGER NOT NULL,

    CONSTRAINT fk_associado_associacao
        FOREIGN KEY (id_associacao)
        REFERENCES associacao(id_associacao),

    CONSTRAINT fk_associado_localidade
        FOREIGN KEY (id_localidade)
        REFERENCES localidade(id_localidade)
);


-- ==========================================
-- TABELA ORGAO_SOCIAL
-- ==========================================

CREATE TABLE orgao_social (
    id_orgao_social INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    descricao VARCHAR(255),
    id_associacao INTEGER NOT NULL,

    CONSTRAINT fk_orgao_associacao
        FOREIGN KEY (id_associacao)
        REFERENCES associacao(id_associacao)
);


-- ==========================================
-- TABELA CARGO
-- ==========================================

CREATE TABLE cargo (
    id_cargo INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    descricao VARCHAR(255),
    id_orgao_social INTEGER NOT NULL,

    CONSTRAINT fk_cargo_orgao
        FOREIGN KEY (id_orgao_social)
        REFERENCES orgao_social(id_orgao_social)
);


-- ==========================================
-- TABELA MANDATO
-- ==========================================

CREATE TABLE mandato (
    id_mandato INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    data_inicio DATE NOT NULL,
    data_fim DATE NOT NULL,
    id_associacao INTEGER NOT NULL,

    CONSTRAINT fk_mandato_associacao
        FOREIGN KEY (id_associacao)
        REFERENCES associacao(id_associacao),

    CONSTRAINT chk_mandato_datas
        CHECK (data_fim >= data_inicio)
);


-- ==========================================
-- TABELA EXERCICIO_CARGO
-- ==========================================

CREATE TABLE exercicio_cargo (
    id_exercicio_cargo INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    data_inicio DATE NOT NULL,
    data_fim DATE,
    id_associado INTEGER NOT NULL,
    id_cargo INTEGER NOT NULL,
    id_mandato INTEGER NOT NULL,

    CONSTRAINT fk_exercicio_associado
        FOREIGN KEY (id_associado)
        REFERENCES associado(id_associado),

    CONSTRAINT fk_exercicio_cargo
        FOREIGN KEY (id_cargo)
        REFERENCES cargo(id_cargo),

    CONSTRAINT fk_exercicio_mandato
        FOREIGN KEY (id_mandato)
        REFERENCES mandato(id_mandato),

    CONSTRAINT chk_exercicio_datas
        CHECK (data_fim IS NULL OR data_fim >= data_inicio)
);


-- ==========================================
-- TABELA QUOTA
-- ==========================================


CREATE OR REPLACE PROCEDURE registar_quota(
    p_designacao_quota VARCHAR(100),
    p_valor_quota REAL,
    p_periodicidade_quota VARCHAR(20),
    p_data_inicio_quota DATE,
    p_data_fim_quota DATE,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO quota (
        designacao_quota,
        valor_quota,
        periodicidade_quota,
        data_inicio_quota,
        data_fim_quota,
        id_associacao
    )
    VALUES (
        p_designacao_quota,
        p_valor_quota,
        p_periodicidade_quota,
        p_data_inicio_quota,
        p_data_fim_quota,
        p_id_associacao
    );
END;
$$;



-- ==========================================
-- TABELA QUOTA_ASSOCIADO
-- ==========================================

CREATE TABLE quota_associado (
    id_quota_associado INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    valor_devido NUMERIC(10,2) NOT NULL,
    data_vencimento DATE NOT NULL,
    periodo_referencia VARCHAR(20) NOT NULL,
    estado_quota_associado VARCHAR(20) NOT NULL,

    id_associado INTEGER NOT NULL,
    id_quota INTEGER NOT NULL,

    CONSTRAINT fk_quota_associado_associado
        FOREIGN KEY (id_associado)
        REFERENCES associado(id_associado),

    CONSTRAINT fk_quota_associado_quota
        FOREIGN KEY (id_quota)
        REFERENCES quota(id_quota)
);


-- ==========================================
-- TABELA MOVIMENTO_BANCARIO
-- ==========================================

CREATE TABLE movimento_bancario (
    id_movimento INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    data_movimento DATE NOT NULL,
    descricao_movimento VARCHAR(255),
    valor_movimento NUMERIC(10,2) NOT NULL,
    referencia_movimento VARCHAR(100)
);


-- ==========================================
-- TABELA PAGAMENTO
-- ==========================================

CREATE TABLE pagamento (
    id_pagamento INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    data_pagamento TIMESTAMP NOT NULL,
    valor_pago NUMERIC(10,2) NOT NULL,
    metodo_pagamento VARCHAR(100) NOT NULL,
    referencia_pagamento VARCHAR(100),

    id_quota_associado INTEGER NOT NULL,
    id_movimento INTEGER UNIQUE,

    CONSTRAINT fk_pagamento_quota_associado
        FOREIGN KEY (id_quota_associado)
        REFERENCES quota_associado(id_quota_associado),

    CONSTRAINT fk_pagamento_movimento
        FOREIGN KEY (id_movimento)
        REFERENCES movimento_bancario(id_movimento)
);


-- ==========================================
-- TABELA EVENTO
-- ==========================================

CREATE TABLE evento (
    id_evento INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome_evento VARCHAR(100) NOT NULL,
    descricao_evento VARCHAR(400),
    data_inicio_evento TIMESTAMP NOT NULL,
    data_fim_evento TIMESTAMP,
    local_evento VARCHAR(100),
    estado_evento VARCHAR(100) NOT NULL,

    id_associacao INTEGER NOT NULL,

    CONSTRAINT fk_evento_associacao
        FOREIGN KEY (id_associacao)
        REFERENCES associacao(id_associacao),

    CONSTRAINT chk_evento_datas
        CHECK (
            data_fim_evento IS NULL
            OR data_fim_evento >= data_inicio_evento
        )
);


-- ==========================================
-- TABELA TIPO_DOCUMENTO
-- ==========================================

CREATE TABLE tipo_documento (
    id_tipo_documento INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome_tipo_documento VARCHAR(150) NOT NULL,
    descricao_tipo_documento VARCHAR(255),

    id_associacao INTEGER NOT NULL,

    CONSTRAINT fk_tipo_documento_associacao
        FOREIGN KEY (id_associacao)
        REFERENCES associacao(id_associacao)
);


-- ==========================================
-- TABELA DOCUMENTO
-- ==========================================

CREATE TABLE documento (
    id_documento INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome_documento VARCHAR(150) NOT NULL,
    data_upload TIMESTAMP NOT NULL,
    data_documento DATE,
    ficheiro VARCHAR(255) NOT NULL,
    observacoes VARCHAR(400),

    id_tipo_documento INTEGER NOT NULL,
    id_associacao INTEGER NOT NULL,
    id_mandato INTEGER,

    CONSTRAINT fk_documento_tipo
        FOREIGN KEY (id_tipo_documento)
        REFERENCES tipo_documento(id_tipo_documento),

    CONSTRAINT fk_documento_associacao
        FOREIGN KEY (id_associacao)
        REFERENCES associacao(id_associacao),

    CONSTRAINT fk_documento_mandato
        FOREIGN KEY (id_mandato)
        REFERENCES mandato(id_mandato)
);
