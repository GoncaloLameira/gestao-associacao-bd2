-- ============================================================================
-- MIGRAÇÃO 11 — RECÁLCULO DE ESTADOS EXISTENTES DE QUOTA_ASSOCIADO
-- ============================================================================
-- Esta migração recalcula automaticamente o estado de todas as quota_associado
-- existentes baseado nos pagamentos registados, garantindo consistência financeira.
-- É IDEMPOTENTE e pode ser executada múltiplas vezes sem efeitos colaterais.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. FUNÇÃO DE APOIO: Identificar inconsistências ANTES da correção
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION identificar_inconsistencias_quotas(p_id_associacao INTEGER DEFAULT NULL)
RETURNS TABLE (
    id_quota_associado INTEGER,
    periodo_referencia VARCHAR(20),
    estado_atual VARCHAR(100),
    estado_calculado VARCHAR(100),
    valor_devido NUMERIC(10,2),
    total_pago NUMERIC(10,2),
    data_vencimento DATE,
    associado_nome VARCHAR(150),
    quota_designacao VARCHAR(150)
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_id_associacao_filtro INTEGER := p_id_associacao;
BEGIN
    RETURN QUERY
    SELECT
        qa.id_quota_associado,
        qa.periodo_referencia,
        qa.estado_quota_associado AS estado_atual,
        calcular_estado_quota_associado(qa.id_quota_associado) AS estado_calculado,
        qa.valor_devido,
        COALESCE(SUM(p.valor_pago), 0) AS total_pago,
        qa.data_vencimento,
        a.nome AS associado_nome,
        q.designacao_quota AS quota_designacao
    FROM quota_associado qa
    JOIN quota q ON qa.id_quota = q.id_quota
    JOIN associado a ON qa.id_associado = a.id_associado
    LEFT JOIN pagamento p ON p.id_quota_associado = qa.id_quota_associado
    WHERE (v_id_associacao_filtro IS NULL OR q.id_associacao = v_id_associacao_filtro)
    GROUP BY qa.id_quota_associado, qa.periodo_referencia, qa.estado_quota_associado,
             qa.valor_devido, qa.data_vencimento, a.nome, q.designacao_quota
    HAVING qa.estado_quota_associado != calcular_estado_quota_associado(qa.id_quota_associado);
END;
$$;

-- ---------------------------------------------------------------------------
-- 2. PROCEDURE PRINCIPAL: Recalcular todos os estados (idempotente)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE recalcular_estados_quotas_associado(p_id_associacao INTEGER DEFAULT NULL)
LANGUAGE plpgsql
AS $$
DECLARE
    v_processados INTEGER := 0;
    v_alterados INTEGER := 0;
    v_inconsistencias RECORD;
BEGIN
    -- Log inicial
    RAISE NOTICE '=== INÍCIO RECÁLCULO ESTADOS QUOTA_ASSOCIADO ===';
    RAISE NOTICE 'Associação filtro: %', COALESCE(p_id_associacao::TEXT, 'TODAS');

    -- Iterar sobre todas as quota_associado (filtradas por associação se fornecida)
    -- Pular quotas com estado 'Isento' (imutável)
    FOR v_inconsistencias IN
        SELECT qa.id_quota_associado, qa.estado_quota_associado,
               calcular_estado_quota_associado(qa.id_quota_associado) AS novo_estado
        FROM quota_associado qa
        JOIN quota q ON qa.id_quota = q.id_quota
        WHERE (p_id_associacao IS NULL OR q.id_associacao = p_id_associacao)
          AND qa.estado_quota_associado != 'Isento'
    LOOP
        v_processados := v_processados + 1;

        IF v_inconsistencias.estado_quota_associado != v_inconsistencias.novo_estado THEN
            -- Atualizar estado
            UPDATE quota_associado
            SET estado_quota_associado = v_inconsistencias.novo_estado
            WHERE id_quota_associado = v_inconsistencias.id_quota_associado;

            v_alterados := v_alterados + 1;
            RAISE NOTICE '  Alterado: QA % | % -> %',
                v_inconsistencias.id_quota_associado,
                v_inconsistencias.estado_quota_associado,
                v_inconsistencias.novo_estado;
        END IF;
    END LOOP;

    RAISE NOTICE '=== FIM RECÁLCULO ===';
    RAISE NOTICE 'Processados: %, Alterados: %', v_processados, v_alterados;
END;
$$;

-- ---------------------------------------------------------------------------
-- 3. EXECUÇÃO DA MIGRAÇÃO (Transação atómica)
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    v_inconsistencias_antes RECORD;
    v_total_inconsistencias INTEGER := 0;
    v_total_quotas INTEGER := 0;
BEGIN
    -- Verificar se já foi executada (idempotência)
    -- Se não houver inconsistências, a migração já foi aplicada
    SELECT COUNT(*) INTO v_total_inconsistencias
    FROM quota_associado qa
    JOIN quota q ON qa.id_quota = q.id_quota
    WHERE qa.estado_quota_associado != calcular_estado_quota_associado(qa.id_quota_associado);

    IF v_total_inconsistencias = 0 THEN
        RAISE NOTICE 'Migração 11: Nenhuma inconsistência encontrada. Migração já aplicada ou dados já consistentes.';
        RAISE NOTICE '=== MIGRAÇÃO 11 CONCLUÍDA (SEM ALTERAÇÕES) ===';
        RETURN;
    END IF;

    -- Contar total de quotas para relatório
    SELECT COUNT(*) INTO v_total_quotas
    FROM quota_associado qa
    JOIN quota q ON qa.id_quota = q.id_quota;

    RAISE NOTICE '=== MIGRAÇÃO 11 — RECÁLCULO ESTADOS QUOTA_ASSOCIADO ===';
    RAISE NOTICE 'Total quotas_associado: %', v_total_quotas;
    RAISE NOTICE 'Inconsistências detectadas: %', v_total_inconsistencias;
    RAISE NOTICE '';

    -- Mostrar inconsistências ANTES da correção
    RAISE NOTICE 'Inconsistências ANTES da correção:';
    FOR v_inconsistencias_antes IN
        SELECT * FROM identificar_inconsistencias_quotas()
    LOOP
        RAISE NOTICE '  QA % | % | % | Atual: % -> Calculado: % | Devido: % | Pago: % | Venc: %',
            v_inconsistencias_antes.id_quota_associado,
            v_inconsistencias_antes.periodo_referencia,
            v_inconsistencias_antes.associado_nome,
            v_inconsistencias_antes.estado_atual,
            v_inconsistencias_antes.estado_calculado,
            v_inconsistencias_antes.valor_devido,
            v_inconsistencias_antes.total_pago,
            v_inconsistencias_antes.data_vencimento;
    END LOOP;

    RAISE NOTICE '';

    -- Executar recálculo
    CALL recalcular_estados_quotas_associado();

    -- Verificar resultado
    SELECT COUNT(*) INTO v_total_inconsistencias
    FROM quota_associado qa
    JOIN quota q ON qa.id_quota = q.id_quota
    WHERE qa.estado_quota_associado != calcular_estado_quota_associado(qa.id_quota_associado);

    IF v_total_inconsistencias = 0 THEN
        RAISE NOTICE '=== SUCESSO: Todas as inconsistências corrigidas ===';
    ELSE
        RAISE WARNING '=== ATENÇÃO: Ainda existem % inconsistências após recálculo ===', v_total_inconsistencias;
    END IF;

    RAISE NOTICE '=== MIGRAÇÃO 11 CONCLUÍDA ===';
END;
$$;

-- ---------------------------------------------------------------------------
-- 4. VERIFICAÇÃO PÓS-MIGRAÇÃO (para validação manual)
-- ---------------------------------------------------------------------------
-- Para verificar resultados após execução:
-- SELECT * FROM identificar_inconsistencias_quotas();
-- Deve retornar 0 linhas se migração bem-sucedida.

-- ============================================================================
-- INSTRUÇÕES DE APLICAÇÃO
-- ============================================================================
-- 1. Executar esta migração APÓS a migração 10 (fase21_financeiro.sql)
--    Ordem: 01_tabelas -> 02_procedures -> 03_views -> 04_alter -> 05_functions ->
--           06_triggers -> 09_migration_movimento -> 10_fase21_financeiro -> 11_migration_recalcular
-- 2. A migração é idempotente - pode ser executada múltiplas vezes
-- 3. Executa numa transação implícita (DO $$ bloc) - rollback automático em erro
-- 4. Não elimina pagamentos nem altera valores financeiros
-- 5. Apenas corrige o campo estado_quota_associado baseado na realidade dos pagamentos
-- 6. Preserva estado 'Isento' (não é alterado pela função calcular_estado_quota_associado)
-- ============================================================================