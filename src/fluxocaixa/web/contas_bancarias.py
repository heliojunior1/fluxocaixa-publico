"""Web controller da gestão de contas bancárias (spec cadastros-nucleo R19–R22)."""
from fastapi import Request
from fastapi.responses import RedirectResponse

from ..auth.permissoes import requer
from ..services.conta_bancaria_service import (
    alterar_conta,
    conta_tem_vinculos,
    criar_conta,
    inativar_conta,
    listar_contas,
    reativar_conta,
)
from . import handle_exceptions, router, templates


@router.get('/contas-bancarias', dependencies=[requer('FC_CONS_CONTA')])
@handle_exceptions
async def contas_bancarias(request: Request):
    cod_banco = request.query_params.get('cod_banco') or None
    num_agencia = request.query_params.get('num_agencia') or None
    num_conta = request.query_params.get('num_conta') or None
    dsc = request.query_params.get('dsc') or None
    status = request.query_params.get('status') or 'ativo'

    lista = listar_contas(cod_banco=cod_banco, num_agencia=num_agencia,
                          num_conta=num_conta, dsc=dsc, status=status)
    contas_view = [
        {
            'seq_conta': c.seq_conta,
            'cod_banco': c.cod_banco,
            'num_agencia': c.num_agencia,
            'num_conta': c.num_conta,
            'dsc_conta': c.dsc_conta or '',
            'ativo': c.ind_status == 'A',
            # Tripla desabilitada no modal quando há vínculos (conveniência de
            # UI — a proteção real é o serviço, R21)
            'tem_vinculos': conta_tem_vinculos(c.seq_conta),
        }
        for c in lista
    ]
    return templates.TemplateResponse(
        'contas_bancarias.html',
        {
            'request': request,
            'contas': contas_view,
            'filtros': {'cod_banco': cod_banco or '', 'num_agencia': num_agencia or '',
                        'num_conta': num_conta or '', 'dsc': dsc or '',
                        'status': status},
        },
    )


@router.post('/contas-bancarias/adicionar', name='add_conta_bancaria',
             dependencies=[requer('FC_INS_CONTA')])
@handle_exceptions
async def add_conta_bancaria(request: Request):
    form = await request.form()
    criar_conta(form.get('cod_banco', ''), form.get('num_agencia', ''),
                form.get('num_conta', ''), form.get('dsc_conta', ''))
    return RedirectResponse('/contas-bancarias', status_code=303)


@router.post('/contas-bancarias/{seq_conta}/editar', name='edit_conta_bancaria',
             dependencies=[requer('FC_ALT_CONTA')])
@handle_exceptions
async def edit_conta_bancaria(request: Request, seq_conta: int):
    form = await request.form()
    alterar_conta(seq_conta, form.get('cod_banco', ''), form.get('num_agencia', ''),
                  form.get('num_conta', ''), form.get('dsc_conta', ''))
    return RedirectResponse('/contas-bancarias', status_code=303)


@router.post('/contas-bancarias/{seq_conta}/inativar', name='inativar_conta_bancaria',
             dependencies=[requer('FC_DEL_CONTA')])
@handle_exceptions
async def inativar_conta_bancaria(request: Request, seq_conta: int):
    inativar_conta(seq_conta)
    return RedirectResponse('/contas-bancarias', status_code=303)


@router.post('/contas-bancarias/{seq_conta}/reativar', name='reativar_conta_bancaria',
             dependencies=[requer('FC_ATIVAR_CONTA')])
@handle_exceptions
async def reativar_conta_bancaria(request: Request, seq_conta: int):
    reativar_conta(seq_conta)
    # Mantém o filtro "todas" — é de onde a ação de reativar é acionada
    return RedirectResponse('/contas-bancarias?status=todas', status_code=303)
