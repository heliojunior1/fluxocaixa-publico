"""Telas e rotas de extração embutida (spec extracao-configuravel R6/R10–R12).

- Execução manual (R6): endpoint JSON consumido pelo botão "Executar agora".
- Fontes (R10): listagem, formulário dinâmico (R12), criar/editar/inativar,
  testar conexão.
- Execuções (R11): histórico com filtros e detalhe de erros.
As permissões são as da F3.1a; toda rota declara a sua.
"""
from fastapi import File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse

from ..auth.permissoes import requer
from ..domain.extracao import ExecucaoManualIn, ExecucaoOut
from ..extracao import registry
from ..extracao.conector import ErroLinha, LinhaExtraida
from ..extracao.form_schema import descrever_formulario
from ..extracao.mapeamento_json import (
    _TRANSF_API,
    LayoutApiRest,
    mapear_item,
)
from ..extracao.mapeamento_json import (
    itens as itens_mapeamento,
)
from ..extracao.parser_arquivo import (
    _DESTINO_COMPOSTO,
    _DESTINOS_SIMPLES,
    TRANSFORMACOES,
    LayoutArquivo,
    ParserArquivoError,
    parsear,
)
from ..models import SistemaOrigem
from ..services.extracao_service import (
    DISPARO_MANUAL,
    alterar_fonte,
    criar_fonte,
    executar_fonte,
    inativar_fonte,
    listar_execucoes,
    listar_fontes,
    montar_config_do_form,
    montar_janela,
    montar_layout_do_form,
    obter_fonte_para_edicao,
    testar_conexao_fonte,
)
from ..services.validacao import RegraNegocioError
from . import handle_exceptions, router, templates

# Opções expostas ao editor de layout (R17) — acompanham o registro de
# transformações; a UI não hardcoda nomes.
_DESTINOS_LAYOUT = sorted(_DESTINOS_SIMPLES) + [_DESTINO_COMPOSTO]
_TRANSFORMACOES_LAYOUT = sorted(TRANSFORMACOES)
_TRANSFORMACOES_MAPEAMENTO = sorted(_TRANSF_API)
_ENCODINGS_LAYOUT = ["utf-8-sig", "utf-8", "latin-1"]

PREVIEW_MAX_BYTES = 1_048_576  # 1 MB
PREVIEW_MAX_LINHAS = 20


# --------------------------------------------------------------------------
# Execução manual (R6)
# --------------------------------------------------------------------------

@router.post(
    '/api/extracao/fontes/{seq_fonte}/executar',
    dependencies=[requer('FC_EXEC_EXTRACAO')],
)
@handle_exceptions
async def executar_fonte_agora(seq_fonte: int, dados: ExecucaoManualIn | None = None):
    dados = dados or ExecucaoManualIn()
    janela = montar_janela(dados.data_inicio, dados.data_fim)
    execucao = executar_fonte(seq_fonte, janela=janela, disparo=DISPARO_MANUAL)
    resposta = ExecucaoOut.model_validate(execucao)
    return JSONResponse(resposta.model_dump(mode="json", by_alias=True))


# --------------------------------------------------------------------------
# Fontes (R10/R12)
# --------------------------------------------------------------------------

@router.get('/extracao/fontes', dependencies=[requer('FC_CONS_FONTE_EXTRACAO')])
@handle_exceptions
async def extracao_fontes(request: Request):
    nome = request.query_params.get('nome') or None
    tipo = request.query_params.get('tipo') or None
    status = request.query_params.get('status') or None
    fontes = listar_fontes(nome=nome, tipo=tipo, status=status)
    return templates.TemplateResponse('extracao_fontes.html', {
        'request': request,
        'fontes': fontes,
        'tipos_conector': registry.tipos_disponiveis(),
        'filtros': {'nome': nome or '', 'tipo': tipo or '', 'status': status or ''},
    })


def _contexto_form(request, *, tipo, fonte=None, config=None, layout=None):
    conector = registry.obter(tipo)
    if conector is None:
        raise RegraNegocioError(
            f"Tipo de conector '{tipo}' não está disponível", destino='/extracao/fontes'
        )
    # A tela escolhe a seção de layout pelo layout_kind do conector (R17/R22):
    # ARQUIVO → editor de arquivo (F3.2b); MAPEAMENTO → editor de mapeamento.
    return {
        'request': request,
        'tipo': tipo,
        'formulario': descrever_formulario(conector),
        'fonte': fonte,
        'config': config or {},
        'sistemas': [s.txt_sigla for s in SistemaOrigem.query.filter_by(ind_status='A').all()],
        'layout_kind': getattr(conector, 'layout_kind', None),
        'layout': layout or {},
        'destinos_layout': _DESTINOS_LAYOUT,
        'transformacoes_arquivo': _TRANSFORMACOES_LAYOUT,
        'transformacoes_mapeamento': _TRANSFORMACOES_MAPEAMENTO,
        'encodings_layout': _ENCODINGS_LAYOUT,
    }


@router.get('/extracao/fontes/nova', dependencies=[requer('FC_MANT_FONTE_EXTRACAO')])
@handle_exceptions
async def extracao_fonte_nova(request: Request):
    tipo = request.query_params.get('tipo')
    if not tipo:
        # sem tipo escolhido, volta à lista (a tela escolhe o tipo antes)
        return RedirectResponse('/extracao/fontes', status_code=303)
    return templates.TemplateResponse('extracao_fonte_form.html',
                                      _contexto_form(request, tipo=tipo))


@router.get('/extracao/fontes/{seq_fonte}/editar',
            dependencies=[requer('FC_MANT_FONTE_EXTRACAO')])
@handle_exceptions
async def extracao_fonte_editar(request: Request, seq_fonte: int):
    dados = obter_fonte_para_edicao(seq_fonte)
    return templates.TemplateResponse('extracao_fonte_form.html',
                                      _contexto_form(request, tipo=dados['cod_tipo_conector'],
                                                     fonte=dados, config=dados['json_config'],
                                                     layout=dados.get('json_layout')))


@router.post('/extracao/fontes', dependencies=[requer('FC_MANT_FONTE_EXTRACAO')])
@handle_exceptions
async def extracao_fonte_criar(request: Request):
    form = await request.form()
    tipo = form.get('cod_tipo_conector', '')
    config = montar_config_do_form(None, tipo, dict(form))
    layout = montar_layout_do_form(dict(form))
    criar_fonte(
        nom_fonte=form.get('nom_fonte', ''),
        cod_tipo_conector=tipo,
        sigla_sistema=form.get('sigla_sistema', ''),
        txt_cron=form.get('txt_cron') or None,
        json_config=config,
        json_layout=layout,
        cod_destino=form.get('cod_destino') or 'SALDO_FUNDO',
    )
    return RedirectResponse('/extracao/fontes', status_code=303)


@router.post('/extracao/fontes/{seq_fonte}/editar',
             dependencies=[requer('FC_MANT_FONTE_EXTRACAO')])
@handle_exceptions
async def extracao_fonte_atualizar(request: Request, seq_fonte: int):
    form = await request.form()
    tipo = form.get('cod_tipo_conector', '')
    config = montar_config_do_form(seq_fonte, tipo, dict(form))
    layout = montar_layout_do_form(dict(form))
    alterar_fonte(
        seq_fonte,
        nom_fonte=form.get('nom_fonte') or None,
        txt_cron=form.get('txt_cron') or None,
        json_config=config,
        json_layout=layout,
    )
    return RedirectResponse('/extracao/fontes', status_code=303)


@router.post('/extracao/fontes/preview-layout',
             dependencies=[requer('FC_MANT_FONTE_EXTRACAO')])
@handle_exceptions
async def extracao_preview_layout(
    arquivo: UploadFile = File(...),
    json_layout_raw: str = Form(...),
):
    """Prévia do parsing (R18): parseia o arquivo de amostra com o layout do
    form, em memória, SEM gravar nem registrar execução."""
    from pydantic import ValidationError

    layout = montar_layout_do_form({'json_layout_raw': json_layout_raw})
    try:
        LayoutArquivo.model_validate(layout or {})
    except ValidationError as exc:
        detalhes = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or 'layout'}: {e['msg']}"
            for e in exc.errors()
        )
        raise RegraNegocioError(f"Layout inválido: {detalhes}")

    conteudo = await arquivo.read(PREVIEW_MAX_BYTES + 1)
    if len(conteudo) > PREVIEW_MAX_BYTES:
        raise RegraNegocioError("Arquivo de amostra excede o limite do preview (1 MB)")

    try:
        emitidos = list(parsear(conteudo, layout, arquivo.filename or "amostra"))
    except ParserArquivoError as exc:
        return JSONResponse({'rejeitado': True, 'mensagem': str(exc)})

    linhas, erros = [], []
    for item in emitidos:
        if len(linhas) >= PREVIEW_MAX_LINHAS and len(erros) >= PREVIEW_MAX_LINHAS:
            break
        if isinstance(item, LinhaExtraida) and len(linhas) < PREVIEW_MAX_LINHAS:
            linhas.append({
                'cod_banco': item.cod_banco, 'num_agencia': item.num_agencia,
                'num_conta': item.num_conta, 'cod_fundo': item.cod_fundo,
                'dsc_fundo': item.dsc_fundo, 'val_saldo': str(item.val_saldo),
                'dat_saldo': item.dat_saldo.isoformat() if item.dat_saldo else None,
            })
        elif isinstance(item, ErroLinha) and len(erros) < PREVIEW_MAX_LINHAS:
            erros.append({'linha': item.numero, 'mensagem': item.mensagem})
    return JSONResponse({
        'rejeitado': False,
        'linhas': linhas,
        'erros': erros,
        'truncado': len(emitidos) > len(linhas) + len(erros),
    })


@router.post('/extracao/fontes/preview-mapeamento',
             dependencies=[requer('FC_MANT_FONTE_EXTRACAO')])
@handle_exceptions
async def extracao_preview_mapeamento(
    amostra_json: str = Form(...),
    json_layout_raw: str = Form(...),
):
    """Prévia do mapeamento (R22): mapeia uma amostra JSON colada com o layout
    do form, em memória, SEM gravar nem registrar execução."""
    import json as _json

    from pydantic import ValidationError

    layout = montar_layout_do_form({'json_layout_raw': json_layout_raw})
    try:
        LayoutApiRest.model_validate(layout or {})
    except ValidationError as exc:
        detalhes = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or 'layout'}: {e['msg']}"
            for e in exc.errors()
        )
        raise RegraNegocioError(f"Mapeamento inválido: {detalhes}")

    if len(amostra_json.encode('utf-8')) > PREVIEW_MAX_BYTES:
        raise RegraNegocioError("Amostra excede o limite do preview (1 MB)")
    try:
        dados = _json.loads(amostra_json)
    except ValueError:
        raise RegraNegocioError("Amostra inválida: JSON malformado")

    linhas, erros = [], []
    for i, item in enumerate(itens_mapeamento(dados, (layout or {}).get('lista_path'))):
        if len(linhas) >= PREVIEW_MAX_LINHAS and len(erros) >= PREVIEW_MAX_LINHAS:
            break
        mapeado = mapear_item(item, layout, cod_banco='', agencia='', conta='')
        if isinstance(mapeado, LinhaExtraida) and len(linhas) < PREVIEW_MAX_LINHAS:
            linhas.append({
                'cod_fundo': mapeado.cod_fundo, 'dsc_fundo': mapeado.dsc_fundo,
                'val_saldo': str(mapeado.val_saldo),
                'num_agencia': mapeado.num_agencia, 'num_conta': mapeado.num_conta,
            })
        elif isinstance(mapeado, ErroLinha) and len(erros) < PREVIEW_MAX_LINHAS:
            erros.append({'item': i, 'mensagem': mapeado.mensagem})
    return JSONResponse({'linhas': linhas, 'erros': erros})


@router.post('/extracao/fontes/{seq_fonte}/inativar',
             dependencies=[requer('FC_MANT_FONTE_EXTRACAO')])
@handle_exceptions
async def extracao_fonte_inativar(request: Request, seq_fonte: int):
    form = await request.form()
    if form.get('confirmado') != 'true':
        raise RegraNegocioError(
            'Confirme a inativação da fonte de extração', destino='/extracao/fontes'
        )
    inativar_fonte(seq_fonte)
    return RedirectResponse('/extracao/fontes', status_code=303)


@router.post('/extracao/fontes/{seq_fonte}/testar-conexao',
             dependencies=[requer('FC_MANT_FONTE_EXTRACAO')])
@handle_exceptions
async def extracao_fonte_testar(seq_fonte: int):
    resultado = testar_conexao_fonte(seq_fonte)
    return JSONResponse({'ok': resultado.ok, 'mensagem': resultado.mensagem})


# --------------------------------------------------------------------------
# Execuções (R11)
# --------------------------------------------------------------------------

@router.get('/extracao/execucoes', dependencies=[requer('FC_CONS_EXECUCAO_EXTRACAO')])
@handle_exceptions
async def extracao_execucoes(request: Request):
    seq_fonte = request.query_params.get('fonte')
    seq_fonte = int(seq_fonte) if seq_fonte else None
    status = request.query_params.get('status') or None
    execucoes = listar_execucoes(seq_fonte=seq_fonte, status=status)
    return templates.TemplateResponse('extracao_execucoes.html', {
        'request': request,
        'execucoes': execucoes,
        'fontes': listar_fontes(),
        'filtros': {'fonte': seq_fonte or '', 'status': status or ''},
    })
