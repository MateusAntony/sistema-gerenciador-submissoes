-- Notificação sem evento: solicitação de evento recusada (B5). Idempotente.
ALTER TABLE notificacoes ALTER COLUMN evento_id DROP NOT NULL;
