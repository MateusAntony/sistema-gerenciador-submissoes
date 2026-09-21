CREATE TABLE IF NOT EXISTS decisoes (
    id BIGSERIAL PRIMARY KEY,
    rodada_id BIGINT NOT NULL UNIQUE REFERENCES rodadas(id),
    resultado VARCHAR(32) NOT NULL,  -- 'aceita' | 'aceita_com_correcoes' | 'nova_rodada' | 'rejeitada'
    justificativa TEXT NOT NULL,
    decidido_por_id BIGINT REFERENCES usuarios(id),
    decidido_por_nome VARCHAR(200),
    decidido_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    comunicada_em TIMESTAMPTZ,
    prazo_versao_corrigida TIMESTAMPTZ
);