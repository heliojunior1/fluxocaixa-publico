"""Web controller da programação de desembolso (spec desembolso R21–R22)."""
from datetime import date
from decimal import Decimal

from fastapi import File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse

from . import handle_exceptions, router, templates
from ..auth.permissoes import requer
from ..services.orgao_service import listar_orgaos
from ..services.programacao_service import registrar_cota, visao_anual


@router.get('/desembolso/programacao', name='programacao_desembolso',
            dependencies=[requer('FC_CONS_PROGRAMACAO')])
@handle_exceptions
async def programacao_desembolso(request: Request):
    ano_raw = request.query_params.get('ano') or ''
    ano = int(ano_raw) if ano_raw.isdigit() else date.today().year
    orgaos = listar_orgaos(status='ativo')
    return templates.TemplateResponse('programacao_desembolso.html', {
        'request': request,
        'ano': ano,
        'linhas': visao_anual(ano),
        'orgaos': orgaos,
        'nomes_orgaos': {o.cod_orgao: o.nom_orgao for o in orgaos},
    })


@router.post('/desembolso/programacao/cota', name='registrar_cota_route',
             dependencies=[requer('FC_MANT_PROGRAMACAO')])
@handle_exceptions
async def registrar_cota_route(request: Request):
    form = await request.form()
    registrar_cota(
        num_ano=int(form['num_ano']), num_mes=int(form['num_mes']),
        cod_orgao=int(form['cod_orgao']),
        val_cota=Decimal(form['val_cota']),
        dsc_referencia_ato=form.get('dsc_referencia_ato', ''))
    return RedirectResponse(
        f"/desembolso/programacao?ano={form['num_ano']}", status_code=303)


@router.post('/desembolso/programacao/importar', name='importar_programacao',
             dependencies=[requer('FC_IMP_PROGRAMACAO')])
@handle_exceptions
async def importar_programacao(request: Request, arquivo: UploadFile = File(...),
                               ano_import: int = Form(...)):
    """Importa o decreto de programação (upload → preview → confirmar)."""
    from ..services.preprocessamento import criar_preview
    from ..services.preprocessamento_adapters import _AdapterProgramacao
    from .importacao import render_preview

    _AdapterProgramacao._ano = ano_import
    token, preview = criar_preview(
        'programacao', await arquivo.read(), arquivo.filename, request.session)
    return render_preview(request, 'programacao', token, preview)
