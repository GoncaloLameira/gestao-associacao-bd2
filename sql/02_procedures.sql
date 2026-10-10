-- =====================================================
-- Procedures
-- Entidades: Mandato e ExercicioCargo
-- =====================================================

-- Registar um novo mandato
CREATE OR REPLACE PROCEDURE registar_mandato(
    p_data_inicio DATE,
    p_data_fim DATE,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO mandato (
        data_inicio,
        data_fim,
        id_associacao
    )
    VALUES (
        p_data_inicio,
        p_data_fim,
        p_id_associacao
    );
END;
$$;


-- Registar o exercício de um cargo por um associado
CREATE OR REPLACE PROCEDURE registar_exercicio_cargo(
    p_data_inicio DATE,
    p_data_fim DATE,
    p_id_associado INTEGER,
    p_id_cargo INTEGER,
    p_id_mandato INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO exercicio_cargo (
        data_inicio,
        data_fim,
        id_associado,
        id_cargo,
        id_mandato
    )
    VALUES (
        p_data_inicio,
        p_data_fim,
        p_id_associado,
        p_id_cargo,
        p_id_mandato
    );
END;
$$;


-- ==========================================
-- PROCEDURE: REGISTAR ASSOCIACAO
-- ==========================================

CREATE OR REPLACE PROCEDURE registar_associacao(
    p_nipc VARCHAR(9),
    p_nome VARCHAR(150),
    p_data_fundacao DATE,
    p_email VARCHAR(150),
    p_telefone VARCHAR(20),
    p_password_hash VARCHAR(255),
    p_tipo_via VARCHAR(30),
    p_nome_via VARCHAR(150),
    p_numero_porta VARCHAR(20),
    p_andar VARCHAR(20),
    p_codigo_postal VARCHAR(8),
    p_id_localidade INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO associacao (
        nipc,
        nome,
        data_fundacao,
        email,
        telefone,
        password_hash,
        tipo_via,
        nome_via,
        numero_porta,
        andar,
        codigo_postal,
        id_localidade
    )
    VALUES (
        p_nipc,
        p_nome,
        p_data_fundacao,
        p_email,
        p_telefone,
        p_password_hash,
        p_tipo_via,
        p_nome_via,
        p_numero_porta,
        p_andar,
        p_codigo_postal,
        p_id_localidade
    );
END;
$$;


-- ==========================================
-- PROCEDURE: REGISTAR EVENTO
-- ==========================================

CREATE OR REPLACE PROCEDURE registar_evento(
    p_nome_evento VARCHAR(100),
    p_descricao_evento VARCHAR(400),
    p_data_inicio_evento TIMESTAMP,
    p_data_fim_evento TIMESTAMP,
    p_local_evento VARCHAR(100),
    p_estado_evento VARCHAR(100),
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO evento (
        nome_evento,
        descricao_evento,
        data_inicio_evento,
        data_fim_evento,
        local_evento,
        estado_evento,
        id_associacao
    )
    VALUES (
        p_nome_evento,
        p_descricao_evento,
        p_data_inicio_evento,
        p_data_fim_evento,
        p_local_evento,
        p_estado_evento,
        p_id_associacao
    );
END;
$$;


-- Registar associado
CREATE OR REPLACE PROCEDURE registar_associado(
    p_numero_associado INTEGER,
    p_nome VARCHAR(150),
    p_nif VARCHAR(9),
    p_data_nascimento DATE,
    p_email VARCHAR(150),
    p_telefone VARCHAR(20),
    p_data_adesao DATE,
    p_data_saida DATE,
    p_estado VARCHAR(30),
    p_tipo_via VARCHAR(30),
    p_nome_via VARCHAR(150),
    p_numero_porta VARCHAR(20),
    p_andar VARCHAR(20),
    p_codigo_postal VARCHAR(8),
    p_id_localidade INTEGER,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO associado (
        numero_associado, nome, nif, data_nascimento,
        email, telefone, data_adesao, data_saida, estado,
        tipo_via, nome_via, numero_porta, andar, codigo_postal,
        id_localidade, id_associacao
    )
    VALUES (
        p_numero_associado, p_nome, p_nif, p_data_nascimento,
        p_email, p_telefone, p_data_adesao, p_data_saida, p_estado,
        p_tipo_via, p_nome_via, p_numero_porta, p_andar, p_codigo_postal,
        p_id_localidade, p_id_associacao
    );
END;
$$;


-- Registar quota
CREATE OR REPLACE PROCEDURE registar_quota(
    p_designacao_quota VARCHAR(150),
    p_valor_quota REAL,
    p_periodicidade_quota VARCHAR(30),
    p_data_inicio_quota DATE,
    p_data_fim_quota DATE,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO quota (
        designacao_quota, valor_quota, periodicidade_quota,
        data_inicio_quota, data_fim_quota, id_associacao
    )
    VALUES (
        p_designacao_quota, p_valor_quota, p_periodicidade_quota,
        p_data_inicio_quota, p_data_fim_quota, p_id_associacao
    );
END;
$$;


-- ==========================================
-- REGISTAR ÓRGÃO SOCIAL
-- ==========================================

CREATE OR REPLACE PROCEDURE registar_orgao_social(
    p_nome VARCHAR(100),
    p_descricao VARCHAR(255),
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO orgao_social (
        nome,
        descricao,
        id_associacao
    )
    VALUES (
        p_nome,
        p_descricao,
        p_id_associacao
    );
END;
$$;


-- ==========================================
-- REGISTAR CARGO
-- ==========================================

CREATE OR REPLACE PROCEDURE registar_cargo(
    p_nome VARCHAR(100),
    p_descricao VARCHAR(255),
    p_id_orgao_social INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO cargo (
        nome,
        descricao,
        id_orgao_social
    )
    VALUES (
        p_nome,
        p_descricao,
        p_id_orgao_social
    );
END;
$$;
