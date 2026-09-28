"""Cenários de teste montados pelas mesmas rotas que o front usa.

Só o que não tem rota (usuário com e-mail confirmado, evento já aprovado com
chair) é gravado direto no banco; o resto passa pela API, para que o teste
alcance os mesmos ramos que a interface.
"""
import io
from itertools import count

from app.extensions import bcrypt, db
from app.models.evento import Chamada, Evento, ParticipacaoEvento
from app.models.rodada import Rodada
from app.models.user import Usuario

SENHA_PADRAO = 'senha-bem-forte-1'
_sequencia = count(1)


class Fabrica:
    def __init__(self, app):
        self.app = app

    # --- gravação direta (não há rota para isto) ---

    def usuario(self, nome=None, email=None, administrador=False, senha=SENHA_PADRAO):
        numero = next(_sequencia)
        usuario = Usuario(
            nome=nome or f'Pessoa {numero}',
            email=email or f'pessoa{numero}@teste.br',
            senha_hash=bcrypt.generate_password_hash(senha).decode('utf-8'),
            instituicao='UEFS',
            pais='Brasil',
            email_confirmado=True,
            administrador=administrador,
            ativo=True,
        )
        db.session.add(usuario)
        db.session.commit()
        return usuario

    def evento(self, chair=None, situacao='aprovado', **campos):
        numero = next(_sequencia)
        dados = dict(
            situacao=situacao,
            titulo=f'Evento {numero}',
            sigla=f'EV{numero}',
            ano=2026,
            identificador_pagina=f'evento-{numero}',
            tipo='conferencia',
            pais='Brasil',
            fuso='America/Bahia',
            data_inicio='2026-11-10',
            data_termino='2026-11-12',
            modelo_de_avaliacao='aberta',
            avaliadores_por_submissao=1,
            rebuttal_habilitado=False,
            maximo_de_rodadas=1,
            versao=1,
        )
        dados.update(campos)
        evento = Evento(**dados)
        db.session.add(evento)
        db.session.flush()
        if chair is not None:
            db.session.add(ParticipacaoEvento(evento_id=evento.id, usuario_id=chair.id, papel='chair'))
        db.session.commit()
        return evento

    def chamada(self, evento, **campos):
        dados = dict(
            evento_id=evento.id,
            titulo='Chamada principal',
            data_abertura='2026-01-01T00:00',
            data_limite='2099-12-31T23:59',
            formatos_aceitos='["pdf"]',
            tamanho_maximo_mb=10,
        )
        dados.update(campos)
        chamada = Chamada(**dados)
        db.session.add(chamada)
        db.session.commit()
        return chamada

    # --- pela API ---

    def cliente(self, usuario=None):
        cliente = self.app.test_client()
        if usuario is not None:
            with cliente.session_transaction() as sessao:
                sessao['user_id'] = usuario.id
        return cliente

    def enviar_versao(self, cliente, submissao_id, nome='trabalho.pdf', conteudo=b'%PDF-1.4 conteudo'):
        resposta = cliente.post(
            f'/api/submissoes/{submissao_id}/versoes',
            data={'arquivo': (io.BytesIO(conteudo), nome), 'nomeArquivo': nome, 'tamanhoBytes': str(len(conteudo))},
            content_type='multipart/form-data',
        )
        assert resposta.status_code == 201, resposta.get_json()
        return resposta.get_json()

    def submissao_confirmada(self, autor, chamada, titulo='Trabalho de teste', conteudo=b'%PDF-1.4 v1'):
        cliente = self.cliente(autor)
        criada = cliente.post(f'/api/chamadas/{chamada.id}/submissoes', json={})
        assert criada.status_code == 201, criada.get_json()
        submissao_id = int(criada.get_json()['id'])

        salva = cliente.patch(f'/api/submissoes/{submissao_id}', json={
            'respostas': {'titulo': titulo, 'resumo': 'Um resumo.'},
        })
        assert salva.status_code == 200, salva.get_json()

        self.enviar_versao(cliente, submissao_id, conteudo=conteudo)

        confirmada = cliente.post(f'/api/submissoes/{submissao_id}/confirmar')
        assert confirmada.status_code == 200, confirmada.get_json()
        return submissao_id

    def rodada_atual(self, submissao_id):
        return (
            Rodada.query.filter_by(submissao_id=submissao_id)
            .order_by(Rodada.numero.desc()).first()
        )

    def convidar(self, chair, rodada_id, avaliador):
        resposta = self.cliente(chair).post(f'/api/rodadas/{rodada_id}/atribuicoes', json=[
            {'avaliadorId': avaliador.id, 'nome': avaliador.nome, 'email': avaliador.email},
        ])
        assert resposta.status_code == 201, resposta.get_json()
        resultado = resposta.get_json()[0]
        assert resultado['sucesso'], resultado
        return resultado['atribuicao']['id']

    def aceitar(self, avaliador, atribuicao_id):
        resposta = self.cliente(avaliador).post(f'/api/atribuicoes/{atribuicao_id}/aceitar')
        assert resposta.status_code == 200, resposta.get_json()
