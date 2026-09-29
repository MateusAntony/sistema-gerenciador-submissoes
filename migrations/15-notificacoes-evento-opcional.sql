-- Migração para bancos existentes (idempotente; aplicar com psql -f).
-- Notificações de solicitação de evento (B5): a recusada não tem evento.
ALTER TABLE notificacoes ALTER COLUMN evento_id DROP NOT NULL;
