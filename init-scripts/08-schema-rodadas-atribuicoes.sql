CREATE TABLE IF NOT EXISTS rodadas (
    id BIGSERIAL PRIMARY KEY,
    submissao_id BIGINT NOT NULL REFERENCES submissoes(id),
    evento_id BIGINT NOT NULL REFERENCES eventos(id),
    numero INTEGER NOT NULL DEFAULT 1,
    aberta_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    encerrada_em TIMESTAMPTZ,
    encerrada_por_id BIGINT REFERENCES usuarios(id),
    data_limite_parecer TIMESTAMPTZ,
    UNIQUE (submissao_id, numero)
);

CREATE TABLE IF NOT EXISTS atribuicoes (
    id BIGSERIAL PRIMARY KEY,
    rodada_id BIGINT NOT NULL REFERENCES rodadas(id),
    submissao_id BIGINT NOT NULL REFERENCES submissoes(id),
    evento_id BIGINT NOT NULL REFERENCES eventos(id),
    situacao VARCHAR(20) NOT NULL DEFAULT 'convidado',
    -- 'convidado' | 'aceito' | 'recusado' | 'sem_resposta' | 'conflito' | 'cancelado'
    avaliador_id BIGINT REFERENCES usuarios(id),
    avaliador_nome VARCHAR(200) NOT NULL,
    avaliador_email VARCHAR(255) NOT NULL,
    sem_cadastro BOOLEAN NOT NULL DEFAULT FALSE,
    convidado_por_id BIGINT REFERENCES usuarios(id),
    convidado_por_nome VARCHAR(200),
    convidado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    prazo_resposta TIMESTAMPTZ,
    respondido_em TIMESTAMPTZ,
    justificativa_recusa TEXT,
    motivo_conflito TEXT,
    delegada_de_id BIGINT REFERENCES atribuicoes(id),
    pode_delegar BOOLEAN NOT NULL DEFAULT TRUE,
    lembretes_enviados INTEGER NOT NULL DEFAULT 0,
    ultimo_lembrete_em TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_atribuicoes_rodada ON atribuicoes(rodada_id);
CREATE INDEX IF NOT EXISTS idx_atribuicoes_avaliador ON atribuicoes(avaliador_id, situacao);
CREATE INDEX IF NOT EXISTS idx_rodadas_submissao ON rodadas(submissao_id);