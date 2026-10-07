-- =====================================================
-- Procedures
-- Entidades: Mandato e ExercicioCargo
-- =====================================================

-- Registar um novo mandato
CREATE OR REPLACE PROCEDURE registar_mandato(
    p_data_inicio DATE,
    p_data_fim DATE,
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO mandato (
        data_inicio,
        data_fim,
        id_associacao
    )
    VALUES (
        p_data_inicio,
        p_data_fim,
        p_id_associacao
    );
END;
$$;


-- Registar o exercício de um cargo por um associado
CREATE OR REPLACE PROCEDURE registar_exercicio_cargo(
    p_data_inicio DATE,
    p_data_fim DATE,
    p_id_associado INTEGER,
    p_id_cargo INTEGER,
    p_id_mandato INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO exercicio_cargo (
        data_inicio,
        data_fim,
        id_associado,
        id_cargo,
        id_mandato
    )
    VALUES (
        p_data_inicio,
        p_data_fim,
        p_id_associado,
        p_id_cargo,
        p_id_mandato
    );
END;
$$;