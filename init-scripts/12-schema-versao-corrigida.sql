CREATE TABLE IF NOT EXISTS versoes_corrigidas (
    id BIGSERIAL PRIMARY KEY,
    submissao_id BIGINT NOT NULL UNIQUE REFERENCES submissoes(id),
    versao_id BIGINT REFERENCES versoes_arquivo(id),
    descricao_das_alteracoes TEXT,
    enviada_em TIMESTAMPTZ,
    validada_em TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS versoes_corrigidas_devolucoes (
    id BIGSERIAL PRIMARY KEY,
    versao_corrigida_id BIGINT NOT NULL REFERENCES versoes_corrigidas(id),
    apontamentos TEXT NOT NULL,
    devolvida_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    devolvida_por_nome VARCHAR(200)
);

CREATE INDEX IF NOT EXISTS idx_devolucoes_versao_corrigida ON versoes_corrigidas_devolucoes(versao_corrigida_id);