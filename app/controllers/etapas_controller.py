from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from app import notificacoes
from app.ids import id_numerico
from app.extensions import db
from app.controllers.auth_controller import usuario_autenticado
from app.models.evento import Chamada, Evento, ParticipacaoEvento, Submissao, VersaoDeArquivo
from app.models.passo import PassoEnvio
from app.models.fase import DefinicaoFase
from app.models.execucao_fase import ExecucaoFase
from app.models.user import Usuario

etapas_bp = Blueprint('etapas', __name__, url_prefix='/api')

MOMENTOS_VALIDOS = {'triagem', 'producao'}


def _json_error(codigo: str, mensagem: str, status: int, **extra):
    payload = {
        'codigo': codigo,
        'mensagem': mensagem,
        'correlacao': f'cor-{codigo}',
    }
    payload.update(extra)
    return jsonify(payload), status


def _usuario_ativo(valor):
    usuario_id = id_numerico(valor)
    if usuario_id is None:
        return None
    candidato = Usuario.query.get(usuario_id)
    return candidato if candidato is not None and candidato.ativo else None


def _eh_chair_do_evento(usuario, evento_id):
    if usuario.administrador:
        return True
    participacao = ParticipacaoEvento.query.filter_by(
        usuario_id=usuario.id, evento_id=evento_id, papel='chair'
    ).first()
    return participacao is not None


# --- Passos do formulário ---

@etapas_bp.route('/chamadas/<int:chamada_id>/passos', methods=['GET'])
def listar_passos(chamada_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    passos = (
        PassoEnvio.query
        .filter_by(chamada_id=chamada_id)
        .order_by(PassoEnvio.ordem)
        .all()
    )
    return jsonify([p.to_dict() for p in passos])


@etapas_bp.route('/chamadas/<int:chamada_id>/passos', methods=['PUT'])
def substituir_passos(chamada_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    chamada = Chamada.query.get(chamada_id)
    if chamada is None:
        return _json_error('chamada_inexistente', 'Chamada não encontrada.', 404)
    if not _eh_chair_do_evento(usuario, chamada.evento_id):
        return _json_error('sem_permissao', 'Você não tem permissão para editar esta chamada.', 403)

    dados = request.get_json(silent=True) or {}
    passos_enviados = dados.get('passos')
    if not isinstance(passos_enviados, list) or len(passos_enviados) == 0:
        return _json_error(
            'dados_invalidos', 'Dados inválidos.', 422,
            campos={'passos': 'É preciso enviar ao menos um passo.'},
        )

    erros = {}
    for indice, passo in enumerate(passos_enviados):
        chave_erro = str(indice)
        if not isinstance(passo, dict):
            erros[chave_erro] = 'Passo inválido.'
            continue
        if not isinstance(passo.get('nome'), str) or not passo['nome'].strip():
            erros[chave_erro] = 'O nome do passo é obrigatório.'
            continue
        if not isinstance(passo.get('ordem'), int):
            erros[chave_erro] = "O campo 'ordem' deve ser um número inteiro."
            continue
        campos = passo.get('campos')
        if not isinstance(campos, list) or not all(isinstance(c, str) for c in campos):
            erros[chave_erro] = "O campo 'campos' deve ser uma lista de chaves."
            continue

    if erros:
        return _json_error('dados_invalidos', 'Dados inválidos.', 422, campos=erros)

    PassoEnvio.query.filter_by(chamada_id=chamada_id).delete()
    novos = []
    for passo in passos_enviados:
        novo = PassoEnvio(
            chamada_id=chamada_id,
            nome=passo['nome'],
            descricao=passo.get('descricao'),
            ordem=passo['ordem'],
        )
        novo.set_campos(passo['campos'])
        db.session.add(novo)
        novos.append(novo)
    db.session.commit()

    novos.sort(key=lambda p: p.ordem)
    return jsonify([p.to_dict() for p in novos])


# --- Fases (definição) ---

@etapas_bp.route('/eventos/<int:evento_id>/fases', methods=['GET'])
def listar_fases(evento_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)
    if not _eh_chair_do_evento(usuario, evento_id):
        return _json_error('sem_permissao', 'Você não tem permissão para ver as fases deste evento.', 403)

    fases = (
        DefinicaoFase.query
        .filter_by(evento_id=evento_id)
        .order_by(DefinicaoFase.ordem)
        .all()
    )
    return jsonify([f.to_dict() for f in fases])


@etapas_bp.route('/eventos/<int:evento_id>/fases', methods=['POST'])
def criar_fase(evento_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)
    if Evento.query.get(evento_id) is None:
        return _json_error('evento_inexistente', 'Evento não encontrado.', 404)
    if not _eh_chair_do_evento(usuario, evento_id):
        return _json_error('sem_permissao', 'Você não tem permissão para criar fases neste evento.', 403)

    dados = request.get_json(silent=True) or {}
    erros = {}

    nome = dados.get('nome')
    if not isinstance(nome, str) or not nome.strip():
        erros['nome'] = 'O nome é obrigatório.'

    ordem = dados.get('ordem')
    if not isinstance(ordem, int):
        erros['ordem'] = "O campo 'ordem' deve ser um número inteiro."

    momento = dados.get('momento')
    if momento not in MOMENTOS_VALIDOS:
        erros['momento'] = "O momento deve ser 'triagem' ou 'producao'."

    prazo_padrao_dias = dados.get('prazoPadraoDias')
    if not isinstance(prazo_padrao_dias, int):
        erros['prazoPadraoDias'] = "O campo 'prazoPadraoDias' deve ser um número inteiro."

    for campo_bool in ('obrigatoria', 'exigeArquivo', 'permiteDevolucao', 'ativo'):
        if not isinstance(dados.get(campo_bool), bool):
            erros[campo_bool] = f"O campo '{campo_bool}' deve ser verdadeiro ou falso."

    responsavel_padrao = None
    if dados.get('responsavelPadraoId') is not None:
        responsavel_padrao = _usuario_ativo(dados['responsavelPadraoId'])
        if responsavel_padrao is None:
            erros['responsavelPadraoId'] = 'Usuário não encontrado.'

    if erros:
        return _json_error('dados_invalidos', 'Dados inválidos.', 422, campos=erros)

    fase = DefinicaoFase(
        evento_id=evento_id,
        nome=nome,
        descricao=dados.get('descricao'),
        ordem=ordem,
        momento=momento,
        prazo_padrao_dias=prazo_padrao_dias,
        responsavel_padrao_id=responsavel_padrao.id if responsavel_padrao else None,
        obrigatoria=dados['obrigatoria'],
        exige_arquivo=dados['exigeArquivo'],
        permite_devolucao=dados['permiteDevolucao'],
        ativo=dados['ativo'],
    )
    db.session.add(fase)
    db.session.commit()
    return jsonify(fase.to_dict()), 201


@etapas_bp.route('/fases/<int:fase_id>', methods=['PATCH'])
def atualizar_fase(fase_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    fase = DefinicaoFase.query.get(fase_id)
    if fase is None:
        return _json_error('fase_inexistente', 'Fase não encontrada.', 404)
    if not _eh_chair_do_evento(usuario, fase.evento_id):
        return _json_error('sem_permissao', 'Você não tem permissão para editar esta fase.', 403)

    dados = request.get_json(silent=True) or {}
    erros = {}

    if 'nome' in dados:
        if not isinstance(dados['nome'], str) or not dados['nome'].strip():
            erros['nome'] = 'O nome é obrigatório.'
        else:
            fase.nome = dados['nome']

    if 'descricao' in dados:
        fase.descricao = dados['descricao']

    if 'ordem' in dados:
        if not isinstance(dados['ordem'], int):
            erros['ordem'] = "O campo 'ordem' deve ser um número inteiro."
        else:
            fase.ordem = dados['ordem']

    if 'momento' in dados:
        if dados['momento'] not in MOMENTOS_VALIDOS:
            erros['momento'] = "O momento deve ser 'triagem' ou 'producao'."
        else:
            fase.momento = dados['momento']

    if 'prazoPadraoDias' in dados:
        if not isinstance(dados['prazoPadraoDias'], int):
            erros['prazoPadraoDias'] = "O campo 'prazoPadraoDias' deve ser um número inteiro."
        else:
            fase.prazo_padrao_dias = dados['prazoPadraoDias']

    novo_responsavel = None
    if 'responsavelPadraoId' in dados:
        if dados['responsavelPadraoId'] is None:
            fase.responsavel_padrao_id = None
        else:
            novo_responsavel = _usuario_ativo(dados['responsavelPadraoId'])
            if novo_responsavel is None:
                erros['responsavelPadraoId'] = 'Usuário não encontrado.'
            else:
                fase.responsavel_padrao_id = novo_responsavel.id

    for campo_bool, atributo in (
        ('obrigatoria', 'obrigatoria'),
        ('exigeArquivo', 'exige_arquivo'),
        ('permiteDevolucao', 'permite_devolucao'),
        ('ativo', 'ativo'),
    ):
        if campo_bool in dados:
            if not isinstance(dados[campo_bool], bool):
                erros[campo_bool] = f"O campo '{campo_bool}' deve ser verdadeiro ou falso."
            else:
                setattr(fase, atributo, dados[campo_bool])

    if erros:
        return _json_error('dados_invalidos', 'Dados inválidos.', 422, campos=erros)

    if novo_responsavel is not None:
        # Execuções que ainda esperam alguém passam a ter o responsável padrão (A5).
        for execucao in ExecucaoFase.query.filter_by(fase_id=fase.id, status='pendente', responsavel_id=None).all():
            execucao.responsavel_id = novo_responsavel.id
            notificacoes.notificar_etapa_atribuida(execucao, fase, Submissao.query.get(execucao.submissao_id))

    db.session.commit()
    return jsonify(fase.to_dict())


@etapas_bp.route('/fases/<int:fase_id>', methods=['DELETE'])
def remover_fase(fase_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    fase = DefinicaoFase.query.get(fase_id)
    if fase is None:
        return _json_error('fase_inexistente', 'Fase não encontrada.', 404)
    if not _eh_chair_do_evento(usuario, fase.evento_id):
        return _json_error('sem_permissao', 'Você não tem permissão para remover esta fase.', 403)

    if ExecucaoFase.query.filter_by(fase_id=fase_id).count() > 0:
        return _json_error(
            'fase_com_execucoes', 'Esta fase já tem execuções e não pode ser removida.', 409
        )

    db.session.delete(fase)
    db.session.commit()
    return '', 204


# --- Execuções de fase (consulta) ---

@etapas_bp.route('/submissoes/<int:submissao_id>/execucoes-fase', methods=['GET'])
def listar_execucoes_da_submissao(submissao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    submissao = Submissao.query.get(submissao_id)
    if submissao is None:
        return _json_error('submissao_inexistente', 'Submissão não encontrada.', 404)

    eh_autor = submissao.autor_responsavel_id == usuario.id
    eh_chair = _eh_chair_do_evento(usuario, submissao.evento_id)
    execucoes = ExecucaoFase.query.filter_by(submissao_id=submissao_id).all()
    eh_responsavel = any(e.responsavel_id == usuario.id for e in execucoes)

    if not (eh_autor or eh_chair or eh_responsavel):
        return _json_error('submissao_inexistente', 'Submissão não encontrada.', 404)

    return jsonify([e.to_dict() for e in execucoes])


@etapas_bp.route('/me/execucoes-fase', methods=['GET'])
def minhas_execucoes_de_fase():
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    execucoes = ExecucaoFase.query.filter_by(responsavel_id=usuario.id).all()

    resultado = []
    for execucao in execucoes:
        item = execucao.to_dict()
        fase = DefinicaoFase.query.get(execucao.fase_id)
        submissao = Submissao.query.get(execucao.submissao_id)
        evento = Evento.query.get(submissao.evento_id) if submissao else None
        item['fase'] = fase.to_dict() if fase else None
        item['submissao'] = {
            'id': submissao.id,
            'titulo': submissao.respostas_dict().get('titulo', ''),
            'codigo': submissao.codigo,
        } if submissao else None
        item['eventoFuso'] = evento.fuso if evento else None
        resultado.append(item)

    resposta = jsonify(resultado)
    # O front usa o cabeçalho Date como "agora" do servidor para marcar prazos vencidos.
    resposta.headers['Date'] = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    return resposta


# --- Ações sobre a execução de fase ---

def _buscar_execucao(execucao_id):
    execucao = ExecucaoFase.query.get(execucao_id)
    if execucao is None:
        return None, None, None
    fase = DefinicaoFase.query.get(execucao.fase_id)
    submissao = Submissao.query.get(execucao.submissao_id)
    return execucao, fase, submissao


@etapas_bp.route('/execucoes-fase/<int:execucao_id>', methods=['PATCH'])
def trocar_responsavel_da_execucao(execucao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    execucao, fase, submissao = _buscar_execucao(execucao_id)
    if execucao is None or fase is None:
        return _json_error('execucao_inexistente', 'Execução não encontrada.', 404)
    if not _eh_chair_do_evento(usuario, fase.evento_id):
        return _json_error('sem_permissao', 'Você não tem permissão para alterar esta execução.', 403)

    dados = request.get_json(silent=True) or {}
    responsavel = _usuario_ativo(dados.get('responsavelId'))
    if responsavel is None:
        return _json_error(
            'dados_invalidos', 'Dados inválidos.', 422,
            campos={'responsavelId': 'Informe um usuário ativo.'},
        )

    if execucao.responsavel_id != responsavel.id:
        execucao.responsavel_id = responsavel.id
        notificacoes.notificar_etapa_atribuida(execucao, fase, submissao)
    db.session.commit()
    return jsonify(execucao.to_dict())


@etapas_bp.route('/execucoes-fase/<int:execucao_id>/iniciar', methods=['POST'])
def iniciar_execucao(execucao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    execucao, fase, submissao = _buscar_execucao(execucao_id)
    if execucao is None or execucao.responsavel_id != usuario.id:
        return _json_error('execucao_inexistente', 'Execução não encontrada.', 404)

    execucao.status = 'em_andamento'
    if execucao.data_inicio is None:
        execucao.data_inicio = datetime.utcnow()
    db.session.commit()
    return jsonify(execucao.to_dict())


@etapas_bp.route('/execucoes-fase/<int:execucao_id>/concluir', methods=['POST'])
def concluir_execucao(execucao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    execucao, fase, submissao = _buscar_execucao(execucao_id)
    if execucao is None or execucao.responsavel_id != usuario.id:
        return _json_error('execucao_inexistente', 'Execução não encontrada.', 404)

    dados = request.get_json(silent=True) or {}
    arquivo_resultado_id = id_numerico(dados.get('arquivoResultadoId'))
    arquivo_informado = dados.get('arquivoResultadoId') not in (None, '')
    # O arquivo de resultado é uma versão da própria submissão.
    arquivo_da_submissao = arquivo_resultado_id is not None and submissao is not None and (
        VersaoDeArquivo.query.filter_by(id=arquivo_resultado_id, submissao_id=submissao.id).first() is not None
    )
    if arquivo_informado and not arquivo_da_submissao:
        return _json_error(
            'dados_invalidos', 'Dados inválidos.', 422,
            campos={'arquivoResultadoId': 'O arquivo informado não é uma versão desta submissão.'},
        )

    if fase and fase.exige_arquivo and not arquivo_resultado_id:
        return _json_error(
            'dados_invalidos', 'Dados inválidos.', 422,
            campos={'arquivoResultadoId': 'Esta fase exige o envio de um arquivo de resultado.'},
        )

    if fase is not None and submissao is not None:
        fases_anteriores_pendentes = (
            db.session.query(DefinicaoFase, ExecucaoFase)
            .join(ExecucaoFase, ExecucaoFase.fase_id == DefinicaoFase.id)
            .filter(
                DefinicaoFase.evento_id == fase.evento_id,
                DefinicaoFase.ordem < fase.ordem,
                DefinicaoFase.obrigatoria.is_(True),
                ExecucaoFase.submissao_id == submissao.id,
                ~ExecucaoFase.status.in_(['concluida', 'dispensada']),
            )
            .first()
        )
        if fases_anteriores_pendentes is not None:
            return _json_error(
                'fase_anterior_pendente',
                'Existe uma fase obrigatória anterior ainda pendente para esta submissão.',
                409,
            )

    execucao.status = 'concluida'
    execucao.data_conclusao = datetime.utcnow()
    if arquivo_resultado_id:
        execucao.arquivo_resultado_id = arquivo_resultado_id
    db.session.commit()
    return jsonify(execucao.to_dict())


@etapas_bp.route('/execucoes-fase/<int:execucao_id>/devolver', methods=['POST'])
def devolver_execucao(execucao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    execucao, fase, submissao = _buscar_execucao(execucao_id)
    if execucao is None or execucao.responsavel_id != usuario.id:
        return _json_error('execucao_inexistente', 'Execução não encontrada.', 404)

    dados = request.get_json(silent=True) or {}
    execucao.status = 'aguardando_autor'
    execucao.observacoes = dados.get('observacoes') or execucao.observacoes
    db.session.commit()
    return jsonify(execucao.to_dict())


@etapas_bp.route('/execucoes-fase/<int:execucao_id>/reenviar', methods=['POST'])
def reenviar_execucao(execucao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    execucao, fase, submissao = _buscar_execucao(execucao_id)
    if execucao is None or submissao is None or submissao.autor_responsavel_id != usuario.id:
        return _json_error('execucao_inexistente', 'Execução não encontrada.', 404)

    if execucao.status != 'aguardando_autor':
        return _json_error(
            'reenvio_sem_devolucao', 'Esta execução não foi devolvida pelo responsável.', 409
        )

    execucao.status = 'pendente'
    db.session.commit()
    return jsonify(execucao.to_dict())


@etapas_bp.route('/execucoes-fase/<int:execucao_id>/dispensar', methods=['POST'])
def dispensar_execucao(execucao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    execucao, fase, submissao = _buscar_execucao(execucao_id)
    if execucao is None or fase is None or not _eh_chair_do_evento(usuario, fase.evento_id):
        return _json_error('execucao_inexistente', 'Execução não encontrada.', 404)

    if fase.obrigatoria:
        return _json_error(
            'fase_obrigatoria_nao_dispensavel', 'Esta fase é obrigatória e não pode ser dispensada.', 409
        )

    dados = request.get_json(silent=True) or {}
    observacoes = (dados.get('observacoes') or '').strip()
    if not observacoes:
        return _json_error(
            'dados_invalidos', 'Dados inválidos.', 422,
            campos={'observacoes': 'Informe o motivo da dispensa.'},
        )

    execucao.status = 'dispensada'
    execucao.observacoes = observacoes
    db.session.commit()
    return jsonify(execucao.to_dict())