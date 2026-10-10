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
    a.tipo_via,
    a.nome_via,
    a.numero_porta,
    a.andar,
    a.codigo_postal,
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
    c.nome,
    c.descricao,
    os.nome AS nome_orgao_social,
    a.nome AS nome_associacao
FROM cargo c
JOIN orgao_social os
    ON c.id_orgao_social = os.id_orgao_social
JOIN associacao a
    ON os.id_associacao = a.id_associacao;
