CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TYPE papel_enum AS ENUM ('chair', 'avaliador', 'responsavel_etapa');

CREATE TABLE IF NOT EXISTS usuarios (
    id BIGSERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    email_confirmado BOOLEAN DEFAULT FALSE,
    senha_hash VARCHAR(255) NOT NULL,
    instituicao VARCHAR(200),
    pais VARCHAR(100),
    identificador_orcid VARCHAR(30),
    administrador BOOLEAN DEFAULT FALSE,
    ativo BOOLEAN DEFAULT TRUE,
    criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS participacoes_evento (
    id BIGSERIAL PRIMARY KEY,
    evento_id BIGINT NOT NULL,
    usuario_id BIGINT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    papel papel_enum NOT NULL,
    areas_interesse TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_usuario_evento_papel UNIQUE (evento_id, usuario_id, papel)
);
