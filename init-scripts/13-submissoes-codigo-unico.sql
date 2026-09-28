-- Código da submissão: SUB-{id:04d} (derivado do id, ver confirmar_submissao).
-- 02-schema já cria codigo com UNIQUE; o índice abaixo garante a unicidade
-- também em bancos criados antes disso. Idempotente.
CREATE UNIQUE INDEX IF NOT EXISTS uq_submissoes_codigo ON submissoes (codigo);
