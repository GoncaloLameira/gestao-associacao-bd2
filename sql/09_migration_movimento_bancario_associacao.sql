-- ============================================================================
-- MIGRAÇÃO: Adicionar id_associacao a movimento_bancario (v2 - atómica e segura)
-- ============================================================================
-- Esta migração adiciona a coluna id_associacao à tabela movimento_bancario
-- e preenche-a para movimentos conciliados.
-- Se existirem movimentos não conciliados cuja associação não possa ser
-- determinada, a migração falha com RAISE EXCEPTION e faz rollback total.
-- Permite reexecução segura após resolução dos dados pendentes.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. Adicionar coluna id_associacao (nullable inicialmente) - IDEMPOTENTE
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'movimento_bancario' AND column_name = 'id_associacao'
    ) THEN
        ALTER TABLE movimento_bancario ADD COLUMN id_associacao INTEGER;
        RAISE NOTICE 'Coluna id_associacao adicionada a movimento_bancario';
    ELSE
        RAISE NOTICE 'Coluna id_associacao já existe em movimento_bancario';
    END IF;
END $$;

-- ============================================================================
-- 1b. Adicionar colunas para deduplicação melhorada - IDEMPOTENTE
-- ============================================================================
DO $$
BEGIN
    -- id_externo_banco: identificador único do movimento no banco
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'movimento_bancario' AND column_name = 'id_externo_banco'
    ) THEN
        ALTER TABLE movimento_bancario ADD COLUMN id_externo_banco VARCHAR(100);
        RAISE NOTICE 'Coluna id_externo_banco adicionada a movimento_bancario';
    ELSE
        RAISE NOTICE 'Coluna id_externo_banco já existe em movimento_bancario';
    END IF;

    -- hash_importacao: hash da linha CSV para detetar reimportações
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'movimento_bancario' AND column_name = 'hash_importacao'
    ) THEN
        ALTER TABLE movimento_bancario ADD COLUMN hash_importacao VARCHAR(64);
        RAISE NOTICE 'Coluna hash_importacao adicionada a movimento_bancario';
    ELSE
        RAISE NOTICE 'Coluna hash_importacao já existe em movimento_bancario';
    END IF;

    -- suspeito_duplicado: flag para movimentos suspeitos de duplicação legítima
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'movimento_bancario' AND column_name = 'suspeito_duplicado'
    ) THEN
        ALTER TABLE movimento_bancario ADD COLUMN suspeito_duplicado BOOLEAN NOT NULL DEFAULT FALSE;
        RAISE NOTICE 'Coluna suspeito_duplicado adicionada a movimento_bancario';
    ELSE
        RAISE NOTICE 'Coluna suspeito_duplicado já existe em movimento_bancario';
    END IF;
END $$;

-- ============================================================================
-- 1c. Adicionar unique constraint para id_externo_banco - IDEMPOTENTE
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uk_movimento_bancario_id_externo_banco'
          AND conrelid = 'movimento_bancario'::regclass
    ) THEN
        ALTER TABLE movimento_bancario
        ADD CONSTRAINT uk_movimento_bancario_id_externo_banco
        UNIQUE (id_associacao, id_externo_banco);
        RAISE NOTICE 'Unique constraint uk_movimento_bancario_id_externo_banco criada';
    ELSE
        RAISE NOTICE 'Unique constraint uk_movimento_bancario_id_externo_banco já existe';
    END IF;
END $$;

-- ============================================================================
-- 2. Preencher id_associacao para movimentos conciliados - IDEMPOTENTE
-- ============================================================================
-- Através do pagamento -> quota_associado -> quota -> associacao
-- Apenas preenche onde id_associacao IS NULL
UPDATE movimento_bancario mb
SET id_associacao = q.id_associacao
FROM pagamento p
JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
JOIN quota q ON qa.id_quota = q.id_quota
WHERE mb.id_movimento = p.id_movimento
  AND mb.id_associacao IS NULL;

-- ============================================================================
-- 3. Identificar movimentos sem associação determinada
-- ============================================================================
-- Estes são movimentos que NÃO têm pagamento (não conciliados)
-- e portanto não foi possível determinar a associação via cadeia de FKs
DO $$
DECLARE
    v_sem_associacao INTEGER;
    v_total INTEGER;
    v_com_associacao INTEGER;
    v_sem_pagamento INTEGER;
    v_detalhes TEXT;
BEGIN
    SELECT COUNT(*) INTO v_total FROM movimento_bancario;
    SELECT COUNT(*) INTO v_com_associacao FROM movimento_bancario WHERE id_associacao IS NOT NULL;
    v_sem_associacao := v_total - v_com_associacao;

    -- Contar quantos não têm pagamento (não conciliados)
    SELECT COUNT(*) INTO v_sem_pagamento
    FROM movimento_bancario mb
    LEFT JOIN pagamento p ON mb.id_movimento = p.id_movimento
    WHERE mb.id_associacao IS NULL
      AND p.id_pagamento IS NULL;

    RAISE NOTICE '=== RELATÓRIO DE MIGRAÇÃO MOVIMENTO_BANCARIO ===';
    RAISE NOTICE 'Total de movimentos: %', v_total;
    RAISE NOTICE 'Movimentos com associação definida: %', v_com_associacao;
    RAISE NOTICE 'Movimentos SEM associação (não conciliados): %', v_sem_associacao;
    RAISE NOTICE '  Destes, sem pagamento associado: %', v_sem_pagamento;

    IF v_sem_associacao > 0 THEN
        -- Construir lista de IDs para mensagem de erro
        SELECT string_agg(mb.id_movimento::TEXT, ', ' ORDER BY mb.id_movimento)
        INTO v_detalhes
        FROM movimento_bancario mb
        LEFT JOIN pagamento p ON mb.id_movimento = p.id_movimento
        WHERE mb.id_associacao IS NULL;

        RAISE EXCEPTION 'FALHA NA MIGRAÇÃO: Existem % movimentos bancários sem associação definida (IDs: %). Estes movimentos não estão conciliados (sem pagamento) e a sua associação não pode ser determinada automaticamente. Atribua manualmente id_associacao a estes movimentos antes de reexecutar a migração. Rollback total será efetuado.',
            v_sem_associacao, v_detalhes;
    END IF;
END $$;

-- ============================================================================
-- 4. Aplicar restrição NOT NULL - IDEMPOTENTE
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'movimento_bancario'
          AND column_name = 'id_associacao'
          AND is_nullable = 'YES'
    ) THEN
        ALTER TABLE movimento_bancario ALTER COLUMN id_associacao SET NOT NULL;
        RAISE NOTICE 'Restrição NOT NULL aplicada a id_associacao';
    ELSE
        RAISE NOTICE 'Coluna id_associacao já é NOT NULL';
    END IF;
END $$;

-- ============================================================================
-- 5. Adicionar FOREIGN KEY - IDEMPOTENTE
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_movimento_bancario_associacao'
          AND conrelid = 'movimento_bancario'::regclass
    ) THEN
        ALTER TABLE movimento_bancario
        ADD CONSTRAINT fk_movimento_bancario_associacao
        FOREIGN KEY (id_associacao) REFERENCES associacao(id_associacao);
        RAISE NOTICE 'Foreign Key fk_movimento_bancario_associacao criada';
    ELSE
        RAISE NOTICE 'Foreign Key fk_movimento_bancario_associacao já existe';
    END IF;
END $$;

-- ============================================================================
-- 6. Validação final obrigatória
-- ============================================================================
DO $$
DECLARE
    v_is_not_null BOOLEAN;
    v_fk_exists BOOLEAN;
    v_count_null INTEGER;
BEGIN
    -- Verificar NOT NULL
    SELECT is_nullable = 'NO' INTO v_is_not_null
    FROM information_schema.columns
    WHERE table_name = 'movimento_bancario' AND column_name = 'id_associacao';

    -- Verificar FK existe
    SELECT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_movimento_bancario_associacao'
          AND conrelid = 'movimento_bancario'::regclass
    ) INTO v_fk_exists;

    -- Verificar que não há NULLs
    SELECT COUNT(*) INTO v_count_null
    FROM movimento_bancario WHERE id_associacao IS NULL;

    IF NOT v_is_not_null THEN
        RAISE EXCEPTION 'VALIDAÇÃO FALHOU: id_associacao não é NOT NULL';
    END IF;

    IF NOT v_fk_exists THEN
        RAISE EXCEPTION 'VALIDAÇÃO FALHOU: Foreign Key fk_movimento_bancario_associacao não existe';
    END IF;

    IF v_count_null > 0 THEN
        RAISE EXCEPTION 'VALIDAÇÃO FALHOU: Existem % movimentos com id_associacao NULL', v_count_null;
    END IF;

    RAISE NOTICE '=== MIGRAÇÃO CONCLUÍDA COM SUCESSO ===';
    RAISE NOTICE 'id_associacao: NOT NULL = %, FK válida = %, NULLs = %', v_is_not_null, v_fk_exists, v_count_null;
END $$;

COMMIT;

-- ============================================================================
-- INSTRUÇÕES PARA REEXECUÇÃO APÓS RESOLUÇÃO MANUAL
-- ============================================================================
-- Se a migração falhou com RAISE EXCEPTION:
-- 1. Atribua manualmente id_associacao aos movimentos listados no erro:
--    UPDATE movimento_bancario SET id_associacao = <id_assoc> WHERE id_movimento IN (...);
-- 2. Reexecute ESTE MESMO ficheiro SQL (é seguro reexecutar - todos os passos são idempotentes)
-- 3. A migração completará com sucesso na reexecução
-- ============================================================================