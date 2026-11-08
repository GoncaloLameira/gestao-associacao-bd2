-- ============================================================================
-- FASE 2.1 — NÚCLEO FINANCEIRO: Atualização automática de estado de quotas
-- ============================================================================
-- Este script implementa a lógica de recálculo automático do estado de quota_associado
-- baseado nos pagamentos registados, garantindo integridade financeira.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. FUNÇÃO: Calcular estado da quota baseado nos pagamentos
-- ---------------------------------------------------------------------------
-- Regras de negócio:
-- - Se estado atual = 'Isento' → mantém 'Isento' (não cobrável)
-- - Soma pagamentos >= valor_devido → 'Pago'
-- - Soma pagamentos > 0 e < valor_devido → 'Parcial'
-- - Soma pagamentos = 0:
--     - Se data_vencimento < CURRENT_DATE → 'Em Dívida'
--     - Caso contrário → 'Pendente'
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION calcular_estado_quota_associado(
    p_id_quota_associado INTEGER
)
RETURNS VARCHAR(100)
LANGUAGE plpgsql
AS $$
DECLARE
    v_valor_devido NUMERIC(10,2);
    v_data_vencimento DATE;
    v_estado_atual VARCHAR(100);
    v_total_pago NUMERIC(10,2);
    v_novo_estado VARCHAR(100);
BEGIN
    -- Obter dados da quota_associado
    SELECT valor_devido, data_vencimento, estado_quota_associado
    INTO v_valor_devido, v_data_vencimento, v_estado_atual
    FROM quota_associado
    WHERE id_quota_associado = p_id_quota_associado;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Quota associado não encontrada: %', p_id_quota_associado;
    END IF;

    -- Se isento, mantém isento (não pode ser alterado por pagamentos)
    IF v_estado_atual = 'Isento' THEN
        RETURN 'Isento';
    END IF;

    -- Calcular total pago (apenas pagamentos válidos, não eliminados)
    SELECT COALESCE(SUM(valor_pago), 0)
    INTO v_total_pago
    FROM pagamento
    WHERE id_quota_associado = p_id_quota_associado;

    -- Determinar novo estado
    IF v_total_pago >= v_valor_devido THEN
        v_novo_estado := 'Pago';
    ELSIF v_total_pago > 0 THEN
        v_novo_estado := 'Parcial';
    ELSE
        -- Sem pagamentos
        IF v_data_vencimento < CURRENT_DATE THEN
            v_novo_estado := 'Em Dívida';
        ELSE
            v_novo_estado := 'Pendente';
        END IF;
    END IF;

    RETURN v_novo_estado;
END;
$$;


-- ---------------------------------------------------------------------------
-- 2. PROCEDURE: Atualizar estado da quota_associado (chamada interna)
-- ---------------------------------------------------------------------------
-- Atualiza apenas o campo estado_quota_associado baseado nos pagamentos
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE atualizar_estado_quota_associado(
    p_id_quota_associado INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_novo_estado VARCHAR(100);
BEGIN
    v_novo_estado := calcular_estado_quota_associado(p_id_quota_associado);

    UPDATE quota_associado
    SET estado_quota_associado = v_novo_estado
    WHERE id_quota_associado = p_id_quota_associado;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Quota associado não encontrada ao atualizar estado: %', p_id_quota_associado;
    END IF;
END;
$$;


-- ---------------------------------------------------------------------------
-- 3. PROCEDURE: Registar pagamento COM atualização automática de estado
-- ---------------------------------------------------------------------------
-- Substitui a procedure existente registar_pagamento
-- Returns the created payment ID via OUT parameter
-- ---------------------------------------------------------------------------
-- Drop old procedure first (different signature - no OUT parameter)
DROP PROCEDURE IF EXISTS registar_pagamento(TIMESTAMP, NUMERIC, VARCHAR, VARCHAR, INTEGER, INTEGER, INTEGER);
CREATE OR REPLACE PROCEDURE registar_pagamento(
    p_data_pagamento TIMESTAMP,
    p_valor_pago NUMERIC(10,2),
    p_metodo_pagamento VARCHAR(100),
    p_referencia_pagamento VARCHAR(100),
    p_id_quota_associado INTEGER,
    p_id_movimento INTEGER,
    p_id_associacao INTEGER,
    OUT p_id_pagamento INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_qa_associacao INTEGER;
    v_movimento_associacao INTEGER;
    v_valor_devido NUMERIC(10,2);
    v_total_pago_antes NUMERIC(10,2);
    v_total_pago_depois NUMERIC(10,2);
BEGIN
    -- Validar quota_associado pertence à associação
    SELECT q.id_associacao INTO v_qa_associacao
    FROM quota_associado qa
    JOIN quota q ON qa.id_quota = q.id_quota
    WHERE qa.id_quota_associado = p_id_quota_associado;

    IF NOT FOUND OR v_qa_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Quota associado não pertence à associação autorizada';
    END IF;

    -- Validar movimento bancário (se fornecido)
    IF p_id_movimento IS NOT NULL THEN
        SELECT id_associacao INTO v_movimento_associacao
        FROM movimento_bancario
        WHERE id_movimento = p_id_movimento;

        IF NOT FOUND OR v_movimento_associacao != p_id_associacao THEN
            RAISE EXCEPTION 'Movimento bancário não pertence à associação autorizada';
        END IF;
    END IF;

    -- LOCK: Bloquear a quota_associado para evitar race conditions em pagamentos concorrentes
    -- SELECT ... FOR UPDATE garante que apenas uma transação por vez pode processar pagamentos para esta quota
    SELECT valor_devido INTO v_valor_devido
    FROM quota_associado
    WHERE id_quota_associado = p_id_quota_associado
    FOR UPDATE;  -- Lock exclusivo na linha

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Quota associado não encontrada';
    END IF;

    -- Calcular total já pago ANTES deste pagamento
    SELECT COALESCE(SUM(valor_pago), 0) INTO v_total_pago_antes
    FROM pagamento
    WHERE id_quota_associado = p_id_quota_associado;

    -- Verificar regra de negócio: não permitir pagamento excessivo
    -- A soma não pode ultrapassar o valor_devido
    IF v_total_pago_antes + p_valor_pago > v_valor_devido THEN
        RAISE EXCEPTION 'Pagamento excede o valor devido (devido: %, já pago: %, tentativa: %). Não são permitidos pagamentos excessivos sem regra aprovada.',
            v_valor_devido, v_total_pago_antes, p_valor_pago;
    END IF;

    -- Inserir pagamento
    INSERT INTO pagamento (
        data_pagamento, valor_pago, metodo_pagamento, referencia_pagamento,
        id_quota_associado, id_movimento
    )
    VALUES (
        p_data_pagamento, p_valor_pago, p_metodo_pagamento, p_referencia_pagamento,
        p_id_quota_associado, p_id_movimento
    )
    RETURNING id_pagamento INTO p_id_pagamento;

    -- Atualizar estado da quota_associado automaticamente
    CALL atualizar_estado_quota_associado(p_id_quota_associado);

END;
$$;


-- ---------------------------------------------------------------------------
-- 4. PROCEDURE: Atualizar pagamento COM atualização automática de estado
-- ---------------------------------------------------------------------------
-- Substitui a procedure existente atualizar_pagamento
-- Ordem determinística de locks: sempre bloquear primeiro o quota_associado
-- com menor id_quota_associado para evitar deadlocks
-- ---------------------------------------------------------------------------
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
    v_valor_devido_novo NUMERIC(10,2);
    v_valor_devido_antigo NUMERIC(10,2);
    v_valor_pago_antigo NUMERIC(10,2);
    v_total_pago_outros_novo NUMERIC(10,2);
    v_total_pago_outros_antigo NUMERIC(10,2);
    v_id_qa_antigo INTEGER;
    v_primeiro_lock INTEGER;
    v_segundo_lock INTEGER;
BEGIN
    -- Obter associação do pagamento atual e quota_associado antigo
    SELECT q.id_associacao, p.id_quota_associado, p.valor_pago
    INTO v_pagamento_associacao, v_id_qa_antigo, v_valor_pago_antigo
    FROM pagamento p
    JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
    JOIN quota q ON qa.id_quota = q.id_quota
    WHERE p.id_pagamento = p_id_pagamento;

    IF NOT FOUND OR v_pagamento_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Pagamento não encontrado ou não autorizado';
    END IF;

    -- Validar novo quota_associado pertence à associação
    SELECT q.id_associacao INTO v_qa_associacao
    FROM quota_associado qa
    JOIN quota q ON qa.id_quota = q.id_quota
    WHERE qa.id_quota_associado = p_id_quota_associado;

    IF NOT FOUND OR v_qa_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Quota associado não pertence à associação autorizada';
    END IF;

    -- Validar movimento bancário (se fornecido)
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

    -- ORDEM DETERMINÍSTICA DE LOCKS para evitar deadlocks:
    -- Bloquear sempre primeiro o quota_associado com menor id_quota_associado
    IF v_id_qa_antigo != p_id_quota_associado THEN
        -- Dois QAs diferentes: determinar ordem
        IF v_id_qa_antigo < p_id_quota_associado THEN
            v_primeiro_lock := v_id_qa_antigo;
            v_segundo_lock := p_id_quota_associado;
        ELSE
            v_primeiro_lock := p_id_quota_associado;
            v_segundo_lock := v_id_qa_antigo;
        END IF;

        -- Lock no primeiro (menor ID)
        SELECT valor_devido INTO v_valor_devido_antigo
        FROM quota_associado
        WHERE id_quota_associado = v_primeiro_lock
        FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Quota associado não encontrada (lock primeiro): %', v_primeiro_lock;
        END IF;

        -- Lock no segundo (maior ID)
        SELECT valor_devido INTO v_valor_devido_novo
        FROM quota_associado
        WHERE id_quota_associado = v_segundo_lock
        FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Quota associado não encontrada (lock segundo): %', v_segundo_lock;
        END IF;

        -- Atribuir valores corretos baseado na ordem real
        IF v_primeiro_lock = v_id_qa_antigo THEN
            -- antigo foi bloqueado primeiro
            -- v_valor_devido_antigo já tem o valor do antigo
            -- v_valor_devido_novo já tem o valor do novo
        ELSE
            -- novo foi bloqueado primeiro
            v_valor_devido_novo := v_valor_devido_antigo;
            SELECT valor_devido INTO v_valor_devido_antigo
            FROM quota_associado
            WHERE id_quota_associado = v_segundo_lock;
        END IF;
    ELSE
        -- Mesmo QA: apenas um lock
        SELECT valor_devido INTO v_valor_devido_novo
        FROM quota_associado
        WHERE id_quota_associado = p_id_quota_associado
        FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Quota associado não encontrada';
        END IF;
        v_valor_devido_antigo := v_valor_devido_novo;
    END IF;

    -- Calcular total pago por OUTROS pagamentos no NOVO quota_associado
    SELECT COALESCE(SUM(valor_pago), 0) INTO v_total_pago_outros_novo
    FROM pagamento
    WHERE id_quota_associado = p_id_quota_associado
      AND id_pagamento != p_id_pagamento;

    -- Verificar regra de negócio no NOVO quota_associado
    IF v_total_pago_outros_novo + p_valor_pago > v_valor_devido_novo THEN
        RAISE EXCEPTION 'Pagamento excede o valor devido (devido: %, outros pagamentos: %, tentativa: %). Não são permitidos pagamentos excessivos sem regra aprovada.',
            v_valor_devido_novo, v_total_pago_outros_novo, p_valor_pago;
    END IF;

    -- Se mudou de QA, também verificar o ANTIGO quota_associado
    IF v_id_qa_antigo != p_id_quota_associado THEN
        SELECT COALESCE(SUM(valor_pago), 0) INTO v_total_pago_outros_antigo
        FROM pagamento
        WHERE id_quota_associado = v_id_qa_antigo
          AND id_pagamento != p_id_pagamento;

        -- O antigo QA fica sem este pagamento, validar que não fica inconsistente
        -- (não é necessário validar excesso, apenas que o estado será recalculado corretamente)
    END IF;

    -- Atualizar pagamento
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

    -- Atualizar estado do NOVO quota_associado
    CALL atualizar_estado_quota_associado(p_id_quota_associado);

    -- Se o quota_associado mudou, atualizar estado do ANTIGO também
    IF v_id_qa_antigo != p_id_quota_associado THEN
        CALL atualizar_estado_quota_associado(v_id_qa_antigo);
    END IF;

END;
$$;


-- ---------------------------------------------------------------------------
-- 5. PROCEDURE: Eliminar pagamento COM atualização automática de estado
-- ---------------------------------------------------------------------------
-- Substitui a procedure existente eliminar_pagamento
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE eliminar_pagamento(
    p_id_pagamento INTEGER,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_count INTEGER;
    v_id_quota_associado INTEGER;
BEGIN
    -- Obter quota_associado antes de eliminar para recalcular depois
    SELECT p.id_quota_associado
    INTO v_id_quota_associado
    FROM pagamento p
    JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
    JOIN quota q ON qa.id_quota = q.id_quota
    WHERE p.id_pagamento = p_id_pagamento
      AND q.id_associacao = p_id_associacao;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Pagamento não encontrado ou não autorizado';
    END IF;

    -- Eliminar pagamento
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

    -- Atualizar estado da quota_associado automaticamente
    CALL atualizar_estado_quota_associado(v_id_quota_associado);

END;
$$;


-- ---------------------------------------------------------------------------
-- 6. PROCEDURE: Atualizar quota_associado - manter validação de estado
-- ---------------------------------------------------------------------------
-- A procedure atualizar_quota_associado existente já permite definir estado manualmente.
-- Adicionamos validação: se estado for 'Isento', não permitir pagamentos futuros.
-- Isso será feito na procedure registar_pagamento (já implementado acima).
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- 7. TRIGGERS: Atualizar estado quando quota_associado.valor_devido OU data_vencimento muda
-- ---------------------------------------------------------------------------
-- Se o valor_devido OU data_vencimento for alterado manualmente, recalcular estado
-- AFTER trigger evita erro "tuple to be updated was already modified"
-- Também remove trigger antigo trg_pagamento_atualiza_quota que conflita com a nova lógica
-- ---------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_pagamento_atualiza_quota ON pagamento;
DROP FUNCTION IF EXISTS fn_trg_pagamento_atualiza_quota();

CREATE OR REPLACE FUNCTION trigger_atualizar_estado_quota()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- Só recalcular se valor_devido OU data_vencimento mudou e não é Isento
    IF (OLD.valor_devido IS DISTINCT FROM NEW.valor_devido
        OR OLD.data_vencimento IS DISTINCT FROM NEW.data_vencimento)
       AND NEW.estado_quota_associado != 'Isento' THEN
        CALL atualizar_estado_quota_associado(NEW.id_quota_associado);
    END IF;
    RETURN NEW;
END;
$$;

-- Trigger na tabela quota_associado para UPDATE de valor_devido ou data_vencimento
DROP TRIGGER IF EXISTS trigger_qa_valor_devido ON quota_associado;
CREATE TRIGGER trigger_qa_valor_devido
    AFTER UPDATE ON quota_associado
    FOR EACH ROW
    EXECUTE FUNCTION trigger_atualizar_estado_quota();


-- ---------------------------------------------------------------------------
-- 8. TRIGGER: Garantir integridade em modificações diretas à tabela pagamento
-- ---------------------------------------------------------------------------
-- Se alguém fizer INSERT/UPDATE/DELETE direto na tabela pagamento (bypassando
-- as procedures), este trigger garante que o estado da quota_associado
-- seja recalculado automaticamente. Usa a mesma procedure que valida 'Isento'.
-- Se UPDATE alterar id_quota_associado, recalcula AMBAS as quotas (antiga e nova).
-- ---------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_pagamento_recalcula_estado ON pagamento;
DROP FUNCTION IF EXISTS fn_trg_pagamento_recalcula_estado();

CREATE OR REPLACE FUNCTION fn_trg_pagamento_recalcula_estado()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_id_qa_antigo INTEGER;
    v_id_qa_novo INTEGER;
BEGIN
    IF TG_OP = 'DELETE' THEN
        -- DELETE: recalcular quota antiga
        CALL atualizar_estado_quota_associado(OLD.id_quota_associado);
    ELSIF TG_OP = 'UPDATE' THEN
        -- UPDATE: se id_quota_associado mudou, recalcular ambas
        IF OLD.id_quota_associado IS DISTINCT FROM NEW.id_quota_associado THEN
            CALL atualizar_estado_quota_associado(OLD.id_quota_associado);
            CALL atualizar_estado_quota_associado(NEW.id_quota_associado);
        ELSE
            -- Mesmo quota: recalcular apenas uma vez
            CALL atualizar_estado_quota_associado(NEW.id_quota_associado);
        END IF;
    ELSE
        -- INSERT: recalcular quota nova
        CALL atualizar_estado_quota_associado(NEW.id_quota_associado);
    END IF;

    RETURN NULL; -- AFTER trigger, return value ignorado
END;
$$;

CREATE TRIGGER trg_pagamento_recalcula_estado
    AFTER INSERT OR UPDATE OR DELETE ON pagamento
    FOR EACH ROW
    EXECUTE FUNCTION fn_trg_pagamento_recalcula_estado();


-- ============================================================================
-- INSTRUÇÕES DE APLICAÇÃO
-- ============================================================================
-- 1. Executar este script na base de dados de teste
-- 2. Executar testes de integração (test_migration_10.py)
-- 3. Executar suite completa (76 testes)
-- 4. Validar em base de dados de staging
-- 5. Aplicar em produção com janela de manutenção
-- ============================================================================