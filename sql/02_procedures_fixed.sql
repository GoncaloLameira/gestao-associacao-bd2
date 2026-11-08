-- =====================================================
-- Procedures - CORRIGIDAS PARA ISOLAMENTO MULTI-TENANCY
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
-- Valida que associado, cargo e mandato pertencem à mesma associação
CREATE OR REPLACE PROCEDURE registar_exercicio_cargo(
    p_data_inicio DATE,
    p_data_fim DATE,
    p_id_associado INTEGER,
    p_id_cargo INTEGER,
    p_id_mandato INTEGER,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_associado_associacao INTEGER;
    v_cargo_associacao INTEGER;
    v_mandato_associacao INTEGER;
BEGIN
    -- Validar associado
    SELECT id_associacao INTO v_associado_associacao
    FROM associado WHERE id_associado = p_id_associado;

    IF NOT FOUND OR v_associado_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Associado não pertence à associação autorizada';
    END IF;

    -- Validar cargo (via orgao_social)
    SELECT os.id_associacao INTO v_cargo_associacao
    FROM cargo c
    JOIN orgao_social os ON c.id_orgao_social = os.id_orgao_social
    WHERE c.id_cargo = p_id_cargo;

    IF NOT FOUND OR v_cargo_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Cargo não pertence à associação autorizada';
    END IF;

    -- Validar mandato
    SELECT id_associacao INTO v_mandato_associacao
    FROM mandato WHERE id_mandato = p_id_mandato;

    IF NOT FOUND OR v_mandato_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Mandato não pertence à associação autorizada';
    END IF;

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
-- Valida que o órgão social pertence à associação
-- ==========================================

CREATE OR REPLACE PROCEDURE registar_cargo(
    p_nome VARCHAR(100),
    p_descricao VARCHAR(255),
    p_id_orgao_social INTEGER,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_orgao_associacao INTEGER;
BEGIN
    SELECT id_associacao INTO v_orgao_associacao
    FROM orgao_social WHERE id_orgao_social = p_id_orgao_social;

    IF NOT FOUND OR v_orgao_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Órgão social não pertence à associação autorizada';
    END IF;

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


-- ==========================================
-- PROCEDURES: UPDATE/DELETE - MANDATO
-- ==========================================

-- Atualizar mandato - NÃO permite alterar id_associacao
CREATE OR REPLACE PROCEDURE atualizar_mandato(
    p_id_mandato INTEGER,
    p_data_inicio DATE,
    p_data_fim DATE,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE mandato
    SET data_inicio = p_data_inicio,
        data_fim = p_data_fim
    WHERE id_mandato = p_id_mandato
      AND id_associacao = p_id_associacao;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Mandato não encontrado ou não autorizado';
    END IF;
END;
$$;

-- Eliminar mandato - restringe à associação
CREATE OR REPLACE PROCEDURE eliminar_mandato(
    p_id_mandato INTEGER,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM mandato
    WHERE id_mandato = p_id_mandato
      AND id_associacao = p_id_associacao;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Mandato não encontrado ou não autorizado';
    END IF;
END;
$$;


-- ==========================================
-- PROCEDURES: UPDATE/DELETE - EXERCICIO_CARGO
-- ==========================================

-- Atualizar exercício de cargo - valida entidades relacionadas
CREATE OR REPLACE PROCEDURE atualizar_exercicio_cargo(
    p_id_exercicio_cargo INTEGER,
    p_data_inicio DATE,
    p_data_fim DATE,
    p_id_associado INTEGER,
    p_id_cargo INTEGER,
    p_id_mandato INTEGER,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_associado_associacao INTEGER;
    v_cargo_associacao INTEGER;
    v_mandato_associacao INTEGER;
    v_exercicio_associacao INTEGER;
BEGIN
    -- Verificar que o exercício atual pertence à associação
    -- exercicio_cargo não tem id_associacao direto, validar via associado
    SELECT a.id_associacao INTO v_exercicio_associacao
    FROM exercicio_cargo ec
    JOIN associado a ON ec.id_associado = a.id_associado
    WHERE ec.id_exercicio_cargo = p_id_exercicio_cargo;

    IF NOT FOUND OR v_exercicio_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Exercício de cargo não encontrado ou não autorizado';
    END IF;

    -- Validar novo associado
    SELECT id_associacao INTO v_associado_associacao
    FROM associado WHERE id_associado = p_id_associado;

    IF NOT FOUND OR v_associado_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Associado não pertence à associação autorizada';
    END IF;

    -- Validar novo cargo (via orgao_social)
    SELECT os.id_associacao INTO v_cargo_associacao
    FROM cargo c
    JOIN orgao_social os ON c.id_orgao_social = os.id_orgao_social
    WHERE c.id_cargo = p_id_cargo;

    IF NOT FOUND OR v_cargo_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Cargo não pertence à associação autorizada';
    END IF;

    -- Validar novo mandato
    SELECT id_associacao INTO v_mandato_associacao
    FROM mandato WHERE id_mandato = p_id_mandato;

    IF NOT FOUND OR v_mandato_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Mandato não pertence à associação autorizada';
    END IF;

    UPDATE exercicio_cargo
    SET data_inicio = p_data_inicio,
        data_fim = p_data_fim,
        id_associado = p_id_associado,
        id_cargo = p_id_cargo,
        id_mandato = p_id_mandato
    WHERE id_exercicio_cargo = p_id_exercicio_cargo;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Exercício de cargo não encontrado';
    END IF;
END;
$$;

-- Eliminar exercício de cargo - restringe à associação via associado
CREATE OR REPLACE PROCEDURE eliminar_exercicio_cargo(
    p_id_exercicio_cargo INTEGER,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_count INTEGER;
BEGIN
    DELETE FROM exercicio_cargo ec
    WHERE ec.id_exercicio_cargo = p_id_exercicio_cargo
      AND EXISTS (
          SELECT 1 FROM associado a
          WHERE a.id_associado = ec.id_associado
          AND a.id_associacao = p_id_associacao
      );

    GET DIAGNOSTICS v_count = ROW_COUNT;
    IF v_count = 0 THEN
        RAISE EXCEPTION 'Exercício de cargo não encontrado ou não autorizado';
    END IF;
END;
$$;


-- ==========================================
-- PROCEDURES: UPDATE/DELETE - ASSOCIACAO
-- ==========================================

-- Atualizar associação - WHERE já garante isolamento (PK = id_associacao)
CREATE OR REPLACE PROCEDURE atualizar_associacao(
    p_id_associacao INTEGER,
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
    UPDATE associacao
    SET nipc = p_nipc,
        nome = p_nome,
        data_fundacao = p_data_fundacao,
        email = p_email,
        telefone = p_telefone,
        password_hash = p_password_hash,
        tipo_via = p_tipo_via,
        nome_via = p_nome_via,
        numero_porta = p_numero_porta,
        andar = p_andar,
        codigo_postal = p_codigo_postal,
        id_localidade = p_id_localidade
    WHERE id_associacao = p_id_associacao;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Associação não encontrada';
    END IF;
END;
$$;

-- Eliminar associação - apenas se não houver dados dependentes (FK constraints impedem)
CREATE OR REPLACE PROCEDURE eliminar_associacao(
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM associacao WHERE id_associacao = p_id_associacao;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Associação não encontrada';
    END IF;
END;
$$;


-- ==========================================
-- PROCEDURES: UPDATE/DELETE - EVENTO
-- ==========================================

-- Atualizar evento - NÃO permite alterar id_associacao
CREATE OR REPLACE PROCEDURE atualizar_evento(
    p_id_evento INTEGER,
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
    UPDATE evento
    SET nome_evento = p_nome_evento,
        descricao_evento = p_descricao_evento,
        data_inicio_evento = p_data_inicio_evento,
        data_fim_evento = p_data_fim_evento,
        local_evento = p_local_evento,
        estado_evento = p_estado_evento
    WHERE id_evento = p_id_evento
      AND id_associacao = p_id_associacao;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Evento não encontrado ou não autorizado';
    END IF;
END;
$$;

-- Eliminar evento - restringe à associação
CREATE OR REPLACE PROCEDURE eliminar_evento(
    p_id_evento INTEGER,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM evento
    WHERE id_evento = p_id_evento
      AND id_associacao = p_id_associacao;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Evento não encontrado ou não autorizado';
    END IF;
END;
$$;


-- ==========================================
-- PROCEDURES: UPDATE/DELETE - ASSOCIADO
-- ==========================================

-- Atualizar associado - NÃO permite alterar id_associacao
CREATE OR REPLACE PROCEDURE atualizar_associado(
    p_id_associado INTEGER,
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
    UPDATE associado
    SET numero_associado = p_numero_associado,
        nome = p_nome,
        nif = p_nif,
        data_nascimento = p_data_nascimento,
        email = p_email,
        telefone = p_telefone,
        data_adesao = p_data_adesao,
        data_saida = p_data_saida,
        estado = p_estado,
        tipo_via = p_tipo_via,
        nome_via = p_nome_via,
        numero_porta = p_numero_porta,
        andar = p_andar,
        codigo_postal = p_codigo_postal,
        id_localidade = p_id_localidade
    WHERE id_associado = p_id_associado
      AND id_associacao = p_id_associacao;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Associado não encontrado ou não autorizado';
    END IF;
END;
$$;

-- Eliminar associado - restringe à associação
CREATE OR REPLACE PROCEDURE eliminar_associado(
    p_id_associado INTEGER,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM associado
    WHERE id_associado = p_id_associado
      AND id_associacao = p_id_associacao;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Associado não encontrado ou não autorizado';
    END IF;
END;
$$;


-- ==========================================
-- PROCEDURES: UPDATE/DELETE - QUOTA
-- ==========================================

-- Atualizar quota - NÃO permite alterar id_associacao
CREATE OR REPLACE PROCEDURE atualizar_quota(
    p_id_quota INTEGER,
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
    UPDATE quota
    SET designacao_quota = p_designacao_quota,
        valor_quota = p_valor_quota,
        periodicidade_quota = p_periodicidade_quota,
        data_inicio_quota = p_data_inicio_quota,
        data_fim_quota = p_data_fim_quota
    WHERE id_quota = p_id_quota
      AND id_associacao = p_id_associacao;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Quota não encontrada ou não autorizada';
    END IF;
END;
$$;

-- Eliminar quota - restringe à associação
CREATE OR REPLACE PROCEDURE eliminar_quota(
    p_id_quota INTEGER,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM quota
    WHERE id_quota = p_id_quota
      AND id_associacao = p_id_associacao;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Quota não encontrada ou não autorizada';
    END IF;
END;
$$;


-- ==========================================
-- PROCEDURES: UPDATE/DELETE - ORGAO_SOCIAL
-- ==========================================

-- Atualizar órgão social - NÃO permite alterar id_associacao
CREATE OR REPLACE PROCEDURE atualizar_orgao_social(
    p_id_orgao_social INTEGER,
    p_nome VARCHAR(100),
    p_descricao VARCHAR(255),
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE orgao_social
    SET nome = p_nome,
        descricao = p_descricao
    WHERE id_orgao_social = p_id_orgao_social
      AND id_associacao = p_id_associacao;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Órgão social não encontrado ou não autorizado';
    END IF;
END;
$$;

-- Eliminar órgão social - restringe à associação
CREATE OR REPLACE PROCEDURE eliminar_orgao_social(
    p_id_orgao_social INTEGER,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM orgao_social
    WHERE id_orgao_social = p_id_orgao_social
      AND id_associacao = p_id_associacao;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Órgão social não encontrado ou não autorizado';
    END IF;
END;
$$;


-- ==========================================
-- PROCEDURES: UPDATE/DELETE - CARGO
-- ==========================================

-- Atualizar cargo - valida que o novo órgão social pertence à associação
CREATE OR REPLACE PROCEDURE atualizar_cargo(
    p_id_cargo INTEGER,
    p_nome VARCHAR(100),
    p_descricao VARCHAR(255),
    p_id_orgao_social INTEGER,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_orgao_associacao INTEGER;
    v_cargo_associacao INTEGER;
BEGIN
    -- Verificar que o cargo atual pertence à associação (via orgao_social)
    SELECT os.id_associacao INTO v_cargo_associacao
    FROM cargo c
    JOIN orgao_social os ON c.id_orgao_social = os.id_orgao_social
    WHERE c.id_cargo = p_id_cargo;

    IF NOT FOUND OR v_cargo_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Cargo não encontrado ou não autorizado';
    END IF;

    -- Validar novo órgão social
    SELECT id_associacao INTO v_orgao_associacao
    FROM orgao_social WHERE id_orgao_social = p_id_orgao_social;

    IF NOT FOUND OR v_orgao_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Órgão social não pertence à associação autorizada';
    END IF;

    UPDATE cargo
    SET nome = p_nome,
        descricao = p_descricao,
        id_orgao_social = p_id_orgao_social
    WHERE id_cargo = p_id_cargo;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Cargo não encontrado';
    END IF;
END;
$$;

-- Eliminar cargo - restringe à associação via orgao_social
CREATE OR REPLACE PROCEDURE eliminar_cargo(
    p_id_cargo INTEGER,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_count INTEGER;
BEGIN
    DELETE FROM cargo c
    WHERE c.id_cargo = p_id_cargo
      AND EXISTS (
          SELECT 1 FROM orgao_social os
          WHERE os.id_orgao_social = c.id_orgao_social
          AND os.id_associacao = p_id_associacao
      );

    GET DIAGNOSTICS v_count = ROW_COUNT;
    IF v_count = 0 THEN
        RAISE EXCEPTION 'Cargo não encontrado ou não autorizado';
    END IF;
END;
$$;


-- ==========================================
-- PROCEDURES: QUOTA_ASSOCIADO
-- ==========================================

-- Gerar quotas para associados (RF09) - já valida via quota.id_associacao
CREATE OR REPLACE PROCEDURE gerar_quotas_associados(
    p_id_quota INTEGER,
    p_data_vencimento_inicial DATE,
    p_periodos INTEGER DEFAULT 12
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_associado RECORD;
    v_periodo INTEGER := 0;
    v_data_vencimento DATE;
    v_periodo_referencia VARCHAR(20);
    v_valor_devido NUMERIC(10,2);
    v_quota RECORD;
BEGIN
    -- Obter detalhes da quota
    SELECT * INTO v_quota FROM quota WHERE id_quota = p_id_quota;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Quota não encontrada: %', p_id_quota;
    END IF;

    v_valor_devido := v_quota.valor_quota;

    -- Para cada associado ativo da associação
    FOR v_associado IN
        SELECT id_associado FROM associado
        WHERE id_associacao = v_quota.id_associacao
        AND estado = 'Ativo'
    LOOP
        v_data_vencimento := p_data_vencimento_inicial;

        -- Gerar quotas para o número de períodos
        FOR v_periodo IN 1..p_periodos LOOP
            -- Formatar período de referência conforme periodicidade
            CASE v_quota.periodicidade_quota
                WHEN 'Mensal' THEN
                    v_periodo_referencia := TO_CHAR(v_data_vencimento, 'MM/YYYY');
                    v_data_vencimento := v_data_vencimento + INTERVAL '1 month';
                WHEN 'Trimestral' THEN
                    v_periodo_referencia := CONCAT('T', CEIL(EXTRACT(MONTH FROM v_data_vencimento)::int / 3), '/', EXTRACT(YEAR FROM v_data_vencimento)::int);
                    v_data_vencimento := v_data_vencimento + INTERVAL '3 months';
                WHEN 'Semestral' THEN
                    v_periodo_referencia := CONCAT('S', CEIL(EXTRACT(MONTH FROM v_data_vencimento)::int / 6), '/', EXTRACT(YEAR FROM v_data_vencimento)::int);
                    v_data_vencimento := v_data_vencimento + INTERVAL '6 months';
                WHEN 'Anual' THEN
                    v_periodo_referencia := EXTRACT(YEAR FROM v_data_vencimento)::int::VARCHAR;
                    v_data_vencimento := v_data_vencimento + INTERVAL '1 year';
                ELSE
                    v_periodo_referencia := TO_CHAR(v_data_vencimento, 'MM/YYYY');
                    v_data_vencimento := v_data_vencimento + INTERVAL '1 month';
            END CASE;

            -- Inserir quota_associado se não existir
            INSERT INTO quota_associado (
                valor_devido, data_vencimento, periodo_referencia, estado_quota_associado,
                id_associado, id_quota
            )
            SELECT v_valor_devido, v_data_vencimento - INTERVAL '1 month', v_periodo_referencia, 'Pendente',
                   v_associado.id_associado, p_id_quota
            WHERE NOT EXISTS (
                SELECT 1 FROM quota_associado
                WHERE id_associado = v_associado.id_associado
                AND id_quota = p_id_quota
                AND periodo_referencia = v_periodo_referencia
            );
        END LOOP;
    END LOOP;
END;
$$;

-- Atualizar quota_associado - valida quota e associado
CREATE OR REPLACE PROCEDURE atualizar_quota_associado(
    p_id_quota_associado INTEGER,
    p_valor_devido NUMERIC(10,2),
    p_data_vencimento DATE,
    p_periodo_referencia VARCHAR(20),
    p_estado_quota_associado VARCHAR(100),
    p_id_associado INTEGER,
    p_id_quota INTEGER,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_quota_associacao INTEGER;
    v_associado_associacao INTEGER;
    v_qa_associacao INTEGER;
BEGIN
    -- Verificar que a quota_associado atual pertence à associação
    SELECT q.id_associacao INTO v_qa_associacao
    FROM quota_associado qa
    JOIN quota q ON qa.id_quota = q.id_quota
    WHERE qa.id_quota_associado = p_id_quota_associado;

    IF NOT FOUND OR v_qa_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Quota associado não encontrada ou não autorizada';
    END IF;

    -- Validar nova quota
    SELECT id_associacao INTO v_quota_associacao
    FROM quota WHERE id_quota = p_id_quota;

    IF NOT FOUND OR v_quota_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Quota não pertence à associação autorizada';
    END IF;

    -- Validar novo associado
    SELECT id_associacao INTO v_associado_associacao
    FROM associado WHERE id_associado = p_id_associado;

    IF NOT FOUND OR v_associado_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Associado não pertence à associação autorizada';
    END IF;

    UPDATE quota_associado
    SET valor_devido = p_valor_devido,
        data_vencimento = p_data_vencimento,
        periodo_referencia = p_periodo_referencia,
        estado_quota_associado = p_estado_quota_associado,
        id_associado = p_id_associado,
        id_quota = p_id_quota
    WHERE id_quota_associado = p_id_quota_associado;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Quota associado não encontrada';
    END IF;
END;
$$;

-- Eliminar quota_associado - restringe à associação via quota
CREATE OR REPLACE PROCEDURE eliminar_quota_associado(
    p_id_quota_associado INTEGER,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_count INTEGER;
BEGIN
    DELETE FROM quota_associado qa
    WHERE qa.id_quota_associado = p_id_quota_associado
      AND EXISTS (
          SELECT 1 FROM quota q
          WHERE q.id_quota = qa.id_quota
          AND q.id_associacao = p_id_associacao
      );

    GET DIAGNOSTICS v_count = ROW_COUNT;
    IF v_count = 0 THEN
        RAISE EXCEPTION 'Quota associado não encontrada ou não autorizada';
    END IF;
END;
$$;


-- ==========================================
-- PROCEDURES: PAGAMENTO E MOVIMENTO_BANCARIO (RF10)
-- ==========================================

-- Registar movimento bancário - SEM validação de associação (tabela não tem id_associacao)
-- NOTA: Movimentos não conciliados não têm associação direta
CREATE OR REPLACE PROCEDURE registar_movimento_bancario(
    p_data_movimento DATE,
    p_descricao_movimento VARCHAR(255),
    p_valor_movimento NUMERIC(10,2),
    p_referencia_movimento VARCHAR(100)
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO movimento_bancario (
        data_movimento,
        descricao_movimento,
        valor_movimento,
        referencia_movimento
    )
    VALUES (
        p_data_movimento,
        p_descricao_movimento,
        p_valor_movimento,
        p_referencia_movimento
    );
END;
$$;


-- Registar pagamento - valida quota_associado e movimento
CREATE OR REPLACE PROCEDURE registar_pagamento(
    p_data_pagamento TIMESTAMP,
    p_valor_pago NUMERIC(10,2),
    p_metodo_pagamento VARCHAR(100),
    p_referencia_pagamento VARCHAR(100),
    p_id_quota_associado INTEGER,
    p_id_movimento INTEGER,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_qa_associacao INTEGER;
    v_movimento_associacao INTEGER;
BEGIN
    -- Validar quota_associado
    SELECT q.id_associacao INTO v_qa_associacao
    FROM quota_associado qa
    JOIN quota q ON qa.id_quota = q.id_quota
    WHERE qa.id_quota_associado = p_id_quota_associado;

    IF NOT FOUND OR v_qa_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Quota associado não pertence à associação autorizada';
    END IF;

    -- Validar movimento bancário (se fornecido) - via quota_associado do pagamento
    IF p_id_movimento IS NOT NULL THEN
        SELECT q.id_associacao INTO v_movimento_associacao
        FROM movimento_bancario mb
        LEFT JOIN pagamento p ON mb.id_movimento = p.id_movimento
        LEFT JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
        LEFT JOIN quota q ON qa.id_quota = q.id_quota
        WHERE mb.id_movimento = p_id_movimento;

        IF NOT FOUND OR v_movimento_associacao != p_id_associacao THEN
            RAISE EXCEPTION 'Movimento bancário não pertence à associação autorizada';
        END IF;
    END IF;

    INSERT INTO pagamento (
        data_pagamento,
        valor_pago,
        metodo_pagamento,
        referencia_pagamento,
        id_quota_associado,
        id_movimento
    )
    VALUES (
        p_data_pagamento,
        p_valor_pago,
        p_metodo_pagamento,
        p_referencia_pagamento,
        p_id_quota_associado,
        p_id_movimento
    );
END;
$$;


-- Atualizar movimento bancário - SEM validação de associação direta
-- NOTA: Esta operação é de risco, apenas permitir se movimento não estiver conciliado
CREATE OR REPLACE PROCEDURE atualizar_movimento_bancario(
    p_id_movimento INTEGER,
    p_data_movimento DATE,
    p_descricao_movimento VARCHAR(255),
    p_valor_movimento NUMERIC(10,2),
    p_referencia_movimento VARCHAR(100),
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_movimento_associacao INTEGER;
    v_conciliado BOOLEAN;
BEGIN
    -- Verificar se movimento está conciliado e pertence à associação
    SELECT q.id_associacao, (p.id_pagamento IS NOT NULL) INTO v_movimento_associacao, v_conciliado
    FROM movimento_bancario mb
    LEFT JOIN pagamento p ON mb.id_movimento = p.id_movimento
    LEFT JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
    LEFT JOIN quota q ON qa.id_quota = q.id_quota
    WHERE mb.id_movimento = p_id_movimento;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Movimento bancário não encontrado';
    END IF;

    -- Se estiver conciliado, validar associação
    IF v_conciliado AND v_movimento_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Movimento bancário conciliado não pertence à associação autorizada';
    END IF;

    UPDATE movimento_bancario
    SET data_movimento = p_data_movimento,
        descricao_movimento = p_descricao_movimento,
        valor_movimento = p_valor_movimento,
        referencia_movimento = p_referencia_movimento
    WHERE id_movimento = p_id_movimento;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Movimento bancário não encontrado';
    END IF;
END;
$$;


-- Eliminar movimento bancário - apenas se não estiver conciliado ou se pertencer à associação
CREATE OR REPLACE PROCEDURE eliminar_movimento_bancario(
    p_id_movimento INTEGER,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_movimento_associacao INTEGER;
    v_conciliado BOOLEAN;
    v_count INTEGER;
BEGIN
    -- Verificar se movimento está conciliado e pertence à associação
    SELECT q.id_associacao, (p.id_pagamento IS NOT NULL) INTO v_movimento_associacao, v_conciliado
    FROM movimento_bancario mb
    LEFT JOIN pagamento p ON mb.id_movimento = p.id_movimento
    LEFT JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
    LEFT JOIN quota q ON qa.id_quota = q.id_quota
    WHERE mb.id_movimento = p_id_movimento;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Movimento bancário não encontrado';
    END IF;

    -- Se estiver conciliado, validar associação
    IF v_conciliado AND v_movimento_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Movimento bancário conciliado não pertence à associação autorizada';
    END IF;

    DELETE FROM movimento_bancario
    WHERE id_movimento = p_id_movimento;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    IF v_count = 0 THEN
        RAISE EXCEPTION 'Movimento bancário não encontrado';
    END IF;
END;
$$;


-- Atualizar pagamento - valida quota_associado e movimento
CREATE OR REPLACE PROCEDURE atualizar_pagamento(
    p_id_pagamento INTEGER,
    p_data_pagamento TIMESTAMP,
    p_valor_pago NUMERIC(10,2),
    p_metodo_pagamento VARCHAR(100),
    p_referencia_pagamento VARCHAR(100),
    p_id_quota_associado INTEGER,
    p_id_movimento INTEGER,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_qa_associacao INTEGER;
    v_movimento_associacao INTEGER;
    v_pagamento_associacao INTEGER;
BEGIN
    -- Verificar que o pagamento atual pertence à associação
    SELECT q.id_associacao INTO v_pagamento_associacao
    FROM pagamento p
    JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
    JOIN quota q ON qa.id_quota = q.id_quota
    WHERE p.id_pagamento = p_id_pagamento;

    IF NOT FOUND OR v_pagamento_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Pagamento não encontrado ou não autorizado';
    END IF;

    -- Validar nova quota_associado
    SELECT q.id_associacao INTO v_qa_associacao
    FROM quota_associado qa
    JOIN quota q ON qa.id_quota = q.id_quota
    WHERE qa.id_quota_associado = p_id_quota_associado;

    IF NOT FOUND OR v_qa_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Quota associado não pertence à associação autorizada';
    END IF;

    -- Validar novo movimento (se fornecido)
    IF p_id_movimento IS NOT NULL THEN
        SELECT q.id_associacao INTO v_movimento_associacao
        FROM movimento_bancario mb
        LEFT JOIN pagamento p2 ON mb.id_movimento = p2.id_movimento
        LEFT JOIN quota_associado qa2 ON p2.id_quota_associado = qa2.id_quota_associado
        LEFT JOIN quota q ON qa2.id_quota = q.id_quota
        WHERE mb.id_movimento = p_id_movimento;

        IF NOT FOUND OR v_movimento_associacao != p_id_associacao THEN
            RAISE EXCEPTION 'Movimento bancário não pertence à associação autorizada';
        END IF;
    END IF;

    UPDATE pagamento
    SET data_pagamento = p_data_pagamento,
        valor_pago = p_valor_pago,
        metodo_pagamento = p_metodo_pagamento,
        referencia_pagamento = p_referencia_pagamento,
        id_quota_associado = p_id_quota_associado,
        id_movimento = p_id_movimento
    WHERE id_pagamento = p_id_pagamento;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Pagamento não encontrado';
    END IF;
END;
$$;


-- Eliminar pagamento - restringe à associação via quota_associado
CREATE OR REPLACE PROCEDURE eliminar_pagamento(
    p_id_pagamento INTEGER,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_count INTEGER;
BEGIN
    DELETE FROM pagamento p
    WHERE p.id_pagamento = p_id_pagamento
      AND EXISTS (
          SELECT 1 FROM quota_associado qa
          JOIN quota q ON qa.id_quota = q.id_quota
          WHERE qa.id_quota_associado = p.id_quota_associado
          AND q.id_associacao = p_id_associacao
      );

    GET DIAGNOSTICS v_count = ROW_COUNT;
    IF v_count = 0 THEN
        RAISE EXCEPTION 'Pagamento não encontrado ou não autorizado';
    END IF;
END;
$$;


-- ==========================================
-- PROCEDURES: TIPO_DOCUMENTO E DOCUMENTO (RF11)
-- ==========================================

-- Registar tipo de documento
CREATE OR REPLACE PROCEDURE registar_tipo_documento(
    p_nome_tipo_documento VARCHAR(150),
    p_descricao_tipo_documento VARCHAR(255),
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO tipo_documento (
        nome_tipo_documento,
        descricao_tipo_documento,
        id_associacao
    )
    VALUES (
        p_nome_tipo_documento,
        p_descricao_tipo_documento,
        p_id_associacao
    );
END;
$$;


-- Registar documento - valida tipo_documento e mandato
CREATE OR REPLACE PROCEDURE registar_documento(
    p_nome_documento VARCHAR(150),
    p_data_upload TIMESTAMP,
    p_data_documento DATE,
    p_ficheiro VARCHAR(255),
    p_observacoes VARCHAR(400),
    p_id_tipo_documento INTEGER,
    p_id_associacao INTEGER,
    p_id_mandato INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_tipo_associacao INTEGER;
    v_mandato_associacao INTEGER;
BEGIN
    -- Validar tipo_documento
    SELECT id_associacao INTO v_tipo_associacao
    FROM tipo_documento WHERE id_tipo_documento = p_id_tipo_documento;

    IF NOT FOUND OR v_tipo_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Tipo de documento não pertence à associação autorizada';
    END IF;

    -- Validar mandato (se fornecido)
    IF p_id_mandato IS NOT NULL THEN
        SELECT id_associacao INTO v_mandato_associacao
        FROM mandato WHERE id_mandato = p_id_mandato;

        IF NOT FOUND OR v_mandato_associacao != p_id_associacao THEN
            RAISE EXCEPTION 'Mandato não pertence à associação autorizada';
        END IF;
    END IF;

    INSERT INTO documento (
        nome_documento,
        data_upload,
        data_documento,
        ficheiro,
        observacoes,
        id_tipo_documento,
        id_associacao,
        id_mandato
    )
    VALUES (
        p_nome_documento,
        p_data_upload,
        p_data_documento,
        p_ficheiro,
        p_observacoes,
        p_id_tipo_documento,
        p_id_associacao,
        p_id_mandato
    );
END;
$$;


-- Atualizar tipo de documento - NÃO permite alterar id_associacao
CREATE OR REPLACE PROCEDURE atualizar_tipo_documento(
    p_id_tipo_documento INTEGER,
    p_nome_tipo_documento VARCHAR(150),
    p_descricao_tipo_documento VARCHAR(255),
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE tipo_documento
    SET nome_tipo_documento = p_nome_tipo_documento,
        descricao_tipo_documento = p_descricao_tipo_documento
    WHERE id_tipo_documento = p_id_tipo_documento
      AND id_associacao = p_id_associacao;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Tipo de documento não encontrado ou não autorizado';
    END IF;
END;
$$;


-- Eliminar tipo de documento - restringe à associação
CREATE OR REPLACE PROCEDURE eliminar_tipo_documento(
    p_id_tipo_documento INTEGER,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM tipo_documento
    WHERE id_tipo_documento = p_id_tipo_documento
      AND id_associacao = p_id_associacao;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Tipo de documento não encontrado ou não autorizado';
    END IF;
END;
$$;


-- Atualizar documento - valida tipo_documento e mandato
CREATE OR REPLACE PROCEDURE atualizar_documento(
    p_id_documento INTEGER,
    p_nome_documento VARCHAR(150),
    p_data_upload TIMESTAMP,
    p_data_documento DATE,
    p_ficheiro VARCHAR(255),
    p_observacoes VARCHAR(400),
    p_id_tipo_documento INTEGER,
    p_id_associacao INTEGER,
    p_id_mandato INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_tipo_associacao INTEGER;
    v_mandato_associacao INTEGER;
    v_doc_associacao INTEGER;
BEGIN
    -- Verificar que o documento atual pertence à associação
    SELECT id_associacao INTO v_doc_associacao
    FROM documento WHERE id_documento = p_id_documento;

    IF NOT FOUND OR v_doc_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Documento não encontrado ou não autorizado';
    END IF;

    -- Validar novo tipo_documento
    SELECT id_associacao INTO v_tipo_associacao
    FROM tipo_documento WHERE id_tipo_documento = p_id_tipo_documento;

    IF NOT FOUND OR v_tipo_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Tipo de documento não pertence à associação autorizada';
    END IF;

    -- Validar novo mandato (se fornecido)
    IF p_id_mandato IS NOT NULL THEN
        SELECT id_associacao INTO v_mandato_associacao
        FROM mandato WHERE id_mandato = p_id_mandato;

        IF NOT FOUND OR v_mandato_associacao != p_id_associacao THEN
            RAISE EXCEPTION 'Mandato não pertence à associação autorizada';
        END IF;
    END IF;

    UPDATE documento
    SET nome_documento = p_nome_documento,
        data_upload = p_data_upload,
        data_documento = p_data_documento,
        ficheiro = p_ficheiro,
        observacoes = p_observacoes,
        id_tipo_documento = p_id_tipo_documento,
        id_mandato = p_id_mandato
    WHERE id_documento = p_id_documento;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Documento não encontrado';
    END IF;
END;
$$;


-- Eliminar documento - restringe à associação
CREATE OR REPLACE PROCEDURE eliminar_documento(
    p_id_documento INTEGER,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM documento
    WHERE id_documento = p_id_documento
      AND id_associacao = p_id_associacao;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Documento não encontrado ou não autorizado';
    END IF;
END;
$$;