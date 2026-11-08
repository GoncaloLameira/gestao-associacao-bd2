-- Estado persistente para obrigar a substituição da palavra-passe temporária.
ALTER TABLE associado
ADD COLUMN IF NOT EXISTS exigir_alteracao_password BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN associado.exigir_alteracao_password IS
  'Indica que o associado tem de substituir a palavra-passe temporária no primeiro acesso.';
