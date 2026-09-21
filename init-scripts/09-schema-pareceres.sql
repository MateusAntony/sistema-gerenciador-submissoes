CREATE TABLE IF NOT EXISTS pareceres (
    id BIGSERIAL PRIMARY KEY,
    atribuicao_id BIGINT NOT NULL UNIQUE REFERENCES atribuicoes(id),
    situacao VARCHAR(16) NOT NULL DEFAULT 'rascunho',  -- 'rascunho' | 'submetido'
    notas TEXT NOT NULL DEFAULT '[]',  -- JSON: [{criterioId, nota}]
    recomendacao VARCHAR(32),  -- 'aceitar' | 'aceitar_com_correcoes' | 'nova_rodada' | 'rejeitar'
    comentarios_aos_autores TEXT,
    comentarios_confidenciais TEXT,
    nivel_de_confianca INTEGER,
    arquivo_nome VARCHAR(255),
    arquivo_tamanho_bytes INTEGER,
    pontuacao_ponderada DOUBLE PRECISION,
    data_submissao TIMESTAMPTZ,
    atualizado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pareceres_atribuicao ON pareceres(atribuicao_id);