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