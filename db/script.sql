BEGIN;

CREATE TYPE papel_usuario AS ENUM (
    'chair',
    'avaliador',
    'responsavel_etapa'
);

CREATE TYPE tipo_evento AS ENUM (
    'conferencia',
    'periodico',
    'chamada_interna',
    'outro'
);

CREATE TYPE modelo_avaliacao AS ENUM (
    'aberta',
    'simples_cega',
    'duplo_cega'
);

CREATE TYPE status_evento AS ENUM (
    'rascunho',
    'pendente_aprovacao',
    'aprovado',
    'recusado',
    'publicado',
    'encerrado'
);

CREATE TYPE status_solicitacao AS ENUM (
    'pendente',
    'aprovada',
    'recusada'
);

CREATE TYPE status_chamada AS ENUM (
    'rascunho',
    'aberta',
    'encerrada',
    'cancelada'
);

CREATE TYPE status_submissao AS ENUM (
    'rascunho',
    'submetida',
    'em_avaliacao',
    'aguardando_rebuttal',
    'aguardando_decisao',
    'aceita',
    'aceita_com_correcoes',
    'aguardando_versao_corrigida',
    'rejeitada',
    'retirada',
    'em_producao',
    'concluida'
);

CREATE TYPE status_rodada AS ENUM (
    'aberta',
    'encerrada'
);

CREATE TYPE situacao_convite AS ENUM (
    'convidado',
    'aceito',
    'recusado',
    'sem_resposta',
    'cancelado'
);

CREATE TYPE recomendacao_parecer AS ENUM (
    'aceitar',
    'aceitar_com_correcoes',
    'nova_rodada',
    'rejeitar'
);

CREATE TYPE situacao_parecer AS ENUM (
    'rascunho',
    'submetido'
);

CREATE TYPE status_rebuttal AS ENUM (
    'aguardando',
    'enviado',
    'expirado'
);

CREATE TYPE resultado_decisao AS ENUM (
    'aceita',
    'aceita_com_correcoes',
    'nova_rodada',
    'rejeitada'
);

CREATE TYPE status_execucao_etapa AS ENUM (
    'pendente',
    'em_andamento',
    'aguardando_autor',
    'concluida',
    'dispensada'
);

CREATE TYPE canal_notificacao AS ENUM (
    'email',
    'sistema'
);

CREATE TYPE status_notificacao AS ENUM (
    'pendente',
    'enviada',
    'falha'
);

CREATE TYPE operacao_log AS ENUM (
    'insercao',
    'atualizacao',
    'exclusao'
);

CREATE TABLE usuarios (
    id BIGSERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    email_confirmado BOOLEAN NOT NULL DEFAULT FALSE,
    senha_hash VARCHAR(255) NOT NULL,
    instituicao VARCHAR(200),
    pais VARCHAR(100),
    identificador_orcid VARCHAR(30),
    administrador BOOLEAN NOT NULL DEFAULT FALSE,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE eventos (
    id BIGSERIAL PRIMARY KEY,
    evento_pai_id BIGINT
        REFERENCES eventos(id),
    titulo VARCHAR(500) NOT NULL,
    sigla VARCHAR(50) NOT NULL,
    ano INT NOT NULL
        CHECK (ano >= 1900),
    identificador_pagina VARCHAR(100) NOT NULL UNIQUE,
    tipo_evento tipo_evento NOT NULL,
    cidade VARCHAR(150),
    estado VARCHAR(150),
    pais VARCHAR(100),
    fuso_horario VARCHAR(60) NOT NULL,
    data_inicio DATE,
    data_fim DATE,
    data_publicacao TIMESTAMPTZ,
    modelo_avaliacao modelo_avaliacao NOT NULL,
    avaliadores_por_submissao INT NOT NULL
        CHECK (avaliadores_por_submissao >= 1),
    prazo_resposta_convite_dias INT NOT NULL
        CHECK (prazo_resposta_convite_dias >= 1),
    permite_rebuttal BOOLEAN NOT NULL DEFAULT FALSE,
    prazo_rebuttal_dias INT,
    maximo_rodadas INT NOT NULL
        CHECK (maximo_rodadas >= 1),
    nota_corte NUMERIC(6,2),
    limite_submissoes_por_autor INT
        CHECK (limite_submissoes_por_autor >= 1),
    status status_evento NOT NULL,
    criado_por BIGINT NOT NULL
        REFERENCES usuarios(id),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_evento_datas
        CHECK (
            data_fim IS NULL
            OR data_inicio IS NULL
            OR data_fim >= data_inicio
        ),
    CONSTRAINT chk_evento_rebuttal
        CHECK (
            permite_rebuttal = TRUE
            OR prazo_rebuttal_dias IS NULL
        ),
    CONSTRAINT chk_evento_prazo_rebuttal
        CHECK (
            prazo_rebuttal_dias IS NULL
            OR prazo_rebuttal_dias >= 1
        ),
    CONSTRAINT chk_evento_nota_corte
        CHECK (
            nota_corte IS NULL
            OR nota_corte >= 0
        )
);

CREATE TABLE participacoes_evento (
    id BIGSERIAL PRIMARY KEY,
    evento_id BIGINT NOT NULL
        REFERENCES eventos(id),
    usuario_id BIGINT NOT NULL
        REFERENCES usuarios(id),
    papel papel_usuario NOT NULL,
    areas_interesse TEXT,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (evento_id, usuario_id, papel)
);

CREATE TABLE solicitacoes_evento (
    id BIGSERIAL PRIMARY KEY,
    evento_id BIGINT NOT NULL UNIQUE
        REFERENCES eventos(id),
    solicitante_id BIGINT NOT NULL
        REFERENCES usuarios(id),
    justificativa TEXT NOT NULL,
    status status_solicitacao NOT NULL,
    parecer_administrador TEXT,
    analisado_por BIGINT
        REFERENCES usuarios(id),
    solicitado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    analisado_em TIMESTAMPTZ
);

CREATE TABLE trilhas (
    id BIGSERIAL PRIMARY KEY,
    evento_id BIGINT NOT NULL
        REFERENCES eventos(id),
    nome VARCHAR(200) NOT NULL,
    descricao TEXT,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    UNIQUE (evento_id, nome)
);

CREATE TABLE chamadas (
    id BIGSERIAL PRIMARY KEY,
    evento_id BIGINT NOT NULL
        REFERENCES eventos(id),
    titulo VARCHAR(300) NOT NULL,
    descricao TEXT,
    data_abertura TIMESTAMPTZ NOT NULL,
    data_limite_submissao TIMESTAMPTZ NOT NULL,
    permite_submissao_apos_prazo BOOLEAN NOT NULL DEFAULT FALSE,
    formatos_aceitos VARCHAR(200) NOT NULL,
    tamanho_maximo_mb INT NOT NULL
        CHECK (tamanho_maximo_mb > 0),
    status status_chamada NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_chamada_datas
        CHECK (data_limite_submissao >= data_abertura)
);

CREATE TABLE criterios_avaliacao (
    id BIGSERIAL PRIMARY KEY,
    evento_id BIGINT NOT NULL
        REFERENCES eventos(id),
    titulo VARCHAR(300) NOT NULL,
    descricao TEXT,
    nota_minima NUMERIC(6,2) NOT NULL,
    nota_maxima NUMERIC(6,2) NOT NULL,
    peso NUMERIC(5,2) NOT NULL,
    ordem INT NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT chk_criterio_notas
        CHECK (nota_maxima > nota_minima),
    CONSTRAINT chk_criterio_peso
        CHECK (peso >= 0),
    CONSTRAINT chk_criterio_ordem
        CHECK (ordem >= 1),

    UNIQUE (evento_id, ordem)
);

CREATE TABLE etapas_producao (
    id BIGSERIAL PRIMARY KEY,
    evento_id BIGINT NOT NULL
        REFERENCES eventos(id),
    nome VARCHAR(200) NOT NULL,
    descricao TEXT,
    ordem INT NOT NULL,
    prazo_padrao_dias INT NOT NULL,
    responsavel_padrao_id BIGINT
        REFERENCES usuarios(id),
    obrigatoria BOOLEAN NOT NULL DEFAULT TRUE,
    exige_arquivo BOOLEAN NOT NULL DEFAULT FALSE,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT chk_etapa_ordem
        CHECK (ordem >= 1),
    CONSTRAINT chk_etapa_prazo
        CHECK (prazo_padrao_dias >= 0),

    UNIQUE (evento_id, ordem)
);

CREATE TABLE arquivos (
    id BIGSERIAL PRIMARY KEY,
    nome_original VARCHAR(300) NOT NULL,
    caminho VARCHAR(500) NOT NULL,
    tipo_mime VARCHAR(120) NOT NULL,
    tamanho_bytes BIGINT NOT NULL,
    soma_verificacao VARCHAR(64) NOT NULL,
    enviado_por BIGINT NOT NULL
        REFERENCES usuarios(id),
    enviado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_arquivo_tamanho
        CHECK (tamanho_bytes >= 0),

    UNIQUE (caminho)
);

CREATE TABLE submissoes (
    id BIGSERIAL PRIMARY KEY,
    chamada_id BIGINT NOT NULL
        REFERENCES chamadas(id),
    trilha_id BIGINT
        REFERENCES trilhas(id),
    autor_responsavel_id BIGINT NOT NULL
        REFERENCES usuarios(id),
    codigo VARCHAR(30) NOT NULL,
    titulo VARCHAR(500) NOT NULL,
    resumo TEXT NOT NULL,
    palavras_chave VARCHAR(500) NOT NULL,
    status status_submissao NOT NULL,
    rodada_atual INT,
    fora_do_prazo BOOLEAN NOT NULL DEFAULT FALSE,
    identificador_externo VARCHAR(100),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    submetido_em TIMESTAMPTZ,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_submissao_rodada
        CHECK (
            rodada_atual IS NULL
            OR rodada_atual >= 1
        ),

    UNIQUE (chamada_id, codigo)
);

CREATE TABLE autorias (
    id BIGSERIAL PRIMARY KEY,
    submissao_id BIGINT NOT NULL
        REFERENCES submissoes(id),
    usuario_id BIGINT
        REFERENCES usuarios(id),
    nome VARCHAR(200) NOT NULL,
    email VARCHAR(255) NOT NULL,
    instituicao VARCHAR(200),
    ordem INT NOT NULL,
    autor_correspondente BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT chk_autoria_ordem
        CHECK (ordem >= 1),

    UNIQUE (submissao_id, ordem)
);

CREATE TABLE versoes_submissao (
    id BIGSERIAL PRIMARY KEY,
    submissao_id BIGINT NOT NULL
        REFERENCES submissoes(id),
    numero INT NOT NULL,
    arquivo_id BIGINT NOT NULL
        REFERENCES arquivos(id),
    resumo_alteracoes TEXT,
    enviado_por BIGINT NOT NULL
        REFERENCES usuarios(id),
    enviado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_versao_numero
        CHECK (numero >= 1),

    UNIQUE (submissao_id, numero)
);

CREATE TABLE rodadas_avaliacao (
    id BIGSERIAL PRIMARY KEY,
    submissao_id BIGINT NOT NULL
        REFERENCES submissoes(id),
    numero INT NOT NULL,
    data_inicio TIMESTAMPTZ NOT NULL,
    data_limite_parecer TIMESTAMPTZ NOT NULL,
    status status_rodada NOT NULL,
    encerrada_em TIMESTAMPTZ,

    CONSTRAINT chk_rodada_numero
        CHECK (numero >= 1),
    CONSTRAINT chk_rodada_prazo
        CHECK (data_limite_parecer >= data_inicio),

    UNIQUE (submissao_id, numero)
);

CREATE TABLE atribuicoes_avaliacao (
    id BIGSERIAL PRIMARY KEY,
    rodada_id BIGINT NOT NULL
        REFERENCES rodadas_avaliacao(id),
    avaliador_id BIGINT NOT NULL
        REFERENCES usuarios(id),
    atribuido_por BIGINT NOT NULL
        REFERENCES usuarios(id),
    situacao_convite situacao_convite NOT NULL,
    conflito_interesse BOOLEAN NOT NULL DEFAULT FALSE,
    justificativa_recusa TEXT,
    data_convite TIMESTAMPTZ NOT NULL,
    data_limite_resposta TIMESTAMPTZ NOT NULL,
    data_resposta TIMESTAMPTZ,
    lembretes_enviados INT NOT NULL DEFAULT 0,

    CONSTRAINT chk_atribuicao_prazo
        CHECK (data_limite_resposta >= data_convite),
    CONSTRAINT chk_atribuicao_lembretes
        CHECK (lembretes_enviados >= 0),

    UNIQUE (rodada_id, avaliador_id)
);

CREATE TABLE pareceres (
    id BIGSERIAL PRIMARY KEY,
    atribuicao_id BIGINT NOT NULL UNIQUE
        REFERENCES atribuicoes_avaliacao(id),
    recomendacao recomendacao_parecer NOT NULL,
    pontuacao_total NUMERIC(8,2),
    comentarios_autores TEXT,
    comentarios_organizacao TEXT,
    nivel_confianca INT,
    arquivo_id BIGINT
        REFERENCES arquivos(id),
    situacao situacao_parecer NOT NULL,
    submetido_em TIMESTAMPTZ,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_parecer_confianca
        CHECK (
            nivel_confianca IS NULL
            OR nivel_confianca BETWEEN 1 AND 5
        )
);

CREATE TABLE notas_parecer (
    id BIGSERIAL PRIMARY KEY,
    parecer_id BIGINT NOT NULL
        REFERENCES pareceres(id),
    criterio_id BIGINT NOT NULL
        REFERENCES criterios_avaliacao(id),
    nota NUMERIC(6,2) NOT NULL,

    UNIQUE (parecer_id, criterio_id)
);

CREATE TABLE rebuttals (
    id BIGSERIAL PRIMARY KEY,
    rodada_id BIGINT NOT NULL UNIQUE
        REFERENCES rodadas_avaliacao(id),
    prazo_limite TIMESTAMPTZ NOT NULL,
    texto_resposta TEXT,
    versao_submissao_id BIGINT
        REFERENCES versoes_submissao(id),
    enviado_por BIGINT
        REFERENCES usuarios(id),
    enviado_em TIMESTAMPTZ,
    status status_rebuttal NOT NULL
);

CREATE TABLE decisoes (
    id BIGSERIAL PRIMARY KEY,
    submissao_id BIGINT NOT NULL
        REFERENCES submissoes(id),
    rodada_id BIGINT NOT NULL UNIQUE
        REFERENCES rodadas_avaliacao(id),
    resultado resultado_decisao NOT NULL,
    justificativa TEXT NOT NULL,
    decidido_por BIGINT NOT NULL
        REFERENCES usuarios(id),
    decidido_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    comunicado_em TIMESTAMPTZ
);

CREATE TABLE execucoes_etapa (
    id BIGSERIAL PRIMARY KEY,
    submissao_id BIGINT NOT NULL
        REFERENCES submissoes(id),
    etapa_id BIGINT NOT NULL
        REFERENCES etapas_producao(id),
    responsavel_id BIGINT
        REFERENCES usuarios(id),
    status status_execucao_etapa NOT NULL,
    data_inicio TIMESTAMPTZ,
    prazo TIMESTAMPTZ,
    data_conclusao TIMESTAMPTZ,
    arquivo_resultado_id BIGINT
        REFERENCES arquivos(id),
    observacoes TEXT,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (submissao_id, etapa_id)
);

CREATE TABLE notificacoes (
    id BIGSERIAL PRIMARY KEY,
    usuario_id BIGINT NOT NULL
        REFERENCES usuarios(id),
    evento_id BIGINT
        REFERENCES eventos(id),
    submissao_id BIGINT
        REFERENCES submissoes(id),
    tipo VARCHAR(80) NOT NULL,
    assunto VARCHAR(300) NOT NULL,
    corpo TEXT NOT NULL,
    canal canal_notificacao NOT NULL,
    status status_notificacao NOT NULL,
    identificador_provedor VARCHAR(120),
    tentativas INT NOT NULL DEFAULT 0,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    enviado_em TIMESTAMPTZ,

    CONSTRAINT chk_notificacao_tentativas
        CHECK (tentativas >= 0)
);

CREATE TABLE log_auditoria (
    id BIGSERIAL PRIMARY KEY,
    tabela VARCHAR(80) NOT NULL,
    registro_id BIGINT NOT NULL,
    operacao operacao_log NOT NULL,
    dados_anteriores JSONB,
    dados_novos JSONB,
    usuario_id BIGINT
        REFERENCES usuarios(id),
    endereco_ip VARCHAR(45) NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- EVENTOS
CREATE INDEX idx_eventos_evento_pai ON eventos(evento_pai_id);
CREATE INDEX idx_eventos_criado_por ON eventos(criado_por);
CREATE INDEX idx_eventos_status ON eventos(status);

-- PARTICIPAÇÕES
CREATE INDEX idx_participacoes_usuario ON participacoes_evento(usuario_id);
CREATE INDEX idx_participacoes_evento ON participacoes_evento(evento_id);

-- SOLICITAÇÕES
CREATE INDEX idx_solicitacoes_status ON solicitacoes_evento(status);
CREATE INDEX idx_solicitacoes_solicitante ON solicitacoes_evento(solicitante_id);

-- TRILHAS
CREATE INDEX idx_trilhas_evento ON trilhas(evento_id);

-- CHAMADAS
CREATE INDEX idx_chamadas_evento ON chamadas(evento_id);
CREATE INDEX idx_chamadas_status ON chamadas(status);
CREATE INDEX idx_chamadas_prazo ON chamadas(data_limite_submissao);

-- CRITÉRIOS
CREATE INDEX idx_criterios_evento ON criterios_avaliacao(evento_id);

-- ETAPAS
CREATE INDEX idx_etapas_evento ON etapas_producao(evento_id);
CREATE INDEX idx_etapas_responsavel ON etapas_producao(responsavel_padrao_id);

-- ARQUIVOS
CREATE INDEX idx_arquivos_enviado_por ON arquivos(enviado_por);

-- SUBMISSÕES
CREATE INDEX idx_submissoes_chamada ON submissoes(chamada_id);
CREATE INDEX idx_submissoes_trilha ON submissoes(trilha_id);
CREATE INDEX idx_submissoes_autor ON submissoes(autor_responsavel_id);
CREATE INDEX idx_submissoes_status ON submissoes(status);
CREATE INDEX idx_submissoes_codigo ON submissoes(codigo);

-- AUTORIAS
CREATE INDEX idx_autorias_submissao ON autorias(submissao_id);
CREATE INDEX idx_autorias_usuario ON autorias(usuario_id);

-- VERSÕES
CREATE INDEX idx_versoes_submissao ON versoes_submissao(submissao_id);
CREATE INDEX idx_versoes_arquivo ON versoes_submissao(arquivo_id);

-- RODADAS
CREATE INDEX idx_rodadas_submissao ON rodadas_avaliacao(submissao_id);
CREATE INDEX idx_rodadas_status ON rodadas_avaliacao(status);

-- ATRIBUIÇÕES
CREATE INDEX idx_atribuicoes_rodada ON atribuicoes_avaliacao(rodada_id);
CREATE INDEX idx_atribuicoes_avaliador ON atribuicoes_avaliacao(avaliador_id);
CREATE INDEX idx_atribuicoes_status ON atribuicoes_avaliacao(situacao_convite);
CREATE INDEX idx_atribuicoes_prazo ON atribuicoes_avaliacao(data_limite_resposta);

-- PARECERES
CREATE INDEX idx_pareceres_atribuicao ON pareceres(atribuicao_id);
CREATE INDEX idx_pareceres_situacao ON pareceres(situacao);

-- NOTAS
CREATE INDEX idx_notas_parecer ON notas_parecer(parecer_id);
CREATE INDEX idx_notas_criterio ON notas_parecer(criterio_id);

-- REBUTTALS
CREATE INDEX idx_rebuttals_status ON rebuttals(status);
CREATE INDEX idx_rebuttals_prazo ON rebuttals(prazo_limite);

-- DECISÕES
CREATE INDEX idx_decisoes_submissao ON decisoes(submissao_id);
CREATE INDEX idx_decisoes_resultado ON decisoes(resultado);

-- EXECUÇÕES
CREATE INDEX idx_execucoes_submissao ON execucoes_etapa(submissao_id);
CREATE INDEX idx_execucoes_etapa ON execucoes_etapa(etapa_id);
CREATE INDEX idx_execucoes_responsavel ON execucoes_etapa(responsavel_id);
CREATE INDEX idx_execucoes_status ON execucoes_etapa(status);

-- NOTIFICAÇÕES
CREATE INDEX idx_notificacoes_usuario ON notificacoes(usuario_id);
CREATE INDEX idx_notificacoes_evento ON notificacoes(evento_id);
CREATE INDEX idx_notificacoes_submissao ON notificacoes(submissao_id);
CREATE INDEX idx_notificacoes_status ON notificacoes(status);
CREATE INDEX idx_notificacoes_pendentes ON notificacoes(status, criado_em);

-- AUDITORIA
CREATE INDEX idx_auditoria_tabela_registro ON log_auditoria(tabela, registro_id);
CREATE INDEX idx_auditoria_usuario ON log_auditoria(usuario_id);
CREATE INDEX idx_auditoria_data ON log_auditoria(criado_em);
CREATE INDEX idx_auditoria_operacao ON log_auditoria(operacao);

CREATE OR REPLACE FUNCTION fn_atualizar_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.atualizado_em = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_usuarios_updated_at
BEFORE UPDATE ON usuarios
FOR EACH ROW
EXECUTE FUNCTION fn_atualizar_updated_at();

CREATE TRIGGER trg_eventos_updated_at
BEFORE UPDATE ON eventos
FOR EACH ROW
EXECUTE FUNCTION fn_atualizar_updated_at();

CREATE TRIGGER trg_chamadas_updated_at
BEFORE UPDATE ON chamadas
FOR EACH ROW
EXECUTE FUNCTION fn_atualizar_updated_at();

CREATE TRIGGER trg_submissoes_updated_at
BEFORE UPDATE ON submissoes
FOR EACH ROW
EXECUTE FUNCTION fn_atualizar_updated_at();

CREATE TRIGGER trg_pareceres_updated_at
BEFORE UPDATE ON pareceres
FOR EACH ROW
EXECUTE FUNCTION fn_atualizar_updated_at();

CREATE TRIGGER trg_execucoes_etapa_updated_at
BEFORE UPDATE ON execucoes_etapa
FOR EACH ROW
EXECUTE FUNCTION fn_atualizar_updated_at();

CREATE OR REPLACE FUNCTION fn_registrar_auditoria()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_usuario_id BIGINT;
    v_endereco_ip VARCHAR(45);
BEGIN

    BEGIN
        v_usuario_id :=
            NULLIF(current_setting('app.usuario_id', true), '')::BIGINT;
    EXCEPTION
        WHEN OTHERS THEN
            v_usuario_id := NULL;
    END;

    v_endereco_ip :=
        COALESCE(
            NULLIF(current_setting('app.endereco_ip', true), ''),
            '0.0.0.0'
        );

    IF TG_OP = 'INSERT' THEN
        INSERT INTO log_auditoria (
            tabela,
            registro_id,
            operacao,
            dados_anteriores,
            dados_novos,
            usuario_id,
            endereco_ip
        )
        VALUES (
            TG_TABLE_NAME,
            NEW.id,
            'insercao',
            NULL,
            to_jsonb(NEW),
            v_usuario_id,
            v_endereco_ip
        );
        RETURN NEW;

    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO log_auditoria (
            tabela,
            registro_id,
            operacao,
            dados_anteriores,
            dados_novos,
            usuario_id,
            endereco_ip
        )
        VALUES (
            TG_TABLE_NAME,
            NEW.id,
            'atualizacao',
            to_jsonb(OLD),
            to_jsonb(NEW),
            v_usuario_id,
            v_endereco_ip
        );
        RETURN NEW;

    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO log_auditoria (
            tabela,
            registro_id,
            operacao,
            dados_anteriores,
            dados_novos,
            usuario_id,
            endereco_ip
        )
        VALUES (
            TG_TABLE_NAME,
            OLD.id,
            'exclusao',
            to_jsonb(OLD),
            NULL,
            v_usuario_id,
            v_endereco_ip
        );
        RETURN OLD;
    END IF;

    RETURN NULL;
END;
$$;

CREATE TRIGGER trg_auditoria_eventos
AFTER INSERT OR UPDATE OR DELETE ON eventos
FOR EACH ROW
EXECUTE FUNCTION fn_registrar_auditoria();

CREATE TRIGGER trg_auditoria_chamadas
AFTER INSERT OR UPDATE OR DELETE ON chamadas
FOR EACH ROW
EXECUTE FUNCTION fn_registrar_auditoria();

CREATE TRIGGER trg_auditoria_submissoes
AFTER INSERT OR UPDATE OR DELETE ON submissoes
FOR EACH ROW
EXECUTE FUNCTION fn_registrar_auditoria();

CREATE TRIGGER trg_auditoria_versoes
AFTER INSERT OR UPDATE OR DELETE ON versoes_submissao
FOR EACH ROW
EXECUTE FUNCTION fn_registrar_auditoria();

CREATE TRIGGER trg_auditoria_atribuicoes
AFTER INSERT OR UPDATE OR DELETE ON atribuicoes_avaliacao
FOR EACH ROW
EXECUTE FUNCTION fn_registrar_auditoria();

CREATE TRIGGER trg_auditoria_pareceres
AFTER INSERT OR UPDATE OR DELETE ON pareceres
FOR EACH ROW
EXECUTE FUNCTION fn_registrar_auditoria();

CREATE TRIGGER trg_auditoria_decisoes
AFTER INSERT OR UPDATE OR DELETE ON decisoes
FOR EACH ROW
EXECUTE FUNCTION fn_registrar_auditoria();

CREATE TRIGGER trg_auditoria_execucoes
AFTER INSERT OR UPDATE OR DELETE ON execucoes_etapa
FOR EACH ROW
EXECUTE FUNCTION fn_registrar_auditoria();

COMMIT;
