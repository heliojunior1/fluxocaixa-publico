"""Web controller do cadastro de órgãos (spec desembolso R5)."""
from fastapi import Request
from fastapi.responses import RedirectResponse

from ..auth.permissoes import requer
from ..services.orgao_service import (
    alterar_orgao,
    criar_orgao,
    inativar_orgao,
    listar_orgaos,
)
from . import handle_exceptions, router, templates


@router.get('/orgaos', name='orgaos', dependencies=[requer('FC_CONS_ORGAO')])
@handle_exceptions
async def orgaos(request: Request):
    status = request.query_params.get('status') or None
    return templates.TemplateResponse('orgaos.html', {
        'request': request,
        'orgaos': listar_orgaos(status=status),
        'filtros': {'status': status or ''},
    })


@router.post('/orgaos/adicionar', name='add_orgao', dependencies=[requer('FC_MANT_ORGAO')])
@handle_exceptions
async def add_orgao(request: Request):
    form = await request.form()
    criar_orgao(int(form['cod_orgao']), form.get('nom_orgao', ''))
    return RedirectResponse('/orgaos', status_code=303)


@router.post('/orgaos/{cod_orgao}/editar', name='edit_orgao', dependencies=[requer('FC_MANT_ORGAO')])
@handle_exceptions
async def edit_orgao(request: Request, cod_orgao: int):
    form = await request.form()
    alterar_orgao(cod_orgao, form.get('nom_orgao', ''))
    return RedirectResponse('/orgaos', status_code=303)


@router.post('/orgaos/{cod_orgao}/inativar', name='inativar_orgao_route',
             dependencies=[requer('FC_MANT_ORGAO')])
@handle_exceptions
async def inativar_orgao_route(request: Request, cod_orgao: int):
    inativar_orgao(cod_orgao)
    return RedirectResponse('/orgaos', status_code=303)
