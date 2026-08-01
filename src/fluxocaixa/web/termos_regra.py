"""Tela do dicionário de termos de regra (spec automacao-lancamentos R9).

As opções (origens, tipos, whitelist de colunas) são injetadas pelo servidor —
a UI não hardcoda vocabulário, mesmo padrão do editor de mapeamento da extração.
"""
from fastapi import Request
from fastapi.responses import RedirectResponse

from . import handle_exceptions, router, templates
from ..auth.permissoes import requer
from ..models.termo_regra import (
    COLUNAS_PERMITIDAS,
    ORIGEM_ATRIBUTO,
    ORIGEM_COLUNA,
    ORIGENS_VALIDAS,
    TIPOS_VALIDOS,
)
from ..services.termo_regra_service import (
    alterar_termo,
    criar_termo,
    inativar_termo,
    listar_termos,
)
from ..services.validacao import RegraNegocioError

_DESTINO = '/termos-regra'


@router.get('/termos-regra', name='termos_regra',
            dependencies=[requer('FC_CONS_TERMO_REGRA')])
@handle_exceptions
async def termos_regra(request: Request):
    return templates.TemplateResponse('termos_regra.html', {
        'request': request,
        'termos': listar_termos(apenas_ativos=False),
        'origens': list(ORIGENS_VALIDAS),
        'tipos': list(TIPOS_VALIDOS),
        # a whitelist é a fonte da verdade das colunas oferecidas (R5)
        'colunas_permitidas': COLUNAS_PERMITIDAS,
        'origem_coluna': ORIGEM_COLUNA,
        'origem_atributo': ORIGEM_ATRIBUTO,
    })


@router.post('/termos-regra/add', name='add_termo_regra',
             dependencies=[requer('FC_MANT_TERMO_REGRA')])
@handle_exceptions
async def termo_regra_add(request: Request):
    form = await request.form()
    criar_termo(
        nom_termo=form.get('nom_termo', ''),
        cod_origem_campo=form.get('cod_origem_campo', ''),
        nom_campo=form.get('nom_campo', ''),
        cod_tipo=form.get('cod_tipo', ''),
    )
    return RedirectResponse(_DESTINO, status_code=303)


@router.post('/termos-regra/edit/{seq_termo_regra}', name='edit_termo_regra',
             dependencies=[requer('FC_MANT_TERMO_REGRA')])
@handle_exceptions
async def termo_regra_edit(request: Request, seq_termo_regra: int):
    form = await request.form()
    alterar_termo(
        seq_termo_regra,
        nom_termo=form.get('nom_termo', ''),
        cod_origem_campo=form.get('cod_origem_campo', ''),
        nom_campo=form.get('nom_campo', ''),
        cod_tipo=form.get('cod_tipo', ''),
    )
    return RedirectResponse(_DESTINO, status_code=303)


@router.post('/termos-regra/inativar/{seq_termo_regra}', name='inativar_termo_regra',
             dependencies=[requer('FC_MANT_TERMO_REGRA')])
@handle_exceptions
async def termo_regra_inativar(request: Request, seq_termo_regra: int):
    form = await request.form()
    if form.get('confirmado') != 'true':
        raise RegraNegocioError("Confirme a inativação do termo", destino=_DESTINO)
    inativar_termo(seq_termo_regra)
    return RedirectResponse(_DESTINO, status_code=303)
