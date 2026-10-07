-- =====================================================
-- Sistema de Gestão de Associações
-- Bases de Dados II - Ficha 3
-- =====================================================

CREATE TABLE associacao (
    id_associacao INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nipc VARCHAR(9) NOT NULL UNIQUE,
    nome VARCHAR(150) NOT NULL,
    data_fundacao DATE,
    email VARCHAR(150),
    telefone VARCHAR(20),
    morada VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL
);

CREATE TABLE associado (
    id_associado INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numero_associado INTEGER NOT NULL UNIQUE,
    nome VARCHAR(150) NOT NULL,
    nif VARCHAR(9),
    data_nascimento DATE,
    email VARCHAR(150),
    telefone VARCHAR(20),
    morada VARCHAR(255),
    data_adesao DATE NOT NULL,
    data_saida DATE,
    estado VARCHAR(30) NOT NULL,
    id_associacao INTEGER NOT NULL,

    CONSTRAINT fk_associado_associacao
        FOREIGN KEY (id_associacao)
        REFERENCES associacao(id_associacao)
);

CREATE TABLE orgao_social (
    id_orgao_social INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    descricao VARCHAR(255),
    id_associacao INTEGER NOT NULL,

    CONSTRAINT fk_orgao_associacao
        FOREIGN KEY (id_associacao)
        REFERENCES associacao(id_associacao)
);

CREATE TABLE cargo (
    id_cargo INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    descricao VARCHAR(255),
    id_orgao_social INTEGER NOT NULL,

    CONSTRAINT fk_cargo_orgao
        FOREIGN KEY (id_orgao_social)
        REFERENCES orgao_social(id_orgao_social)
);

-- =====================================================
-- Entidades atribuídas: Mandato e ExercicioCargo
-- =====================================================

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