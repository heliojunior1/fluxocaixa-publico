"""Tela de execuções de mapeamento (spec automacao-lancamentos R16).

Consultar e executar exigem permissões distintas: processar **gera lançamentos**
(e pode remover, no resync), então não é consulta.
"""
from fastapi import Request
from fastapi.responses import RedirectResponse

from ..auth.permissoes import requer
from ..models import ExecucaoMapeamento
from ..models.execucao_mapeamento import DISPARO_MANUAL
from ..services.mapeamento_service import listar_mapeamentos
from ..services.processamento_service import processar_mapeamento
from . import handle_exceptions, router, templates

_DESTINO = '/mapeamentos/execucoes'
_LIMITE = 200



@router.get('/mapeamentos/execucoes', name='execucoes_mapeamento',
            dependencies=[requer('FC_CONS_EXECUCAO_MAPEAMENTO')])
@handle_exceptions
async def execucoes_mapeamento(request: Request):
    execucoes = (ExecucaoMapeamento.query
                 .order_by(ExecucaoMapeamento.seq_execucao_mapeamento.desc())
                 .limit(_LIMITE).all())
    linhas = []
    for e in execucoes:
        mapeamento = e.mapeamento
        linhas.append({
            'seq_execucao_mapeamento': e.seq_execucao_mapeamento,
            'mapeamento': mapeamento.dsc_mapeamento if mapeamento else '—',
            'cod_status': e.cod_status,
            'cod_disparo': e.cod_disparo,
            'dat_inicio_execucao': e.dat_inicio_execucao,
            'num_duracao_segundos': e.num_duracao_segundos,
            'qtd_lancamentos_gerados': e.qtd_lancamentos_gerados,
            'qtd_linhas_erro': e.qtd_linhas_erro,
            'qtd_lancamentos_removidos': e.qtd_lancamentos_removidos,
            'txt_detalhe_erros': e.txt_detalhe_erros,
        })
    return templates.TemplateResponse('execucoes_mapeamento.html', {
        'request': request,
        'execucoes': linhas,
        'mapeamentos': listar_mapeamentos(apenas_ativos=True),
    })


@router.post('/mapeamentos/processar/{seq_mapeamento}', name='processar_mapeamento_web',
             dependencies=[requer('FC_EXEC_MAPEAMENTO')])
@handle_exceptions
async def processar_mapeamento_web(request: Request, seq_mapeamento: int):
    processar_mapeamento(seq_mapeamento, disparo=DISPARO_MANUAL)
    return RedirectResponse(_DESTINO, status_code=303)
