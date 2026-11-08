-- Isolamento de identidades e configurações próprias de cada associação.
-- Não elimina dados: apenas substitui uma unicidade global incorreta por
-- unicidades no âmbito da associação ou do respetivo órgão social.

ALTER TABLE associado
    DROP CONSTRAINT IF EXISTS associado_numero_associado_key;

ALTER TABLE associado
    ADD CONSTRAINT uq_associado_associacao_numero
    UNIQUE (id_associacao, numero_associado);

ALTER TABLE orgao_social
    ADD CONSTRAINT uq_orgao_social_associacao_nome
    UNIQUE (id_associacao, nome);

ALTER TABLE tipo_documento
    ADD CONSTRAINT uq_tipo_documento_associacao_nome
    UNIQUE (id_associacao, nome_tipo_documento);

ALTER TABLE cargo
    ADD CONSTRAINT uq_cargo_orgao_nome
    UNIQUE (id_orgao_social, nome);
