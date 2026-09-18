-- Tabelas usadas pelos models de app/models/evento.py que ainda não existiam no banco.

CREATE TABLE IF NOT EXISTS solicitacoes_evento (
    id BIGSERIAL PRIMARY KEY,
    solicitante_id BIGINT NOT NULL REFERENCES usuarios(id),
    situacao VARCHAR(32) NOT NULL DEFAULT 'pendente',
    criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    decidido_por_id BIGINT REFERENCES usuarios(id),
    decidido_em TIMESTAMPTZ,
    motivo_recusa TEXT,
    titulo VARCHAR(255) NOT NULL,
    sigla VARCHAR(64),
    ano INTEGER NOT NULL,
    identificador_pagina VARCHAR(120) NOT NULL UNIQUE,
    tipo VARCHAR(64) NOT NULL,
    cidade VARCHAR(120),
    estado VARCHAR(120),
    pais VARCHAR(120) NOT NULL,
    fuso VARCHAR(80) NOT NULL,
    data_inicio VARCHAR(40) NOT NULL,
    data_termino VARCHAR(40) NOT NULL,
    data_publicacao VARCHAR(40),
    justificativa TEXT NOT NULL,
    evento_pai_id BIGINT,
    chairs_iniciais TEXT DEFAULT '[]',
    versao INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS eventos (
    id BIGSERIAL PRIMARY KEY,
    situacao VARCHAR(32) NOT NULL DEFAULT 'aprovado',
    titulo VARCHAR(255) NOT NULL,
    sigla VARCHAR(64),
    ano INTEGER NOT NULL,
    identificador_pagina VARCHAR(120) NOT NULL UNIQUE,
    tipo VARCHAR(64) NOT NULL,
    cidade VARCHAR(120),
    estado VARCHAR(120),
    pais VARCHAR(120) NOT NULL,
    fuso VARCHAR(80) NOT NULL,
    data_inicio VARCHAR(40) NOT NULL,
    data_termino VARCHAR(40) NOT NULL,
    data_publicacao VARCHAR(40),
    evento_pai_id BIGINT,
    modelo_de_avaliacao VARCHAR(32) NOT NULL DEFAULT 'aberta',
    avaliadores_por_submissao INTEGER NOT NULL DEFAULT 1,
    rebuttal_habilitado BOOLEAN NOT NULL DEFAULT FALSE,
    prazo_rebuttal_dias INTEGER,
    maximo_de_rodadas INTEGER NOT NULL DEFAULT 1,
    nota_de_corte DOUBLE PRECISION,
    limite_submissoes_por_autor INTEGER,
    versao INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS trilhas (
    id BIGSERIAL PRIMARY KEY,
    evento_id BIGINT NOT NULL REFERENCES eventos(id),
    nome VARCHAR(200) NOT NULL,
    descricao TEXT,
    ativa BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS chamadas (
    id BIGSERIAL PRIMARY KEY,
    evento_id BIGINT NOT NULL REFERENCES eventos(id),
    trilha_id BIGINT REFERENCES trilhas(id),
    titulo VARCHAR(255) NOT NULL,
    data_abertura VARCHAR(40) NOT NULL,
    data_limite VARCHAR(40) NOT NULL,
    permite_submissao_apos_prazo BOOLEAN NOT NULL DEFAULT FALSE,
    formatos_aceitos TEXT DEFAULT '[]',
    tamanho_maximo_mb INTEGER NOT NULL DEFAULT 0,
    encerrada_manualmente BOOLEAN NOT NULL DEFAULT FALSE,
    versao INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS submissoes (
    id BIGSERIAL PRIMARY KEY,
    chamada_id BIGINT NOT NULL REFERENCES chamadas(id),
    evento_id BIGINT NOT NULL REFERENCES eventos(id),
    trilha_id BIGINT REFERENCES trilhas(id),
    autor_responsavel_id BIGINT NOT NULL REFERENCES usuarios(id),
    codigo VARCHAR(32) UNIQUE,
    situacao VARCHAR(40) NOT NULL DEFAULT 'rascunho',
    fora_do_prazo BOOLEAN NOT NULL DEFAULT FALSE,
    identificador_externo VARCHAR(120),
    versao_formulario INTEGER NOT NULL DEFAULT 1,
    formulario_versao_id VARCHAR(120) NOT NULL DEFAULT 'formulario-padrao',
    respostas TEXT NOT NULL DEFAULT '{}',
    data_ultimo_salvamento TIMESTAMPTZ,
    data_confirmacao TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS autorias (
    id BIGSERIAL PRIMARY KEY,
    submissao_id BIGINT NOT NULL REFERENCES submissoes(id),
    usuario_id BIGINT REFERENCES usuarios(id),
    nome VARCHAR(200) NOT NULL,
    email VARCHAR(255) NOT NULL,
    instituicao VARCHAR(200) NOT NULL DEFAULT '',
    ordem INTEGER NOT NULL DEFAULT 1,
    correspondente BOOLEAN NOT NULL DEFAULT FALSE,
    eh_responsavel BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS versoes_arquivo (
    id BIGSERIAL PRIMARY KEY,
    submissao_id BIGINT NOT NULL REFERENCES submissoes(id),
    numero INTEGER NOT NULL,
    nome_original VARCHAR(255) NOT NULL,
    tamanho_bytes INTEGER NOT NULL,
    resumo_das_alteracoes TEXT,
    enviado_por VARCHAR(200) NOT NULL,
    data_envio TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    vigente BOOLEAN NOT NULL DEFAULT TRUE,
    caminho_arquivo VARCHAR(500)
);

CREATE TABLE IF NOT EXISTS criterios (
    id BIGSERIAL PRIMARY KEY,
    evento_id BIGINT NOT NULL REFERENCES eventos(id),
    titulo VARCHAR(255) NOT NULL,
    descricao TEXT,
    nota_minima DOUBLE PRECISION NOT NULL DEFAULT 0,
    nota_maxima DOUBLE PRECISION NOT NULL DEFAULT 0,
    peso DOUBLE PRECISION NOT NULL DEFAULT 1,
    ordem INTEGER NOT NULL DEFAULT 1,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    tem_notas BOOLEAN NOT NULL DEFAULT FALSE
);