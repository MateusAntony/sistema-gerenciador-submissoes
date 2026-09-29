import json
import mimetypes
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from flask import Blueprint, current_app, jsonify, request, send_file
from werkzeug.utils import secure_filename

from app import notificacoes, prazos, sigilo
from app.ids import id_numerico
from app.controllers.auth_controller import usuario_autenticado
from app.extensions import db
from app.models.evento import Autoria, Chamada, Evento, ParticipacaoEvento, Submissao, Trilha, VersaoDeArquivo
from app.models.formulario import FormularioVersao
from app.models.fase import DefinicaoFase
from app.models.execucao_fase import ExecucaoFase
from app.models.rodada import Rodada
from app.models.decisao import Decisao
from app.models.rebuttal import Rebuttal
from app.models.atribuicao import Atribuicao
from app.models.versao_corrigida import VersaoCorrigida, DevolucaoDeVersaoCorrigida
from app.models.user import Usuario


submissoes_bp = Blueprint('submissoes', __name__, url_prefix='/api')


def _erro(codigo: str, mensagem: str, status: int, **extra):
    payload = {'codigo': codigo, 'mensagem': mensagem, 'correlacao': f'cor-{codigo}'}
    payload.update(extra)
    return jsonify(payload), status


def _usuario():
    return usuario_autenticado()


def _submissao_do_autor(submissao_id: int):
    usuario = _usuario()
    submissao = Submissao.query.get(submissao_id)
    if usuario is None:
        return None, _erro('nao_autenticado', 'Sua sessão expirou.', 401)
    if submissao is None or submissao.autor_responsavel_id != usuario.id:
        return None, _erro('submissao_inexistente', 'Submissão não encontrada.', 404)
    return submissao, None


def _decisao_oculta(submissao, usuario):
    """Há decisão registrada e não comunicada na rodada mais recente, e quem
    pede não é chair/admin do evento. Nesse caso nenhuma resposta pode
    depender do resultado: registrar a decisão já muda submissao.situacao
    (ex.: 'rejeitada')."""
    if _eh_chair_do_evento(usuario, submissao.evento_id):
        return False
    rodada = (
        Rodada.query.filter_by(submissao_id=submissao.id)
        .order_by(Rodada.numero.desc()).first()
    )
    decisao = Decisao.query.filter_by(rodada_id=rodada.id).first() if rodada else None
    return decisao is not None and decisao.comunicada_em is None


def _situacao_efetiva(submissao):
    """Rebuttal vencido sem resposta conta como fechado: não há job que o
    expire, então 'aguardando_rebuttal' vira 'aguardando_decisao' na leitura."""
    if submissao.situacao != 'aguardando_rebuttal':
        return submissao.situacao
    rodada = (
        Rodada.query.filter_by(submissao_id=submissao.id)
        .order_by(Rodada.numero.desc()).first()
    )
    rebuttal = Rebuttal.query.filter_by(rodada_id=rodada.id, situacao='aguardando').first() if rodada else None
    if rebuttal is not None and rebuttal.prazo is not None and datetime.now(timezone.utc) > _com_fuso(rebuttal.prazo):
        return 'aguardando_decisao'
    return submissao.situacao


def _situacao_visivel(submissao, usuario):
    """Quem não é chair/admin vê 'aguardando_decisao' enquanto a decisão da
    rodada mais recente não for comunicada (A15)."""
    if submissao.situacao != 'retirada' and _decisao_oculta(submissao, usuario):
        return 'aguardando_decisao'
    return _situacao_efetiva(submissao)


def _resumo(submissao: Submissao, usuario):
    chamada = Chamada.query.get(submissao.chamada_id)
    evento = Evento.query.get(submissao.evento_id)
    trilha = Trilha.query.get(submissao.trilha_id) if submissao.trilha_id else None
    respostas = submissao.respostas_dict()
    titulo = respostas.get('titulo', '')
    return {
        'id': str(submissao.id),
        'codigo': submissao.codigo,
        'titulo': titulo if isinstance(titulo, str) else '',
        'eventoId': str(submissao.evento_id),
        'eventoTitulo': evento.titulo if evento else '',
        'chamadaId': str(submissao.chamada_id),
        'chamadaTitulo': chamada.titulo if chamada else '',
        'trilhaNome': trilha.nome if trilha else None,
        'situacao': _situacao_visivel(submissao, usuario),
        'foraDoPrazo': submissao.fora_do_prazo,
        'dataUltimaAtualizacao': (
            submissao.data_ultimo_salvamento or submissao.data_confirmacao or datetime.utcnow()
        ).isoformat(),
        'dataLimiteChamada': chamada.data_limite if chamada else '',
    }


def _eh_chair_do_evento(usuario, evento_id):
    if usuario.administrador:
        return True
    participacao = ParticipacaoEvento.query.filter_by(
        usuario_id=usuario.id, evento_id=evento_id, papel='chair'
    ).first()
    return participacao is not None


def _campo_esta_visivel(campo, respostas):
    """Avalia campo.condicao contra as respostas atuais. Sem condição = sempre visível."""
    condicao = campo.get('condicao')
    if not condicao or not condicao.get('regras'):
        return True

    def _regra_satisfeita(regra):
        valor_atual = respostas.get(regra.get('campoChave'))
        operador = regra.get('operador')
        valor_esperado = regra.get('valor')
        if operador == 'preenchido':
            return valor_atual not in (None, '', [])
        if operador == 'vazio':
            return valor_atual in (None, '', [])
        if operador == 'igual':
            return valor_atual == valor_esperado
        if operador == 'diferente':
            return valor_atual != valor_esperado
        if operador == 'contem':
            return isinstance(valor_atual, (list, str)) and valor_esperado in valor_atual
        # Operador desconhecido: não bloqueia o campo (evita exigir algo indevidamente).
        return True

    resultados = [_regra_satisfeita(regra) for regra in condicao['regras']]
    if condicao.get('operadorGrupo') == 'OU':
        return any(resultados)
    return all(resultados)


def _validar_respostas_contra_formulario(campos, respostas):
    """Valida `respostas` contra os `campos` de uma FormularioVersao publicada.
    Retorna dict {chave: mensagem}. Campos base (titulo/resumo/autoria/arquivo)
    são ignorados aqui: continuam validados separadamente (título/resumo vêm de
    respostas mas são tratados como base; autoria e arquivo têm tabelas próprias)."""
    erros = {}
    for campo in campos:
        chave = campo.get('chave')
        if not chave or campo.get('base'):
            continue
        if not _campo_esta_visivel(campo, respostas):
            continue

        valor = respostas.get(chave)
        validacoes = campo.get('validacoes') or {}

        if campo.get('obrigatorio') and valor in (None, '', []):
            erros[chave] = 'Este campo é obrigatório.'
            continue
        if valor in (None, '', []):
            continue  # não obrigatório e vazio: nada a validar

        if isinstance(valor, str):
            if validacoes.get('minCaracteres') and len(valor) < validacoes['minCaracteres']:
                erros[chave] = f"Mínimo de {validacoes['minCaracteres']} caracteres."
                continue
            if validacoes.get('maxCaracteres') and len(valor) > validacoes['maxCaracteres']:
                erros[chave] = f"Máximo de {validacoes['maxCaracteres']} caracteres."
                continue
            if validacoes.get('padrao'):
                try:
                    if not re.match(validacoes['padrao'], valor):
                        erros[chave] = validacoes.get('mensagemPadrao') or 'Formato inválido.'
                        continue
                except re.error:
                    pass

        if isinstance(valor, (int, float)):
            if validacoes.get('minValor') is not None and valor < validacoes['minValor']:
                erros[chave] = f"O valor mínimo é {validacoes['minValor']}."
                continue
            if validacoes.get('maxValor') is not None and valor > validacoes['maxValor']:
                erros[chave] = f"O valor máximo é {validacoes['maxValor']}."
                continue

        if isinstance(valor, list):
            if validacoes.get('minSelecoes') and len(valor) < validacoes['minSelecoes']:
                erros[chave] = f"Selecione ao menos {validacoes['minSelecoes']} opção(ões)."
                continue
            if validacoes.get('maxSelecoes') and len(valor) > validacoes['maxSelecoes']:
                erros[chave] = f"Selecione no máximo {validacoes['maxSelecoes']} opção(ões)."
                continue

    return erros


@submissoes_bp.route('/chamadas/<int:chamada_id>/submissoes', methods=['POST'])
def criar_submissao(chamada_id):
    usuario = _usuario()
    if usuario is None:
        return _erro('nao_autenticado', 'Sua sessão expirou.', 401)

    chamada = Chamada.query.get(chamada_id)
    if chamada is None:
        return _erro('chamada_inexistente', 'Chamada não encontrada.', 404)

    if prazos.chamada_encerrada(chamada, Evento.query.get(chamada.evento_id)):
        return _erro('chamada_encerrada', 'Esta chamada está encerrada e não aceita novas submissões.', 409)

    dados = request.get_json(silent=True) or {}
    trilha_bruta = dados.get('trilhaId')
    trilha_id = id_numerico(trilha_bruta)
    trilhas_ativas = Trilha.query.filter_by(evento_id=chamada.evento_id, ativa=True).count()
    if trilhas_ativas and not trilha_id:
        return _erro(
            'dados_invalidos',
            'Verifique os campos destacados.',
            422,
            campos={'trilhaId': 'Selecione a trilha desta submissão.'},
        )

    if trilha_bruta not in (None, ''):
        trilha = Trilha.query.filter_by(id=trilha_id, evento_id=chamada.evento_id, ativa=True).first()
        if trilha is None:
            return _erro('dados_invalidos', 'A trilha selecionada não existe ou está inativa.', 422)

    submissao = Submissao(
        chamada_id=chamada.id,
        evento_id=chamada.evento_id,
        trilha_id=trilha_id,
        autor_responsavel_id=usuario.id,
        situacao='rascunho',
        fora_do_prazo=False,
        versao_formulario=1,
        formulario_versao_id=f'formulario-chamada-{chamada.id}-v1',
        respostas=json.dumps({}),
        data_ultimo_salvamento=datetime.utcnow(),
    )
    db.session.add(submissao)
    db.session.flush()
    db.session.add(Autoria(
        submissao_id=submissao.id,
        usuario_id=usuario.id,
        nome=usuario.nome,
        email=usuario.email,
        instituicao=usuario.instituicao or '',
        ordem=1,
        correspondente=True,
        eh_responsavel=True,
    ))
    db.session.commit()
    return jsonify(submissao.to_dict()), 201


@submissoes_bp.route('/submissoes/<int:submissao_id>', methods=['GET'])
def obter_submissao(submissao_id):
    submissao, erro = _submissao_do_autor(submissao_id)
    if erro:
        return erro
    resposta = submissao.to_dict()
    resposta['situacao'] = _situacao_visivel(submissao, _usuario())
    evento = Evento.query.get(submissao.evento_id)
    resposta['fusoDoEvento'] = evento.fuso if evento else ''
    return jsonify(resposta)


@submissoes_bp.route('/submissoes/<int:submissao_id>', methods=['PATCH'])
def atualizar_submissao(submissao_id):
    submissao, erro = _submissao_do_autor(submissao_id)
    if erro:
        return erro
    if submissao.situacao != 'rascunho':
        return _erro('submissao_nao_e_rascunho', 'Esta submissão não pode mais ser editada.', 409)

    dados = request.get_json(silent=True) or {}

    if 'versaoFormulario' in dados:
        formulario_publicado = FormularioVersao.query.filter_by(
            chamada_id=submissao.chamada_id, status='publicado'
        ).order_by(FormularioVersao.versao.desc()).first()
        if formulario_publicado is not None and dados['versaoFormulario'] != formulario_publicado.versao:
            return _erro(
                'versao_desatualizada',
                'O formulário desta chamada foi atualizado. Recarregue a página antes de continuar.',
                409,
                versaoAtual=formulario_publicado.versao,
            )

    if 'trilhaId' in dados:
        trilha_id = id_numerico(dados['trilhaId'])
        trilha = Trilha.query.filter_by(id=trilha_id, evento_id=submissao.evento_id, ativa=True).first()
        if trilha is None:
            return _erro('dados_invalidos', 'A trilha selecionada não existe ou está inativa.', 422)
        submissao.trilha_id = trilha_id
    if 'respostas' in dados:
        if not isinstance(dados['respostas'], dict):
            return _erro('dados_invalidos', 'Respostas devem ser um objeto JSON.', 422)
        submissao.respostas = json.dumps(dados['respostas'])
    if 'identificadorExterno' in dados:
        submissao.identificador_externo = dados['identificadorExterno']

    submissao.data_ultimo_salvamento = datetime.utcnow()
    db.session.commit()
    return jsonify(submissao.to_dict())


@submissoes_bp.route('/submissoes/<int:submissao_id>', methods=['DELETE'])
def excluir_submissao(submissao_id):
    submissao, erro = _submissao_do_autor(submissao_id)
    if erro:
        return erro
    if submissao.situacao != 'rascunho':
        return _erro('submissao_nao_e_rascunho', 'Só é possível excluir uma submissão em rascunho.', 409)
    db.session.delete(submissao)
    db.session.commit()
    return '', 204


@submissoes_bp.route('/me/submissoes', methods=['GET'])
def listar_minhas_submissoes():
    usuario = _usuario()
    if usuario is None:
        return _erro('nao_autenticado', 'Sua sessão expirou.', 401)

    consulta = Submissao.query.filter_by(autor_responsavel_id=usuario.id)
    evento_id = request.args.get('evento')
    status = request.args.get('status')
    termo = (request.args.get('q') or '').lower()
    if evento_id:
        consulta = consulta.filter_by(evento_id=evento_id)

    resultados = [_resumo(item, usuario) for item in consulta.order_by(Submissao.id.desc()).all()]
    if status:
        # Filtra pela situação que a pessoa vê, não pela gravada.
        resultados = [item for item in resultados if item['situacao'] == status]
    if termo:
        resultados = [
            item for item in resultados
            if termo in item['titulo'].lower() or termo in (item['codigo'] or '').lower()
        ]
    return jsonify(resultados)


@submissoes_bp.route('/submissoes/<int:submissao_id>/autorias', methods=['GET'])
def listar_autorias(submissao_id):
    submissao, erro = _submissao_do_autor(submissao_id)
    if erro:
        return erro
    autorias = Autoria.query.filter_by(submissao_id=submissao.id).order_by(Autoria.ordem).all()
    if not any(autoria.correspondente for autoria in autorias):
        for autoria in autorias:
            if autoria.eh_responsavel:
                autoria.correspondente = True
    return jsonify([autoria.to_dict() for autoria in autorias])


@submissoes_bp.route('/submissoes/<int:submissao_id>/autorias', methods=['POST'])
def adicionar_autoria(submissao_id):
    submissao, erro = _submissao_do_autor(submissao_id)
    if erro:
        return erro
    if submissao.situacao != 'rascunho':
        return _erro('submissao_nao_e_rascunho', 'Esta submissão não pode mais ser editada.', 409)

    dados = request.get_json(silent=True) or {}
    email = (dados.get('email') or '').strip()
    if not email or not dados.get('nome'):
        return _erro('dados_invalidos', 'Nome e e-mail são obrigatórios.', 422)
    if Autoria.query.filter_by(submissao_id=submissao.id, email=email).first() is not None:
        return _erro('dados_invalidos', 'Este e-mail já foi adicionado a esta submissão.', 422,
                     campos={'email': 'Este e-mail já foi adicionado a esta submissão.'})

    usuario = Usuario.query.filter_by(email=email).first()
    ordem = Autoria.query.filter_by(submissao_id=submissao.id).count() + 1
    autoria = Autoria(
        submissao_id=submissao.id,
        usuario_id=usuario.id if usuario else None,
        nome=dados.get('nome'),
        email=email,
        instituicao=dados.get('instituicao') or '',
        ordem=ordem,
        correspondente=False,
        eh_responsavel=False,
    )
    db.session.add(autoria)
    db.session.commit()
    return jsonify(autoria.to_dict()), 201


@submissoes_bp.route('/submissoes/<int:submissao_id>/autorias/<int:autor_id>', methods=['PATCH'])
def atualizar_autoria(submissao_id, autor_id):
    submissao, erro = _submissao_do_autor(submissao_id)
    if erro:
        return erro
    autoria = Autoria.query.filter_by(id=autor_id, submissao_id=submissao.id).first()
    if autoria is None:
        return _erro('autoria_inexistente', 'Autoria não encontrada.', 404)
    dados = request.get_json(silent=True) or {}
    if 'ordem' in dados:
        autoria.ordem = dados['ordem']
    if dados.get('correspondente') is True:
        Autoria.query.filter_by(submissao_id=submissao.id).update({'correspondente': False})
        autoria.correspondente = True
    elif dados.get('correspondente') is False:
        autoria.correspondente = False
    db.session.commit()
    return jsonify(autoria.to_dict())


@submissoes_bp.route('/submissoes/<int:submissao_id>/autorias/<int:autor_id>', methods=['DELETE'])
def remover_autoria(submissao_id, autor_id):
    submissao, erro = _submissao_do_autor(submissao_id)
    if erro:
        return erro
    autoria = Autoria.query.filter_by(id=autor_id, submissao_id=submissao.id).first()
    if autoria is None:
        return _erro('autoria_inexistente', 'Autoria não encontrada.', 404)
    if autoria.eh_responsavel:
        return _erro('nao_pode_remover_responsavel', 'O autor responsável não pode ser removido da submissão.', 422)
    db.session.delete(autoria)
    db.session.commit()
    return '', 204


@submissoes_bp.route('/submissoes/<int:submissao_id>/versoes', methods=['GET'])
def listar_versoes(submissao_id):
    usuario = _usuario()
    if usuario is None:
        return _erro('nao_autenticado', 'Sua sessão expirou.', 401)
    submissao = Submissao.query.get(submissao_id)
    pode_ver = submissao is not None and (
        _eh_autor_com_conta(usuario, submissao)  # responsável ou coautor com conta vinculada
        or _eh_chair_do_evento(usuario, submissao.evento_id)
    )
    if not pode_ver:
        return _erro('submissao_inexistente', 'Submissão não encontrada.', 404)
    versoes = VersaoDeArquivo.query.filter_by(submissao_id=submissao.id).order_by(VersaoDeArquivo.numero).all()
    return jsonify([versao.to_dict() for versao in versoes])


@submissoes_bp.route('/submissoes/<int:submissao_id>/versoes', methods=['POST'])
def criar_versao(submissao_id):
    submissao, erro = _submissao_do_autor(submissao_id)
    if erro:
        return erro
    chamada = Chamada.query.get(submissao.chamada_id)
    if chamada is None:
        return _erro('chamada_inexistente', 'Chamada não encontrada.', 404)
    situacoes_reenvio = {'aguardando_rebuttal', 'aguardando_versao_corrigida'}
    situacao = _situacao_efetiva(submissao)
    pode_enviar = not _decisao_oculta(submissao, _usuario()) and (
        situacao == 'rascunho' or situacao in situacoes_reenvio
    )
    if not pode_enviar:
        return _erro(
            'versao_bloqueada',
            'Esta submissão não aceita nova versão agora: só no rascunho ou quando a organização pede correções.',
            409,
        )
    encerrada = prazos.chamada_encerrada(chamada, Evento.query.get(chamada.evento_id))
    if encerrada and submissao.situacao not in situacoes_reenvio:
        return _erro('chamada_encerrada', 'Esta chamada está encerrada e não aceita novos envios.', 409)

    arquivo = request.files.get('arquivo')
    nome = _sanear_nome_de_arquivo(request.form.get('nomeArquivo') or (arquivo.filename if arquivo else ''))
    tamanho = int(request.form.get('tamanhoBytes') or (arquivo.content_length if arquivo else 0) or 0)
    if arquivo is None or not nome:
        return _erro('dados_invalidos', 'Verifique os campos destacados.', 422, campos={'arquivo': 'Anexe um arquivo.'})

    extensao = nome.rsplit('.', 1)[-1].lower() if '.' in nome else ''
    formatos = _formatos_da_chamada(chamada.formatos_aceitos)
    if formatos and extensao not in formatos:
        return _erro('dados_invalidos', 'Verifique os campos destacados.', 422,
                     campos={'arquivo': f"Formatos aceitos: {', '.join(formatos)}."})
    if chamada.tamanho_maximo_mb and tamanho > chamada.tamanho_maximo_mb * 1024 * 1024:
        return _erro('dados_invalidos', 'Verifique os campos destacados.', 422,
                     campos={'arquivo': f'O tamanho máximo é {chamada.tamanho_maximo_mb}MB.'})

    anteriores = VersaoDeArquivo.query.filter_by(submissao_id=submissao.id).all()
    for anterior in anteriores:
        anterior.vigente = False
    nome_seguro = _sanear_nome_de_arquivo(secure_filename(nome), LIMITE_NOME_EM_DISCO) or 'arquivo'
    pasta = current_app.config['PASTA_UPLOADS']
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, f'{submissao.id}-{len(anteriores) + 1}-{nome_seguro}')
    arquivo.save(caminho)
    usuario = _usuario()
    versao = VersaoDeArquivo(
        submissao_id=submissao.id,
        numero=len(anteriores) + 1,
        nome_original=nome,
        tamanho_bytes=tamanho,
        resumo_das_alteracoes=request.form.get('resumoDasAlteracoes'),
        enviado_por=usuario.nome,
        vigente=True,
        caminho_arquivo=caminho,
    )
    db.session.add(versao)
    db.session.commit()
    return jsonify(versao.to_dict()), 201


LIMITE_NOME_ORIGINAL = 200
LIMITE_NOME_EM_DISCO = 100


def _sanear_nome_de_arquivo(nome, limite=LIMITE_NOME_ORIGINAL):
    """Tira NUL e caracteres de controle (o Postgres recusa NUL e o nome vai
    para cabeçalhos HTTP) e corta nomes longos preservando a extensão."""
    nome = re.sub(r'[\x00-\x1f\x7f]', '', nome or '').strip()
    if len(nome) <= limite:
        return nome
    base, ponto, extensao = nome.rpartition('.')
    if ponto and base and 0 < len(extensao) <= 10:
        return base[:limite - len(extensao) - 1] + '.' + extensao
    return nome[:limite]


def _eh_autor_com_conta(usuario, submissao):
    if submissao.autor_responsavel_id == usuario.id:
        return True
    return Autoria.query.filter_by(submissao_id=submissao.id, usuario_id=usuario.id).first() is not None


def _avaliador_pode_baixar(usuario, versao):
    """Avaliador com atribuição aceita na submissão, só até a versão vigente."""
    aceita = Atribuicao.query.filter_by(
        submissao_id=versao.submissao_id, avaliador_id=usuario.id, situacao='aceito'
    ).first()
    if aceita is None:
        return False
    vigente = VersaoDeArquivo.query.filter_by(submissao_id=versao.submissao_id, vigente=True).first()
    return vigente is not None and versao.numero <= vigente.numero


def _content_disposition(nome):
    reserva = nome.encode('ascii', 'replace').decode('ascii').replace('\\', '_').replace('"', '_')
    # nomeArquivo é campo livre: caracteres de controle quebrariam o cabeçalho
    # (o werkzeug recusa \r\n com 500). O original segue em filename*, codificado.
    reserva = re.sub(r'[\x00-\x1f\x7f]', '', reserva)
    valor = f'attachment; filename="{reserva}"'
    if reserva != nome:
        valor += f"; filename*=UTF-8''{quote(nome, safe='')}"
    return valor


@submissoes_bp.route('/versoes/<int:versao_id>/arquivo', methods=['GET'])
def baixar_arquivo_da_versao(versao_id):
    usuario = _usuario()
    if usuario is None:
        return _erro('nao_autenticado', 'Sua sessão expirou.', 401)

    versao = VersaoDeArquivo.query.get(versao_id)
    submissao = Submissao.query.get(versao.submissao_id) if versao else None
    if versao is None or submissao is None:
        return _erro('versao_inexistente', 'Versão não encontrada.', 404)

    ve_nome_real = (
        _eh_autor_com_conta(usuario, submissao)
        or _eh_chair_do_evento(usuario, submissao.evento_id)
    )
    pode_baixar = ve_nome_real or _avaliador_pode_baixar(usuario, versao)
    if not pode_baixar:
        return _erro('sem_permissao', 'Você não tem acesso a este arquivo.', 403)

    if not versao.caminho_arquivo or not os.path.isfile(versao.caminho_arquivo):
        return _erro('arquivo_indisponivel', 'O arquivo desta versão não está disponível.', 404)

    tipo = mimetypes.guess_type(versao.nome_original)[0] or 'application/octet-stream'
    resposta = send_file(versao.caminho_arquivo, mimetype=tipo)
    nome = versao.nome_original if ve_nome_real else sigilo.nome_para_avaliador(
        versao, submissao, Evento.query.get(submissao.evento_id))
    resposta.headers['Content-Disposition'] = _content_disposition(nome)
    return resposta


def _formatos_da_chamada(valor):
    if isinstance(valor, list):
        return [str(item).lower().lstrip('.') for item in valor]
    try:
        return [str(item).lower().lstrip('.') for item in json.loads(valor or '[]')]
    except (TypeError, ValueError):
        return []


@submissoes_bp.route('/submissoes/<int:submissao_id>/confirmar', methods=['POST'])
def confirmar_submissao(submissao_id):
    submissao, erro = _submissao_do_autor(submissao_id)
    if erro:
        return erro
    evento = Evento.query.get(submissao.evento_id)
    if submissao.situacao != 'rascunho':
        confirmacao = _confirmacao(submissao, evento)
        confirmacao['situacao'] = _situacao_visivel(submissao, _usuario())
        return jsonify(confirmacao)

    respostas = submissao.respostas_dict()
    faltando = {}
    if not respostas.get('titulo'):
        faltando['titulo'] = 'Informe o título.'
    if not respostas.get('resumo'):
        faltando['resumo'] = 'Informe o resumo.'
    if not Autoria.query.filter_by(submissao_id=submissao.id).count():
        faltando['autores'] = 'Adicione ao menos um autor.'
    if not VersaoDeArquivo.query.filter_by(submissao_id=submissao.id).count():
        faltando['arquivo'] = 'Envie o arquivo do trabalho.'

    formulario_publicado = FormularioVersao.query.filter_by(
        chamada_id=submissao.chamada_id, status='publicado'
    ).order_by(FormularioVersao.versao.desc()).first()
    if formulario_publicado is not None:
        faltando.update(_validar_respostas_contra_formulario(formulario_publicado.get_campos(), respostas))

    if faltando:
        return _erro('dados_invalidos', 'Verifique os campos destacados.', 422, campos=faltando)

    chamada = Chamada.query.get(submissao.chamada_id)
    encerrada = chamada is not None and prazos.chamada_encerrada(chamada, evento)
    if encerrada and not chamada.permite_submissao_apos_prazo:
        return _erro('prazo_encerrado', 'O prazo desta chamada terminou e não permite envio fora do prazo.', 409)

    # Derivado do próprio id: único por construção, qualquer que seja a ordem das confirmações.
    submissao.codigo = f'SUB-{submissao.id:04d}'
    submissao.situacao = 'submetida'
    submissao.fora_do_prazo = bool(encerrada)
    submissao.data_confirmacao = datetime.utcnow()

    # Instancia uma execução por fase de triagem ativa do evento (regra transversal).
    fases_de_triagem = DefinicaoFase.query.filter_by(
        evento_id=submissao.evento_id, momento='triagem', ativo=True
    ).all()
    for fase in fases_de_triagem:
        prazo = None
        if fase.prazo_padrao_dias:
            prazo = datetime.utcnow() + timedelta(days=fase.prazo_padrao_dias)
        execucao = ExecucaoFase(
            submissao_id=submissao.id,
            fase_id=fase.id,
            responsavel_id=fase.responsavel_padrao_id,
            status='pendente',
            prazo=prazo,
        )
        db.session.add(execucao)
        db.session.flush()  # execucao.id para a notificação; sem responsável, não notifica
        notificacoes.notificar_etapa_atribuida(execucao, fase, submissao)

    # Abre a rodada 1 de avaliação para esta submissão.
    db.session.add(Rodada(
        submissao_id=submissao.id,
        evento_id=submissao.evento_id,
        numero=1,
        aberta_em=datetime.utcnow(),
    ))

    db.session.commit()
    return jsonify(_confirmacao(submissao, evento))


def _confirmacao(submissao, evento):
    return {
        'submissaoId': str(submissao.id),
        'codigo': submissao.codigo or '',
        'situacao': submissao.situacao,
        'dataConfirmacao': submissao.data_confirmacao.isoformat() if submissao.data_confirmacao else '',
        'fusoDoEvento': evento.fuso if evento else '',
        'foraDoPrazo': submissao.fora_do_prazo,
    }


SITUACOES_COM_DECISAO_FINAL = {'aceita', 'aceita_com_correcoes', 'aguardando_versao_corrigida', 'rejeitada'}


@submissoes_bp.route('/submissoes/<int:submissao_id>/retirar', methods=['POST'])
def retirar_submissao(submissao_id):
    submissao, erro = _submissao_do_autor(submissao_id)
    if erro:
        return erro
    if _decisao_oculta(submissao, _usuario()):
        # Mesma resposta para qualquer resultado: senão ela revelaria a decisão.
        return _erro('retirada_bloqueada', 'A submissão está aguardando decisão e não pode ser retirada agora.', 409)
    if submissao.situacao in SITUACOES_COM_DECISAO_FINAL:
        return _erro('decisao_ja_emitida', 'Esta submissão já tem decisão emitida e não pode ser retirada.', 409)
    submissao.situacao = 'retirada'
    submissao.retirada_em = datetime.utcnow()
    db.session.commit()
    return jsonify(submissao.to_dict())


# --- P1: aba "Submissões" do chair ---

@submissoes_bp.route('/eventos/<int:evento_id>/submissoes', methods=['GET'])
def listar_submissoes_do_evento(evento_id):
    usuario = _usuario()
    if usuario is None:
        return _erro('nao_autenticado', 'Sua sessão expirou.', 401)

    evento = Evento.query.get(evento_id)
    if evento is None:
        return _erro('evento_inexistente', 'Evento não encontrado.', 404)
    if not _eh_chair_do_evento(usuario, evento_id):
        return _erro('sem_permissao', 'Você não tem permissão para ver as submissões deste evento.', 403)

    consulta = Submissao.query.filter_by(evento_id=evento_id)

    situacao_pedida = request.args.get('situacao')

    trilha = request.args.get('trilha')
    if trilha == 'nenhuma':
        consulta = consulta.filter(Submissao.trilha_id.is_(None))
    elif trilha:
        consulta = consulta.filter_by(trilha_id=trilha)

    rodada_filtro = request.args.get('rodada')

    termo = (request.args.get('q') or '').lower()

    resultados = []
    for submissao in consulta.order_by(Submissao.id.desc()).all():
        respostas = submissao.respostas_dict()
        titulo = respostas.get('titulo', '')
        titulo = titulo if isinstance(titulo, str) else ''
        if termo and termo not in titulo.lower() and termo not in (submissao.codigo or '').lower():
            continue
        situacao = _situacao_efetiva(submissao)
        if situacao_pedida and situacao != situacao_pedida:
            continue

        ultima_rodada = (
            Rodada.query
            .filter_by(submissao_id=submissao.id)
            .order_by(Rodada.numero.desc())
            .first()
        )
        rodada_atual = ultima_rodada.numero if ultima_rodada else 0
        if rodada_filtro is not None and str(rodada_atual) != rodada_filtro:
            continue

        trilha_obj = Trilha.query.get(submissao.trilha_id) if submissao.trilha_id else None
        autores = [
            a.nome for a in
            Autoria.query.filter_by(submissao_id=submissao.id).order_by(Autoria.ordem).all()
        ]
        versao_vigente = (
            VersaoDeArquivo.query
            .filter_by(submissao_id=submissao.id, vigente=True)
            .first()
        )

        resultados.append({
            'id': str(submissao.id),
            'codigo': submissao.codigo,
            'titulo': titulo,
            'autores': autores,
            'trilhaId': str(submissao.trilha_id) if submissao.trilha_id else None,
            'trilhaNome': trilha_obj.nome if trilha_obj else None,
            'situacao': situacao,
            'rodadaAtual': rodada_atual,
            'foraDoPrazo': submissao.fora_do_prazo,
            'versaoVigente': versao_vigente.numero if versao_vigente else None,
            'dataUltimaAtualizacao': (
                submissao.data_ultimo_salvamento or submissao.data_confirmacao or submissao.criado_em
            ).isoformat() if (submissao.data_ultimo_salvamento or submissao.data_confirmacao or submissao.criado_em) else None,
        })

    return jsonify(resultados)


@submissoes_bp.route('/submissoes/<int:submissao_id>/linha-do-tempo', methods=['GET'])
def linha_do_tempo(submissao_id):
    usuario = _usuario()
    if usuario is None:
        return _erro('nao_autenticado', 'Sua sessão expirou.', 401)

    submissao = Submissao.query.get(submissao_id)
    pode_ver = submissao is not None and (
        submissao.autor_responsavel_id == usuario.id
        or _eh_chair_do_evento(usuario, submissao.evento_id)
    )
    if not pode_ver:
        return _erro('submissao_inexistente', 'Submissão não encontrada.', 404)

    evento = Evento.query.get(submissao.evento_id)
    fuso = evento.fuso if evento else ''
    eventos_da_linha = []

    if submissao.criado_em:
        eventos_da_linha.append({
            'id': f'submissao-{submissao.id}-criada',
            'tipo': 'submissao',
            'rotulo': 'Rascunho criado',
            'data': submissao.criado_em.isoformat(),
            'fuso': fuso,
        })

    for versao in VersaoDeArquivo.query.filter_by(submissao_id=submissao.id).order_by(VersaoDeArquivo.numero).all():
        if versao.data_envio:
            eventos_da_linha.append({
                'id': f'versao-{versao.id}',
                'tipo': 'versao',
                'rotulo': f'Versão {versao.numero} enviada',
                'data': versao.data_envio.isoformat(),
                'fuso': fuso,
            })

    if submissao.data_confirmacao:
        eventos_da_linha.append({
            'id': f'submissao-{submissao.id}-confirmada',
            'tipo': 'submissao',
            'rotulo': 'Submissão confirmada',
            'data': submissao.data_confirmacao.isoformat(),
            'fuso': fuso,
        })

    eventos_da_linha.extend(_eventos_de_avaliacao(submissao, usuario, fuso))

    if submissao.retirada_em:
        eventos_da_linha.append({
            'id': f'submissao-{submissao.id}-retirada',
            'tipo': 'submissao',
            'rotulo': 'Submissão retirada',
            'data': submissao.retirada_em.isoformat(),
            'fuso': fuso,
        })

    # Ordena pelo instante, não pela string: datas gravadas com e sem fuso convivem.
    eventos_da_linha.sort(key=lambda item: _instante_para_ordenar(item['data']))
    return jsonify(eventos_da_linha)


def _instante_para_ordenar(texto):
    instante = datetime.fromisoformat(texto)
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=timezone.utc)
    return instante


def _eventos_de_avaliacao(submissao, usuario, fuso):
    """Rodadas, rebuttal, decisão e versão corrigida (A13). A decisão
    registrada só aparece para o chair; ao autor só chega a comunicada."""
    eh_chair = _eh_chair_do_evento(usuario, submissao.evento_id)
    eventos = []

    def evento(identificador, tipo, rotulo, instante):
        if instante is not None:
            eventos.append({'id': identificador, 'tipo': tipo, 'rotulo': rotulo,
                            'data': instante.isoformat(), 'fuso': fuso})

    for rodada in Rodada.query.filter_by(submissao_id=submissao.id).order_by(Rodada.numero).all():
        evento(f'rodada-{rodada.id}-abertura', 'rodada', f'Rodada {rodada.numero} aberta', rodada.aberta_em)
        evento(f'rodada-{rodada.id}-encerramento', 'rodada', f'Rodada {rodada.numero} encerrada', rodada.encerrada_em)

        rebuttal = Rebuttal.query.filter_by(rodada_id=rodada.id).first()
        if rebuttal is not None:
            evento(f'rebuttal-{rebuttal.id}-abertura', 'rebuttal', 'Rebuttal aberto', rodada.encerrada_em)
            evento(f'rebuttal-{rebuttal.id}-envio', 'rebuttal', 'Rebuttal enviado', rebuttal.enviado_em)
            # Sem resposta e com o prazo passado (não há job que marque 'expirado').
            vencido = (
                rebuttal.enviado_em is None
                and rebuttal.prazo is not None
                and datetime.now(timezone.utc) > _com_fuso(rebuttal.prazo)
            )
            if vencido:
                evento(f'rebuttal-{rebuttal.id}-expiracao', 'rebuttal', 'Rebuttal expirado', rebuttal.prazo)

        decisao = Decisao.query.filter_by(rodada_id=rodada.id).first()
        if decisao is not None:
            if eh_chair:
                evento(f'decisao-{decisao.id}-registro', 'decisao',
                       f'Decisão da rodada {rodada.numero} registrada', decisao.decidido_em)
            evento(f'decisao-{decisao.id}-comunicacao', 'decisao',
                   f'Decisão da rodada {rodada.numero} comunicada', decisao.comunicada_em)

    corrigida = VersaoCorrigida.query.filter_by(submissao_id=submissao.id).first()
    if corrigida is not None:
        evento(f'versao-corrigida-{corrigida.id}-envio', 'versao', 'Versão corrigida enviada', corrigida.enviada_em)
        devolucoes = DevolucaoDeVersaoCorrigida.query.filter_by(versao_corrigida_id=corrigida.id).all()
        for devolucao in devolucoes:
            evento(f'versao-corrigida-devolucao-{devolucao.id}', 'versao', 'Versão corrigida devolvida',
                   devolucao.devolvida_em)
        evento(f'versao-corrigida-{corrigida.id}-validacao', 'versao', 'Versão corrigida validada',
               corrigida.validada_em)
    return eventos


def _com_fuso(instante):
    return instante if instante.tzinfo is not None else instante.replace(tzinfo=timezone.utc)


# --- P2: versão corrigida ---

@submissoes_bp.route('/submissoes/<int:submissao_id>/versao-corrigida', methods=['GET'])
def obter_versao_corrigida(submissao_id):
    usuario = _usuario()
    if usuario is None:
        return _erro('nao_autenticado', 'Sua sessão expirou.', 401)

    submissao = Submissao.query.get(submissao_id)
    eh_autor = submissao is not None and submissao.autor_responsavel_id == usuario.id
    eh_chair = submissao is not None and _eh_chair_do_evento(usuario, submissao.evento_id)
    versao_corrigida = VersaoCorrigida.query.filter_by(submissao_id=submissao_id).first()

    if submissao is None or versao_corrigida is None or not (eh_autor or eh_chair):
        return _erro('versao_corrigida_inexistente', 'Versão corrigida não encontrada.', 404)

    return jsonify(versao_corrigida.to_dict())


@submissoes_bp.route('/submissoes/<int:submissao_id>/versao-corrigida', methods=['POST'])
def enviar_versao_corrigida(submissao_id):
    usuario = _usuario()
    if usuario is None:
        return _erro('nao_autenticado', 'Sua sessão expirou.', 401)

    submissao = Submissao.query.get(submissao_id)
    if submissao is None:
        return _erro('submissao_inexistente', 'Submissão não encontrada.', 404)
    if submissao.autor_responsavel_id != usuario.id:
        return _erro('somente_autor_responsavel', 'Somente o autor responsável pode enviar a versão corrigida.', 403)

    dados = request.get_json(silent=True) or {}
    descricao = (dados.get('descricaoDasAlteracoes') or '').strip()
    versao_id = id_numerico(dados.get('versaoId'))

    if not descricao:
        return _erro('descricao_obrigatoria', 'Descreva as alterações realizadas.', 422)

    versao = VersaoDeArquivo.query.filter_by(id=versao_id, submissao_id=submissao_id).first()
    if versao is None:
        return _erro('versao_invalida', 'A versão informada não pertence a esta submissão.', 422)

    versao_corrigida = VersaoCorrigida.query.filter_by(submissao_id=submissao_id).first()
    if versao_corrigida is None:
        versao_corrigida = VersaoCorrigida(submissao_id=submissao_id)
        db.session.add(versao_corrigida)

    versao_corrigida.versao_id = versao_id
    versao_corrigida.descricao_das_alteracoes = descricao
    versao_corrigida.enviada_em = datetime.utcnow()

    db.session.commit()
    return jsonify(versao_corrigida.to_dict())


@submissoes_bp.route('/submissoes/<int:submissao_id>/versao-corrigida/validar', methods=['POST'])
def validar_versao_corrigida(submissao_id):
    usuario = _usuario()
    if usuario is None:
        return _erro('nao_autenticado', 'Sua sessão expirou.', 401)

    submissao = Submissao.query.get(submissao_id)
    if submissao is None:
        return _erro('submissao_inexistente', 'Submissão não encontrada.', 404)
    if not _eh_chair_do_evento(usuario, submissao.evento_id):
        return _erro('sem_permissao', 'Você não tem permissão para validar esta versão.', 403)

    versao_corrigida = VersaoCorrigida.query.filter_by(submissao_id=submissao_id).first()
    if versao_corrigida is None:
        return _erro('versao_corrigida_inexistente', 'Versão corrigida não encontrada.', 404)

    versao_corrigida.validada_em = datetime.utcnow()
    submissao.situacao = 'aceita'
    db.session.commit()
    return jsonify(versao_corrigida.to_dict())


@submissoes_bp.route('/submissoes/<int:submissao_id>/versao-corrigida/devolver', methods=['POST'])
def devolver_versao_corrigida(submissao_id):
    usuario = _usuario()
    if usuario is None:
        return _erro('nao_autenticado', 'Sua sessão expirou.', 401)

    submissao = Submissao.query.get(submissao_id)
    if submissao is None:
        return _erro('submissao_inexistente', 'Submissão não encontrada.', 404)
    if not _eh_chair_do_evento(usuario, submissao.evento_id):
        return _erro('sem_permissao', 'Você não tem permissão para devolver esta versão.', 403)

    versao_corrigida = VersaoCorrigida.query.filter_by(submissao_id=submissao_id).first()
    if versao_corrigida is None:
        return _erro('versao_corrigida_inexistente', 'Versão corrigida não encontrada.', 404)

    dados = request.get_json(silent=True) or {}
    apontamentos = (dados.get('apontamentos') or '').strip()
    if not apontamentos:
        return _erro('apontamentos_obrigatorios', 'Informe os apontamentos para o autor.', 422)

    db.session.add(DevolucaoDeVersaoCorrigida(
        versao_corrigida_id=versao_corrigida.id,
        apontamentos=apontamentos,
        devolvida_em=datetime.utcnow(),
        devolvida_por_nome=usuario.nome,
    ))
    submissao.situacao = 'aguardando_versao_corrigida'

    db.session.commit()
    return jsonify(versao_corrigida.to_dict())