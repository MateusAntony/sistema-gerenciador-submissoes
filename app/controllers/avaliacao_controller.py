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
    # Pareceres ainda não existem neste bloco (chegam no próximo); fica 0 por ora.
    dados['pareceresRecebidos'] = 0
    dados['pendentes'] = pendentes_lista

    dados['encerradaPorNome'] = None
    if rodada.encerrada_por_id:
        responsavel = Usuario.query.get(rodada.encerrada_por_id)
        dados['encerradaPorNome'] = responsavel.nome if responsavel else None

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