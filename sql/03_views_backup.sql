-- =====================================================
-- Views
-- Entidades: Mandato e ExercicioCargo
-- =====================================================

-- Consulta dos mandatos da associação
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
CREATE OR REPLACE VIEW vw_exercicios_cargo AS
SELECT
    ec.id_exercicio_cargo,
    ec.data_inicio,
    ec.data_fim,
    a.id_associado,
    a.id_associacao,
    a.nome AS associado,
    c.id_cargo,
    c.nome AS cargo,
    os.id_orgao_social,
    os.nome AS orgao_social,
    m.id_mandato,
    m.data_inicio AS inicio_mandato,
    m.data_fim AS fim_mandato
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
-- ==========================================

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
-- ==========================================

CREATE OR REPLACE VIEW vw_eventos AS
SELECT
    e.id_evento,
    e.id_associacao,
    e.nome_evento,
    e.descricao_evento,
    e.data_inicio_evento,
    e.data_fim_evento,
    e.local_evento,
    e.estado_evento,
    a.nome AS nome_associacao
FROM evento e
INNER JOIN associacao a
    ON e.id_associacao = a.id_associacao;


-- ==========================================
-- VIEW ASSOCIADOS
-- ==========================================

CREATE OR REPLACE VIEW vw_associados AS
SELECT
    a.id_associado,
    a.id_associacao,
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
    ass.nome AS nome_associacao
FROM associado a
LEFT JOIN localidade l
    ON a.id_localidade = l.id_localidade
JOIN associacao ass
    ON a.id_associacao = ass.id_associacao;


-- ==========================================
-- VIEW QUOTAS
-- ==========================================

CREATE OR REPLACE VIEW vw_quotas AS
SELECT
    q.id_quota,
    q.id_associacao,
    q.designacao_quota,
    q.valor_quota,
    q.periodicidade_quota,
    q.data_inicio_quota,
    q.data_fim_quota,
    a.nome AS nome_associacao
FROM quota q
JOIN associacao a
    ON q.id_associacao = a.id_associacao;


-- ==========================================
-- VIEW ÓRGÃOS SOCIAIS
-- ==========================================

CREATE OR REPLACE VIEW vw_orgaos_sociais AS
SELECT
    os.id_orgao_social,
    os.id_associacao,
    os.nome,
    os.descricao,
    a.nome AS nome_associacao
FROM orgao_social os
JOIN associacao a
    ON os.id_associacao = a.id_associacao;


-- ==========================================
-- VIEW CARGOS
-- ==========================================

CREATE OR REPLACE VIEW vw_cargos AS
SELECT
    c.id_cargo,
    c.id_associacao,
    c.nome,
    c.descricao,
    os.nome AS nome_orgao_social,
    a.nome AS nome_associacao
FROM cargo c
JOIN orgao_social os
    ON c.id_orgao_social = os.id_orgao_social
JOIN associacao a
    ON os.id_associacao = a.id_associacao;

-- ==========================================
-- VIEW: MOVIMENTOS BANCÁRIOS
-- ==========================================

CREATE OR REPLACE VIEW vw_movimentos_bancarios AS
SELECT
    mb.id_movimento,
    mb.id_associacao,
    mb.data_movimento,
    mb.descricao_movimento,
    mb.valor_movimento,
    mb.referencia_movimento
FROM movimento_bancario mb
ORDER BY mb.data_movimento DESC;


-- ==========================================
-- VIEW: PAGAMENTOS
-- ==========================================

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
    a.id_associacao,
    a.numero_associado,
    a.nome AS associado,
    q.id_quota,
    q.designacao_quota,
    q.valor_quota,
    q.periodicidade_quota
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
-- ==========================================

CREATE OR REPLACE VIEW vw_tipos_documento AS
SELECT
    td.id_tipo_documento,
    td.id_associacao,
    td.nome_tipo_documento,
    td.descricao_tipo_documento,
    a.nome AS nome_associacao
FROM tipo_documento td
JOIN associacao a
    ON td.id_associacao = a.id_associacao
ORDER BY td.nome_tipo_documento;


-- ==========================================
-- VIEW: DOCUMENTOS
-- ==========================================

CREATE OR REPLACE VIEW vw_documentos AS
SELECT
    d.id_documento,
    d.id_associacao,
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
    m.data_fim AS fim_mandato
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
    END AS dias_em_atraso
FROM quota_associado qa
INNER JOIN associado a
    ON qa.id_associado = a.id_associado
INNER JOIN quota q
    ON qa.id_quota = q.id_quota
WHERE qa.estado_quota_associado IN ('Pendente', 'Em Dívida', 'Parcial')
ORDER BY qa.data_vencimento;


-- View: Pagamentos com detalhes completos
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
    mb.referencia_movimento
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
