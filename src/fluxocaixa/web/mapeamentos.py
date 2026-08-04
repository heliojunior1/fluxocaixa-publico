"""Tela de mapeamentos com builder, validação e preview (spec R10/R11).

O texto é a verdade: o builder é açúcar de UI que gera `txt_regra`. Validar e
prever exigem apenas CONSULTA — não gravam nada.
"""
import json

from fastapi import Form, Request
from fastapi.responses import JSONResponse, RedirectResponse

from ..auth.permissoes import requer
from ..models import Mapeamento, SistemaOrigem
from ..services.mapeamento_service import (
    alterar_mapeamento,
    criar_mapeamento,
    inativar_mapeamento,
    listar_mapeamentos,
)
from ..services.qualificador_service import (
    list_despesa_qualificadores_folha,
    list_receita_qualificadores_folha,
)
from ..services.regra import preview_regra, validar_regra
from ..services.regra.builder import ROTULOS_OPERADOR, montar_regra, regra_para_builder
from ..services.termo_regra_service import listar_termos
from ..services.validacao import RegraNegocioError
from . import handle_exceptions, router, templates


def _exercicio_combo():
    """F10.4 (R28): combos de tela oferecem o plano do exercício corrente
    RESOLVIDO — nunca a união de todos os planos."""
    from ..services.qualificador_service import exercicio_corrente

    return exercicio_corrente()

_DESTINO = '/mapeamentos'



def _itens_do_form(itens_raw: str) -> list[dict]:
    """Hidden com JSON → list[dict] (padrão `json_layout_raw` da extração).

    Só desserializa; validação de conteúdo é do serviço.
    """
    try:
        itens = json.loads(itens_raw or '[]')
    except json.JSONDecodeError as exc:
        raise RegraNegocioError(f"Itens inválidos: {exc}")
    if not isinstance(itens, list):
        raise RegraNegocioError("Itens inválidos: esperava uma lista")
    return itens


def _contexto_form(request, mapeamento=None):
    termos = listar_termos(apenas_ativos=True)
    itens = []
    if mapeamento is not None:
        for item in mapeamento.itens:
            if item.ind_status != 'A':
                continue
            estado = regra_para_builder(item.txt_regra)
            itens.append({
                'seq_item_mapeamento': item.seq_item_mapeamento,
                'seq_qualificador': item.seq_qualificador,
                'txt_regra': item.txt_regra,
                'ind_inversao_sinal': item.ind_inversao_sinal,
                **estado,
            })
    return {
        'request': request,
        'mapeamento': mapeamento,
        'itens': itens,
        'sistemas': SistemaOrigem.query.filter_by(ind_status='A')
                                       .order_by(SistemaOrigem.txt_sigla).all(),
        'termos': [{'nom_termo': t.nom_termo, 'cod_tipo': t.cod_tipo} for t in termos],
        'operadores': ROTULOS_OPERADOR,
        # TODAS as folhas juntas: um mapeamento reúne itens de receita E de
        # despesa (change mapeamento-sem-dimensao-receita-despesa)
        'qualificadores_folha': (
            list_receita_qualificadores_folha(_exercicio_combo())
            + list_despesa_qualificadores_folha(_exercicio_combo())
        ),
    }


@router.get('/mapeamentos', name='mapeamentos',
            dependencies=[requer('FC_CONS_MAPEAMENTO')])
@handle_exceptions
async def mapeamentos(request: Request):
    linhas = []
    for m in listar_mapeamentos(apenas_ativos=True):
        linhas.append({
            'seq_mapeamento': m.seq_mapeamento,
            'num_ano_exercicio': m.num_ano_exercicio,
            'origem': m.sistema_origem.txt_sigla if m.sistema_origem else '—',
            'dsc_mapeamento': m.dsc_mapeamento,
            'qtd_itens': len([i for i in m.itens if i.ind_status == 'A']),
        })
    return templates.TemplateResponse('mapeamentos.html', {
        'request': request, 'mapeamentos': linhas,
    })


@router.get('/mapeamentos/form', name='mapeamento_novo',
            dependencies=[requer('FC_INS_MAPEAMENTO')])
@handle_exceptions
async def mapeamento_novo(request: Request):
    return templates.TemplateResponse('mapeamento_form.html', _contexto_form(request))


@router.get('/mapeamentos/form/{seq_mapeamento}', name='mapeamento_editar',
            dependencies=[requer('FC_ALT_MAPEAMENTO')])
@handle_exceptions
async def mapeamento_editar(request: Request, seq_mapeamento: int):
    mapeamento = Mapeamento.query.get(seq_mapeamento)
    if mapeamento is None or mapeamento.ind_status != 'A':
        raise RegraNegocioError("Mapeamento inexistente ou inativo", destino=_DESTINO)
    return templates.TemplateResponse(
        'mapeamento_form.html', _contexto_form(request, mapeamento))


@router.post('/mapeamentos/salvar', name='mapeamento_salvar',
             dependencies=[requer('FC_INS_MAPEAMENTO')])
@handle_exceptions
async def mapeamento_salvar(request: Request):
    form = await request.form()
    itens = _itens_do_form(form.get('itens_raw', '[]'))
    dados = dict(
        num_ano_exercicio=int(form.get('num_ano_exercicio') or 0),
        seq_sistema_origem=int(form.get('seq_sistema_origem') or 0),
        dsc_mapeamento=form.get('dsc_mapeamento', ''),
        itens=itens,
    )
    seq = form.get('seq_mapeamento')
    if seq:
        alterar_mapeamento(int(seq), **dados)
    else:
        criar_mapeamento(**dados)
    return RedirectResponse(_DESTINO, status_code=303)


@router.post('/mapeamentos/inativar/{seq_mapeamento}', name='mapeamento_inativar',
             dependencies=[requer('FC_DEL_MAPEAMENTO')])
@handle_exceptions
async def mapeamento_inativar(request: Request, seq_mapeamento: int):
    form = await request.form()
    if form.get('confirmado') != 'true':
        raise RegraNegocioError("Confirme a inativação do mapeamento", destino=_DESTINO)
    inativar_mapeamento(seq_mapeamento)
    return RedirectResponse(_DESTINO, status_code=303)


# --------------------------------------------------------------------------
# Endpoints JSON — não gravam, por isso exigem só consulta (R11)
# --------------------------------------------------------------------------

@router.post('/mapeamentos/validar-regra', name='mapeamento_validar_regra',
             dependencies=[requer('FC_CONS_MAPEAMENTO')])
@handle_exceptions
async def mapeamento_validar_regra(txt_regra: str = Form(...)):
    ok, erro = validar_regra(txt_regra)
    return JSONResponse({'ok': ok, 'erro': erro})


@router.post('/mapeamentos/validar-regra-builder', name='mapeamento_validar_builder',
             dependencies=[requer('FC_CONS_MAPEAMENTO')])
@handle_exceptions
async def mapeamento_validar_builder(nom_termo: str = Form(...),
                                     operador: str = Form(...),
                                     valor: str = Form(...)):
    """Monta a regra de UMA linha do builder e valida — é aqui que o apóstrofo
    é recusado, antes de virar texto inparseável."""
    try:
        txt = montar_regra([{'nom_termo': nom_termo, 'operador': operador,
                             'valor': valor}], 'e')
    except RegraNegocioError as exc:
        return JSONResponse({'ok': False, 'erro': exc.mensagem})
    ok, erro = validar_regra(txt)
    return JSONResponse({'ok': ok, 'erro': erro, 'txt_regra': txt})


@router.post('/mapeamentos/preview-regra', name='mapeamento_preview_regra',
             dependencies=[requer('FC_CONS_MAPEAMENTO')])
@handle_exceptions
async def mapeamento_preview_regra(txt_regra: str = Form(...),
                                   seq_sistema_origem: int = Form(...),
                                   num_ano_exercicio: int | None = Form(None)):
    resultado = preview_regra(txt_regra, seq_sistema_origem, num_ano_exercicio)
    return JSONResponse({
        'total': resultado['total'],
        'amostra': [
            {
                'seq_etl_staging': ln['seq_etl_staging'],
                'dat_referencia': (ln['dat_referencia'].isoformat()
                                   if ln['dat_referencia'] else None),
                'val_referencia': (str(ln['val_referencia'])
                                   if ln['val_referencia'] is not None else None),
                'num_ano_exercicio': ln['num_ano_exercicio'],
                'json_atributos': ln['json_atributos'],
            }
            for ln in resultado['amostra']
        ],
    })
