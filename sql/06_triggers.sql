-- =====================================================
-- Triggers
-- Sistema de Gestão de Associações
-- Bases de Dados II - Ficha 3
-- =====================================================

-- ==========================================
-- TRG_EVENTO_ESTADO
-- Atualiza automaticamente o estado do evento baseado nas datas
-- ==========================================

-- Função do trigger para evento
CREATE OR REPLACE FUNCTION fn_trg_evento_estado()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.data_inicio_evento > CURRENT_TIMESTAMP THEN
        NEW.estado_evento := 'Planeado';
    ELSIF NEW.data_fim_evento IS NOT NULL AND NEW.data_fim_evento < CURRENT_TIMESTAMP THEN
        NEW.estado_evento := 'Concluído';
    ELSE
        NEW.estado_evento := 'Em curso';
    END IF;
    RETURN NEW;
END;
$$;

-- Trigger para INSERT
CREATE TRIGGER trg_evento_estado_insert
BEFORE INSERT ON evento
FOR EACH ROW
EXECUTE FUNCTION fn_trg_evento_estado();

-- Trigger para UPDATE
CREATE TRIGGER trg_evento_estado_update
BEFORE UPDATE ON evento
FOR EACH ROW
EXECUTE FUNCTION fn_trg_evento_estado();


-- ==========================================
-- TRG_ASSOCIADO_DATA_SAIDA
-- Valida que data_saida não é anterior a data_adesao
-- ==========================================

CREATE OR REPLACE FUNCTION fn_trg_associado_data_saida()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.data_saida IS NOT NULL AND NEW.data_adesao IS NOT NULL
       AND NEW.data_saida < NEW.data_adesao THEN
        RAISE EXCEPTION 'A data de saída não pode ser anterior à data de adesão.';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_associado_data_saida
BEFORE INSERT OR UPDATE ON associado
FOR EACH ROW
EXECUTE FUNCTION fn_trg_associado_data_saida();


-- ==========================================
-- TRG_EXERCICIO_CARGO_VALIDACAO
-- Valida que o exercício de cargo está dentro do período do mandato
-- ==========================================

CREATE OR REPLACE FUNCTION fn_trg_exercicio_cargo_validacao()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_mandato_inicio DATE;
    v_mandato_fim DATE;
BEGIN
    -- Obter datas do mandato
    SELECT data_inicio, data_fim INTO v_mandato_inicio, v_mandato_fim
    FROM mandato
    WHERE id_mandato = NEW.id_mandato;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Mandato não encontrado: %', NEW.id_mandato;
    END IF;

    -- Validar data de início do exercício
    IF NEW.data_inicio < v_mandato_inicio THEN
        RAISE EXCEPTION 'A data de início do exercício (% não pode ser anterior ao início do mandato (%))',
            NEW.data_inicio, v_mandato_inicio;
    END IF;

    -- Validar data de fim do exercício (se existir)
    IF NEW.data_fim IS NOT NULL AND v_mandato_fim IS NOT NULL AND NEW.data_fim > v_mandato_fim THEN
        RAISE EXCEPTION 'A data de fim do exercício (% não pode ser posterior ao fim do mandato (%))',
            NEW.data_fim, v_mandato_fim;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_exercicio_cargo_validacao
BEFORE INSERT OR UPDATE ON exercicio_cargo
FOR EACH ROW
EXECUTE FUNCTION fn_trg_exercicio_cargo_validacao();


-- ==========================================
-- TRG_PAGAMENTO_ATUALIZA_QUOTA
-- Atualiza o estado da quota_associado após pagamento
-- ==========================================

CREATE OR REPLACE FUNCTION fn_trg_pagamento_atualiza_quota()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_valor_devido NUMERIC(10,2);
    v_total_pago NUMERIC(10,2);
BEGIN
    -- Obter valor devido da quota
    SELECT valor_devido INTO v_valor_devido
    FROM quota_associado
    WHERE id_quota_associado = NEW.id_quota_associado;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Quota associado não encontrada: %', NEW.id_quota_associado;
    END IF;

    -- Calcular total pago para esta quota (incluindo o novo pagamento)
    SELECT COALESCE(SUM(valor_pago), 0) + NEW.valor_pago INTO v_total_pago
    FROM pagamento
    WHERE id_quota_associado = NEW.id_quota_associado;

    -- Atualizar estado da quota
    IF v_total_pago >= v_valor_devido THEN
        UPDATE quota_associado
        SET estado_quota_associado = 'Pago'
        WHERE id_quota_associado = NEW.id_quota_associado;
    ELSIF v_total_pago > 0 THEN
        UPDATE quota_associado
        SET estado_quota_associado = 'Parcial'
        WHERE id_quota_associado = NEW.id_quota_associado;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_pagamento_atualiza_quota
AFTER INSERT ON pagamento
FOR EACH ROW
EXECUTE FUNCTION fn_trg_pagamento_atualiza_quota();


-- ==========================================
-- TRG_DOCUMENTO_VALIDACAO
-- Valida que o documento tem ficheiro e tipo válido
-- ==========================================

CREATE OR REPLACE FUNCTION fn_trg_documento_validacao()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- Validar que ficheiro não está vazio
    IF NEW.ficheiro IS NULL OR NEW.ficheiro = '' THEN
        RAISE EXCEPTION 'O campo ficheiro é obrigatório.';
    END IF;

    -- Validar que o tipo de documento pertence à mesma associação
    IF EXISTS (
        SELECT 1 FROM tipo_documento
        WHERE id_tipo_documento = NEW.id_tipo_documento
        AND id_associacao != NEW.id_associacao
    ) THEN
        RAISE EXCEPTION 'O tipo de documento não pertence à mesma associação.';
    END IF;

    -- Validar que o mandato (se fornecido) pertence à mesma associação
    IF NEW.id_mandato IS NOT NULL THEN
        IF EXISTS (
            SELECT 1 FROM mandato
            WHERE id_mandato = NEW.id_mandato
            AND id_associacao != NEW.id_associacao
        ) THEN
            RAISE EXCEPTION 'O mandato não pertence à mesma associação.';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_documento_validacao
BEFORE INSERT OR UPDATE ON documento
FOR EACH ROW
EXECUTE FUNCTION fn_trg_documento_validacao();