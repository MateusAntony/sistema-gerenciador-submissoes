from datetime import datetime, timedelta

import requests
from flask import Blueprint, current_app, jsonify, request
from itsdangerous import URLSafeTimedSerializer

from app.extensions import db
from app.controllers.auth_controller import usuario_autenticado
from app.models.evento import Autoria, Chamada, Criterio, Evento, ParticipacaoEvento, Submissao, Trilha, VersaoDeArquivo
from app.models.fase import DefinicaoFase
from app.models.execucao_fase import ExecucaoFase
from app.models.user import Usuario
from app.models.rodada import Rodada
from app.models.atribuicao import Atribuicao
from app.models.parecer import Parecer
from app.models.rebuttal import Rebuttal
from app.models.decisao import Decisao

avaliacao_bp = Blueprint('avaliacao', __name__, url_prefix='/api')

DIAS_VALIDADE_CONVITE = 30
DIAS_PRAZO_RESPOSTA_PADRAO = 7


def _json_error(codigo: str, mensagem: str, status: int, **extra):
    payload = {
        'codigo': codigo,
        'mensagem': mensagem,
        'correlacao': f'cor-{codigo}',
    }
    payload.update(extra)
    return jsonify(payload), status


def _eh_chair_do_evento(usuario, evento_id):
    if usuario.administrador:
        return True
    participacao = ParticipacaoEvento.query.filter_by(
        usuario_id=usuario.id, evento_id=evento_id, papel='chair'
    ).first()
    return participacao is not None


def _rodada_com_resumo(rodada):
    dados = rodada.to_dict()
    atribuicoes = Atribuicao.query.filter_by(rodada_id=rodada.id).all()
    ativas = [a for a in atribuicoes if a.situacao not in ('recusado', 'cancelado')]
    aceitas = [a for a in ativas if a.situacao == 'aceito']
    pendentes_lista = [
        {'atribuicaoId': a.id, 'avaliadorNome': a.avaliador_nome}
        for a in ativas if a.situacao in ('convidado', 'sem_resposta')
    ]

    dados['pareceresEsperados'] = len(aceitas)
    ids_aceitas = [a.id for a in aceitas]
    dados['pareceresRecebidos'] = (
        Parecer.query.filter(Parecer.atribuicao_id.in_(ids_aceitas), Parecer.situacao == 'submetido').count()
        if ids_aceitas else 0
    )
    dados['pendentes'] = pendentes_lista

    dados['encerradaPorNome'] = None
    if rodada.encerrada_por_id:
        responsavel = Usuario.query.get(rodada.encerrada_por_id)
        dados['encerradaPorNome'] = responsavel.nome if responsavel else None

    rebuttal = Rebuttal.query.filter_by(rodada_id=rodada.id).first()
    dados['rebuttal'] = {'situacao': rebuttal.situacao, 'prazo': rebuttal.prazo.isoformat() if rebuttal.prazo else None} if rebuttal else None

    decisao = Decisao.query.filter_by(rodada_id=rodada.id).first()
    dados['decisao'] = (
        {'id': decisao.id, 'resultado': decisao.resultado, 'comunicadaEm': decisao.comunicada_em.isoformat() if decisao.comunicada_em else None}
        if decisao else None
    )

    return dados


@avaliacao_bp.route('/eventos/<int:evento_id>/avaliadores', methods=['GET'])
def listar_candidatos_a_avaliador(evento_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)
    if not _eh_chair_do_evento(usuario, evento_id):
        return _json_error('sem_permissao', 'Você não tem permissão para ver os avaliadores deste evento.', 403)

    termo = (request.args.get('q') or '').strip().lower()
    submissao_id = request.args.get('submissaoId')
    # `areas` ainda não é suportado: não há campo de áreas de interesse no cadastro do usuário hoje.

    submissao = Submissao.query.get(submissao_id) if submissao_id else None

    candidatos = []
    for candidato in Usuario.query.filter_by(ativo=True).order_by(Usuario.nome).all():
        if termo and termo not in candidato.nome.lower() and termo not in candidato.email.lower():
            continue

        atribuicoes_abertas = (
            Atribuicao.query
            .filter_by(avaliador_id=candidato.id)
            .filter(Atribuicao.situacao.in_(['convidado', 'aceito']))
            .count()
        )

        impedimento = None
        if submissao is not None:
            if submissao.autor_responsavel_id == candidato.id:
                impedimento = {'motivo': 'autor', 'detalhe': 'É o autor responsável desta submissão.'}
            elif Autoria.query.filter_by(submissao_id=submissao.id, usuario_id=candidato.id).first():
                impedimento = {'motivo': 'coautor', 'detalhe': 'É coautor desta submissão.'}
            else:
                ja_convidado = (
                    Atribuicao.query
                    .filter_by(submissao_id=submissao.id, avaliador_id=candidato.id)
                    .filter(Atribuicao.situacao.notin_(['recusado', 'cancelado']))
                    .first()
                )
                if ja_convidado is not None:
                    impedimento = {'motivo': 'ja_convidado', 'detalhe': 'Já foi convidado para esta submissão.'}

        candidatos.append({
            'usuarioId': candidato.id,
            'nome': candidato.nome,
            'email': candidato.email,
            'instituicao': candidato.instituicao,
            'areasDeInteresse': [],
            'atribuicoesEmAberto': atribuicoes_abertas,
            'impedimento': impedimento,
        })

    return jsonify(candidatos)


@avaliacao_bp.route('/submissoes/<int:submissao_id>/rodadas', methods=['GET'])
def listar_rodadas_da_submissao(submissao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    submissao = Submissao.query.get(submissao_id)
    eh_autor = submissao is not None and submissao.autor_responsavel_id == usuario.id
    eh_chair = submissao is not None and _eh_chair_do_evento(usuario, submissao.evento_id)
    if submissao is None or not (eh_autor or eh_chair):
        return _json_error('submissao_inexistente', 'Submissão não encontrada.', 404)

    rodadas = (
        Rodada.query
        .filter_by(submissao_id=submissao_id)
        .order_by(Rodada.numero)
        .all()
    )
    return jsonify([_rodada_com_resumo(r) for r in rodadas])


# --- Convites de avaliador (token stateless, sem tabela própria) ---

def gerar_token_convite_atribuicao(atribuicao_id: int, email: str) -> str:
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps({'tipo': 'atribuicao', 'atribuicaoId': atribuicao_id, 'email': email}, salt='convite')


def gerar_token_convite_participacao(evento_id: int, papel: str, email: str) -> str:
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(
        {'tipo': 'participacao', 'eventoId': evento_id, 'papel': papel, 'email': email}, salt='convite'
    )


def _enviar_email_convite(destinatario_nome, destinatario_email, assunto, link):
    api_key = current_app.config.get('BREVO_API_KEY')
    if not api_key:
        current_app.logger.info('Convite para %s: %s', destinatario_email, link)
        return
    try:
        requests.post(
            'https://api.brevo.com/v3/smtp/email',
            headers={
                'api-key': api_key,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            json={
                'sender': {
                    'name': current_app.config['BREVO_REMETENTE_NOME'],
                    'email': current_app.config['BREVO_REMETENTE_EMAIL'],
                },
                'to': [{'email': destinatario_email, 'name': destinatario_nome}],
                'subject': assunto,
                'htmlContent': f'<p>Olá, {destinatario_nome}!</p><p>{assunto}</p><p><a href="{link}">{link}</a></p>',
            },
            timeout=10,
        )
    except requests.RequestException as erro:
        current_app.logger.error('Erro ao enviar convite por e-mail: %s', erro)


def _criar_notificacao_convite(atribuicao, evento, submissao):
    from app.models.notificacao import Notificacao
    db.session.add(Notificacao(
        evento_id=evento.id,
        submissao_id=submissao.id,
        destinatario_id=atribuicao.avaliador_id,
        destinatario_nome=atribuicao.avaliador_nome,
        destinatario_email=atribuicao.avaliador_email,
        tipo='convite_avaliacao',
        assunto=f'Convite para avaliar "{submissao.respostas_dict().get("titulo", "uma submissão")}"',
        objeto_tipo='atribuicao',
        objeto_id=str(atribuicao.id),
        canal='sistema' if atribuicao.avaliador_id else 'email',
        situacao='enviada',
    ))


# --- Painel de atribuições de uma submissão ---

@avaliacao_bp.route('/submissoes/<int:submissao_id>/atribuicoes', methods=['GET'])
def painel_de_atribuicoes(submissao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    submissao = Submissao.query.get(submissao_id)
    if submissao is None:
        return _json_error('submissao_nao_encontrada', 'Submissão não encontrada.', 404)
    if not _eh_chair_do_evento(usuario, submissao.evento_id):
        return _json_error('sem_permissao', 'Você não tem permissão para ver este painel.', 403)

    evento = Evento.query.get(submissao.evento_id)
    rodada = (
        Rodada.query.filter_by(submissao_id=submissao_id)
        .order_by(Rodada.numero.desc()).first()
    )

    impedimento = None
    if submissao.situacao == 'rascunho':
        impedimento = {'motivo': 'submissao_nao_confirmada', 'detalhe': 'A submissão ainda não foi confirmada pelo autor.'}
    else:
        fase_pendente = (
            db.session.query(ExecucaoFase)
            .join(DefinicaoFase, DefinicaoFase.id == ExecucaoFase.fase_id)
            .filter(
                ExecucaoFase.submissao_id == submissao_id,
                DefinicaoFase.momento == 'triagem',
                DefinicaoFase.obrigatoria.is_(True),
                ~ExecucaoFase.status.in_(['concluida', 'dispensada']),
            )
            .first()
        )
        if fase_pendente is not None:
            impedimento = {'motivo': 'fase_de_triagem_pendente', 'detalhe': 'Existe uma fase de triagem obrigatória ainda pendente.'}

    atribuicoes = Atribuicao.query.filter_by(rodada_id=rodada.id).all() if rodada else []
    contagem = {
        'aceitos': sum(1 for a in atribuicoes if a.situacao == 'aceito'),
        'recusados': sum(1 for a in atribuicoes if a.situacao == 'recusado'),
        'semResposta': sum(1 for a in atribuicoes if a.situacao == 'sem_resposta'),
        'pendentes': sum(1 for a in atribuicoes if a.situacao == 'convidado'),
    }
    meta = evento.avaliadores_por_submissao if evento else 0
    ativos = contagem['aceitos'] + contagem['pendentes'] + contagem['semResposta']

    return jsonify({
        'submissaoId': submissao.id,
        'rodadaId': rodada.id if rodada else None,
        'metaDeAvaliadores': meta,
        'contagem': contagem,
        'abaixoDaMeta': ativos < meta,
        'acimaDaMeta': ativos > meta,
        'atribuicoes': [a.to_dict() for a in atribuicoes],
        'impedimento': impedimento,
    })


# --- Convite em lote para uma rodada ---

@avaliacao_bp.route('/rodadas/<int:rodada_id>/atribuicoes', methods=['POST'])
def convidar_avaliadores(rodada_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    rodada = Rodada.query.get(rodada_id)
    if rodada is None:
        return _json_error('rodada_nao_encontrada', 'Rodada não encontrada.', 404)
    if not _eh_chair_do_evento(usuario, rodada.evento_id):
        return _json_error('sem_permissao', 'Você não tem permissão para convidar avaliadores.', 403)

    submissao = Submissao.query.get(rodada.submissao_id)
    evento = Evento.query.get(rodada.evento_id)
    convites = request.get_json(silent=True) or []
    if not isinstance(convites, list):
        convites = []

    resultados = []
    for item in convites:
        email = (item or {}).get('email') or ''
        nome = (item or {}).get('nome') or ''
        avaliador_id = (item or {}).get('avaliadorId')

        if not nome.strip() or not email.strip():
            resultados.append({'email': email, 'sucesso': False, 'codigo': 'dados_invalidos', 'mensagem': 'Nome e e-mail são obrigatórios.'})
            continue

        avaliador_usuario = None
        if avaliador_id:
            avaliador_usuario = Usuario.query.get(avaliador_id)
            if avaliador_usuario is None or not avaliador_usuario.ativo:
                resultados.append({'email': email, 'sucesso': False, 'codigo': 'avaliador_invalido', 'mensagem': 'Avaliador não encontrado.'})
                continue
            if submissao.autor_responsavel_id == avaliador_id:
                resultados.append({'email': email, 'sucesso': False, 'codigo': 'autor', 'mensagem': 'É o autor responsável desta submissão.'})
                continue
            if Autoria.query.filter_by(submissao_id=submissao.id, usuario_id=avaliador_id).first():
                resultados.append({'email': email, 'sucesso': False, 'codigo': 'coautor', 'mensagem': 'É coautor desta submissão.'})
                continue
            ja_convidado = (
                Atribuicao.query.filter_by(submissao_id=submissao.id, avaliador_id=avaliador_id)
                .filter(Atribuicao.situacao.notin_(['recusado', 'cancelado']))
                .first()
            )
            if ja_convidado is not None:
                resultados.append({'email': email, 'sucesso': False, 'codigo': 'ja_convidado', 'mensagem': 'Já foi convidado para esta submissão.'})
                continue

        atribuicao = Atribuicao(
            rodada_id=rodada.id,
            submissao_id=submissao.id,
            evento_id=evento.id,
            situacao='convidado',
            avaliador_id=avaliador_id,
            avaliador_nome=nome,
            avaliador_email=email,
            sem_cadastro=avaliador_id is None,
            convidado_por_id=usuario.id,
            convidado_por_nome=usuario.nome,
            convidado_em=datetime.utcnow(),
            prazo_resposta=datetime.utcnow() + timedelta(days=DIAS_PRAZO_RESPOSTA_PADRAO),
        )
        db.session.add(atribuicao)
        db.session.flush()  # garante atribuicao.id antes de gerar o token/objeto

        _criar_notificacao_convite(atribuicao, evento, submissao)

        token = gerar_token_convite_atribuicao(atribuicao.id, email)
        link_base = current_app.config['URL_BASE_FRONTEND']
        if avaliador_id:
            link = f'{link_base}/atribuicoes/{atribuicao.id}'
        else:
            link = f'{link_base}/convites/{token}'
        _enviar_email_convite(nome, email, f'Convite para avaliar uma submissão em {evento.titulo}', link)

        resultados.append({'email': email, 'sucesso': True, 'atribuicao': atribuicao.to_dict()})

    db.session.commit()
    return jsonify(resultados), 201


# --- Painel do evento: submissões abaixo da meta ---

@avaliacao_bp.route('/eventos/<int:evento_id>/atribuicoes', methods=['GET'])
def resumo_de_atribuicoes_do_evento(evento_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    evento = Evento.query.get(evento_id)
    if evento is None:
        return _json_error('evento_nao_encontrado', 'Evento não encontrado.', 404)
    if not _eh_chair_do_evento(usuario, evento_id):
        return _json_error('sem_permissao', 'Você não tem permissão para ver as atribuições deste evento.', 403)

    somente_abaixo_da_meta = request.args.get('abaixo_da_meta') == '1'
    meta = evento.avaliadores_por_submissao

    resultado = []
    submissoes = Submissao.query.filter_by(evento_id=evento_id).filter(Submissao.situacao != 'rascunho').all()
    for submissao in submissoes:
        rodada = (
            Rodada.query.filter_by(submissao_id=submissao.id)
            .order_by(Rodada.numero.desc()).first()
        )
        atribuicoes = Atribuicao.query.filter_by(rodada_id=rodada.id).all() if rodada else []
        contagem = {
            'aceitos': sum(1 for a in atribuicoes if a.situacao == 'aceito'),
            'recusados': sum(1 for a in atribuicoes if a.situacao == 'recusado'),
            'semResposta': sum(1 for a in atribuicoes if a.situacao == 'sem_resposta'),
            'pendentes': sum(1 for a in atribuicoes if a.situacao == 'convidado'),
        }
        ativos = contagem['aceitos'] + contagem['pendentes'] + contagem['semResposta']
        abaixo_da_meta = ativos < meta

        if somente_abaixo_da_meta and not abaixo_da_meta:
            continue

        resultado.append({
            'submissaoId': submissao.id,
            'titulo': submissao.respostas_dict().get('titulo', ''),
            'metaDeAvaliadores': meta,
            'contagem': contagem,
            'abaixoDaMeta': abaixo_da_meta,
        })

    return jsonify(resultado)


# --- Fila do avaliador ---

def _atribuicao_na_fila(atribuicao):
    dados = atribuicao.to_dict()
    submissao = Submissao.query.get(atribuicao.submissao_id)
    evento = Evento.query.get(atribuicao.evento_id)

    autores = None
    if submissao and evento and evento.modelo_de_avaliacao != 'duplo_cega':
        autores_lista = [
            a.nome for a in Autoria.query.filter_by(submissao_id=submissao.id).order_by(Autoria.ordem).all()
        ]
        autores = ', '.join(autores_lista) if autores_lista else None

    trilha_nome = None
    if submissao and submissao.trilha_id:
        trilha = Trilha.query.get(submissao.trilha_id)
        trilha_nome = trilha.nome if trilha else None

    documento = None
    if submissao:
        versao_vigente = VersaoDeArquivo.query.filter_by(submissao_id=submissao.id, vigente=True).first()
        if versao_vigente:
            documento = {'nome': versao_vigente.nome_original, 'tamanhoBytes': versao_vigente.tamanho_bytes}

    dados['submissaoTitulo'] = submissao.respostas_dict().get('titulo', '') if submissao else ''
    dados['autores'] = autores
    dados['eventoTitulo'] = evento.titulo if evento else ''
    dados['trilhaNome'] = trilha_nome
    dados['documento'] = documento
    return dados


@avaliacao_bp.route('/me/atribuicoes', methods=['GET'])
def minhas_atribuicoes():
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    atribuicoes = Atribuicao.query.filter_by(avaliador_id=usuario.id).all()
    resposta = jsonify([_atribuicao_na_fila(a) for a in atribuicoes])
    resposta.headers['Date'] = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    return resposta


@avaliacao_bp.route('/atribuicoes/<int:atribuicao_id>', methods=['GET'])
def obter_atribuicao(atribuicao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    atribuicao = Atribuicao.query.get(atribuicao_id)
    eh_dono = atribuicao is not None and atribuicao.avaliador_id == usuario.id
    eh_chair = atribuicao is not None and _eh_chair_do_evento(usuario, atribuicao.evento_id)
    if atribuicao is None or not (eh_dono or eh_chair):
        return _json_error('atribuicao_nao_encontrada', 'Atribuição não encontrada.', 404)

    dados = _atribuicao_na_fila(atribuicao)
    submissao = Submissao.query.get(atribuicao.submissao_id)
    chamada = Chamada.query.get(submissao.chamada_id) if submissao else None
    evento = Evento.query.get(atribuicao.evento_id)
    criterios = Criterio.query.filter_by(evento_id=atribuicao.evento_id, ativo=True).order_by(Criterio.ordem).all()

    dados['chamadaTitulo'] = chamada.titulo if chamada else ''
    dados['fusoDoEvento'] = evento.fuso if evento else ''
    dados['resumo'] = submissao.respostas_dict().get('resumo') if submissao else None
    dados['criterios'] = [c.to_dict() for c in criterios]
    return jsonify(dados)


# --- Respostas do avaliador convidado ---

@avaliacao_bp.route('/atribuicoes/<int:atribuicao_id>/aceitar', methods=['POST'])
def aceitar_atribuicao(atribuicao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    atribuicao = Atribuicao.query.get(atribuicao_id)
    if atribuicao is None or atribuicao.avaliador_id != usuario.id:
        return _json_error('atribuicao_nao_encontrada', 'Atribuição não encontrada.', 404)
    if atribuicao.situacao != 'convidado':
        return _json_error('atribuicao_ja_respondida', 'Esta atribuição já foi respondida ou cancelada.', 409)

    atribuicao.situacao = 'aceito'
    atribuicao.respondido_em = datetime.utcnow()
    db.session.commit()
    return jsonify(atribuicao.to_dict())


@avaliacao_bp.route('/atribuicoes/<int:atribuicao_id>/recusar', methods=['POST'])
def recusar_atribuicao(atribuicao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    atribuicao = Atribuicao.query.get(atribuicao_id)
    if atribuicao is None or atribuicao.avaliador_id != usuario.id:
        return _json_error('atribuicao_nao_encontrada', 'Atribuição não encontrada.', 404)
    if atribuicao.situacao != 'convidado':
        return _json_error('atribuicao_ja_respondida', 'Esta atribuição já foi respondida ou cancelada.', 409)

    dados = request.get_json(silent=True) or {}
    atribuicao.situacao = 'recusado'
    atribuicao.respondido_em = datetime.utcnow()
    atribuicao.justificativa_recusa = dados.get('justificativa')
    db.session.commit()
    return jsonify(atribuicao.to_dict())


@avaliacao_bp.route('/atribuicoes/<int:atribuicao_id>/conflito', methods=['POST'])
def declarar_conflito(atribuicao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    atribuicao = Atribuicao.query.get(atribuicao_id)
    if atribuicao is None or atribuicao.avaliador_id != usuario.id:
        return _json_error('atribuicao_nao_encontrada', 'Atribuição não encontrada.', 404)
    if atribuicao.situacao != 'convidado':
        return _json_error('atribuicao_ja_respondida', 'Esta atribuição já foi respondida ou cancelada.', 409)

    dados = request.get_json(silent=True) or {}
    atribuicao.situacao = 'conflito'
    atribuicao.respondido_em = datetime.utcnow()
    atribuicao.motivo_conflito = dados.get('motivo')
    db.session.commit()
    return jsonify(atribuicao.to_dict())


# --- Delegação ---

@avaliacao_bp.route('/atribuicoes/<int:atribuicao_id>/delegar', methods=['POST'])
def delegar_atribuicao(atribuicao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    original = Atribuicao.query.get(atribuicao_id)
    if original is None or original.avaliador_id != usuario.id:
        return _json_error('atribuicao_nao_encontrada', 'Atribuição não encontrada.', 404)

    if not original.pode_delegar:
        return _json_error(
            'delegacao_ja_usada', 'Esta atribuição já foi delegada uma vez.', 422
        )

    dados = request.get_json(silent=True) or {}
    nome = (dados.get('nome') or '').strip()
    email = (dados.get('email') or '').strip()
    if not nome or not email:
        return _json_error(
            'dados_do_delegado_incompletos', 'Informe nome e e-mail do delegado.', 422
        )

    submissao = Submissao.query.get(original.submissao_id)
    candidato = Usuario.query.filter_by(email=email, ativo=True).first()

    if candidato is not None:
        if submissao.autor_responsavel_id == candidato.id or Autoria.query.filter_by(
            submissao_id=submissao.id, usuario_id=candidato.id
        ).first():
            return _json_error(
                'delegado_inelegivel', 'O delegado é autor ou coautor desta submissão.', 422
            )
        ja_convidado = (
            Atribuicao.query.filter_by(submissao_id=submissao.id, avaliador_id=candidato.id)
            .filter(Atribuicao.situacao.notin_(['recusado', 'cancelado']))
            .first()
        )
        if ja_convidado is not None:
            return _json_error('ja_convidado', 'O delegado já foi convidado para esta submissão.', 409)
    else:
        if Autoria.query.filter_by(submissao_id=submissao.id, email=email).first():
            return _json_error(
                'delegado_inelegivel', 'O delegado é autor ou coautor desta submissão.', 422
            )

    evento = Evento.query.get(original.evento_id)
    nova = Atribuicao(
        rodada_id=original.rodada_id,
        submissao_id=original.submissao_id,
        evento_id=original.evento_id,
        situacao='convidado',
        avaliador_id=candidato.id if candidato else None,
        avaliador_nome=nome,
        avaliador_email=email,
        sem_cadastro=candidato is None,
        convidado_por_id=usuario.id,
        convidado_por_nome=usuario.nome,
        convidado_em=datetime.utcnow(),
        prazo_resposta=original.prazo_resposta or (datetime.utcnow() + timedelta(days=DIAS_PRAZO_RESPOSTA_PADRAO)),
        delegada_de_id=original.id,
    )
    db.session.add(nova)
    original.pode_delegar = False
    db.session.flush()

    _criar_notificacao_convite(nova, evento, submissao)
    token = gerar_token_convite_atribuicao(nova.id, email)
    link_base = current_app.config['URL_BASE_FRONTEND']
    link = f'{link_base}/atribuicoes/{nova.id}' if candidato else f'{link_base}/convites/{token}'
    _enviar_email_convite(nome, email, f'Convite para avaliar uma submissão em {evento.titulo}', link)

    db.session.commit()
    return jsonify(nova.to_dict()), 201


# --- Cancelamento (chair) ---

@avaliacao_bp.route('/atribuicoes/<int:atribuicao_id>/cancelar', methods=['POST'])
def cancelar_atribuicao(atribuicao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    atribuicao = Atribuicao.query.get(atribuicao_id)
    if atribuicao is None:
        return _json_error('atribuicao_nao_encontrada', 'Atribuição não encontrada.', 404)
    if not _eh_chair_do_evento(usuario, atribuicao.evento_id):
        return _json_error('sem_permissao', 'Você não tem permissão para cancelar esta atribuição.', 403)

    # A checagem de "parecer já submetido" agora usa o modelo de Parecer.
    parecer = Parecer.query.filter_by(atribuicao_id=atribuicao_id).first()
    if parecer is not None and parecer.situacao == 'submetido':
        return _json_error(
            'parecer_submetido', 'Esta atribuição já tem parecer submetido e não pode ser cancelada.', 409
        )

    atribuicao.situacao = 'cancelado'
    db.session.commit()
    return jsonify(atribuicao.to_dict())


# --- Parecer ---

def _obter_ou_criar_parecer(atribuicao_id):
    parecer = Parecer.query.filter_by(atribuicao_id=atribuicao_id).first()
    if parecer is None:
        parecer = Parecer(atribuicao_id=atribuicao_id, situacao='rascunho')
        db.session.add(parecer)
        db.session.commit()
    return parecer


@avaliacao_bp.route('/atribuicoes/<int:atribuicao_id>/parecer', methods=['GET'])
def obter_parecer(atribuicao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    atribuicao = Atribuicao.query.get(atribuicao_id)
    if atribuicao is None or atribuicao.avaliador_id != usuario.id:
        return _json_error('atribuicao_nao_encontrada', 'Atribuição não encontrada.', 404)

    parecer = _obter_ou_criar_parecer(atribuicao_id)
    return jsonify(parecer.to_dict())


@avaliacao_bp.route('/atribuicoes/<int:atribuicao_id>/parecer', methods=['PUT'])
def salvar_parecer(atribuicao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    atribuicao = Atribuicao.query.get(atribuicao_id)
    if atribuicao is None or atribuicao.avaliador_id != usuario.id:
        return _json_error('atribuicao_nao_encontrada', 'Atribuição não encontrada.', 404)

    parecer = _obter_ou_criar_parecer(atribuicao_id)
    if parecer.situacao == 'submetido':
        return _json_error('parecer_imutavel', 'Este parecer já foi submetido e não pode mais ser editado.', 409)

    dados = request.get_json(silent=True) or {}
    if 'notas' in dados and isinstance(dados['notas'], list):
        parecer.set_notas(dados['notas'])
    if 'recomendacao' in dados:
        parecer.recomendacao = dados['recomendacao']
    if 'comentariosAosAutores' in dados:
        parecer.comentarios_aos_autores = dados['comentariosAosAutores']
    if 'comentariosConfidenciais' in dados:
        parecer.comentarios_confidenciais = dados['comentariosConfidenciais']
    if 'nivelDeConfianca' in dados:
        parecer.nivel_de_confianca = dados['nivelDeConfianca']
    if 'arquivo' in dados and isinstance(dados['arquivo'], dict):
        parecer.arquivo_nome = dados['arquivo'].get('nome')
        parecer.arquivo_tamanho_bytes = dados['arquivo'].get('tamanhoBytes')

    parecer.atualizado_em = datetime.utcnow()
    db.session.commit()
    return jsonify(parecer.to_dict())


@avaliacao_bp.route('/atribuicoes/<int:atribuicao_id>/parecer/submeter', methods=['POST'])
def submeter_parecer(atribuicao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    atribuicao = Atribuicao.query.get(atribuicao_id)
    if atribuicao is None or atribuicao.avaliador_id != usuario.id:
        return _json_error('atribuicao_nao_encontrada', 'Atribuição não encontrada.', 404)

    parecer = _obter_ou_criar_parecer(atribuicao_id)
    if parecer.situacao == 'submetido':
        return _json_error('parecer_imutavel', 'Este parecer já foi submetido e não pode mais ser editado.', 409)

    criterios = Criterio.query.filter_by(evento_id=atribuicao.evento_id, ativo=True).order_by(Criterio.ordem).all()
    notas = parecer.get_notas()
    notas_por_criterio = {n.get('criterioId'): n.get('nota') for n in notas if isinstance(n, dict)}

    campos_faltando = {}
    for criterio in criterios:
        nota = notas_por_criterio.get(criterio.id)
        if nota is None:
            campos_faltando[f'nota_{criterio.id}'] = f"Falta a nota do critério '{criterio.titulo}'."
        elif not (criterio.nota_minima <= nota <= criterio.nota_maxima):
            campos_faltando[f'nota_{criterio.id}'] = (
                f"A nota do critério '{criterio.titulo}' deve estar entre "
                f"{criterio.nota_minima} e {criterio.nota_maxima}."
            )

    recomendacoes_validas = {'aceitar', 'aceitar_com_correcoes', 'nova_rodada', 'rejeitar'}
    if parecer.recomendacao not in recomendacoes_validas:
        campos_faltando['recomendacao'] = 'Selecione uma recomendação.'

    if campos_faltando:
        return _json_error('parecer_incompleto', 'Verifique os campos destacados.', 422, campos=campos_faltando)

    peso_total = sum(c.peso for c in criterios) or 1
    pontuacao = sum(notas_por_criterio[c.id] * c.peso for c in criterios) / peso_total

    for criterio in criterios:
        criterio.tem_notas = True

    parecer.situacao = 'submetido'
    parecer.pontuacao_ponderada = round(pontuacao, 2)
    parecer.data_submissao = datetime.utcnow()
    parecer.atualizado_em = datetime.utcnow()
    db.session.commit()
    return jsonify(parecer.to_dict())


# --- Encerrar rodada ---

def _pareceres_pendentes(rodada_id):
    atribuicoes = Atribuicao.query.filter_by(rodada_id=rodada_id).all()
    pendentes = []
    for atribuicao in atribuicoes:
        if atribuicao.situacao in ('convidado', 'sem_resposta'):
            pendentes.append(atribuicao)
        elif atribuicao.situacao == 'aceito':
            parecer = Parecer.query.filter_by(atribuicao_id=atribuicao.id).first()
            if parecer is None or parecer.situacao != 'submetido':
                pendentes.append(atribuicao)
    return pendentes


@avaliacao_bp.route('/rodadas/<int:rodada_id>/encerrar', methods=['POST'])
def encerrar_rodada(rodada_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    rodada = Rodada.query.get(rodada_id)
    if rodada is None:
        return _json_error('rodada_nao_encontrada', 'Rodada não encontrada.', 404)
    if not _eh_chair_do_evento(usuario, rodada.evento_id):
        return _json_error('sem_permissao', 'Você não tem permissão para encerrar esta rodada.', 403)
    if rodada.encerrada_em is not None:
        return _json_error('rodada_ja_encerrada', 'Esta rodada já foi encerrada.', 409)

    dados = request.get_json(silent=True) or {}
    pendentes = _pareceres_pendentes(rodada_id)
    if pendentes and not dados.get('confirmarPendentes'):
        return _json_error(
            'pendentes_sem_confirmacao',
            'Há pareceres pendentes. Envie confirmarPendentes: true para encerrar mesmo assim.',
            409,
            pendentes=[{'atribuicaoId': a.id, 'avaliadorNome': a.avaliador_nome} for a in pendentes],
        )

    rodada.encerrada_em = datetime.utcnow()
    rodada.encerrada_por_id = usuario.id

    evento = Evento.query.get(rodada.evento_id)
    if evento and evento.rebuttal_habilitado and not Rebuttal.query.filter_by(rodada_id=rodada.id).first():
        dias = evento.prazo_rebuttal_dias or 7
        db.session.add(Rebuttal(
            rodada_id=rodada.id,
            situacao='aguardando',
            prazo=datetime.utcnow() + timedelta(days=dias),
        ))

    db.session.commit()
    return jsonify(_rodada_com_resumo(rodada))


# --- Rebuttal ---

@avaliacao_bp.route('/rodadas/<int:rodada_id>/rebuttal', methods=['GET'])
def obter_rebuttal_do_autor(rodada_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    rodada = Rodada.query.get(rodada_id)
    submissao = Submissao.query.get(rodada.submissao_id) if rodada else None
    rebuttal = Rebuttal.query.filter_by(rodada_id=rodada_id).first() if rodada else None

    if rebuttal is None or submissao is None or submissao.autor_responsavel_id != usuario.id:
        return _json_error('rebuttal_inexistente', 'Rebuttal não encontrado.', 404)

    atribuicoes_aceitas = Atribuicao.query.filter_by(rodada_id=rodada_id, situacao='aceito').all()
    pareceres = []
    for indice, atribuicao in enumerate(atribuicoes_aceitas, start=1):
        parecer = Parecer.query.filter_by(atribuicao_id=atribuicao.id, situacao='submetido').first()
        if parecer is None:
            continue
        pareceres.append({
            'rotulo': f'Avaliador {indice}',
            'recomendacao': parecer.recomendacao,
            'comentariosAosAutores': parecer.comentarios_aos_autores,
        })

    dados = rebuttal.to_dict()
    dados['pareceres'] = pareceres
    return jsonify(dados)


@avaliacao_bp.route('/rodadas/<int:rodada_id>/rebuttal', methods=['PUT'])
def salvar_rebuttal(rodada_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    rodada = Rodada.query.get(rodada_id)
    submissao = Submissao.query.get(rodada.submissao_id) if rodada else None
    rebuttal = Rebuttal.query.filter_by(rodada_id=rodada_id).first() if rodada else None

    if rebuttal is None or submissao is None or submissao.autor_responsavel_id != usuario.id:
        return _json_error('rebuttal_inexistente', 'Rebuttal não encontrado.', 404)

    agora = datetime.utcnow()
    if rebuttal.situacao != 'aguardando' or (rebuttal.prazo and agora > rebuttal.prazo):
        return _json_error('rebuttal_fora_do_prazo', 'O prazo para responder este rebuttal já passou.', 409)

    dados = request.get_json(silent=True) or {}
    rebuttal.texto = dados.get('texto')
    if 'versaoId' in dados:
        rebuttal.versao_id = dados['versaoId']

    db.session.commit()
    return jsonify(rebuttal.to_dict())


@avaliacao_bp.route('/rodadas/<int:rodada_id>/rebuttal/enviar', methods=['POST'])
def enviar_rebuttal(rodada_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    rodada = Rodada.query.get(rodada_id)
    submissao = Submissao.query.get(rodada.submissao_id) if rodada else None
    rebuttal = Rebuttal.query.filter_by(rodada_id=rodada_id).first() if rodada else None

    if rebuttal is None or submissao is None or submissao.autor_responsavel_id != usuario.id:
        return _json_error('rebuttal_inexistente', 'Rebuttal não encontrado.', 404)

    agora = datetime.utcnow()
    if rebuttal.situacao != 'aguardando' or (rebuttal.prazo and agora > rebuttal.prazo):
        return _json_error('rebuttal_fora_do_prazo', 'O prazo para responder este rebuttal já passou.', 409)

    dados = request.get_json(silent=True) or {}
    texto = (dados.get('texto') or '').strip()
    if not texto:
        return _json_error('rebuttal_vazio', 'O texto do rebuttal não pode ficar vazio.', 422)

    versao_id = dados.get('versaoId')
    if versao_id is not None:
        versao = VersaoDeArquivo.query.filter_by(id=versao_id, submissao_id=submissao.id).first()
        if versao is None:
            return _json_error('versao_invalida', 'A versão informada não pertence a esta submissão.', 422)

    rebuttal.texto = texto
    rebuttal.versao_id = versao_id
    rebuttal.situacao = 'enviado'
    rebuttal.enviado_em = agora
    rebuttal.enviado_por_nome = usuario.nome
    db.session.commit()
    return jsonify(rebuttal.to_dict())


# --- Decisão ---

RESULTADOS_VALIDOS = {'aceita', 'aceita_com_correcoes', 'nova_rodada', 'rejeitada'}
MAPA_SITUACAO_POR_RESULTADO = {
    'aceita': 'aceita',
    'aceita_com_correcoes': 'aguardando_versao_corrigida',
    'rejeitada': 'rejeitada',
    # 'nova_rodada' só muda a situação quando a nova rodada é de fato aberta (outro bloco).
}


def _criar_notificacao_decisao_comunicada(decisao, rodada, submissao, evento):
    from app.models.notificacao import Notificacao
    autor = Usuario.query.get(submissao.autor_responsavel_id)
    if autor is None:
        return
    db.session.add(Notificacao(
        evento_id=evento.id,
        submissao_id=submissao.id,
        destinatario_id=autor.id,
        destinatario_nome=autor.nome,
        destinatario_email=autor.email,
        tipo='decisao_comunicada',
        assunto=f'Decisão sobre "{submissao.respostas_dict().get("titulo", "sua submissão")}"',
        objeto_tipo='submissao',
        objeto_id=str(submissao.id),
        canal='sistema',
        situacao='enviada',
    ))


@avaliacao_bp.route('/rodadas/<int:rodada_id>/contexto-de-decisao', methods=['GET'])
def contexto_de_decisao(rodada_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    rodada = Rodada.query.get(rodada_id)
    if rodada is None:
        return _json_error('rodada_nao_encontrada', 'Rodada não encontrada.', 404)
    if not _eh_chair_do_evento(usuario, rodada.evento_id):
        return _json_error('sem_permissao', 'Você não tem permissão para ver esta rodada.', 403)

    evento = Evento.query.get(rodada.evento_id)
    atribuicoes_aceitas = Atribuicao.query.filter_by(rodada_id=rodada_id, situacao='aceito').all()

    pareceres = []
    pontuacoes = []
    for indice, atribuicao in enumerate(atribuicoes_aceitas, start=1):
        parecer = Parecer.query.filter_by(atribuicao_id=atribuicao.id, situacao='submetido').first()
        if parecer is None:
            continue
        if parecer.pontuacao_ponderada is not None:
            pontuacoes.append(parecer.pontuacao_ponderada)
        pareceres.append({
            'rotulo': f'Avaliador {indice}',
            'avaliadorNome': atribuicao.avaliador_nome,
            'recomendacao': parecer.recomendacao,
            'pontuacaoPonderada': parecer.pontuacao_ponderada,
            'comentariosAosAutores': parecer.comentarios_aos_autores,
            'comentariosConfidenciais': parecer.comentarios_confidenciais,
        })

    media_ponderada = round(sum(pontuacoes) / len(pontuacoes), 2) if pontuacoes else None
    nota_de_corte = evento.nota_de_corte if evento else None

    rebuttal = Rebuttal.query.filter_by(rodada_id=rodada_id).first()
    pode_abrir_nova_rodada = bool(evento) and rodada.numero < evento.maximo_de_rodadas
    motivo_bloqueio = None if pode_abrir_nova_rodada else 'Limite de rodadas do evento já foi atingido.'

    return jsonify({
        'rodada': _rodada_com_resumo(rodada),
        'pareceres': pareceres,
        'mediaPonderada': media_ponderada,
        'notaDeCorte': nota_de_corte,
        'abaixoDaNotaDeCorte': (media_ponderada is not None and nota_de_corte is not None and media_ponderada < nota_de_corte),
        'rebuttal': rebuttal.to_dict() if rebuttal else None,
        'podeAbrirNovaRodada': pode_abrir_nova_rodada,
        'motivoBloqueioNovaRodada': motivo_bloqueio,
        'maximoDeRodadas': evento.maximo_de_rodadas if evento else None,
    })


@avaliacao_bp.route('/rodadas/<int:rodada_id>/decisao', methods=['POST'])
def registrar_decisao(rodada_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    rodada = Rodada.query.get(rodada_id)
    if rodada is None:
        return _json_error('rodada_nao_encontrada', 'Rodada não encontrada.', 404)
    if not _eh_chair_do_evento(usuario, rodada.evento_id):
        return _json_error('sem_permissao', 'Você não tem permissão para decidir esta rodada.', 403)
    if rodada.encerrada_em is None:
        return _json_error('rodada_aberta', 'A rodada precisa estar encerrada antes de registrar uma decisão.', 409)
    if Decisao.query.filter_by(rodada_id=rodada_id).first() is not None:
        return _json_error('decisao_ja_registrada', 'Esta rodada já tem uma decisão registrada.', 409)

    dados = request.get_json(silent=True) or {}
    resultado = dados.get('resultado')
    justificativa = (dados.get('justificativa') or '').strip()
    prazo_versao_corrigida = dados.get('prazoVersaoCorrigida')

    if resultado not in RESULTADOS_VALIDOS:
        return _json_error('resultado_invalido', 'Resultado de decisão inválido.', 422)
    if not justificativa:
        return _json_error('justificativa_obrigatoria', 'A justificativa é obrigatória.', 422)
    if prazo_versao_corrigida and resultado != 'aceita_com_correcoes':
        return _json_error(
            'prazo_nao_aplicavel', 'O prazo de versão corrigida só se aplica a "aceita_com_correcoes".', 422
        )

    evento = Evento.query.get(rodada.evento_id)
    if resultado == 'nova_rodada' and rodada.numero >= evento.maximo_de_rodadas:
        return _json_error('limite_de_rodadas', 'O limite de rodadas deste evento já foi atingido.', 409)

    prazo_corrigida_dt = None
    if resultado == 'aceita_com_correcoes' and prazo_versao_corrigida:
        try:
            prazo_corrigida_dt = datetime.fromisoformat(prazo_versao_corrigida)
        except (TypeError, ValueError):
            prazo_corrigida_dt = None

    decisao = Decisao(
        rodada_id=rodada_id,
        resultado=resultado,
        justificativa=justificativa,
        decidido_por_id=usuario.id,
        decidido_por_nome=usuario.nome,
        decidido_em=datetime.utcnow(),
        prazo_versao_corrigida=prazo_corrigida_dt,
    )
    db.session.add(decisao)

    submissao = Submissao.query.get(rodada.submissao_id)
    nova_situacao = MAPA_SITUACAO_POR_RESULTADO.get(resultado)
    if nova_situacao:
        submissao.situacao = nova_situacao

    db.session.commit()
    return jsonify(decisao.to_dict()), 201


@avaliacao_bp.route('/rodadas/<int:rodada_id>/decisao', methods=['GET'])
def obter_decisao_da_rodada(rodada_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    rodada = Rodada.query.get(rodada_id)
    decisao = Decisao.query.filter_by(rodada_id=rodada_id).first() if rodada else None
    if rodada is None or decisao is None:
        return _json_error('decisao_inexistente', 'Decisão não encontrada.', 404)

    eh_chair = _eh_chair_do_evento(usuario, rodada.evento_id)
    submissao = Submissao.query.get(rodada.submissao_id)
    eh_autor = submissao is not None and submissao.autor_responsavel_id == usuario.id

    if eh_chair or (eh_autor and decisao.comunicada_em is not None):
        return jsonify(decisao.to_dict())
    return _json_error('decisao_inexistente', 'Decisão não encontrada.', 404)


@avaliacao_bp.route('/decisoes/<int:decisao_id>/comunicar', methods=['POST'])
def comunicar_decisao(decisao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    decisao = Decisao.query.get(decisao_id)
    if decisao is None:
        return _json_error('decisao_inexistente', 'Decisão não encontrada.', 404)

    rodada = Rodada.query.get(decisao.rodada_id)
    if not _eh_chair_do_evento(usuario, rodada.evento_id):
        return _json_error('sem_permissao', 'Você não tem permissão para comunicar esta decisão.', 403)

    if decisao.comunicada_em is None:
        decisao.comunicada_em = datetime.utcnow()
        submissao = Submissao.query.get(rodada.submissao_id)
        evento = Evento.query.get(rodada.evento_id)
        _criar_notificacao_decisao_comunicada(decisao, rodada, submissao, evento)
        db.session.commit()

    return jsonify(decisao.to_dict())


# --- Fila de decisões do evento ---

def _estagio_da_submissao(submissao, rodada, decisao):
    if decisao is not None:
        if decisao.comunicada_em is None:
            return 'decidida_nao_comunicada'
        if decisao.resultado == 'aceita_com_correcoes':
            return 'aguardando_versao_corrigida'
        return 'comunicada'

    if rodada is None:
        return 'em_avaliacao'
    if rodada.encerrada_em is not None:
        return 'aguardando_decisao'

    rebuttal = Rebuttal.query.filter_by(rodada_id=rodada.id).first()
    if rebuttal is not None and rebuttal.situacao == 'aguardando':
        return 'em_rebuttal'
    if not _pareceres_pendentes(rodada.id):
        return 'pronta_para_encerrar'
    return 'em_avaliacao'


@avaliacao_bp.route('/eventos/<int:evento_id>/decisoes', methods=['GET'])
def fila_de_decisoes_do_evento(evento_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    evento = Evento.query.get(evento_id)
    if evento is None:
        return _json_error('evento_inexistente', 'Evento não encontrado.', 404)
    if not _eh_chair_do_evento(usuario, evento_id):
        return _json_error('sem_permissao', 'Você não tem permissão para ver a fila de decisões.', 403)

    linhas = []
    submissoes = Submissao.query.filter_by(evento_id=evento_id).filter(Submissao.situacao != 'rascunho').all()
    for submissao in submissoes:
        rodada = Rodada.query.filter_by(submissao_id=submissao.id).order_by(Rodada.numero.desc()).first()
        decisao = Decisao.query.filter_by(rodada_id=rodada.id).first() if rodada else None

        aceitas = Atribuicao.query.filter_by(rodada_id=rodada.id, situacao='aceito').all() if rodada else []
        recebidos = sum(
            1 for a in aceitas
            if Parecer.query.filter_by(atribuicao_id=a.id, situacao='submetido').first() is not None
        )

        linhas.append({
            'submissaoId': submissao.id,
            'codigo': submissao.codigo,
            'titulo': submissao.respostas_dict().get('titulo', ''),
            'rodadaId': rodada.id if rodada else None,
            'numero': rodada.numero if rodada else None,
            'pareceresRecebidos': recebidos,
            'pareceresEsperados': len(aceitas),
            'estagio': _estagio_da_submissao(submissao, rodada, decisao),
            'decisao': (
                {'id': decisao.id, 'resultado': decisao.resultado, 'comunicadaEm': decisao.comunicada_em.isoformat() if decisao.comunicada_em else None}
                if decisao else None
            ),
        })

    return jsonify(linhas)


@avaliacao_bp.route('/eventos/<int:evento_id>/decisoes/comunicar-lote', methods=['POST'])
def comunicar_decisoes_em_lote(evento_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    evento = Evento.query.get(evento_id)
    if evento is None:
        return _json_error('evento_inexistente', 'Evento não encontrado.', 404)
    if not _eh_chair_do_evento(usuario, evento_id):
        return _json_error('sem_permissao', 'Você não tem permissão para comunicar decisões deste evento.', 403)

    dados = request.get_json(silent=True) or {}
    ids = dados.get('decisaoIds') or []

    resultados = []
    for decisao_id in ids:
        decisao = Decisao.query.get(decisao_id)
        if decisao is None:
            resultados.append({'decisaoId': decisao_id, 'sucesso': False, 'mensagem': 'Decisão não encontrada.'})
            continue
        rodada = Rodada.query.get(decisao.rodada_id)
        if rodada is None or rodada.evento_id != evento_id:
            resultados.append({'decisaoId': decisao_id, 'sucesso': False, 'mensagem': 'Decisão não pertence a este evento.'})
            continue

        if decisao.comunicada_em is None:
            decisao.comunicada_em = datetime.utcnow()
            submissao = Submissao.query.get(rodada.submissao_id)
            _criar_notificacao_decisao_comunicada(decisao, rodada, submissao, evento)

        resultados.append({'decisaoId': decisao_id, 'sucesso': True})

    db.session.commit()
    return jsonify(resultados)


# --- Nova rodada ---

@avaliacao_bp.route('/submissoes/<int:submissao_id>/rodadas/<int:numero>/avaliadores-preservaveis', methods=['GET'])
def avaliadores_preservaveis(submissao_id, numero):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    rodada = Rodada.query.filter_by(submissao_id=submissao_id, numero=numero).first()
    if rodada is None:
        return _json_error('rodada_nao_encontrada', 'Rodada não encontrada.', 404)
    if not _eh_chair_do_evento(usuario, rodada.evento_id):
        return _json_error('sem_permissao', 'Você não tem permissão para ver esta rodada.', 403)

    atribuicoes = Atribuicao.query.filter_by(rodada_id=rodada.id).all()
    return jsonify([
        {
            'atribuicaoId': a.id,
            'avaliadorNome': a.avaliador_nome,
            'aceitou': a.situacao == 'aceito',
        }
        for a in atribuicoes
    ])


@avaliacao_bp.route('/submissoes/<int:submissao_id>/rodadas', methods=['POST'])
def abrir_nova_rodada(submissao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    submissao = Submissao.query.get(submissao_id)
    if submissao is None:
        return _json_error('submissao_nao_encontrada', 'Submissão não encontrada.', 404)
    if not _eh_chair_do_evento(usuario, submissao.evento_id):
        return _json_error('sem_permissao', 'Você não tem permissão para abrir uma nova rodada.', 403)

    ultima_rodada = (
        Rodada.query.filter_by(submissao_id=submissao_id).order_by(Rodada.numero.desc()).first()
    )
    if ultima_rodada is None:
        return _json_error('rodada_nao_encontrada', 'Nenhuma rodada encontrada para esta submissão.', 404)

    decisao = Decisao.query.filter_by(rodada_id=ultima_rodada.id).first()
    if decisao is None or decisao.resultado != 'nova_rodada':
        return _json_error(
            'decisao_nao_e_nova_rodada', 'A última decisão desta submissão não pede uma nova rodada.', 409
        )

    evento = Evento.query.get(submissao.evento_id)
    if ultima_rodada.numero >= evento.maximo_de_rodadas:
        return _json_error('limite_de_rodadas', 'O limite de rodadas deste evento já foi atingido.', 409)

    dados = request.get_json(silent=True) or {}
    prazo_bruto = dados.get('dataLimiteParecer')
    prazo_parecer = None
    if prazo_bruto:
        try:
            prazo_parecer = datetime.fromisoformat(prazo_bruto)
        except (TypeError, ValueError):
            prazo_parecer = None
        if prazo_parecer is not None and prazo_parecer < datetime.utcnow():
            return _json_error('prazo_no_passado', 'O prazo de parecer não pode estar no passado.', 422)

    nova_rodada = Rodada(
        submissao_id=submissao_id,
        evento_id=submissao.evento_id,
        numero=ultima_rodada.numero + 1,
        aberta_em=datetime.utcnow(),
        data_limite_parecer=prazo_parecer,
    )
    db.session.add(nova_rodada)
    db.session.flush()

    submissao.situacao = 'em_avaliacao'

    ids_preservados = dados.get('avaliadoresPreservados') or []
    for atribuicao_id in ids_preservados:
        original = Atribuicao.query.get(atribuicao_id)
        if original is None or original.rodada_id != ultima_rodada.id:
            continue

        nova_atribuicao = Atribuicao(
            rodada_id=nova_rodada.id,
            submissao_id=submissao_id,
            evento_id=submissao.evento_id,
            situacao='convidado',
            avaliador_id=original.avaliador_id,
            avaliador_nome=original.avaliador_nome,
            avaliador_email=original.avaliador_email,
            sem_cadastro=original.sem_cadastro,
            convidado_por_id=usuario.id,
            convidado_por_nome=usuario.nome,
            convidado_em=datetime.utcnow(),
            prazo_resposta=datetime.utcnow() + timedelta(days=DIAS_PRAZO_RESPOSTA_PADRAO),
        )
        db.session.add(nova_atribuicao)
        db.session.flush()

        _criar_notificacao_convite(nova_atribuicao, evento, submissao)
        token = gerar_token_convite_atribuicao(nova_atribuicao.id, nova_atribuicao.avaliador_email)
        link_base = current_app.config['URL_BASE_FRONTEND']
        link = (
            f'{link_base}/atribuicoes/{nova_atribuicao.id}'
            if nova_atribuicao.avaliador_id else f'{link_base}/convites/{token}'
        )
        _enviar_email_convite(
            nova_atribuicao.avaliador_nome, nova_atribuicao.avaliador_email,
            f'Convite para avaliar novamente uma submissão em {evento.titulo}', link,
        )

    db.session.commit()
    return jsonify(_rodada_com_resumo(nova_rodada)), 201