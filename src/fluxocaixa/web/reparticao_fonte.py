"""Web controller da repartição por fonte (spec fonte-recurso R8–R9)."""
from decimal import Decimal

from fastapi import Request
from fastapi.responses import RedirectResponse

from . import handle_exceptions, router, templates
from ..auth.permissoes import requer
from ..services.fonte_recurso_service import listar_fontes
from ..services.reparticao_fonte_service import (
    definir_reparticao,
    reparticoes_de,
    sugestao_do_historico,
)


@router.get('/reparticao-fonte', name='reparticao_fonte',
            dependencies=[requer('FC_CONS_REPARTICAO_FONTE')])
@handle_exceptions
async def reparticao_fonte(request: Request):
    from datetime import date

    from ..models import FonteRecurso, Qualificador

    vigencia_raw = request.query_params.get('vigencia') or ''
    vigencia = int(vigencia_raw) if vigencia_raw.isdigit() else date.today().year

    fontes_por_seq = {f.seq_fonte_recurso: f for f in FonteRecurso.query.all()}
    receitas = [
        q for q in Qualificador.query.filter_by(ind_status='A').all()
        if q.is_folha() and q.tipo_fluxo == 'receita'
    ]

    linhas = []
    for q in receitas:
        reparticoes = reparticoes_de(q.seq_qualificador, vigencia)
        linhas.append({
            'qualificador': q,
            'reparticoes': [
                {'fonte': fontes_por_seq[r.seq_fonte_recurso],
                 'pct': r.pct_reparticao}
                for r in reparticoes
            ],
            'sugestao': [
                {'fonte': fontes_por_seq.get(s['seq_fonte_recurso']),
                 'pct': s['pct']}
                for s in sugestao_do_historico(q.seq_qualificador)
            ],
        })

    fontes_ativas = [
        {'seq': f.seq_fonte_recurso,
         'rotulo': f"{f.codigo_completo} · {f.dsc_fonte_recurso}"}
        for f in listar_fontes(status='ativo')
    ]
    return templates.TemplateResponse('reparticao_fonte.html', {
        'request': request,
        'linhas': linhas,
        'vigencia': vigencia,
        'fontes_ativas': fontes_ativas,
    })


@router.post('/reparticao-fonte/{seq_qualificador}/definir', name='definir_reparticao_route',
             dependencies=[requer('FC_MANT_REPARTICAO_FONTE')])
@handle_exceptions
async def definir_reparticao_route(request: Request, seq_qualificador: int):
    form = await request.form()
    vigencia = int(form['vigencia'])
    percentuais = []
    for chave, valor in form.multi_items():
        if chave.startswith('pct_') and str(valor).strip():
            percentuais.append((int(chave.replace('pct_', '')), Decimal(str(valor))))
    definir_reparticao(seq_qualificador, vigencia, percentuais)
    return RedirectResponse(f'/reparticao-fonte?vigencia={vigencia}', status_code=303)
