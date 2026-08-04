"""Web controller das liberações do desembolso (spec desembolso R1–R4).

Visão semanal (segunda a sexta) agrupada por natureza → órgão, inserção
manual (rascunho), confirmação (permissão própria — ato distinto de manter)
e cancelamento com confirmação explícita.
"""
from datetime import date, timedelta
from decimal import Decimal

from fastapi import Request
from fastapi.responses import RedirectResponse

from ..auth.permissoes import requer
from ..services.fonte_recurso_service import listar_fontes
from ..services.liberacao_service import (
    cancelar_liberacao,
    confirmar_liberacao,
    criar_liberacao,
    saldo_liberado_pendente,
    visao_semanal,
)
from ..services.orgao_service import listar_orgaos
from . import handle_exceptions, router, templates


@router.get('/liberacoes', name='liberacoes', dependencies=[requer('FC_CONS_LIBERACAO')])
@handle_exceptions
async def liberacoes(request: Request):
    from ..models import Qualificador

    ref_raw = request.query_params.get('ref') or ''
    referencia = date.fromisoformat(ref_raw) if ref_raw else date.today()

    visao = visao_semanal(referencia)
    orgaos = listar_orgaos(status='ativo')
    nomes_orgaos = {o.cod_orgao: o.nom_orgao for o in orgaos}
    fontes = [
        {'seq': f.seq_fonte_recurso,
         'rotulo': f"{f.codigo_completo} · {f.dsc_fonte_recurso}"}
        for f in listar_fontes(status='ativo')
    ]
    qualificadores_despesa = [
        q for q in Qualificador.query.filter_by(ind_status='A').all()
        if q.is_folha() and q.tipo_fluxo == 'despesa'
    ]

    from ..services.execucao_orcamentaria_service import liquidado_nao_pago
    from ..services.previsto_loa_service import previsto_da_semana

    return templates.TemplateResponse('liberacoes.html', {
        'request': request,
        'previsto_semana': previsto_da_semana(visao['dias']),
        'devido_ano': liquidado_nao_pago(date.today().year)['total'],
        'visao': visao,
        'referencia': referencia,
        'semana_anterior': (visao['dias'][0] - timedelta(days=7)).isoformat(),
        'semana_seguinte': (visao['dias'][0] + timedelta(days=7)).isoformat(),
        'pendente': saldo_liberado_pendente(),
        'orgaos': orgaos,
        'nomes_orgaos': nomes_orgaos,
        'fontes': fontes,
        'qualificadores_despesa': qualificadores_despesa,
    })


@router.post('/liberacoes/adicionar', name='add_liberacao',
             dependencies=[requer('FC_MANT_LIBERACAO')])
@handle_exceptions
async def add_liberacao(request: Request):
    form = await request.form()
    criar_liberacao(
        dat_liberacao=date.fromisoformat(form['dat_liberacao']),
        cod_orgao=int(form['cod_orgao']),
        seq_qualificador=int(form['seq_qualificador']),
        seq_fonte_recurso=(int(form.get('seq_fonte_recurso'))
                           if form.get('seq_fonte_recurso') else None),
        val_liberacao=Decimal(form['val_liberacao']),
        dsc_liberacao=form.get('dsc_liberacao'),
        dsc_justificativa=form.get('dsc_justificativa'),
        cod_natureza_obrigacao=form.get('cod_natureza_obrigacao') or 'D',
        dsc_base_legal=form.get('dsc_base_legal'),
        dat_prevista_desembolso=(date.fromisoformat(form['dat_prevista_desembolso'])
                                 if form.get('dat_prevista_desembolso') else None),
    )
    return RedirectResponse(
        f"/liberacoes?ref={form['dat_liberacao']}", status_code=303)


@router.post('/liberacoes/{seq}/confirmar', name='confirmar_liberacao_route',
             dependencies=[requer('FC_CONF_LIBERACAO')])
@handle_exceptions
async def confirmar_liberacao_route(request: Request, seq: int):
    form = await request.form()
    liberacao = confirmar_liberacao(seq, confirmado=form.get('confirmado') == 'true')
    return RedirectResponse(
        f"/liberacoes?ref={liberacao.dat_liberacao.isoformat()}", status_code=303)


@router.get('/desembolso/execucao', name='execucao_desembolso',
            dependencies=[requer('FC_REL_EXECUCAO_DESEMBOLSO')])
@handle_exceptions
async def execucao_desembolso(request: Request):
    """Relatório previsto (LOA) × liberado × pago por natureza (F7.3a)."""
    from ..services.previsto_loa_service import relatorio_execucao

    ano_raw = request.query_params.get('ano') or ''
    ano = int(ano_raw) if ano_raw.isdigit() else date.today().year
    return templates.TemplateResponse('execucao_desembolso.html', {
        'request': request,
        'rel': relatorio_execucao(ano),
        'naturezas_rotulos': {'D': 'Discricionária', 'O': 'Constitucional/legal',
                              'J': 'Judicial', 'F': 'Folha', 'V': 'Dívida'},
    })


@router.post('/liberacoes/{seq}/cancelar', name='cancelar_liberacao_route',
             dependencies=[requer('FC_MANT_LIBERACAO')])
@handle_exceptions
async def cancelar_liberacao_route(request: Request, seq: int):
    form = await request.form()
    liberacao = cancelar_liberacao(
        seq,
        justificativa=form.get('justificativa'),
        confirmado=form.get('confirmado') == 'true',
    )
    return RedirectResponse(
        f"/liberacoes?ref={liberacao.dat_liberacao.isoformat()}", status_code=303)
