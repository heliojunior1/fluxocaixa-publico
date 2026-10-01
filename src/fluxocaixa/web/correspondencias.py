"""Tela do De/Para de rubricas entre exercícios (previsao R30–R32).

Rotas finas: parse + chamada de serviço + redirect. Regra de negócio vive em
`correspondencia_rubrica_service` e levanta `RegraNegocioError` (flash +
redirect pelo handler global).
"""
from fastapi import Request
from fastapi.responses import RedirectResponse

from ..auth.permissoes import requer
from ..services import correspondencia_rubrica_service as de_para
from . import handle_exceptions, router, templates

_TELA = '/previsao/correspondencias'


@router.get(_TELA, name='correspondencias_rubricas',
            dependencies=[requer('FC_CONS_CORRESPONDENCIA_RUBRICA')])
@handle_exceptions
async def correspondencias_rubricas(request: Request):
    return templates.TemplateResponse('correspondencias_rubricas.html', {
        'request': request,
        'linhas': de_para.listar_para_tela(),
        'versao': de_para.versao_atual(),
    })


@router.post(_TELA, name='correspondencia_criar',
             dependencies=[requer('FC_MANT_CORRESPONDENCIA_RUBRICA')])
@handle_exceptions
async def correspondencia_criar(request: Request):
    form = await request.form()
    de_para.criar_por_codigos(
        form.get('cod_tipo'), form.get('num_ano_vigencia'), form.get('origens'),
        form.get('destinos'), form.get('dsc_referencia_ato'), form.get('dsc_fundamento'),
        regras_txt=form.get('regras') or '')
    request.session['flash'] = 'Correspondência cadastrada'
    return RedirectResponse(_TELA, status_code=303)


@router.post(_TELA + '/{seq}/inativar', name='correspondencia_inativar',
             dependencies=[requer('FC_MANT_CORRESPONDENCIA_RUBRICA')])
@handle_exceptions
async def correspondencia_inativar(request: Request, seq: int):
    form = await request.form()
    de_para.inativar_correspondencia(seq, form.get('motivo'))
    return RedirectResponse(_TELA, status_code=303)


@router.post(_TELA + '/{seq}/rateio', name='correspondencia_rateio',
             dependencies=[requer('FC_DEFINIR_RATEIO_CORRESPONDENCIA')])
@handle_exceptions
async def correspondencia_rateio(request: Request, seq: int):
    form = await request.form()
    percentuais = {chave[len('pct_'):]: valor for chave, valor in form.items()
                   if chave.startswith('pct_')}
    de_para.definir_rateio(seq, percentuais, form.get('dsc_fundamento'))
    return RedirectResponse(_TELA, status_code=303)


@router.post(_TELA + '/{seq}/rateio/remover', name='correspondencia_rateio_remover',
             dependencies=[requer('FC_DEFINIR_RATEIO_CORRESPONDENCIA')])
@handle_exceptions
async def correspondencia_rateio_remover(request: Request, seq: int):
    form = await request.form()
    de_para.remover_rateio(seq, form.get('motivo'))
    return RedirectResponse(_TELA, status_code=303)
