"""Web controller da simulação de disponibilidade (spec desembolso R9–R12)."""
from datetime import date
from decimal import Decimal

from fastapi import Request
from fastapi.responses import RedirectResponse

from . import handle_exceptions, router, templates
from ..auth.permissoes import requer
from ..services.simulacao_desembolso_service import (
    MODO_PRUDENTE,
    colchao_do_grupo,
    confirmar_lote,
    definir_colchao,
    simular,
)


def _params(request: Request) -> dict:
    qp = request.query_params
    return {
        'cenario_id': int(qp['cenario']) if qp.get('cenario', '').isdigit() else None,
        'ano': int(qp.get('ano') or date.today().year),
        'grupo': qp.get('grupo') or 'L',
        'modo': qp.get('modo') or MODO_PRUDENTE,
        'mes_inicial': int(qp.get('mes') or date.today().month),
    }


@router.get('/simulacao-desembolso', name='simulacao_desembolso',
            dependencies=[requer('FC_EXEC_SIMULACAO_DESEMBOLSO')])
@handle_exceptions
async def simulacao_desembolso(request: Request):
    from ..models import SimuladorCenario

    p = _params(request)
    cenarios = SimuladorCenario.query.filter_by(ind_status='A').all()
    resultado = None
    if p['cenario_id'] is not None:
        resultado = simular(p['cenario_id'], p['ano'], grupo=p['grupo'],
                            modo=p['modo'], mes_inicial=p['mes_inicial'])

    return templates.TemplateResponse('simulacao_desembolso.html', {
        'request': request,
        'cenarios': cenarios,
        'params': p,
        'resultado': resultado,
        'colchao_l': colchao_do_grupo('L'),
        'colchao_v': colchao_do_grupo('V'),
    })


@router.post('/simulacao-desembolso/confirmar', name='confirmar_lote_route',
             dependencies=[requer('FC_CONF_LIBERACAO')])
@handle_exceptions
async def confirmar_lote_route(request: Request):
    form = await request.form()
    confirmar_lote(
        int(form['cenario']), int(form['ano']),
        grupo=form.get('grupo') or 'L',
        modo=form.get('modo') or MODO_PRUDENTE,
        mes_inicial=int(form.get('mes') or 1),
        justificativa=form.get('justificativa'),
    )
    return RedirectResponse(
        f"/simulacao-desembolso?cenario={form['cenario']}&ano={form['ano']}"
        f"&grupo={form.get('grupo') or 'L'}&mes={form.get('mes') or 1}",
        status_code=303)


@router.post('/simulacao-desembolso/colchao', name='definir_colchao_route',
             dependencies=[requer('FC_MANT_PARAM_DESEMBOLSO')])
@handle_exceptions
async def definir_colchao_route(request: Request):
    form = await request.form()
    definir_colchao(Decimal(form['valor']), grupo=form.get('grupo') or None)
    return RedirectResponse('/simulacao-desembolso', status_code=303)
