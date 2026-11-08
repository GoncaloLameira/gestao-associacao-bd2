-- =====================================================
-- Migration: Adicionar password_hash à tabela associado
-- Para suportar autenticação individual de associados (RF14)
-- =====================================================

-- Adicionar coluna password_hash à tabela associado
ALTER TABLE associado
ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);

-- Comentário para documentação
COMMENT ON COLUMN associado.password_hash IS 'Hash da palavra-passe para autenticação individual do associado (Django PBKDF2)';

-- Índice para acelerar lookups por email (usado no login)
CREATE INDEX IF NOT EXISTS idx_associado_email ON associado(email);

-- Nota: Os associados existentes terão password_hash = NULL
-- A criação de contas para associados existentes deve ser feita pela Direção
-- através de um processo de "ativar acesso" que define a password inicial