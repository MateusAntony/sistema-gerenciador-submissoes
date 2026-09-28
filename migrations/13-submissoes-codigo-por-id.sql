-- Migração para bancos existentes (idempotente; aplicar com psql -f).
-- O cálculo antigo do código (última submissão + 1) gravava códigos
-- deslocados (id 1 -> SUB-0002) e podia repeti-los. Normaliza todo código
-- existente para SUB-{id:04d} e garante o índice único.
BEGIN;

-- Em dois passos: o UNIQUE é verificado linha a linha, e a troca direta
-- colidiria (o id 2 quer SUB-0002, que o id 1 ainda usa).
UPDATE submissoes
SET codigo = 'MIGRANDO-' || id
WHERE codigo IS NOT NULL
  AND codigo <> 'SUB-' || lpad(id::text, greatest(4, length(id::text)), '0');

UPDATE submissoes
SET codigo = 'SUB-' || lpad(id::text, greatest(4, length(id::text)), '0')
WHERE codigo LIKE 'MIGRANDO-%';

CREATE UNIQUE INDEX IF NOT EXISTS uq_submissoes_codigo ON submissoes (codigo);

COMMIT;
