"""Testes de ponta a ponta de `POST .../aprovar` — API-12 AC3, AC4, AC7, AC8 (T32).

A aprovacao e o unico caminho pelo qual um evento nasce. Aqui: os padroes com
que ele nasce, o 409 que carrega quem decidiu, e a prova de que duas aprovacoes
simultaneas produzem um evento so.
"""

import uuid
from datetime import date, datetime, timezone

from flask_jwt_extended import create_access_token
from sqlalchemy import create_engine, text

from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.eventos.repository import EventoRepository, SolicitacaoRepository


def rota(solicitacao_id) -> str:
    return f"/api/admin/solicitacoes-evento/{solicitacao_id}/aprovar"


def criar_usuario(
    email: str = "organizador@exemplo.test", *, administrador: bool = False
) -> Usuario:
    usuario = ContaRepository.criar(
        nome="Ada Lovelace", email=email, senha_hash="hash-irrelevante"
    )
    usuario.email_confirmado = True
    usuario.administrador = administrador
    return usuario


def criar_administrador(email: str = "admin@exemplo.test") -> Usuario:
    return criar_usuario(email=email, administrador=True)


def cabecalhos(usuario: Usuario) -> dict:
    return {"Authorization": f"Bearer {create_access_token(identity=str(usuario.id))}"}


def criar_solicitacao(
    solicitante: Usuario,
    *,
    situacao: str = "pendente",
    decidido_por: Usuario | None = None,
    titulo: str = "Simpósio de Extensão",
    identificador: str | None = None,
):
    return SolicitacaoRepository.criar(
        solicitante_id=solicitante.id,
        situacao=situacao,
        titulo=titulo,
        sigla="SEXT",
        ano=2026,
        identificador_pagina=identificador or f"sol-{uuid.uuid4().hex[:8]}",
        tipo="conferencia",
        cidade="Feira de Santana",
        pais="Brasil",
        fuso="America/Bahia",
        data_inicio=date(2026, 5, 1),
        data_termino=date(2026, 5, 3),
        versao=1,
        decidido_por_id=None if decidido_por is None else decidido_por.id,
        decidido_em=(
            None
            if decidido_por is None
            else datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
        ),
    )


# AC3 — 200 `{ solicitacao, evento }`, com a solicitacao `aprovada` decidida.


def test_a_aprovacao_responde_200_com_a_solicitacao_e_o_evento(cliente, sessao):
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(criar_usuario(), identificador="simposio-2026")

    resposta = cliente.post(
        rota(solicitacao.id), headers=cabecalhos(administrador)
    )

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert set(corpo) == {"solicitacao", "evento"}
    assert corpo["solicitacao"]["situacao"] == "aprovada"
    assert corpo["solicitacao"]["decididoPorId"] == str(administrador.id)
    assert corpo["solicitacao"]["decididoEm"].endswith("Z")
    assert corpo["evento"]["situacao"] == "aprovado"
    assert corpo["evento"]["identificadorPagina"] == "simposio-2026"


def test_a_aprovacao_copia_os_dados_da_solicitacao_para_o_evento(cliente, sessao):
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(criar_usuario(), titulo="Congresso de Computação")

    evento = cliente.post(
        rota(solicitacao.id), headers=cabecalhos(administrador)
    ).get_json()["evento"]

    assert evento["titulo"] == "Congresso de Computação"
    assert evento["sigla"] == "SEXT"
    assert evento["ano"] == 2026
    assert evento["tipo"] == "conferencia"
    assert evento["cidade"] == "Feira de Santana"
    assert evento["pais"] == "Brasil"
    assert evento["fuso"] == "America/Bahia"
    assert evento["dataInicio"] == "2026-05-01"
    assert evento["dataTermino"] == "2026-05-03"


def test_a_aprovacao_persiste_o_evento_ligado_a_solicitacao(cliente, sessao):
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(criar_usuario())

    cliente.post(rota(solicitacao.id), headers=cabecalhos(administrador))

    evento = EventoRepository.por_solicitacao(solicitacao.id)
    assert evento is not None
    assert SolicitacaoRepository.por_id(solicitacao.id).situacao == "aprovada"


# AC4 — os cinco padroes com que o evento nasce.


def test_o_evento_nasce_com_o_modelo_de_avaliacao_aberta(cliente, sessao):
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(criar_usuario())

    evento = cliente.post(
        rota(solicitacao.id), headers=cabecalhos(administrador)
    ).get_json()["evento"]

    assert evento["modeloDeAvaliacao"] == "aberta"


def test_o_evento_nasce_com_um_avaliador_por_submissao(cliente, sessao):
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(criar_usuario())

    evento = cliente.post(
        rota(solicitacao.id), headers=cabecalhos(administrador)
    ).get_json()["evento"]

    assert evento["avaliadoresPorSubmissao"] == 1


def test_o_evento_nasce_com_o_rebuttal_desabilitado(cliente, sessao):
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(criar_usuario())

    evento = cliente.post(
        rota(solicitacao.id), headers=cabecalhos(administrador)
    ).get_json()["evento"]

    assert evento["rebuttalHabilitado"] is False


def test_o_evento_nasce_com_uma_rodada_no_maximo(cliente, sessao):
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(criar_usuario())

    evento = cliente.post(
        rota(solicitacao.id), headers=cabecalhos(administrador)
    ).get_json()["evento"]

    assert evento["maximoDeRodadas"] == 1


def test_o_evento_nasce_na_versao_um(cliente, sessao):
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(criar_usuario())

    evento = cliente.post(
        rota(solicitacao.id), headers=cabecalhos(administrador)
    ).get_json()["evento"]

    assert evento["versao"] == 1


# AC7 — aprovar solicitacao ja decidida e 409 carregando quem decidiu e quando.


def test_a_aprovacao_de_solicitacao_ja_decidida_responde_409_com_quem_decidiu(
    cliente, sessao
):
    administrador = criar_administrador()
    quem_decidiu = criar_administrador(email="outro-admin@exemplo.test")
    solicitacao = criar_solicitacao(
        criar_usuario(), situacao="aprovada", decidido_por=quem_decidiu
    )

    resposta = cliente.post(rota(solicitacao.id), headers=cabecalhos(administrador))

    assert resposta.status_code == 409
    corpo = resposta.get_json()
    assert corpo["codigo"] == "solicitacao_ja_decidida"
    assert corpo["decididoPorId"] == str(quem_decidiu.id)
    assert corpo["decididoEm"] == "2026-04-01T12:00:00Z"
    assert corpo["situacao"] == "aprovada"
    assert "correlacao" in corpo
    assert "mensagem" in corpo


def test_a_segunda_aprovacao_sequencial_nao_cria_um_segundo_evento(cliente, sessao):
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(criar_usuario())

    primeira = cliente.post(rota(solicitacao.id), headers=cabecalhos(administrador))
    segunda = cliente.post(rota(solicitacao.id), headers=cabecalhos(administrador))

    assert primeira.status_code == 200
    assert segunda.status_code == 409
    assert segunda.get_json()["decididoPorId"] == str(administrador.id)


# AC8 — solicitacao inexistente e 404; e a fila e do administrador.


def test_a_aprovacao_de_solicitacao_inexistente_responde_404(cliente, sessao):
    resposta = cliente.post(
        rota(uuid.uuid4()), headers=cabecalhos(criar_administrador())
    )

    assert resposta.status_code == 404
    assert resposta.get_json()["codigo"] == "solicitacao_inexistente"


def test_a_aprovacao_por_quem_nao_e_administrador_responde_403(cliente, sessao):
    solicitante = criar_usuario()
    solicitacao = criar_solicitacao(solicitante)

    resposta = cliente.post(rota(solicitacao.id), headers=cabecalhos(solicitante))

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "sem_permissao"
    assert EventoRepository.por_solicitacao(solicitacao.id) is None


def test_a_aprovacao_sem_token_responde_401(cliente, sessao):
    solicitacao = criar_solicitacao(criar_usuario())

    resposta = cliente.post(rota(solicitacao.id))

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"


# Edge Case — duas aprovacoes **simultaneas**: so uma cria evento.
#
# A fixture `sessao` mantem tudo numa transacao so, entao a concorrencia real
# precisa de duas conexoes proprias e de dados comitados. As duas transacoes
# abrem **antes** de qualquer uma decidir e se sobrepoem no tempo; o
# `SELECT ... FOR UPDATE` e o que as serializa. O cenario e criado e apagado
# pelo proprio teste, para nao deixar rastro em `sgs_test`.


def test_duas_aprovacoes_simultaneas_criam_um_evento_so(aplicacao):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from app.core.erros import Conflito
    from app.extensions import db
    from app.modules.eventos.services.solicitacao import SolicitacaoService

    motor = create_engine(aplicacao.config["SQLALCHEMY_DATABASE_URI"])
    marca = f"simultanea-{uuid.uuid4().hex[:8]}@exemplo.test"

    with motor.begin() as preparacao:
        solicitante_id = preparacao.execute(
            text(
                "INSERT INTO usuarios (nome, email, senha_hash) "
                "VALUES ('Solicitante', :email, 'x') RETURNING id"
            ),
            {"email": marca},
        ).scalar_one()
        administrador_id = preparacao.execute(
            text(
                "INSERT INTO usuarios (nome, email, senha_hash, administrador) "
                "VALUES ('Admin', :email, 'x', true) RETURNING id"
            ),
            {"email": f"admin-{marca}"},
        ).scalar_one()
        solicitacao_id = preparacao.execute(
            text(
                "INSERT INTO solicitacoes_evento "
                "(solicitante_id, situacao, titulo, ano, identificador_pagina, "
                " data_inicio, data_termino, versao) "
                "VALUES (:solicitante, 'pendente', 'Simultânea', 2026, "
                ":identificador, '2026-05-01', '2026-05-03', 1) RETURNING id"
            ),
            {
                "solicitante": solicitante_id,
                "identificador": f"simultanea-{uuid.uuid4().hex[:8]}",
            },
        ).scalar_one()

    # As duas transacoes abrem e so entao qualquer uma tenta decidir: a barreira
    # garante que a segunda ja esteja dentro da sua transacao quando a primeira
    # le a solicitacao. Sem o `SELECT ... FOR UPDATE`, as duas leem `pendente`
    # e as duas criam evento — e a asserção de contagem falha.
    portao = Barrier(2)

    def aprovar():
        """Uma aprovacao completa, em transacao propria, do inicio ao commit."""
        conexao = motor.connect()
        transacao = conexao.begin()
        sessao_local = db.sessionmaker(bind=conexao)()
        try:
            with aplicacao.app_context():
                db.session.registry.set(sessao_local)
                try:
                    # Abre a transacao no banco antes de soltar a outra thread.
                    sessao_local.execute(text("SELECT 1"))
                    portao.wait(timeout=10)
                    SolicitacaoService.aprovar(solicitacao_id, administrador_id)
                    sessao_local.flush()
                except Conflito as conflito:
                    transacao.rollback()
                    return conflito
                finally:
                    db.session.registry.clear()
            transacao.commit()
            return None
        finally:
            sessao_local.close()
            conexao.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(lambda _: aprovar(), range(2)))

        conflitos = [r for r in resultados if isinstance(r, Conflito)]
        assert len(conflitos) == 1, "exatamente uma das duas deve ser recusada"
        assert conflitos[0].codigo == "solicitacao_ja_decidida"

        with motor.connect() as leitura:
            eventos = leitura.execute(
                text(
                    "SELECT count(*) FROM eventos WHERE solicitacao_id = :solicitacao"
                ),
                {"solicitacao": solicitacao_id},
            ).scalar_one()
        assert eventos == 1, "so uma das aprovacoes pode ter criado evento"
    finally:
        with motor.begin() as limpeza:
            limpeza.execute(
                text("DELETE FROM eventos WHERE solicitacao_id = :solicitacao"),
                {"solicitacao": solicitacao_id},
            )
            limpeza.execute(
                text("DELETE FROM solicitacoes_evento WHERE id = :solicitacao"),
                {"solicitacao": solicitacao_id},
            )
            limpeza.execute(
                text("DELETE FROM usuarios WHERE email LIKE :marca"),
                {"marca": f"%{marca}"},
            )
        motor.dispose()
