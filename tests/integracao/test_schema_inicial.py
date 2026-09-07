"""Testes do schema inicial versionado — API-02 AC1..AC4, AD-004, AD-005, AD-018."""

from flask_migrate import upgrade
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.extensions import db

TABELAS_ESPERADAS = (
    "usuarios",
    "tokens_confirmacao_email",
    "sessoes",
    "tentativas_login",
    "emails_enviados",
    "solicitacoes_evento",
    "solicitacao_chairs_iniciais",
    "eventos",
    "participacoes_evento",
    "convites",
    "trilhas",
    "chamadas",
    "criterios_avaliacao",
    "formularios_chamada",
    "fases_evento",
    "submissoes",
    "notas_parecer",
)

CHECKS_ESPERADOS = (
    "ck_eventos_rebuttal_com_prazo",
    "ck_eventos_avaliadores_por_submissao",
    "ck_eventos_maximo_rodadas",
    "ck_chamadas_data_limite_apos_abertura",
    "ck_criterios_avaliacao_peso",
    "ck_criterios_avaliacao_faixa_de_nota",
    "ck_convites_avaliacao_com_submissao",
)

CONSULTA_DE_PK = text(
    """
    SELECT coluna.data_type
      FROM information_schema.table_constraints AS restricao
      JOIN information_schema.key_column_usage AS uso
        ON uso.constraint_name = restricao.constraint_name
      JOIN information_schema.columns AS coluna
        ON coluna.table_name = restricao.table_name
       AND coluna.column_name = uso.column_name
     WHERE restricao.constraint_type = 'PRIMARY KEY'
       AND restricao.table_name = :tabela
    """
)


def test_toda_tabela_esperada_existe_com_chave_primaria_uuid(sessao):
    for tabela in TABELAS_ESPERADAS:
        tipos_da_pk = sessao.execute(CONSULTA_DE_PK, {"tabela": tabela}).scalars().all()

        assert tipos_da_pk == ["uuid"], f"{tabela} nao tem chave primaria UUID unica"


def test_participacoes_evento_aponta_para_eventos_por_chave_estrangeira(sessao):
    tabelas_referenciadas = (
        sessao.execute(
            text(
                """
                SELECT DISTINCT alvo.relname
                  FROM pg_constraint AS restricao
                  JOIN pg_class AS origem ON origem.oid = restricao.conrelid
                  JOIN pg_class AS alvo ON alvo.oid = restricao.confrelid
                 WHERE restricao.contype = 'f'
                   AND origem.relname = 'participacoes_evento'
                """
            )
        )
        .scalars()
        .all()
    )

    assert "eventos" in tabelas_referenciadas


def test_os_checks_declarados_no_design_existem_no_banco(sessao):
    nomes = (
        sessao.execute(
            text("SELECT conname FROM pg_constraint WHERE contype = 'c'")
        )
        .scalars()
        .all()
    )

    for check in CHECKS_ESPERADOS:
        assert check in nomes


def test_o_check_de_rebuttal_recusa_prazo_ausente(sessao):
    solicitante = sessao.execute(
        text(
            "INSERT INTO usuarios (nome, email, senha_hash) "
            "VALUES ('Chair', 'chair.rebuttal@exemplo.test', 'hash') RETURNING id"
        )
    ).scalar()
    solicitacao = sessao.execute(
        text(
            "INSERT INTO solicitacoes_evento "
            "(solicitante_id, titulo, ano, identificador_pagina) "
            "VALUES (:solicitante, 'Evento', 2026, 'evento-rebuttal') RETURNING id"
        ),
        {"solicitante": solicitante},
    ).scalar()

    try:
        sessao.execute(
            text(
                "INSERT INTO eventos "
                "(solicitacao_id, situacao, titulo, ano, identificador_pagina, "
                " rebuttal_habilitado) "
                "VALUES (:solicitacao, 'aprovado', 'Evento', 2026, 'evento-rebuttal', true)"
            ),
            {"solicitacao": solicitacao},
        )
    except IntegrityError as erro:
        assert "ck_eventos_rebuttal_com_prazo" in str(erro)
    else:
        raise AssertionError("o banco aceitou rebuttal habilitado sem prazo")


def test_o_schema_manual_deixou_de_ser_fonte_de_verdade(raiz_do_projeto):
    assert not (raiz_do_projeto / "init-scripts" / "01-schema.sql").exists()

    compose = (raiz_do_projeto / "docker-compose.yml").read_text(encoding="utf-8")

    assert "init-scripts" not in compose


def test_upgrade_repetido_nao_altera_o_schema(aplicacao, diretorio_de_migrations):
    def retrato():
        with aplicacao.app_context(), db.engine.connect() as conexao:
            tabelas = (
                conexao.execute(
                    text(
                        "SELECT tablename FROM pg_tables "
                        "WHERE schemaname = 'public' ORDER BY tablename"
                    )
                )
                .scalars()
                .all()
            )
            versao = conexao.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
        return tabelas, versao

    antes = retrato()
    with aplicacao.app_context():
        upgrade(directory=str(diretorio_de_migrations))

    assert retrato() == antes
