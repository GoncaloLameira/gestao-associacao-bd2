-- =====================================================
-- SQL Functions
-- Sistema de Gestão de Associações
-- Bases de Dados II - Ficha 3
-- =====================================================

-- ==========================================
-- FN_EVENTOS_POR_ESTADO
-- Retorna a contagem de eventos por estado para uma associação
-- ==========================================
CREATE OR REPLACE FUNCTION fn_eventos_por_estado(p_id_associacao INTEGER)
RETURNS TABLE (
    estado_evento VARCHAR(100),
    total_eventos BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.estado_evento,
        COUNT(*) AS total_eventos
    FROM evento e
    WHERE e.id_associacao = p_id_associacao
    GROUP BY e.estado_evento
    ORDER BY total_eventos DESC;
END;
$$;


-- ==========================================
-- FN_TOTAL_EM_DIVIDA
-- Retorna o total em dívida (quotas pendentes/em dívida/parcial) para uma associação
-- ==========================================
CREATE OR REPLACE FUNCTION fn_total_em_divida(p_id_associacao INTEGER)
RETURNS NUMERIC(10,2)
LANGUAGE plpgsql
AS $$
DECLARE
    v_total NUMERIC(10,2) := 0;
BEGIN
    SELECT COALESCE(SUM(qa.valor_devido), 0) INTO v_total
    FROM quota_associado qa
    INNER JOIN quota q ON qa.id_quota = q.id_quota
    WHERE q.id_associacao = p_id_associacao
    AND qa.estado_quota_associado IN ('Pendente', 'Em Dívida', 'Parcial');

    RETURN v_total;
END;
$$;


-- ==========================================
-- FN_ASSOCIADO_ATIVO
-- Verifica se um associado está ativo (estado = 'Ativo' e data_saida IS NULL ou > hoje)
-- ==========================================
CREATE OR REPLACE FUNCTION fn_associado_ativo(p_id_associado INTEGER)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_estado VARCHAR(100);
    v_data_saida DATE;
BEGIN
    SELECT estado, data_saida INTO v_estado, v_data_saida
    FROM associado
    WHERE id_associado = p_id_associado;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    IF v_estado != 'Ativo' THEN
        RETURN FALSE;
    END IF;

    IF v_data_saida IS NOT NULL AND v_data_saida <= CURRENT_DATE THEN
        RETURN FALSE;
    END IF;

    RETURN TRUE;
END;
$$;


-- ==========================================
-- FN_MANDATO_ATUAL
-- Retorna o mandato atual (em vigor) para uma associação
-- ==========================================
CREATE OR REPLACE FUNCTION fn_mandato_atual(p_id_associacao INTEGER)
RETURNS TABLE (
    id_mandato INTEGER,
    data_inicio DATE,
    data_fim DATE
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id_mandato,
        m.data_inicio,
        m.data_fim
    FROM mandato m
    WHERE m.id_associacao = p_id_associacao
    AND m.data_inicio <= CURRENT_DATE
    AND (m.data_fim IS NULL OR m.data_fim >= CURRENT_DATE)
    ORDER BY m.data_inicio DESC
    LIMIT 1;
END;
$$;


-- ==========================================
-- FN_TOTAL_PAGO
-- Retorna o total pago (soma de pagamentos) para uma associação
-- ==========================================
CREATE OR REPLACE FUNCTION fn_total_pago(p_id_associacao INTEGER)
RETURNS NUMERIC(10,2)
LANGUAGE plpgsql
AS $$
DECLARE
    v_total NUMERIC(10,2) := 0;
BEGIN
    SELECT COALESCE(SUM(p.valor_pago), 0) INTO v_total
    FROM pagamento p
    INNER JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
    INNER JOIN quota q ON qa.id_quota = q.id_quota
    WHERE q.id_associacao = p_id_associacao;

    RETURN v_total;
END;
$$;


-- ==========================================
-- FN_DOCUMENTOS_POR_TIPO
-- Retorna a contagem de documentos por tipo para uma associação
-- ==========================================
CREATE OR REPLACE FUNCTION fn_documentos_por_tipo(p_id_associacao INTEGER)
RETURNS TABLE (
    nome_tipo_documento VARCHAR(150),
    total_documentos BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        td.nome_tipo_documento,
        COUNT(*) AS total_documentos
    FROM documento d
    INNER JOIN tipo_documento td ON d.id_tipo_documento = td.id_tipo_documento
    WHERE d.id_associacao = p_id_associacao
    GROUP BY td.nome_tipo_documento
    ORDER BY total_documentos DESC;
END;
$$;