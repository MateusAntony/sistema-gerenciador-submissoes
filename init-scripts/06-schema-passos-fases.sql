CREATE TABLE IF NOT EXISTS passos_envio (
    id BIGSERIAL PRIMARY KEY,
    chamada_id BIGINT NOT NULL REFERENCES chamadas(id),
    nome VARCHAR(200) NOT NULL,
    descricao TEXT,
    ordem INTEGER NOT NULL DEFAULT 1,
    campos TEXT NOT NULL DEFAULT '[]'  -- JSON: lista de chaves de Campo
);

CREATE INDEX IF NOT EXISTS idx_passos_envio_chamada ON passos_envio(chamada_id, ordem);

CREATE TABLE IF NOT EXISTS fases_definicao (
    id BIGSERIAL PRIMARY KEY,
    evento_id BIGINT NOT NULL REFERENCES eventos(id),
    nome VARCHAR(200) NOT NULL,
    descricao TEXT,
    ordem INTEGER NOT NULL DEFAULT 1,
    momento VARCHAR(16) NOT NULL DEFAULT 'triagem',  -- 'triagem' | 'producao'
    prazo_padrao_dias INTEGER NOT NULL DEFAULT 0,
    responsavel_padrao_id BIGINT REFERENCES usuarios(id),
    obrigatoria BOOLEAN NOT NULL DEFAULT TRUE,
    exige_arquivo BOOLEAN NOT NULL DEFAULT FALSE,
    permite_devolucao BOOLEAN NOT NULL DEFAULT FALSE,
    ativo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_fases_definicao_evento ON fases_definicao(evento_id, ordem);