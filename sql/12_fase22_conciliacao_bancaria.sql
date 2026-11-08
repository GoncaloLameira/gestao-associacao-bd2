-- ============================================================================
-- FASE 2.2 — IMPORTAÇÃO E CONCILIAÇÃO BANCÁRIA
-- ============================================================================
-- Este script implementa:
-- 1. Importação de movimentos bancários via CSV
-- 2. Conciliação entre movimentos bancários e pagamentos
-- 3. Views de apoio para interface Django
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 0. LIMPEZA: Remover procedures antigas com assinaturas diferentes
-- ---------------------------------------------------------------------------
-- As procedures conciliar_movimento_pagamento e desfazer_conciliacao
-- podem ter sido criadas em ficheiros anteriores (ex: 10_fase21) com
-- assinaturas diferentes. CREATE OR REPLACE não permite mudar nomes/tipos
-- de parâmetros, então precisamos dropar primeiro.
-- ---------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS conciliar_movimento_pagamento(INTEGER, INTEGER, INTEGER, BOOLEAN);
DROP PROCEDURE IF EXISTS conciliar_movimento_pagamento(IN p_id_movimento INTEGER, IN p_id_pagamento INTEGER, IN p_id_associacao INTEGER, IN p_forcar BOOLEAN);
DROP PROCEDURE IF EXISTS desfazer_conciliacao(INTEGER, INTEGER, INTEGER);
DROP PROCEDURE IF EXISTS desfazer_conciliacao(IN p_id_movimento INTEGER, IN p_id_pagamento INTEGER, IN p_id_associacao INTEGER);
DROP FUNCTION IF EXISTS encontrar_correspondencias_conciliacao(INTEGER, INTEGER) CASCADE;
DROP FUNCTION IF EXISTS encontrar_correspondencias_conciliacao(p_id_movimento INTEGER, p_id_associacao INTEGER) CASCADE;

-- ---------------------------------------------------------------------------
-- 1. TABELA: Histórico de conciliações bancárias (auditoria)
-- ---------------------------------------------------------------------------
-- Preserva histórico completo de conciliações e reversões para auditoria.
-- Não remove registos ao desfazer - apenas marca como revertido.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conciliacao_bancaria (
    id_conciliacao SERIAL PRIMARY KEY,
    id_movimento INTEGER NOT NULL REFERENCES movimento_bancario(id_movimento) ON DELETE RESTRICT,
    id_pagamento INTEGER NOT NULL REFERENCES pagamento(id_pagamento) ON DELETE RESTRICT,
    id_associacao INTEGER NOT NULL REFERENCES associacao(id_associacao) ON DELETE RESTRICT,
    data_conciliacao TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_reversao TIMESTAMP,
    confianca_utilizada INTEGER NOT NULL CHECK (confianca_utilizada IN (100, 80, 60, 40)),
    forcado BOOLEAN NOT NULL DEFAULT FALSE,
    observacao TEXT,
    reversao_motivo TEXT,
    reversao_utilizador VARCHAR(100),
    -- Garantir que não há conciliações ativas duplicadas para o mesmo movimento/pagamento
    UNIQUE (id_movimento, id_pagamento, data_reversao)
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_conciliacao_bancaria_movimento ON conciliacao_bancaria(id_movimento);
CREATE INDEX IF NOT EXISTS idx_conciliacao_bancaria_pagamento ON conciliacao_bancaria(id_pagamento);
CREATE INDEX IF NOT EXISTS idx_conciliacao_bancaria_associacao ON conciliacao_bancaria(id_associacao);
CREATE INDEX IF NOT EXISTS idx_conciliacao_bancaria_ativa ON conciliacao_bancaria(id_movimento, id_pagamento) WHERE data_reversao IS NULL;

-- ---------------------------------------------------------------------------
-- 1. FUNÇÃO: Validar e parsear linha CSV de movimento bancário
-- ---------------------------------------------------------------------------
-- Formato CSV esperado (cabeçalho obrigatório):
-- data_movimento,valor_movimento,descricao_movimento,referencia_movimento[,id_externo_banco]
-- Exemplo: 2025-01-15,150.00,Transferência recebida,REF123456,TXN789012
-- Suporta: vírgula como separador decimal (pt-PT), datas ISO (YYYY-MM-DD)
-- Coluna opcional 5: id_externo_banco (identificador único do banco)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION parse_csv_movimento_bancario(
    p_linha TEXT,
    p_associacao_id INTEGER,
    p_delimitador TEXT DEFAULT ','
)
RETURNS TABLE (
    data_movimento DATE,
    descricao_movimento VARCHAR(255),
    valor_movimento NUMERIC(10,2),
    referencia_movimento VARCHAR(100),
    id_externo_banco VARCHAR(100),
    hash_linha VARCHAR(64),
    erro TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_campos TEXT[];
    v_valor_str TEXT;
    v_valor NUMERIC(10,2);
    v_data DATE;
    v_hash VARCHAR(64);
BEGIN
    -- Calcular hash da linha original para detetar reimportações do mesmo ficheiro
    v_hash := encode(digest(p_linha, 'sha256'), 'hex');

    -- Dividir linha pelo delimitador
    v_campos := string_to_array(p_linha, p_delimitador);

    -- Validar número de campos (mínimo 4, opcional 5º para id_externo_banco)
    IF array_length(v_campos, 1) < 4 THEN
        RETURN QUERY SELECT NULL::DATE, NULL::VARCHAR(255), NULL::NUMERIC(10,2), NULL::VARCHAR(100), NULL::VARCHAR(100), v_hash,
            'Linha com menos de 4 campos'::TEXT;
        RETURN;
    END IF;

    -- Parsear data (ISO YYYY-MM-DD)
    BEGIN
        v_data := v_campos[1]::DATE;
    EXCEPTION WHEN OTHERS THEN
        RETURN QUERY SELECT NULL::DATE, NULL::VARCHAR(255), NULL::NUMERIC(10,2), NULL::VARCHAR(100), NULL::VARCHAR(100), v_hash,
            'Data inválida: ' || v_campos[1]::TEXT;
        RETURN;
    END;

    -- Parsear valor (suporta vírgula decimal pt-PT) - campo 2
    v_valor_str := regexp_replace(trim(v_campos[2]), ',', '.', 'g');
    BEGIN
        v_valor := v_valor_str::NUMERIC(10,2);
    EXCEPTION WHEN OTHERS THEN
        RETURN QUERY SELECT NULL::DATE, NULL::VARCHAR(255), NULL::NUMERIC(10,2), NULL::VARCHAR(100), NULL::VARCHAR(100), v_hash,
            'Valor inválido: ' || v_campos[2]::TEXT;
        RETURN;
    END;

    -- Validar descrição - campo 3
    IF trim(v_campos[3]) = '' THEN
        RETURN QUERY SELECT NULL::DATE, NULL::VARCHAR(255), NULL::NUMERIC(10,2), NULL::VARCHAR(100), NULL::VARCHAR(100), v_hash,
            'Descrição vazia'::TEXT;
        RETURN;
    END IF;

    -- Referência (opcional) - campo 4
    -- id_externo_banco (opcional) - campo 5
    IF trim(v_campos[4]) = '' THEN
        IF array_length(v_campos, 1) >= 5 AND trim(v_campos[5]) != '' THEN
            RETURN QUERY SELECT v_data, trim(v_campos[3])::VARCHAR(255), v_valor, NULL::VARCHAR(100), trim(v_campos[5])::VARCHAR(100), v_hash, NULL::TEXT;
        ELSE
            RETURN QUERY SELECT v_data, trim(v_campos[3])::VARCHAR(255), v_valor, NULL::VARCHAR(100), NULL::VARCHAR(100), v_hash, NULL::TEXT;
        END IF;
    ELSE
        IF array_length(v_campos, 1) >= 5 AND trim(v_campos[5]) != '' THEN
            RETURN QUERY SELECT v_data, trim(v_campos[3])::VARCHAR(255), v_valor, trim(v_campos[4])::VARCHAR(100), trim(v_campos[5])::VARCHAR(100), v_hash, NULL::TEXT;
        ELSE
            RETURN QUERY SELECT v_data, trim(v_campos[3])::VARCHAR(255), v_valor, trim(v_campos[4])::VARCHAR(100), NULL::VARCHAR(100), v_hash, NULL::TEXT;
        END IF;
    END IF;
END;
$$;


-- ---------------------------------------------------------------------------
-- 2. PROCEDURE: Importar movimentos bancários de CSV (transacional)
-- ---------------------------------------------------------------------------
-- Processa arquivo CSV linha a linha, valida, deteta duplicados e insere.
-- Retorna relatório com: importados, duplicados, suspeitos, erros.
-- Lógica de deduplicação:
-- 1. Se id_externo_banco fornecido: usa unique constraint (id_associacao, id_externo_banco) - idempotente
-- 2. Se hash_importacao já existe: é reimportação do mesmo ficheiro - ignora
-- 3. Se mesmo (data, valor, referência, associação) mas sem id_externo_banco:
--    - Marca como suspeito_duplicado = true e insere (movimento legítimo idêntico possível)
-- 4. Caso contrário: insere normalmente
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE importar_movimentos_bancario_csv(
    p_conteudo_csv TEXT,
    p_id_associacao INTEGER,
    p_delimitador TEXT DEFAULT ',',
    p_tem_cabecalho BOOLEAN DEFAULT TRUE
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_linhas TEXT[];
    v_linha TEXT;
    v_idx INTEGER;
    v_resultado RECORD;
    v_importados INTEGER := 0;
    v_duplicados INTEGER := 0;
    v_suspeitos INTEGER := 0;
    v_erros INTEGER := 0;
    v_erros_detalhe TEXT[] := ARRAY[]::TEXT[];
    v_movimento_existente INTEGER;
    v_hash_existente BOOLEAN;
BEGIN
    -- Dividir conteúdo em linhas
    v_linhas := string_to_array(p_conteudo_csv, E'\n');

    -- Iterar linhas (pular cabeçalho se existir)
    v_idx := CASE WHEN p_tem_cabecalho THEN 2 ELSE 1 END;

    WHILE v_idx <= array_length(v_linhas, 1) LOOP
        v_linha := trim(v_linhas[v_idx]);

        -- Ignorar linhas vazias
        IF v_linha != '' THEN
            -- Parsear e validar linha
            FOR v_resultado IN SELECT * FROM parse_csv_movimento_bancario(v_linha, p_id_associacao, p_delimitador) LOOP
                IF v_resultado.erro IS NOT NULL THEN
                    v_erros := v_erros + 1;
                    v_erros_detalhe := v_erros_detalhe || format('Linha %s: %s', v_idx, v_resultado.erro);
                ELSE
                    -- 1. Verificar se já existe movimento com mesmo hash (reimportação do mesmo ficheiro)
                    SELECT TRUE INTO v_hash_existente
                    FROM movimento_bancario
                    WHERE id_associacao = p_id_associacao
                      AND hash_importacao = v_resultado.hash_linha;

                    IF v_hash_existente THEN
                        v_duplicados := v_duplicados + 1;
                    ELSE
                        -- 2. Se tem id_externo_banco, tentar inserir com ON CONFLICT (idempotência por ID bancário)
                        IF v_resultado.id_externo_banco IS NOT NULL THEN
                            BEGIN
                                INSERT INTO movimento_bancario (data_movimento, descricao_movimento, valor_movimento, referencia_movimento, id_associacao, id_externo_banco, hash_importacao)
                                VALUES (v_resultado.data_movimento, v_resultado.descricao_movimento, v_resultado.valor_movimento, v_resultado.referencia_movimento, p_id_associacao, v_resultado.id_externo_banco, v_resultado.hash_linha);
                                v_importados := v_importados + 1;
                            EXCEPTION WHEN unique_violation THEN
                                -- Conflito em (id_associacao, id_externo_banco) - já importado
                                v_duplicados := v_duplicados + 1;
                            END;
                        ELSE
                            -- 3. Sem id_externo_banco: verificar duplicado por (data, valor, referência, associação)
                            SELECT id_movimento INTO v_movimento_existente
                            FROM movimento_bancario
                            WHERE id_associacao = p_id_associacao
                              AND data_movimento = v_resultado.data_movimento
                              AND valor_movimento = v_resultado.valor_movimento
                              AND (referencia_movimento IS NOT DISTINCT FROM v_resultado.referencia_movimento);

                            IF v_movimento_existente IS NOT NULL THEN
                                -- Existe movimento com mesma data/valor/referência mas sem ID bancário
                                -- Inserir como suspeito_duplicado = true (pode ser movimento legítimo idêntico)
                                INSERT INTO movimento_bancario (data_movimento, descricao_movimento, valor_movimento, referencia_movimento, id_associacao, hash_importacao, suspeito_duplicado)
                                VALUES (v_resultado.data_movimento, v_resultado.descricao_movimento, v_resultado.valor_movimento, v_resultado.referencia_movimento, p_id_associacao, v_resultado.hash_linha, TRUE);
                                v_suspeitos := v_suspeitos + 1;
                            ELSE
                                -- 4. Novo movimento único
                                INSERT INTO movimento_bancario (data_movimento, descricao_movimento, valor_movimento, referencia_movimento, id_associacao, hash_importacao)
                                VALUES (v_resultado.data_movimento, v_resultado.descricao_movimento, v_resultado.valor_movimento, v_resultado.referencia_movimento, p_id_associacao, v_resultado.hash_linha);
                                v_importados := v_importados + 1;
                            END IF;
                        END IF;
                    END IF;
                END IF;
            END LOOP;
        END IF;

        v_idx := v_idx + 1;
    END LOOP;

    -- Retornar relatório
    RAISE NOTICE 'Importação CSV concluída: importados=%, duplicados=%, suspeitos=%, erros=%', v_importados, v_duplicados, v_suspeitos, v_erros;
    IF v_erros > 0 THEN
        RAISE NOTICE 'Detalhes dos erros: %', array_to_string(v_erros_detalhe, '; ');
    END IF;
END;
$$;


-- ---------------------------------------------------------------------------
-- 3. VIEW: Movimentos bancários não conciliados
-- ---------------------------------------------------------------------------
-- Lista movimentos sem pagamento associado, para a interface de conciliação.
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_movimentos_nao_conciliados;
CREATE OR REPLACE VIEW vw_movimentos_nao_conciliados AS
SELECT
    mb.id_movimento,
    mb.data_movimento,
    mb.descricao_movimento,
    mb.valor_movimento,
    mb.referencia_movimento,
    mb.id_associacao,
    a.nome AS nome_associacao,
    NULL::INTEGER AS id_associado,
    NULL::INTEGER AS numero_associado,
    NULL::VARCHAR(255) AS associado,
    FALSE AS conciliado
FROM movimento_bancario mb
INNER JOIN associacao a ON mb.id_associacao = a.id_associacao
LEFT JOIN pagamento p ON mb.id_movimento = p.id_movimento
WHERE p.id_movimento IS NULL
ORDER BY mb.data_movimento DESC, mb.id_movimento;


-- ---------------------------------------------------------------------------
-- 4. VIEW: Pagamentos sem movimento bancário associado
-- ---------------------------------------------------------------------------
-- Lista pagamentos que ainda não têm movimento bancário vinculado.
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_pagamentos_sem_movimento;
CREATE OR REPLACE VIEW vw_pagamentos_sem_movimento AS
SELECT
    p.id_pagamento,
    p.data_pagamento,
    p.valor_pago,
    p.metodo_pagamento,
    p.referencia_pagamento,
    p.id_quota_associado,
    qa.periodo_referencia,
    qa.valor_devido,
    a.id_associado,
    a.numero_associado,
    a.nome AS associado,
    a.id_associacao
FROM pagamento p
INNER JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
INNER JOIN associado a ON qa.id_associado = a.id_associado
WHERE p.id_movimento IS NULL
ORDER BY p.data_pagamento DESC, p.id_pagamento;


-- ---------------------------------------------------------------------------
-- 5. FUNÇÃO: Encontrar correspondências para conciliação
-- ---------------------------------------------------------------------------
-- Procura pagamentos que correspondam a um movimento bancário por:
-- 1. Referência exata + valor compatível + referência distintiva + única correspondência (confiança 100)
-- 2. Valor exato + data próxima (±3 dias) (confiança 80)
-- 3. Valor exato + mesmo associado (confiança 60)
-- 4. Apenas valor exato (confiança 40)
-- Retorna sugestões ordenadas por confiança.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION encontrar_correspondencias_conciliacao(
    p_id_movimento INTEGER,
    p_id_associacao INTEGER
)
RETURNS TABLE (
    id_pagamento INTEGER,
    data_pagamento TIMESTAMP,
    valor_pago NUMERIC(10,2),
    metodo_pagamento VARCHAR(100),
    referencia_pagamento VARCHAR(100),
    id_quota_associado INTEGER,
    periodo_referencia VARCHAR(20),
    valor_devido NUMERIC(10,2),
    numero_associado INTEGER,
    observacao TEXT,
    tipo_correspondencia VARCHAR(50),
    confianca INTEGER,  -- 100=exata, 80=valor+data, 60=valor+associado, 40=apenas valor
    associado VARCHAR(255),
    id_associado INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_movimento RECORD;
    v_dias_tolerancia INTEGER := 3;
    v_ref_distintiva BOOLEAN;
    v_contagem_ref INTEGER;
BEGIN
    -- Obter dados do movimento
    SELECT * INTO v_movimento
    FROM movimento_bancario
    WHERE id_movimento = p_id_movimento AND id_associacao = p_id_associacao;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Movimento bancário não encontrado ou não autorizado';
    END IF;

    -- Verificar se a referência do movimento é "distintiva" (não genérica)
    -- Referências genéricas comuns que não devem dar 100% confiança sozinhas
    v_ref_distintiva := v_movimento.referencia_movimento IS NOT NULL
        AND v_movimento.referencia_movimento !~* '^(transferencia|pagamento|deposito|levantamento|multibanco|mbway|cheque|numerario|outros?)$';

    -- Contar quantos pagamentos têm a mesma referência (para verificar unicidade)
    IF v_movimento.referencia_movimento IS NOT NULL THEN
        SELECT COUNT(*) INTO v_contagem_ref
        FROM pagamento p
        INNER JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
        INNER JOIN associado a ON qa.id_associado = a.id_associado
        WHERE p.id_movimento IS NULL
          AND a.id_associacao = p_id_associacao
          AND p.referencia_pagamento IS NOT NULL
          AND p.referencia_pagamento = v_movimento.referencia_movimento;
    ELSE
        v_contagem_ref := 0;
    END IF;

    -- 1. Correspondência por referência exata (confiança 100)
    -- Requisitos: mesma associação, referência válida e distintiva, valor compatível,
    -- movimento e pagamento não conciliados, APENAS UM pagamento elegível com essa referência
    IF v_ref_distintiva AND v_contagem_ref = 1 AND v_movimento.referencia_movimento IS NOT NULL THEN
        RETURN QUERY
        SELECT
            p.id_pagamento,
            p.data_pagamento,
            p.valor_pago,
            p.metodo_pagamento,
            p.referencia_pagamento,
            p.id_quota_associado,
            qa.periodo_referencia,
            qa.valor_devido,
            a.numero_associado,
            'Referência bancária idêntica e distintiva'::TEXT AS observacao,
            'referencia_exata'::VARCHAR(50) AS tipo_correspondencia,
            100 AS confianca,
            a.nome AS associado,
            a.id_associado
        FROM pagamento p
        INNER JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
        INNER JOIN associado a ON qa.id_associado = a.id_associado
        WHERE p.id_movimento IS NULL
          AND a.id_associacao = p_id_associacao
          AND p.referencia_pagamento IS NOT NULL
          AND p.referencia_pagamento = v_movimento.referencia_movimento
          AND p.valor_pago = v_movimento.valor_movimento  -- Valor deve ser compatível
        ORDER BY p.data_pagamento DESC;
    END IF;

    -- 2. Correspondência por valor exato + data próxima ±3 dias (confiança 80)
    RETURN QUERY
    SELECT
        p.id_pagamento,
        p.data_pagamento,
        p.valor_pago,
        p.metodo_pagamento,
        p.referencia_pagamento,
        p.id_quota_associado,
        qa.periodo_referencia,
        qa.valor_devido,
        a.numero_associado,
        ('Valor idêntico (' || to_char(v_movimento.valor_movimento, 'FM999999990.00') || '), data ±' || v_dias_tolerancia || ' dias')::TEXT AS observacao,
        'valor_data_proxima'::VARCHAR(50) AS tipo_correspondencia,
        80 AS confianca,
        a.nome AS associado,
        a.id_associado
    FROM pagamento p
    INNER JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
    INNER JOIN associado a ON qa.id_associado = a.id_associado
    WHERE p.id_movimento IS NULL
      AND a.id_associacao = p_id_associacao
      AND p.valor_pago = v_movimento.valor_movimento
      AND p.data_pagamento::DATE BETWEEN v_movimento.data_movimento - v_dias_tolerancia
                                      AND v_movimento.data_movimento + v_dias_tolerancia
      AND (p.referencia_pagamento IS NULL OR p.referencia_pagamento != v_movimento.referencia_movimento OR v_movimento.referencia_movimento IS NULL)
    ORDER BY ABS(p.data_pagamento::DATE - v_movimento.data_movimento);

    -- 3. Correspondência por valor exato + mesmo associado (confiança 60)
    RETURN QUERY
    SELECT
        p.id_pagamento,
        p.data_pagamento,
        p.valor_pago,
        p.metodo_pagamento,
        p.referencia_pagamento,
        p.id_quota_associado,
        qa.periodo_referencia,
        qa.valor_devido,
        a.numero_associado,
        ('Valor idêntico (' || to_char(v_movimento.valor_movimento, 'FM999999990.00') || '), mesmo associado')::TEXT AS observacao,
        'valor_mesmo_associado'::VARCHAR(50) AS tipo_correspondencia,
        60 AS confianca,
        a.nome AS associado,
        a.id_associado
    FROM pagamento p
    INNER JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
    INNER JOIN associado a ON qa.id_associado = a.id_associado
    WHERE p.id_movimento IS NULL
      AND a.id_associacao = p_id_associacao
      AND p.valor_pago = v_movimento.valor_movimento
      AND p.id_pagamento NOT IN (
          SELECT p2.id_pagamento FROM pagamento p2
          INNER JOIN quota_associado qa2 ON p2.id_quota_associado = qa2.id_quota_associado
          INNER JOIN quota q2 ON qa2.id_quota = q2.id_quota
          WHERE p2.id_movimento IS NULL
          AND p2.valor_pago = v_movimento.valor_movimento
          AND p2.data_pagamento::DATE BETWEEN v_movimento.data_movimento - v_dias_tolerancia
                                          AND v_movimento.data_movimento + v_dias_tolerancia
          AND q2.id_associacao = p_id_associacao
      )
    ORDER BY p.data_pagamento DESC;

    -- 4. Correspondência apenas por valor exato (confiança 40) - casos ambíguos
    RETURN QUERY
    SELECT
        p.id_pagamento,
        p.data_pagamento,
        p.valor_pago,
        p.metodo_pagamento,
        p.referencia_pagamento,
        p.id_quota_associado,
        qa.periodo_referencia,
        qa.valor_devido,
        a.numero_associado,
        ('Apenas valor idêntico (' || to_char(v_movimento.valor_movimento, 'FM999999990.00') || ') - verificar manualmente')::TEXT AS observacao,
        'apenas_valor'::VARCHAR(50) AS tipo_correspondencia,
        40 AS confianca,
        a.nome AS associado,
        a.id_associado
    FROM pagamento p
    INNER JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
    INNER JOIN associado a ON qa.id_associado = a.id_associado
    WHERE p.id_movimento IS NULL
      AND a.id_associacao = p_id_associacao
      AND p.valor_pago = v_movimento.valor_movimento
      AND p.id_pagamento NOT IN (
          SELECT p2.id_pagamento FROM pagamento p2
          INNER JOIN quota_associado qa2 ON p2.id_quota_associado = qa2.id_quota_associado
          INNER JOIN quota q2 ON qa2.id_quota = q2.id_quota
          WHERE p2.id_movimento IS NULL
          AND p2.valor_pago = v_movimento.valor_movimento
          AND q2.id_associacao = p_id_associacao
          AND (
              p2.data_pagamento::DATE BETWEEN v_movimento.data_movimento - v_dias_tolerancia
                                          AND v_movimento.data_movimento + v_dias_tolerancia
              OR qa2.id_associado = (
                  SELECT qa3.id_associado FROM quota_associado qa3
                  WHERE qa3.id_quota_associado = p.id_quota_associado
              )
          )
      )
    ORDER BY p.data_pagamento DESC;
END;
$$;


-- ---------------------------------------------------------------------------
-- 6. PROCEDURE: Conciliar movimento com pagamento (confirmar correspondência)
-- ---------------------------------------------------------------------------
-- Associa um movimento bancário a um pagamento, validando:
-- - Ambos pertencem à mesma associação
-- - Movimento não está já conciliado
-- - Pagamento não tem movimento associado
-- - Valores coincidem (opcional, mas recomendado)
-- Insere registo em conciliacao_bancaria para auditoria.
-- Atualiza estados financeiros automaticamente via triggers.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE conciliar_movimento_pagamento(
    p_id_associacao INTEGER,
    p_id_movimento INTEGER,
    p_id_pagamento INTEGER,
    p_forcar BOOLEAN DEFAULT FALSE  -- Se TRUE, ignora validação de valor
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_movimento_associacao INTEGER;
    v_pagamento_associacao INTEGER;
    v_movimento_valor NUMERIC(10,2);
    v_pagamento_valor NUMERIC(10,2);
    v_pagamento_movimento INTEGER;
    v_movimento_pagamento_count INTEGER;
    v_ambiguas INTEGER;
    v_confianca INTEGER;
    v_observacao TEXT;
    v_tipo_correspondencia VARCHAR(50);
BEGIN
    -- Validar movimento pertence à associação
    SELECT id_associacao, valor_movimento INTO v_movimento_associacao, v_movimento_valor
    FROM movimento_bancario
    WHERE id_movimento = p_id_movimento;

    IF NOT FOUND OR v_movimento_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Movimento bancário não encontrado ou não autorizado';
    END IF;

    -- Validar pagamento pertence à associação
    SELECT q.id_associacao, p.valor_pago, p.id_movimento INTO v_pagamento_associacao, v_pagamento_valor, v_pagamento_movimento
    FROM pagamento p
    INNER JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
    INNER JOIN quota q ON qa.id_quota = q.id_quota
    WHERE p.id_pagamento = p_id_pagamento;

    IF NOT FOUND OR v_pagamento_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Pagamento não encontrado ou não autorizado';
    END IF;

    -- Verificar se movimento já está conciliado (active conciliação)
    SELECT COUNT(*) INTO v_movimento_pagamento_count
    FROM pagamento
    WHERE id_movimento = p_id_movimento;

    IF v_movimento_pagamento_count > 0 THEN
        RAISE EXCEPTION 'Movimento bancário já está conciliado com outro pagamento';
    END IF;

    -- Verificar se pagamento já tem movimento
    IF v_pagamento_movimento IS NOT NULL THEN
        RAISE EXCEPTION 'Pagamento já tem movimento bancário associado';
    END IF;

    -- Validar valores (a menos que forçado)
    IF NOT p_forcar AND v_movimento_valor != v_pagamento_valor THEN
        RAISE EXCEPTION 'Valores não coincidem: movimento=%, pagamento=%', v_movimento_valor, v_pagamento_valor;
    END IF;

    -- Verificar correspondências ambíguas (confiança >= 80) - requer forcar=true
    IF NOT p_forcar THEN
        SELECT COUNT(*) INTO v_ambiguas
        FROM encontrar_correspondencias_conciliacao(p_id_movimento, p_id_associacao)
        WHERE confianca >= 80;

        IF v_ambiguas > 1 THEN
            RAISE EXCEPTION 'Correspondência ambígua: % sugestões com confiança >= 80%%. Use forcar=true para confirmar.', v_ambiguas;
        END IF;
    END IF;

    -- Determinar confiança e observação baseada na melhor correspondência
    SELECT confianca, observacao, tipo_correspondencia INTO v_confianca, v_observacao, v_tipo_correspondencia
    FROM encontrar_correspondencias_conciliacao(p_id_movimento, p_id_associacao)
    WHERE id_pagamento = p_id_pagamento
    ORDER BY confianca DESC
    LIMIT 1;

    IF v_confianca IS NULL THEN
        v_confianca := 40;
        v_observacao := 'Conciliação manual sem sugestão automática';
        v_tipo_correspondencia := 'manual';
    END IF;

    -- Associar movimento ao pagamento
    UPDATE pagamento
    SET id_movimento = p_id_movimento
    WHERE id_pagamento = p_id_pagamento;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Falha ao atualizar pagamento';
    END IF;

    -- Inserir registo no histórico de conciliações
    INSERT INTO conciliacao_bancaria (
        id_movimento, id_pagamento, id_associacao,
        confianca_utilizada, forcado, observacao
    )
    VALUES (
        p_id_movimento, p_id_pagamento, p_id_associacao,
        v_confianca, p_forcar, v_observacao
    );

    RAISE NOTICE 'Conciliação realizada: movimento % ↔ pagamento % (confiança: %)', p_id_movimento, p_id_pagamento, v_confianca;
END;
$$;


-- ---------------------------------------------------------------------------
-- 7. PROCEDURE: Desfazer conciliação (remover ligação movimento-pagamento)
-- ---------------------------------------------------------------------------
-- Remove a associação ativa entre movimento e pagamento, mas preserva o
-- registo histórico em conciliacao_bancaria marcando como revertido.
-- Aceita id_conciliacao (chave primária) para identificar a conciliação.
-- Valida que pertence à mesma associação.
-- Impede reversões duplicadas.
-- Atualiza estados financeiros automaticamente via triggers.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE desfazer_conciliacao(
    p_id_associacao INTEGER,
    p_id_conciliacao INTEGER,
    p_motivo TEXT DEFAULT 'Reversão manual',
    p_utilizador VARCHAR(100) DEFAULT CURRENT_USER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_id_movimento INTEGER;
    v_id_pagamento INTEGER;
    v_conciliacao_associacao INTEGER;
    v_ja_revertido BOOLEAN;
BEGIN
    -- Obter detalhes da conciliação
    SELECT id_movimento, id_pagamento, id_associacao
    INTO v_id_movimento, v_id_pagamento, v_conciliacao_associacao
    FROM conciliacao_bancaria
    WHERE id_conciliacao = p_id_conciliacao;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Conciliação não encontrada: %', p_id_conciliacao;
    END IF;

    -- Validar associação
    IF v_conciliacao_associacao != p_id_associacao THEN
        RAISE EXCEPTION 'Conciliação não pertence à associação autorizada';
    END IF;

    -- Verificar se já foi revertida
    SELECT data_reversao IS NOT NULL INTO v_ja_revertido
    FROM conciliacao_bancaria
    WHERE id_conciliacao = p_id_conciliacao;

    IF v_ja_revertido THEN
        RAISE EXCEPTION 'Esta conciliação já foi revertida anteriormente';
    END IF;

    -- Marcar conciliação como revertida (preservar histórico)
    UPDATE conciliacao_bancaria
    SET data_reversao = CURRENT_TIMESTAMP,
        reversao_motivo = p_motivo,
        reversao_utilizador = p_utilizador
    WHERE id_conciliacao = p_id_conciliacao
      AND data_reversao IS NULL;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Registo de conciliação ativa não encontrado';
    END IF;

    -- Remover associação ativa (movimento-pagamento)
    UPDATE pagamento
    SET id_movimento = NULL
    WHERE id_pagamento = v_id_pagamento;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Falha ao remover conciliação do pagamento';
    END IF;

    RAISE NOTICE 'Conciliação desfeita: id_conciliacao=% (movimento % ↔ pagamento %)', p_id_conciliacao, v_id_movimento, v_id_pagamento;
END;
$$;


-- ---------------------------------------------------------------------------
-- 8. VIEW: Histórico de conciliações (ativas por padrão)
-- ---------------------------------------------------------------------------
-- Para auditoria e rastreabilidade. Mostra apenas conciliações ativas por padrão
-- (onde data_reversao IS NULL). Use parâmetros para ver histórico completo.
-- Colunas: id_conciliacao, data_conciliacao, data_reversao, reversao_motivo, reversao_utilizador,
-- id_pagamento, id_movimento, confianca_utilizada, forcado, observacao, data_pagamento, valor_pago,
-- metodo_pagamento, referencia_pagamento, data_movimento, valor_movimento,
-- referencia_movimento, descricao_movimento, id_associado, numero_associado, associado,
-- periodo_referencia, id_quota_associado, id_associacao, ativa (boolean)
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_conciliacoes;
CREATE OR REPLACE VIEW vw_conciliacoes AS
SELECT
    cb.id_conciliacao,
    cb.data_conciliacao,
    cb.data_reversao,
    cb.reversao_motivo,
    cb.reversao_utilizador,
    p.id_pagamento,
    mb.id_movimento,
    cb.confianca_utilizada,
    cb.forcado,
    cb.observacao,
    p.data_pagamento,
    p.valor_pago,
    p.metodo_pagamento,
    p.referencia_pagamento AS ref_pagamento,
    mb.data_movimento,
    mb.valor_movimento,
    mb.referencia_movimento AS ref_movimento,
    mb.descricao_movimento,
    a.id_associado,
    a.numero_associado,
    a.nome AS associado,
    qa.periodo_referencia,
    qa.id_quota_associado,
    a.id_associacao,
    (cb.data_reversao IS NULL) AS ativa
FROM conciliacao_bancaria cb
INNER JOIN pagamento p ON cb.id_pagamento = p.id_pagamento
INNER JOIN movimento_bancario mb ON cb.id_movimento = mb.id_movimento
INNER JOIN quota_associado qa ON p.id_quota_associado = qa.id_quota_associado
INNER JOIN associado a ON qa.id_associado = a.id_associado
WHERE cb.data_reversao IS NULL  -- Apenas conciliações ativas por padrão
ORDER BY cb.data_conciliacao DESC;


-- ---------------------------------------------------------------------------
-- 9. VIEW: Sugestões de conciliação para todos os movimentos pendentes
-- ---------------------------------------------------------------------------
-- Agrega sugestões para interface de conciliação em lote.
-- Columns: count_ref_exata, count_valor_data, count_valor_associado, count_apenas_valor,
-- melhor_confianca, correspondencia_inequivoca
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_sugestoes_conciliacao;
CREATE OR REPLACE VIEW vw_sugestoes_conciliacao AS
SELECT
    mb.id_movimento,
    mb.data_movimento,
    mb.descricao_movimento,
    mb.valor_movimento,
    mb.referencia_movimento,
    mb.id_associacao,
    a.nome AS nome_associacao,
    COUNT(DISTINCT CASE WHEN fc.confianca = 100 THEN fc.id_pagamento END) AS count_ref_exata,
    COUNT(DISTINCT CASE WHEN fc.confianca = 80 THEN fc.id_pagamento END) AS count_valor_data,
    COUNT(DISTINCT CASE WHEN fc.confianca = 60 THEN fc.id_pagamento END) AS count_valor_associado,
    COUNT(DISTINCT CASE WHEN fc.confianca = 40 THEN fc.id_pagamento END) AS count_apenas_valor,
    MAX(fc.confianca) AS melhor_confianca,
    CASE
        WHEN COUNT(DISTINCT CASE WHEN fc.confianca >= 80 THEN fc.id_pagamento END) = 1 THEN TRUE
        ELSE FALSE
    END AS correspondencia_inequivoca
FROM movimento_bancario mb
INNER JOIN associacao a ON mb.id_associacao = a.id_associacao
LEFT JOIN LATERAL encontrar_correspondencias_conciliacao(mb.id_movimento, mb.id_associacao) fc ON TRUE
LEFT JOIN pagamento p ON mb.id_movimento = p.id_movimento
WHERE p.id_movimento IS NULL
GROUP BY
    mb.id_movimento, mb.data_movimento, mb.descricao_movimento,
    mb.valor_movimento, mb.referencia_movimento, mb.id_associacao, a.nome
ORDER BY mb.data_movimento DESC, mb.id_movimento;


-- ---------------------------------------------------------------------------
-- 10. VIEW: Movimentos bancários suspeitos de duplicação
-- ---------------------------------------------------------------------------
-- Lista movimentos marcados como suspeito_duplicado = true para revisão manual.
-- Estes são movimentos que têm a mesma data, valor e referência de outro movimento
-- mas não têm identificador bancário (id_externo_banco) para confirmar se são
-- duplicatas reais ou movimentos legítimos idênticos.
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_movimentos_suspeitos;
CREATE OR REPLACE VIEW vw_movimentos_suspeitos AS
SELECT
    mb.id_movimento,
    mb.data_movimento,
    mb.descricao_movimento,
    mb.valor_movimento,
    mb.referencia_movimento,
    mb.id_externo_banco,
    mb.hash_importacao,
    mb.suspeito_duplicado,
    mb.id_associacao,
    a.nome AS nome_associacao,
    -- Contar quantos outros movimentos têm a mesma data/valor/referência
    (SELECT COUNT(*)
     FROM movimento_bancario mb2
     WHERE mb2.id_associacao = mb.id_associacao
       AND mb2.data_movimento = mb.data_movimento
       AND mb2.valor_movimento = mb.valor_movimento
       AND (mb2.referencia_movimento IS NOT DISTINCT FROM mb.referencia_movimento)
       AND mb2.id_movimento != mb.id_movimento) AS total_com_mesmos_dados
FROM movimento_bancario mb
INNER JOIN associacao a ON mb.id_associacao = a.id_associacao
WHERE mb.suspeito_duplicado = TRUE
ORDER BY mb.data_movimento DESC, mb.id_movimento;


-- ============================================================================
-- INSTRUÇÕES DE APLICAÇÃO
-- ============================================================================
-- 1. Executar após sql/10_fase21_financeiro.sql e sql/11_migration_recalcular_estados_quotas.sql
-- 2. Executar testes de integração (tests_fase22.py)
-- 3. Executar suite completa (97 + 15 = 112 testes)
-- 4. Validar em base de dados de staging
-- 5. Aplicar em produção com janela de manutenção
-- ============================================================================