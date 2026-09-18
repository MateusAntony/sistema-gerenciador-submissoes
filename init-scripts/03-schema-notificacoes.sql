CREATE TABLE IF NOT EXISTS notificacoes (
    id BIGSERIAL PRIMARY KEY,
    evento_id BIGINT NOT NULL REFERENCES eventos(id),
    submissao_id BIGINT REFERENCES submissoes(id),
    destinatario_id BIGINT REFERENCES usuarios(id),
    destinatario_nome VARCHAR(200) NOT NULL,
    destinatario_email VARCHAR(255) NOT NULL,
    tipo VARCHAR(64) NOT NULL,
    assunto VARCHAR(255) NOT NULL,
    objeto_tipo VARCHAR(32) NOT NULL,       -- 'submissao' | 'atribuicao' | 'execucao_fase'
    objeto_id VARCHAR(64) NOT NULL,
    canal VARCHAR(16) NOT NULL DEFAULT 'sistema',   -- 'email' | 'sistema'
    situacao VARCHAR(16) NOT NULL DEFAULT 'pendente', -- 'pendente' | 'enviada' | 'falha'
    tentativas INTEGER NOT NULL DEFAULT 0,
    maximo_de_tentativas INTEGER NOT NULL DEFAULT 3,
    id_provedor VARCHAR(120),
    erro_do_provedor TEXT,
    administrador_avisado BOOLEAN NOT NULL DEFAULT FALSE,
    criada_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    atualizada_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    lida_em TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_notificacoes_destinatario ON notificacoes(destinatario_id);
CREATE INDEX IF NOT EXISTS idx_notificacoes_evento ON notificacoes(evento_id);