"""Criação de notificações no sistema (a central do usuário lê as mesmas linhas)."""
from app.extensions import db
from app.models.notificacao import Notificacao
from app.models.user import Usuario


def notificar(destinatario_id, tipo, assunto, objeto_tipo, objeto_id, evento_id=None, submissao_id=None):
    destinatario = Usuario.query.get(destinatario_id) if destinatario_id else None
    if destinatario is None:
        return
    db.session.add(Notificacao(
        evento_id=evento_id,
        submissao_id=submissao_id,
        destinatario_id=destinatario.id,
        destinatario_nome=destinatario.nome,
        destinatario_email=destinatario.email,
        tipo=tipo,
        assunto=assunto,
        objeto_tipo=objeto_tipo,
        objeto_id=str(objeto_id),
        canal='sistema',
        situacao='enviada',
    ))


def notificar_etapa_atribuida(execucao, fase, submissao):
    """B5: o responsável da execução de fase fica sabendo da etapa."""
    titulo = submissao.respostas_dict().get('titulo') or submissao.codigo or 'uma submissão'
    notificar(
        execucao.responsavel_id, 'etapa_atribuida', f'Etapa "{fase.nome}" atribuída a você: "{titulo}"',
        'execucao_fase', execucao.id, evento_id=fase.evento_id, submissao_id=submissao.id,
    )
