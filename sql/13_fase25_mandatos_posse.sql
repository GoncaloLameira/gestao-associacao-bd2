-- ============================================================================
-- FASE 2.5 — Mandatos, composição e passagem de posse
-- ============================================================================

CREATE OR REPLACE FUNCTION fn_validar_sobreposicao_mandato()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM mandato m
        WHERE m.id_associacao = NEW.id_associacao
          AND m.id_mandato <> COALESCE(NEW.id_mandato, -1)
          AND m.data_inicio <= COALESCE(NEW.data_fim, 'infinity'::date)
          AND COALESCE(m.data_fim, 'infinity'::date) >= NEW.data_inicio
    ) THEN
        RAISE EXCEPTION 'O mandato sobrepõe-se a um mandato já registado.';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION fn_validar_composicao_mandato()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM exercicio_cargo ec
        WHERE ec.id_mandato = NEW.id_mandato
          AND ec.id_cargo = NEW.id_cargo
          AND ec.id_exercicio_cargo <> COALESCE(NEW.id_exercicio_cargo, -1)
          AND ec.data_inicio <= COALESCE(NEW.data_fim, 'infinity'::date)
          AND COALESCE(ec.data_fim, 'infinity'::date) >= NEW.data_inicio
    ) THEN
        RAISE EXCEPTION 'O cargo já está atribuído neste mandato para o período indicado.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_composicao_mandato ON exercicio_cargo;
CREATE TRIGGER trg_composicao_mandato
BEFORE INSERT OR UPDATE ON exercicio_cargo
FOR EACH ROW EXECUTE FUNCTION fn_validar_composicao_mandato();

CREATE OR REPLACE PROCEDURE passagem_posse(
    p_id_mandato_anterior INTEGER,
    p_data_inicio_novo DATE,
    p_data_fim_novo DATE,
    p_id_presidente INTEGER,
    p_composicao JSONB,
    p_password_hash VARCHAR(255),
    p_id_associacao INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_id_mandato_novo INTEGER;
    v_mandato_inicio DATE;
    v_associacao_mandato INTEGER;
    v_membro JSONB;
    v_id_associado INTEGER;
    v_id_cargo INTEGER;
BEGIN
    SELECT data_inicio, id_associacao
    INTO v_mandato_inicio, v_associacao_mandato
    FROM mandato
    WHERE id_mandato = p_id_mandato_anterior
    FOR UPDATE;

    IF NOT FOUND OR v_associacao_mandato <> p_id_associacao THEN
        RAISE EXCEPTION 'Mandato anterior não encontrado ou não autorizado.';
    END IF;
    IF p_data_inicio_novo <= v_mandato_inicio THEN
        RAISE EXCEPTION 'O novo mandato deve iniciar após o mandato anterior.';
    END IF;
    IF p_data_fim_novo IS NOT NULL AND p_data_fim_novo < p_data_inicio_novo THEN
        RAISE EXCEPTION 'A data de fim do novo mandato é inválida.';
    END IF;
    IF jsonb_typeof(p_composicao) <> 'array' OR jsonb_array_length(p_composicao) = 0 THEN
        RAISE EXCEPTION 'A nova direção deve ter pelo menos um cargo atribuído.';
    END IF;

    UPDATE mandato
    SET data_fim = p_data_inicio_novo - 1
    WHERE id_mandato = p_id_mandato_anterior;

    IF EXISTS (
        SELECT 1 FROM mandato m
        WHERE m.id_associacao = p_id_associacao
          AND m.id_mandato <> p_id_mandato_anterior
          AND m.data_inicio <= COALESCE(p_data_fim_novo, 'infinity'::date)
          AND COALESCE(m.data_fim, 'infinity'::date) >= p_data_inicio_novo
    ) THEN
        RAISE EXCEPTION 'O novo mandato sobrepõe-se a um mandato já registado.';
    END IF;

    INSERT INTO mandato (data_inicio, data_fim, id_associacao)
    VALUES (p_data_inicio_novo, p_data_fim_novo, p_id_associacao)
    RETURNING id_mandato INTO v_id_mandato_novo;

    FOR v_membro IN SELECT value FROM jsonb_array_elements(p_composicao) LOOP
        v_id_associado := (v_membro ->> 'id_associado')::INTEGER;
        v_id_cargo := (v_membro ->> 'id_cargo')::INTEGER;

        IF NOT EXISTS (
            SELECT 1 FROM associado
            WHERE id_associado = v_id_associado AND id_associacao = p_id_associacao AND estado = 'Ativo'
        ) THEN
            RAISE EXCEPTION 'O associado da nova direção não é válido.';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM cargo c
            JOIN orgao_social os ON os.id_orgao_social = c.id_orgao_social
            WHERE c.id_cargo = v_id_cargo AND os.id_associacao = p_id_associacao
        ) THEN
            RAISE EXCEPTION 'O cargo da nova direção não é válido.';
        END IF;
        IF EXISTS (SELECT 1 FROM exercicio_cargo WHERE id_mandato = v_id_mandato_novo AND id_cargo = v_id_cargo) THEN
            RAISE EXCEPTION 'Cada cargo só pode ser atribuído uma vez na nova direção.';
        END IF;

        INSERT INTO exercicio_cargo (data_inicio, data_fim, id_associado, id_cargo, id_mandato)
        VALUES (p_data_inicio_novo, p_data_fim_novo, v_id_associado, v_id_cargo, v_id_mandato_novo);
    END LOOP;

    IF NOT EXISTS (
        SELECT 1
        FROM exercicio_cargo ec
        JOIN cargo c ON c.id_cargo = ec.id_cargo
        WHERE ec.id_mandato = v_id_mandato_novo
          AND ec.id_associado = p_id_presidente
          AND LOWER(c.nome) LIKE '%presidente%'
    ) THEN
        RAISE EXCEPTION 'O novo presidente tem de estar atribuído a um cargo de presidente.';
    END IF;

    UPDATE associacao SET password_hash = p_password_hash WHERE id_associacao = p_id_associacao;
END;
$$;
