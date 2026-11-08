-- =====================================================
-- MIGRAÇÃO: ISOLAMENTO MULTI-TENANCY NAS PROCEDURES
-- Versão: 1.0
-- Data: 2025
-- Descrição: Adiciona validação de associação autorizada em todas
--            as procedures UPDATE e DELETE, e validação de
--            entidades relacionadas em INSERT/UPDATE;
-- =====================================================

-- PRÉ-CONDIÇÕES:
-- 1. Base de dados existe e está acessível
-- 2. Tabelas e views já criadas (01_tabelas.sql, 03_views.sql)
-- 3. Procedures antigas existem (02_procedures.sql)
-- 4. Não há transações abertas
-- 5. Backup realizado antes de aplicar

-- AVISOS:
-- - Esta migração usa DROP PROCEDURE com CASCADE para remover sobrecargas antigas
-- - Assinaturas alteradas: PostgreSQL mantém sobrecargas antigas sem DROP CASCADE
-- - As chamadas Python DEVEM ser atualizadas ANTES de aplicar
-- - Testar em ambiente de desenvolvimento primeiro

BEGIN;

-- =====================================================
-- FUNÇÃO AUXILIAR: Dropar TODAS as sobrecargas de uma procedure
-- =====================================================
-- PostgreSQL não permite DROP PROCEDURE com signature wildcard,
-- então usamos uma função que itera sobre pg_proc e droppa tudo;

DO $$
DECLARE
    v_proc RECORD;
    v_sig RECORD;
BEGIN
    -- Lista de procedures a remover completamente (todas as sobrecargas)
    FOR v_proc IN
        SELECT n.nspname as schema, p.proname as name
        FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE p.prokind = 'p'
        AND n.nspname = 'public'
        AND p.proname IN (
            'atualizar_mandato', 'eliminar_mandato',
            'atualizar_exercicio_cargo', 'eliminar_exercicio_cargo',
            'atualizar_evento', 'eliminar_evento',
            'atualizar_associado', 'eliminar_associado',
            'atualizar_quota', 'eliminar_quota',
            'atualizar_orgao_social', 'eliminar_orgao_social',
            'atualizar_cargo', 'eliminar_cargo',
            'atualizar_quota_associado', 'eliminar_quota_associado',
            'atualizar_pagamento', 'eliminar_pagamento',
            'atualizar_movimento_bancario', 'eliminar_movimento_bancario',
            'atualizar_tipo_documento', 'eliminar_tipo_documento',
            'atualizar_documento', 'eliminar_documento',
            'registar_cargo', 'registar_exercicio_cargo',
            'registar_pagamento', 'registar_documento'
        )
        GROUP BY n.nspname, p.proname
    LOOP
        -- Dropar TODAS as sobrecargas desta procedure
        FOR v_sig IN
            SELECT pg_get_function_identity_arguments(p.oid) as args
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE p.proname = v_proc.name
            AND n.nspname = v_proc.schema
            AND p.prokind = 'p'
        LOOP
            EXECUTE format('DROP PROCEDURE IF EXISTS %I.%I(%s) CASCADE',
                           v_proc.schema, v_proc.name, v_sig.args);
        END LOOP;
    END LOOP;
END;
$$;

-- ==========================================
-- MANDATO
-- ==========================================

-- Atualizar mandato: remover id_associacao do SET, adicionar no WHERE
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


-- Eliminar mandato: adicionar p_id_associacao
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
-- EXERCICIO_CARGO
-- ==========================================

-- Registar exercício de cargo: adicionar p_id_associacao e validações
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
    SELECT id_associacao INTO v_associado_associacao
    FROM associado WHERE id_associado = p_id_associado;

    IF NOT FOUND OR v_associado_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Associado não pertence à associação autorizada';
    END IF;

    SELECT os.id_associacao INTO v_cargo_associacao
    FROM cargo c
    JOIN orgao_social os ON c.id_orgao_social = os.id_orgao_social
    WHERE c.id_cargo = p_id_cargo;

    IF NOT FOUND OR v_cargo_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Cargo não pertence à associação autorizada';
    END IF;

    SELECT id_associacao INTO v_mandato_associacao
    FROM mandato WHERE id_mandato = p_id_mandato;

    IF NOT FOUND OR v_mandato_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Mandato não pertence à associação autorizada';
    END IF;

    INSERT INTO exercicio_cargo (
        data_inicio, data_fim, id_associado, id_cargo, id_mandato
    )
    VALUES (
        p_data_inicio, p_data_fim, p_id_associado, p_id_cargo, p_id_mandato
    );
END;
$$;


-- Atualizar exercício de cargo: adicionar p_id_associacao e validações
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
    SELECT a.id_associacao INTO v_exercicio_associacao
    FROM exercicio_cargo ec
    JOIN associado a ON ec.id_associado = a.id_associado
    WHERE ec.id_exercicio_cargo = p_id_exercicio_cargo;

    IF NOT FOUND OR v_exercicio_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Exercício de cargo não encontrado ou não autorizado';
    END IF;

    SELECT id_associacao INTO v_associado_associacao
    FROM associado WHERE id_associado = p_id_associado;

    IF NOT FOUND OR v_associado_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Associado não pertence à associação autorizada';
    END IF;

    SELECT os.id_associacao INTO v_cargo_associacao
    FROM cargo c
    JOIN orgao_social os ON c.id_orgao_social = os.id_orgao_social
    WHERE c.id_cargo = p_id_cargo;

    IF NOT FOUND OR v_cargo_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Cargo não pertence à associação autorizada';
    END IF;

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


-- Eliminar exercício de cargo: adicionar p_id_associacao
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
-- EVENTO
-- ==========================================

-- Atualizar evento: remover id_associacao do SET, adicionar no WHERE
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


-- Eliminar evento: adicionar p_id_associacao
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
-- ASSOCIADO
-- ==========================================

-- Atualizar associado: remover id_associacao do SET, adicionar no WHERE
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


-- Eliminar associado: adicionar p_id_associacao
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
-- QUOTA
-- ==========================================

-- Atualizar quota: remover id_associacao do SET, adicionar no WHERE
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


-- Eliminar quota: adicionar p_id_associacao
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
-- ORGAO_SOCIAL
-- ==========================================

-- Atualizar órgão social: remover id_associacao do SET, adicionar no WHERE
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


-- Eliminar órgão social: adicionar p_id_associacao
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
-- CARGO
-- ==========================================

-- Registar cargo: adicionar p_id_associacao e validação
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

    INSERT INTO cargo (nome, descricao, id_orgao_social)
    VALUES (p_nome, p_descricao, p_id_orgao_social);
END;
$$;


-- Atualizar cargo: adicionar p_id_associacao e validação
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
    SELECT os.id_associacao INTO v_cargo_associacao
    FROM cargo c
    JOIN orgao_social os ON c.id_orgao_social = os.id_orgao_social
    WHERE c.id_cargo = p_id_cargo;

    IF NOT FOUND OR v_cargo_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Cargo não encontrado ou não autorizado';
    END IF;

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


-- Eliminar cargo: adicionar p_id_associacao
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
-- QUOTA_ASSOCIADO
-- ==========================================

-- Atualizar quota_associado: adicionar p_id_associacao e validações
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
    SELECT q.id_associacao INTO v_qa_associacao
    FROM quota_associado qa
    JOIN quota q ON qa.id_quota = q.id_quota
    WHERE qa.id_quota_associado = p_id_quota_associado;

    IF NOT FOUND OR v_qa_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Quota associado não encontrada ou não autorizada';
    END IF;

    SELECT id_associacao INTO v_quota_associacao
    FROM quota WHERE id_quota = p_id_quota;

    IF NOT FOUND OR v_quota_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Quota não pertence à associação autorizada';
    END IF;

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


-- Eliminar quota_associado: adicionar p_id_associacao
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
-- PAGAMENTO
-- ==========================================

-- Registar pagamento: adicionar p_id_associacao e validações
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
    SELECT q.id_associacao INTO v_qa_associacao
    FROM quota_associado qa
    JOIN quota q ON qa.id_quota = q.id_quota
    WHERE qa.id_quota_associado = p_id_quota_associado;

    IF NOT FOUND OR v_qa_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Quota associado não pertence à associação autorizada';
    END IF;

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
        data_pagamento, valor_pago, metodo_pagamento, referencia_pagamento,
        id_quota_associado, id_movimento
    )
    VALUES (
        p_data_pagamento, p_valor_pago, p_metodo_pagamento, p_referencia_pagamento,
        p_id_quota_associado, p_id_movimento
    );
END;
$$;


-- Atualizar pagamento: adicionar p_id_associacao e validações
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
    SELECT q.id_associacao INTO v_pagamento_associacao
    FROM pagamento p
    JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
    JOIN quota q ON qa.id_quota = q.id_quota
    WHERE p.id_pagamento = p_id_pagamento;

    IF NOT FOUND OR v_pagamento_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Pagamento não encontrado ou não autorizado';
    END IF;

    SELECT q.id_associacao INTO v_qa_associacao
    FROM quota_associado qa
    JOIN quota q ON qa.id_quota = q.id_quota
    WHERE qa.id_quota_associado = p_id_quota_associado;

    IF NOT FOUND OR v_qa_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Quota associado não pertence à associação autorizada';
    END IF;

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


-- Eliminar pagamento: adicionar p_id_associacao
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
-- MOVIMENTO_BANCARIO
-- ==========================================

-- Atualizar movimento bancário: adicionar p_id_associacao e validação de conciliação
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
    SELECT q.id_associacao, (p.id_pagamento IS NOT NULL) INTO v_movimento_associacao, v_conciliado
    FROM movimento_bancario mb
    LEFT JOIN pagamento p ON mb.id_movimento = p.id_movimento
    LEFT JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
    LEFT JOIN quota q ON qa.id_quota = q.id_quota
    WHERE mb.id_movimento = p_id_movimento;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Movimento bancário não encontrado';
    END IF;

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


-- Eliminar movimento bancário: adicionar p_id_associacao
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
    SELECT q.id_associacao, (p.id_pagamento IS NOT NULL) INTO v_movimento_associacao, v_conciliado
    FROM movimento_bancario mb
    LEFT JOIN pagamento p ON mb.id_movimento = p.id_movimento
    LEFT JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
    LEFT JOIN quota q ON qa.id_quota = q.id_quota
    WHERE mb.id_movimento = p_id_movimento;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Movimento bancário não encontrado';
    END IF;

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


-- ==========================================
-- TIPO_DOCUMENTO
-- ==========================================

-- Atualizar tipo de documento: remover id_associacao do SET, adicionar no WHERE
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


-- Eliminar tipo de documento: adicionar p_id_associacao
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


-- ==========================================
-- DOCUMENTO
-- ==========================================

-- Registar documento: adicionar validações (já tem p_id_associacao)
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
    SELECT id_associacao INTO v_tipo_associacao
    FROM tipo_documento WHERE id_tipo_documento = p_id_tipo_documento;

    IF NOT FOUND OR v_tipo_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Tipo de documento não pertence à associação autorizada';
    END IF;

    IF p_id_mandato IS NOT NULL THEN
        SELECT id_associacao INTO v_mandato_associacao
        FROM mandato WHERE id_mandato = p_id_mandato;

        IF NOT FOUND OR v_mandato_associacao != p_id_associacao THEN
            RAISE EXCEPTION 'Mandato não pertence à associação autorizada';
        END IF;
    END IF;

    INSERT INTO documento (
        nome_documento, data_upload, data_documento, ficheiro, observacoes,
        id_tipo_documento, id_associacao, id_mandato
    )
    VALUES (
        p_nome_documento, p_data_upload, p_data_documento, p_ficheiro, p_observacoes,
        p_id_tipo_documento, p_id_associacao, p_id_mandato
    );
END;
$$;


-- Atualizar documento: remover id_associacao do SET, adicionar validações
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
    SELECT id_associacao INTO v_doc_associacao
    FROM documento WHERE id_documento = p_id_documento;

    IF NOT FOUND OR v_doc_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Documento não encontrado ou não autorizado';
    END IF;

    SELECT id_associacao INTO v_tipo_associacao
    FROM tipo_documento WHERE id_tipo_documento = p_id_tipo_documento;

    IF NOT FOUND OR v_tipo_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Tipo de documento não pertence à associação autorizada';
    END IF;

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


-- Eliminar documento: adicionar p_id_associacao
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

COMMIT;

-- =====================================================
-- VALIDAÇÃO PÓS-MIGRAÇÃO
-- =====================================================
-- Execute as seguintes queries para validar:
--
-- 1. Verificar que procedures existem com novas assinaturas:
-- \df+ atualizar_*
-- \df+ eliminar_*
-- \df+ registar_*
--
-- 2. Testar isolamento:
-- INSERT INTO associacao ... (criar assoc A e B)
-- CALL registar_evento(..., id_associacao_A);
-- CALL atualizar_evento(id_evento_B, ..., id_associacao_A); -- DEVE FALHAR
--
-- 3. Verificar que DROP PROCEDURE removeu sobrecargas antigas:
-- SELECT proname, oidvectortypes(proargtypes) FROM pg_proc WHERE proname LIKE 'atualizar_%' OR proname LIKE 'eliminar_%';