CREATE TABLE IF NOT EXISTS rebuttals (
    id BIGSERIAL PRIMARY KEY,
    rodada_id BIGINT NOT NULL UNIQUE REFERENCES rodadas(id),
    situacao VARCHAR(16) NOT NULL DEFAULT 'aguardando',  -- 'aguardando' | 'enviado' | 'expirado' | 'cancelado'
    prazo TIMESTAMPTZ,
    texto TEXT,
    versao_id BIGINT REFERENCES versoes_arquivo(id),
    enviado_em TIMESTAMPTZ,
    enviado_por_nome VARCHAR(200)
);