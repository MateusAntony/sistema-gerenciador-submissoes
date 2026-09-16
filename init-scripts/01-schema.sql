-- Ids sao UUID gerados pela aplicacao (uuid4); gen_random_uuid() e nativo no Postgres >= 13 e cobre inserts fora do ORM.

CREATE TYPE papel_enum AS ENUM ('chair', 'avaliador', 'responsavel_etapa');

CREATE TABLE IF NOT EXISTS usuarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evento_id UUID NOT NULL,
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    papel papel_enum NOT NULL,
    areas_interesse TEXT,
    ativo BOOLEAN DEFAULT TRUE,
    criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_usuario_evento_papel UNIQUE (evento_id, usuario_id, papel)
);
