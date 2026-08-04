"""Web controller do funil orçamentário — dotações (spec execucao-orcamentaria R1–R3)."""
from datetime import date
from decimal import Decimal

from fastapi import File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse

from ..auth.permissoes import requer
from ..services.dotacao_service import criar_dotacao, registrar_credito, visao_do_ano
from . import handle_exceptions, router, templates


def _qualificadores_despesa():
    from ..models import Qualificador

    return [q for q in Qualificador.query.filter_by(ind_status='A')
            .order_by(Qualificador.num_qualificador).all()
            if q.is_folha() and q.tipo_fluxo == 'despesa']


@router.get('/orcamento/dotacoes', name='dotacoes',
            dependencies=[requer('FC_CONS_DOTACAO')])
@handle_exceptions
async def dotacoes(request: Request):
    ano_raw = request.query_params.get('ano') or ''
    ano = int(ano_raw) if ano_raw.isdigit() else date.today().year
    return templates.TemplateResponse('dotacoes.html', {
        'request': request,
        'ano': ano,
        'linhas': visao_do_ano(ano),
        'qualificadores': _qualificadores_despesa(),
    })


@router.post('/orcamento/dotacoes', name='criar_dotacao_route',
             dependencies=[requer('FC_MANT_DOTACAO')])
@handle_exceptions
async def criar_dotacao_route(request: Request):
    form = await request.form()
    criar_dotacao(num_ano=int(form['num_ano']),
                  seq_qualificador=int(form['seq_qualificador']),
                  val_dotacao_inicial=Decimal(form['val_dotacao_inicial']))
    return RedirectResponse(f"/orcamento/dotacoes?ano={form['num_ano']}", status_code=303)


@router.post('/orcamento/dotacoes/credito', name='registrar_credito_route',
             dependencies=[requer('FC_MANT_DOTACAO')])
@handle_exceptions
async def registrar_credito_route(request: Request):
    form = await request.form()
    registrar_credito(
        seq_dotacao=int(form['seq_dotacao']),
        cod_tipo_credito=form['cod_tipo_credito'],
        val_credito=Decimal(form['val_credito']),
        dat_credito=date.fromisoformat(form['dat_credito']),
        dsc_referencia_ato=form.get('dsc_referencia_ato', ''))
    return RedirectResponse(f"/orcamento/dotacoes?ano={form['num_ano']}", status_code=303)


@router.get('/orcamento/execucao', name='execucao_orcamentaria',
            dependencies=[requer('FC_CONS_EXECUCAO_ORCAMENTARIA')])
@handle_exceptions
async def execucao_orcamentaria(request: Request):
    from ..services.execucao_orcamentaria_service import funil_do_ano, valor_corrente

    ano_raw = request.query_params.get('ano') or ''
    ano = int(ano_raw) if ano_raw.isdigit() else date.today().year
    funil = funil_do_ano(ano)
    correntes = {d.seq_execucao: valor_corrente(d.seq_execucao)
                 for d in funil['documentos']}
    return templates.TemplateResponse('execucao_orcamentaria.html', {
        'request': request,
        'ano': ano,
        'funil': funil,
        'correntes': correntes,
    })


@router.get('/orcamento/funil', name='funil_orcamento',
            dependencies=[requer('FC_REL_FUNIL')])
@handle_exceptions
async def funil_orcamento(request: Request):
    from ..models import Orgao
    from ..services.funil_service import conciliacao_orcamento_caixa, relatorio_funil

    ano_raw = request.query_params.get('ano') or ''
    ano = int(ano_raw) if ano_raw.isdigit() else date.today().year
    return templates.TemplateResponse('funil_orcamento.html', {
        'request': request,
        'ano': ano,
        'funil': relatorio_funil(ano),
        'conciliacao': conciliacao_orcamento_caixa(ano),
        'nomes_orgaos': {o.cod_orgao: o.nom_orgao
                         for o in Orgao.query.filter_by(ind_status='A').all()},
    })


@router.post('/orcamento/execucao/importar', name='importar_execucao',
             dependencies=[requer('FC_IMP_EXECUCAO_ORCAMENTARIA')])
@handle_exceptions
async def importar_execucao(request: Request, arquivo: UploadFile = File(...),
                            ano_import: int = Form(...)):
    """Importa a execução E/L/P (upload → preview → confirmar)."""
    from ..services.preprocessamento import criar_preview
    from .importacao import render_preview

    token, preview = criar_preview(
        'execucao', await _ler(arquivo), arquivo.filename, request.session,
        contexto={"ano": ano_import})
    return render_preview(request, 'execucao', token, preview)


@router.post('/orcamento/dotacoes/importar', name='importar_dotacao',
             dependencies=[requer('FC_IMP_DOTACAO')])
@handle_exceptions
async def importar_dotacao(request: Request, arquivo: UploadFile = File(...),
                           ano_import: int = Form(...)):
    """Importa a dotação inicial (upload → preview → confirmar)."""
    from ..services.preprocessamento import criar_preview
    from .importacao import render_preview

    token, preview = criar_preview(
        'dotacao', await _ler(arquivo), arquivo.filename, request.session,
        contexto={"ano": ano_import})
    return render_preview(request, 'dotacao', token, preview)


async def _ler(arquivo):
    """Upload com teto de bytes e extensão validada (importacao-arquivos R6)."""
    from ..services.preprocessamento import ler_upload_limitado, validar_extensao

    validar_extensao(arquivo.filename)
    return await ler_upload_limitado(arquivo)
