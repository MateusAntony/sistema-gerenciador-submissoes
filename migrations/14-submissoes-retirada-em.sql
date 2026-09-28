-- Migração para bancos existentes (idempotente; aplicar com psql -f).
-- Instante da retirada da submissão, para a linha do tempo (A13).
-- Submissões já retiradas ficam sem o instante (não há como recuperá-lo).
ALTER TABLE submissoes ADD COLUMN IF NOT EXISTS retirada_em TIMESTAMPTZ;
