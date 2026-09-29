-- Instante da retirada da submissão (linha do tempo, A13). Idempotente.
ALTER TABLE submissoes ADD COLUMN IF NOT EXISTS retirada_em TIMESTAMPTZ;
