CREATE TABLE IF NOT EXISTS formularios_versao (
    id BIGSERIAL PRIMARY KEY,
    chamada_id BIGINT NOT NULL REFERENCES chamadas(id),
    versao INTEGER NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'rascunho',  -- 'rascunho' | 'publicado'
    publicado_em TIMESTAMPTZ,
    campos TEXT NOT NULL DEFAULT '[]',               -- JSON: lista de Campo
    criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (chamada_id, versao)
);

CREATE INDEX IF NOT EXISTS idx_formularios_versao_chamada ON formularios_versao(chamada_id, status);