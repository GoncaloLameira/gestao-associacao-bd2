-- =====================================================
-- Views - Corrected to match existing DB column order
-- Adds id_associacao at END where missing
-- =====================================================

-- Consulta dos mandatos da associação
-- Current: id_mandato, data_inicio, data_fim, id_associacao, associacao
-- Already has id_associacao at position 4 - KEEP AS IS
CREATE OR REPLACE VIEW vw_mandatos AS
SELECT
    m.id_mandato,
    m.data_inicio,
    m.data_fim,
    a.id_associacao,
    a.nome AS associacao
FROM mandato m
INNER JOIN associacao a
    ON m.id_associacao = a.id_associacao;


-- Consulta dos associados que exercem/exerceram cargos
-- Current: id_exercicio_cargo, data_inicio, data_fim, id_associado, associado, id_cargo, cargo, id_orgao_social, orgao_social, id_mandato, inicio_mandato, fim_mandato
-- MISSING id_associacao - ADD AT END
CREATE OR REPLACE VIEW vw_exercicios_cargo AS
SELECT
    ec.id_exercicio_cargo,
    ec.data_inicio,
    ec.data_fim,
    a.id_associado,
    a.nome AS associado,
    c.id_cargo,
    c.nome AS cargo,
    os.id_orgao_social,
    os.nome AS orgao_social,
    m.id_mandato,
    m.data_inicio AS inicio_mandato,
    m.data_fim AS fim_mandato,
    a.id_associacao
FROM exercicio_cargo ec
INNER JOIN associado a
    ON ec.id_associado = a.id_associado
INNER JOIN cargo c
    ON ec.id_cargo = c.id_cargo
INNER JOIN orgao_social os
    ON c.id_orgao_social = os.id_orgao_social
INNER JOIN mandato m
    ON ec.id_mandato = m.id_mandato;


-- ==========================================
-- VIEW: CONSULTAR ASSOCIACOES
-- Current: id_associacao, nipc, nome, data_fundacao, email, telefone, password_hash, tipo_via, nome_via, numero_porta, andar, codigo_postal, id_localidade, nome_localidade
-- Already has id_associacao at position 1 - KEEP AS IS (it's the PK table)
CREATE OR REPLACE VIEW vw_associacoes AS
SELECT
    a.id_associacao,
    a.nipc,
    a.nome,
    a.data_fundacao,
    a.email,
    a.telefone,
    a.password_hash,
    a.tipo_via,
    a.nome_via,
    a.numero_porta,
    a.andar,
    a.codigo_postal,
    a.id_localidade,
    l.nome_localidade
FROM associacao a
LEFT JOIN localidade l
    ON a.id_localidade = l.id_localidade;


-- ==========================================
-- VIEW: CONSULTAR EVENTOS
-- Current: id_evento, nome_evento, descricao_evento, data_inicio_evento, data_fim_evento, local_evento, estado_evento, nome_associacao
-- MISSING id_associacao - ADD AT END
CREATE OR REPLACE VIEW vw_eventos AS
SELECT
    e.id_evento,
    e.nome_evento,
    e.descricao_evento,
    e.data_inicio_evento,
    e.data_fim_evento,
    e.local_evento,
    e.estado_evento,
    a.nome AS nome_associacao,
    e.id_associacao
FROM evento e
INNER JOIN associacao a
    ON e.id_associacao = a.id_associacao;


-- ==========================================
-- VIEW ASSOCIADOS
-- Current: id_associado, numero_associado, nome, nif, data_nascimento, email, telefone, data_adesao, data_saida, estado, tipo_via, nome_via, numero_porta, andar, codigo_postal, id_localidade, nome_localidade, nome_associacao
-- MISSING id_associacao - ADD AT END
CREATE OR REPLACE VIEW vw_associados AS
SELECT
    a.id_associado,
    a.numero_associado,
    a.nome,
    a.nif,
    a.data_nascimento,
    a.email,
    a.telefone,
    a.data_adesao,
    a.data_saida,
    a.estado,
    a.tipo_via,
    a.nome_via,
    a.numero_porta,
    a.andar,
    a.codigo_postal,
    a.id_localidade,
    l.nome_localidade,
    ass.nome AS nome_associacao,
    a.id_associacao
FROM associado a
LEFT JOIN localidade l
    ON a.id_localidade = l.id_localidade
JOIN associacao ass
    ON a.id_associacao = ass.id_associacao;


-- ==========================================
-- VIEW QUOTAS
-- Current: id_quota, designacao_quota, valor_quota, periodicidade_quota, data_inicio_quota, data_fim_quota, nome_associacao
-- MISSING id_associacao - ADD AT END
CREATE OR REPLACE VIEW vw_quotas AS
SELECT
    q.id_quota,
    q.designacao_quota,
    q.valor_quota,
    q.periodicidade_quota,
    q.data_inicio_quota,
    q.data_fim_quota,
    a.nome AS nome_associacao,
    q.id_associacao
FROM quota q
JOIN associacao a
    ON q.id_associacao = a.id_associacao;


-- ==========================================
-- VIEW ÓRGÃOS SOCIAIS
-- Current: id_orgao_social, nome, descricao, nome_associacao
-- MISSING id_associacao - ADD AT END
CREATE OR REPLACE VIEW vw_orgaos_sociais AS
SELECT
    os.id_orgao_social,
    os.nome,
    os.descricao,
    a.nome AS nome_associacao,
    os.id_associacao
FROM orgao_social os
JOIN associacao a
    ON os.id_associacao = a.id_associacao;


-- ==========================================
-- VIEW CARGOS
-- Current: id_cargo, nome, descricao, nome_orgao_social, nome_associacao, id_associacao
-- Already has id_associacao at END - KEEP AS IS
CREATE OR REPLACE VIEW vw_cargos AS
SELECT
    c.id_cargo,
    c.nome,
    c.descricao,
    os.nome AS nome_orgao_social,
    a.nome AS nome_associacao,
    os.id_associacao
FROM cargo c
JOIN orgao_social os
    ON c.id_orgao_social = os.id_orgao_social
JOIN associacao a
    ON os.id_associacao = a.id_associacao;


-- ==========================================
-- VIEW: MOVIMENTOS BANCÁRIOS
-- Current: id_movimento, data_movimento, descricao_movimento, valor_movimento, referencia_movimento
-- ADD id_associacao at END via LEFT JOIN pagamento -> quota_associado -> quota
CREATE OR REPLACE VIEW vw_movimentos_bancarios AS
SELECT
    mb.id_movimento,
    mb.data_movimento,
    mb.descricao_movimento,
    mb.valor_movimento,
    mb.referencia_movimento,
    q.id_associacao
FROM movimento_bancario mb
LEFT JOIN pagamento p
    ON mb.id_movimento = p.id_movimento
LEFT JOIN quota_associado qa
    ON p.id_quota_associado = qa.id_quota_associado
LEFT JOIN quota q
    ON qa.id_quota = q.id_quota
ORDER BY mb.data_movimento DESC;


-- ==========================================
-- VIEW: PAGAMENTOS
-- Current: id_pagamento, data_pagamento, valor_pago, metodo_pagamento, referencia_pagamento, id_quota_associado, periodo_referencia, valor_devido, estado_quota_associado, id_associado, numero_associado, associado, id_quota, designacao_quota, valor_quota, periodicidade_quota
-- MISSING id_associacao - ADD AT END
CREATE OR REPLACE VIEW vw_pagamentos AS
SELECT
    p.id_pagamento,
    p.data_pagamento,
    p.valor_pago,
    p.metodo_pagamento,
    p.referencia_pagamento,
    qa.id_quota_associado,
    qa.periodo_referencia,
    qa.valor_devido,
    qa.estado_quota_associado,
    a.id_associado,
    a.numero_associado,
    a.nome AS associado,
    q.id_quota,
    q.designacao_quota,
    q.valor_quota,
    q.periodicidade_quota,
    a.id_associacao
FROM pagamento p
INNER JOIN quota_associado qa
    ON p.id_quota_associado = qa.id_quota_associado
INNER JOIN associado a
    ON qa.id_associado = a.id_associado
INNER JOIN quota q
    ON qa.id_quota = q.id_quota
ORDER BY p.data_pagamento DESC;


-- ==========================================
-- VIEW: TIPOS DE DOCUMENTO
-- Current: id_tipo_documento, nome_tipo_documento, descricao_tipo_documento, nome_associacao
-- MISSING id_associacao - ADD AT END
CREATE OR REPLACE VIEW vw_tipos_documento AS
SELECT
    td.id_tipo_documento,
    td.nome_tipo_documento,
    td.descricao_tipo_documento,
    a.nome AS nome_associacao,
    td.id_associacao
FROM tipo_documento td
JOIN associacao a
    ON td.id_associacao = a.id_associacao
ORDER BY td.nome_tipo_documento;


-- ==========================================
-- VIEW: DOCUMENTOS
-- Current: id_documento, nome_documento, data_upload, data_documento, ficheiro, observacoes, id_tipo_documento, nome_tipo_documento, descricao_tipo_documento, nome_associacao, id_mandato, inicio_mandato, fim_mandato
-- MISSING id_associacao - ADD AT END
CREATE OR REPLACE VIEW vw_documentos AS
SELECT
    d.id_documento,
    d.nome_documento,
    d.data_upload,
    d.data_documento,
    d.ficheiro,
    d.observacoes,
    td.id_tipo_documento,
    td.nome_tipo_documento,
    td.descricao_tipo_documento,
    a.nome AS nome_associacao,
    m.id_mandato,
    m.data_inicio AS inicio_mandato,
    m.data_fim AS fim_mandato,
    d.id_associacao
FROM documento d
INNER JOIN tipo_documento td
    ON d.id_tipo_documento = td.id_tipo_documento
INNER JOIN associacao a
    ON d.id_associacao = a.id_associacao
LEFT JOIN mandato m
    ON d.id_mandato = m.id_mandato
ORDER BY d.data_upload DESC;


-- ==========================================
-- AGGREGATED VIEWS (RF10, RF11)
-- ==========================================

-- View: Quotas em dívida
-- Current: id_quota_associado, id_associado, numero_associado, associado, email, id_quota, designacao_quota, valor_quota, periodicidade_quota, periodo_referencia, valor_devido, data_vencimento, estado_quota_associado, dias_em_atraso, id_associacao
-- Already has id_associacao at END - KEEP AS IS
CREATE OR REPLACE VIEW vw_quotas_em_divida AS
SELECT
    qa.id_quota_associado,
    a.id_associado,
    a.numero_associado,
    a.nome AS associado,
    a.email,
    q.id_quota,
    q.designacao_quota,
    q.valor_quota,
    q.periodicidade_quota,
    qa.periodo_referencia,
    qa.valor_devido,
    qa.data_vencimento,
    qa.estado_quota_associado,
    CASE
        WHEN qa.data_vencimento < CURRENT_DATE AND qa.estado_quota_associado IN ('Pendente', 'Em Dívida', 'Parcial')
        THEN CURRENT_DATE - qa.data_vencimento
        ELSE 0
    END AS dias_em_atraso,
    a.id_associacao
FROM quota_associado qa
INNER JOIN associado a
    ON qa.id_associado = a.id_associado
INNER JOIN quota q
    ON qa.id_quota = q.id_quota
WHERE qa.estado_quota_associado IN ('Pendente', 'Em Dívida', 'Parcial')
ORDER BY qa.data_vencimento;


-- View: Pagamentos com detalhes completos
-- Current: id_pagamento, data_pagamento, valor_pago, metodo_pagamento, referencia_pagamento, id_quota_associado, periodo_referencia, valor_devido, estado_quota_associado, id_associado, numero_associado, associado, email, id_quota, designacao_quota, valor_quota, periodicidade_quota, id_movimento, data_movimento, descricao_movimento, valor_movimento, referencia_movimento, id_associacao
-- Already has id_associacao at END - KEEP AS IS
CREATE OR REPLACE VIEW vw_pagamentos_detalhes AS
SELECT
    p.id_pagamento,
    p.data_pagamento,
    p.valor_pago,
    p.metodo_pagamento,
    p.referencia_pagamento,
    qa.id_quota_associado,
    qa.periodo_referencia,
    qa.valor_devido,
    qa.estado_quota_associado,
    a.id_associado,
    a.numero_associado,
    a.nome AS associado,
    a.email,
    q.id_quota,
    q.designacao_quota,
    q.valor_quota,
    q.periodicidade_quota,
    mb.id_movimento,
    mb.data_movimento,
    mb.descricao_movimento,
    mb.valor_movimento,
    mb.referencia_movimento,
    a.id_associacao
FROM pagamento p
INNER JOIN quota_associado qa
    ON p.id_quota_associado = qa.id_quota_associado
INNER JOIN associado a
    ON qa.id_associado = a.id_associado
INNER JOIN quota q
    ON qa.id_quota = q.id_quota
LEFT JOIN movimento_bancario mb
    ON p.id_movimento = mb.id_movimento
ORDER BY p.data_pagamento DESC;


-- View: Documentos com detalhes completos
-- Current: id_documento, nome_documento, data_upload, data_documento, ficheiro, observacoes, id_tipo_documento, nome_tipo_documento, descricao_tipo_documento, id_associacao, nome_associacao, id_mandato, inicio_mandato, fim_mandato
-- Already has id_associacao at position 10 - KEEP AS IS
CREATE OR REPLACE VIEW vw_documentos_detalhes AS
SELECT
    d.id_documento,
    d.nome_documento,
    d.data_upload,
    d.data_documento,
    d.ficheiro,
    d.observacoes,
    td.id_tipo_documento,
    td.nome_tipo_documento,
    td.descricao_tipo_documento,
    a.id_associacao,
    a.nome AS nome_associacao,
    m.id_mandato,
    m.data_inicio AS inicio_mandato,
    m.data_fim AS fim_mandato
FROM documento d
INNER JOIN tipo_documento td
    ON d.id_tipo_documento = td.id_tipo_documento
INNER JOIN associacao a
    ON d.id_associacao = a.id_associacao
LEFT JOIN mandato m
    ON d.id_mandato = m.id_mandato
ORDER BY d.data_upload DESC;