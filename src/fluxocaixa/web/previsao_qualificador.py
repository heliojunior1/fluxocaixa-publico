"""Telas da previsão por qualificador (docs/previsao-metodo-por-qualificador.md).

- Métodos por qualificador do cenário: árvore com o método resolvido (próprio
  × herdado × padrão da perna), marcação por nó, fórmulas próprias, cobertura,
  recomendações do backtest, setor do cenário e importação de planilha.
- Duplicar cenário.
- Setores da previsão (cadastro e recorte na árvore).
- Propostas setoriais (avaliação e uso).

Rotas finas: parse + chamada de serviço + render. Regra de negócio vive nos
serviços e levanta `RegraNegocioError` (flash + redirect pelo handler global).
"""
import csv
import io

from fastapi import Request
from fastapi.responses import RedirectResponse, Response

from ..auth.permissoes import requer
from ..services import metodo_qualificador_service as mq
from ..services import setor_previsao_service as setores
from ..services.validacao import RegraNegocioError
from . import handle_exceptions, router, templates
from .entrada import inteiro

_SIM = ('S', 'on', 'true', '1')


def _simulador_ou_404(id: int):
    from ..models import SimuladorCenario

    simulador = SimuladorCenario.query.get(id)
    if simulador is None or simulador.ind_status != 'A':
        raise RegraNegocioError("Cenário inexistente ou inativo", destino='/simulador')
    return simulador


def _voltar(id: int, no: int | None = None, extra: str = '') -> RedirectResponse:
    url = f'/simulador/{id}/metodos'
    params = []
    if no:
        params.append(f'no={no}')
    if extra:
        params.append(extra)
    if params:
        url += '?' + '&'.join(params)
    return RedirectResponse(url, status_code=303)


# ---------------------------------------------------------------------------
# Métodos por qualificador
# ---------------------------------------------------------------------------

@router.get('/simulador/{id}/metodos', name='simulador_metodos',
            dependencies=[requer('FC_CONS_PREVISAO')])
@handle_exceptions
async def simulador_metodos(request: Request, id: int, no: int | None = None,
                            cobertura: int = 0):
    """Árvore de métodos. A cobertura só é calculada a pedido (`?cobertura=1`):
    exige executar o cenário, e abrir a página não treina modelos (R14)."""
    from ..models import CenarioConfig
    from ..services.simulador_cenario_service import executar_simulacao

    simulador = _simulador_ou_404(id)
    cob = None
    status = {}
    if cobertura:
        resultado = executar_simulacao(id)
        cob = mq.cobertura(simulador, resultado)
        status = {item['seq_qualificador']: item for p in ('C', 'D') for item in cob[p]}

    linhas = mq.arvore(simulador, status)
    selecionado = None
    painel = None
    if no:
        selecionado = next((l for l in linhas if l['q'].seq_qualificador == no), None)
    if selecionado is not None:
        q = selecionado['q']
        perna = selecionado['perna']
        folhas = mq.folhas_sob(q)
        painel = {
            'linha': selecionado,
            'metodos': [(cod, nome) for cod, nome in mq.METODOS.items()
                        if cod != mq.MODELO and perna in mq.pernas_do_metodo(cod, {})]
            + ([(mq.MODELO, mq.METODOS[mq.MODELO])] if any(
                perna in mq.pernas_do_metodo(mq.MODELO, {'modelo': m})
                for m in mq.MODELOS_DE_SERIE) else []),
            'modelos': [(m, mq.ROTULO_MODELO[m]) for m in mq.MODELOS_DE_SERIE
                        if perna in mq.pernas_do_metodo(mq.MODELO, {'modelo': m})],
            'propostas': setores.propostas_para(simulador, q),
            'formulas': [
                {'folha': f, **dict(zip(('expressao', 'origem'),
                                        mq.formula_da_folha(id, f.seq_qualificador)))}
                for f in folhas[:60]
            ],
            'qtd_folhas': len(folhas),
        }

    padroes = {c.cod_tipo_lancamento: c for c in CenarioConfig.query.filter_by(
        seq_simulador_cenario=id).all()}
    origem = None
    if simulador.seq_cenario_origem:
        from ..models import SimuladorCenario

        origem = SimuladorCenario.query.get(simulador.seq_cenario_origem)
    from ..services.projecao_versao_service import comparacao_com_origem

    return templates.TemplateResponse('simulador_metodos.html', {
        'request': request,
        'simulador': simulador,
        'origem': origem,
        'comparar_origem': comparacao_com_origem(simulador),
        'linhas': linhas,
        'painel': painel,
        'cobertura': cob,
        'padroes': padroes,
        'rotulo_padrao': mq.ROTULO_PADRAO,
        'recomendacoes': mq.recomendacoes_aplicaveis(simulador),
        'setores': setores.listar_setores(),
        'qtd_marcacoes': sum(1 for l in linhas if l['marcacao_propria']),
    })


def _config_do_form(form, cod_metodo: str) -> dict:
    if cod_metodo == mq.VALOR_FIXO:
        mensais = {str(m): form.get(f'valor_mes_{m}') for m in range(1, 13)
                   if str(form.get(f'valor_mes_{m}') or '').strip()}
        if mensais:
            return {'valores_mensais': mensais}
        return {'valor_anual': form.get('valor_anual')}
    if cod_metodo == mq.PERCENTUAL:
        return {'percentual': form.get('percentual'), 'anos_base': form.get('anos_base')}
    if cod_metodo == mq.MODELO:
        return {'modelo': form.get('modelo'), 'por_folha': form.get('por_folha', '')}
    if cod_metodo == mq.SEM_PROJECAO:
        return {'motivo': form.get('motivo')}
    if cod_metodo == mq.PROPOSTA_SETORIAL:
        return {'seq_projecao_versao': form.get('seq_projecao_versao')}
    return {}


@router.post('/simulador/{id}/metodos', name='simulador_metodo_salvar',
             dependencies=[requer('FC_ALT_PREVISAO')])
@handle_exceptions
async def simulador_metodo_salvar(request: Request, id: int):
    form = await request.form()
    seq_qualificador = inteiro(form.get('seq_qualificador'), 'qualificador', obrigatorio=True)
    cod_metodo = (form.get('cod_metodo') or '').strip()
    _simulador_ou_404(id)
    if not cod_metodo:
        mq.remover_marcacao(id, seq_qualificador)
    else:
        mq.definir_marcacao(id, seq_qualificador, cod_metodo,
                            _config_do_form(form, cod_metodo))
    return _voltar(id, seq_qualificador)


@router.post('/simulador/{id}/metodos/{seq_qualificador}/remover',
             name='simulador_metodo_remover', dependencies=[requer('FC_ALT_PREVISAO')])
@handle_exceptions
async def simulador_metodo_remover(request: Request, id: int, seq_qualificador: int):
    mq.remover_marcacao(id, seq_qualificador)
    return _voltar(id, seq_qualificador)


@router.post('/simulador/{id}/formulas/{seq_qualificador}',
             name='simulador_formula_propria', dependencies=[requer('FC_ALT_PREVISAO')])
@handle_exceptions
async def simulador_formula_propria(request: Request, id: int, seq_qualificador: int):
    from ..services.formula_cenario_service import (
        definir_formula_propria,
        remover_formula_propria,
    )

    form = await request.form()
    expressao = (form.get('expressao') or '').strip()
    if not expressao:
        remover_formula_propria(id, seq_qualificador)
    else:
        definir_formula_propria(id, seq_qualificador, expressao)
    return _voltar(id, inteiro(form.get('no'), 'nó'))


@router.post('/simulador/{id}/recomendacoes', name='simulador_aplicar_recomendacoes',
             dependencies=[requer('FC_ALT_PREVISAO')])
@handle_exceptions
async def simulador_aplicar_recomendacoes(request: Request, id: int):
    form = await request.form()
    escolhidas = [int(v) for v in form.getlist('seq_qualificador') if str(v).isdigit()]
    if not escolhidas:
        raise RegraNegocioError("Selecione ao menos uma recomendação")
    mq.aplicar_recomendacoes(id, escolhidas)
    return _voltar(id)


@router.post('/simulador/{id}/setor', name='simulador_definir_setor',
             dependencies=[requer('FC_ALT_PREVISAO')])
@handle_exceptions
async def simulador_definir_setor(request: Request, id: int):
    form = await request.form()
    setores.definir_setor_do_cenario(id, inteiro(form.get('seq_setor_previsao'), 'setor'))
    return _voltar(id)


@router.get('/simulador/{id}/metodos/modelo-csv', name='simulador_modelo_csv',
            dependencies=[requer('FC_CONS_PREVISAO')])
@handle_exceptions
async def simulador_modelo_csv(request: Request, id: int):
    """Planilha-modelo da proposta: as folhas do cenário (do recorte do setor,
    em cenário setorial) × 12 meses, com a coluna de valor em branco."""
    simulador = _simulador_ou_404(id)
    exercicio = mq.exercicio_do_cenario(simulador)
    memo: dict = {}
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=';')
    escritor.writerow(['codigo', 'descricao', 'mes', 'valor'])
    for perna in ('C', 'D'):
        for folha in mq.folhas_da_perna(perna, exercicio):
            if (simulador.seq_setor_previsao is not None
                    and not setores.no_no_recorte(folha, simulador.seq_setor_previsao, memo)):
                continue
            for mes in range(1, 13):
                escritor.writerow([folha.num_qualificador, folha.dsc_qualificador, mes, ''])
    return Response(
        content=saida.getvalue().encode('utf-8-sig'),
        media_type='text/csv',
        headers={'Content-Disposition':
                 f'attachment; filename="proposta_cenario_{id}.csv"'})


@router.post('/simulador/{id}/metodos/importar', name='simulador_importar_proposta',
             dependencies=[requer('FC_ALT_PREVISAO')])
@handle_exceptions
async def simulador_importar_proposta(request: Request, id: int):
    from ..services.preprocessamento import criar_preview, ler_upload_limitado, validar_extensao
    from .importacao import render_preview

    _simulador_ou_404(id)
    form = await request.form()
    arquivo = form.get('arquivo')
    if arquivo is None or not getattr(arquivo, 'filename', ''):
        raise RegraNegocioError("Selecione o arquivo da proposta")
    validar_extensao(arquivo.filename)
    content = await ler_upload_limitado(arquivo)
    token, preview = criar_preview(
        'previsao_setorial', content, arquivo.filename, request.session,
        contexto={'seq_cenario': id, 'retorno': f'/simulador/{id}/metodos'})
    return render_preview(request, 'previsao_setorial', token, preview)


# ---------------------------------------------------------------------------
# Duplicar cenário
# ---------------------------------------------------------------------------

@router.post('/simulador/{id}/duplicar', name='simulador_duplicar',
             dependencies=[requer('FC_INS_PREVISAO')])
@handle_exceptions
async def simulador_duplicar(request: Request, id: int):
    from ..services.simulador_cenario_service import duplicar_cenario

    form = await request.form()
    copia = duplicar_cenario(id, form.get('nom_cenario'),
                             congelar_formulas=form.get('congelar_formulas') in _SIM)
    return RedirectResponse(f'/simulador/{copia.seq_simulador_cenario}/metodos',
                            status_code=303)


# ---------------------------------------------------------------------------
# Setores da previsão
# ---------------------------------------------------------------------------

@router.get('/previsao/setores', name='setores_previsao',
            dependencies=[requer('FC_CONS_PREVISAO')])
@handle_exceptions
async def setores_previsao(request: Request):
    from ..services.qualificador_service import exercicio_corrente, list_active_qualificadores

    lista = setores.listar_setores()
    return templates.TemplateResponse('setores_previsao.html', {
        'request': request,
        'setores': [{'setor': s, 'recorte': setores.recorte_proprio(s.seq_setor_previsao)}
                    for s in lista],
        'qualificadores': list_active_qualificadores(exercicio_corrente()),
    })


@router.post('/previsao/setores', name='setor_previsao_criar',
             dependencies=[requer('FC_MANT_SETOR_PREVISAO')])
@handle_exceptions
async def setor_previsao_criar(request: Request):
    form = await request.form()
    setores.criar_setor(form.get('nom_setor'), form.get('sgl_setor'), form.get('dsc_setor'))
    return RedirectResponse('/previsao/setores', status_code=303)


@router.post('/previsao/setores/{seq}/alterar', name='setor_previsao_alterar',
             dependencies=[requer('FC_MANT_SETOR_PREVISAO')])
@handle_exceptions
async def setor_previsao_alterar(request: Request, seq: int):
    form = await request.form()
    setores.alterar_setor(seq, form.get('nom_setor'), form.get('sgl_setor'),
                          form.get('dsc_setor'))
    return RedirectResponse('/previsao/setores', status_code=303)


@router.post('/previsao/setores/{seq}/inativar', name='setor_previsao_inativar',
             dependencies=[requer('FC_MANT_SETOR_PREVISAO')])
@handle_exceptions
async def setor_previsao_inativar(request: Request, seq: int):
    setores.inativar_setor(seq)
    return RedirectResponse('/previsao/setores', status_code=303)


@router.post('/previsao/setores/recorte', name='setor_previsao_recorte',
             dependencies=[requer('FC_MANT_SETOR_PREVISAO')])
@handle_exceptions
async def setor_previsao_recorte(request: Request):
    form = await request.form()
    setores.marcar_recorte(
        inteiro(form.get('seq_qualificador'), 'qualificador', obrigatorio=True),
        inteiro(form.get('seq_setor_previsao'), 'setor'))
    return RedirectResponse('/previsao/setores', status_code=303)


# ---------------------------------------------------------------------------
# Propostas setoriais
# ---------------------------------------------------------------------------

@router.get('/previsao/propostas', name='propostas_setoriais',
            dependencies=[requer('FC_CONS_PREVISAO')])
@handle_exceptions
async def propostas_setoriais(request: Request, setor: int | None = None):
    return templates.TemplateResponse('propostas_setoriais.html', {
        'request': request,
        'propostas': setores.listar_propostas(setor),
        'setores': setores.listar_setores(),
        'setor_filtro': setor,
    })


@router.post('/previsao/propostas/{seq_versao}/aceitar', name='proposta_aceitar',
             dependencies=[requer('FC_AVALIAR_PROPOSTA')])
@handle_exceptions
async def proposta_aceitar(request: Request, seq_versao: int):
    setores.avaliar_proposta(seq_versao, aceitar=True)
    return RedirectResponse('/previsao/propostas', status_code=303)


@router.post('/previsao/propostas/{seq_versao}/devolver', name='proposta_devolver',
             dependencies=[requer('FC_AVALIAR_PROPOSTA')])
@handle_exceptions
async def proposta_devolver(request: Request, seq_versao: int):
    form = await request.form()
    setores.avaliar_proposta(seq_versao, aceitar=False, motivo=form.get('motivo'))
    return RedirectResponse('/previsao/propostas', status_code=303)
