CREATE TABLE IF NOT EXISTS execucoes_fase (
    id BIGSERIAL PRIMARY KEY,
    submissao_id BIGINT NOT NULL REFERENCES submissoes(id),
    fase_id BIGINT NOT NULL REFERENCES fases_definicao(id),
    responsavel_id BIGINT REFERENCES usuarios(id),
    status VARCHAR(20) NOT NULL DEFAULT 'pendente',
    -- 'pendente' | 'em_andamento' | 'aguardando_autor' | 'concluida' | 'dispensada'
    data_inicio TIMESTAMPTZ,
    prazo TIMESTAMPTZ,
    data_conclusao TIMESTAMPTZ,
    arquivo_resultado_id BIGINT,
    observacoes TEXT
);

CREATE INDEX IF NOT EXISTS idx_execucoes_fase_submissao ON execucoes_fase(submissao_id);
CREATE INDEX IF NOT EXISTS idx_execucoes_fase_responsavel ON execucoes_fase(responsavel_id, status);