import logging
from datetime import date

from fastapi import Request
from fastapi.responses import JSONResponse

from ..auth.permissoes import requer
from .entrada import data_iso, inteiro, lista_de_inteiros
from ..services import (
    get_analise_comparativa_data,
    get_available_years,
    get_controle_despesa_data,
    get_dfc_data,
    get_dfc_eventos,
    get_indicadores_data,
    get_ldo_orcamento_data,
    get_previsao_receita_data,
    get_resumo_data,
    get_saldos_diarios_data,
    list_active_qualificadores,
    list_active_simuladores,
)
from ..utils.constants import MONTH_NAME_PT
from . import handle_exceptions, router, templates


def _exercicio_combo():
    """F10.4 (R28): combos de tela oferecem o plano do exercício corrente
    RESOLVIDO — nunca a união de todos os planos."""
    from ..services.qualificador_service import exercicio_corrente

    return exercicio_corrente()

logger = logging.getLogger(__name__)


@router.get('/relatorios', dependencies=[requer('FC_EXI_DASHBOARD')])
@handle_exceptions
async def relatorios(request: Request):
    return templates.TemplateResponse("relatorios.html", {"request": request})


@router.get('/relatorios/previsao-receita', name="relatorio_previsao_receita", dependencies=[requer('FC_REL_PREVISAO_RECEITA')])
@handle_exceptions
async def relatorio_previsao_receita(request: Request):
    """Página do relatório de Previsão de Receita."""
    anos_disponiveis = get_available_years()
    ano_default = anos_disponiveis[0] if anos_disponiveis else date.today().year
    cenarios = list_active_simuladores()
    
    # Buscar apenas qualificadores de receita (folha + tipo receita)
    todos_qualificadores = list_active_qualificadores(_exercicio_combo())
    qualificadores_receita = [
        q for q in todos_qualificadores 
        if q.is_folha() and q.tipo_fluxo == 'receita'
    ]
    
    return templates.TemplateResponse(
        "rel_previsao_receita.html",
        {
            "request": request,
            "anos_disponiveis": anos_disponiveis,
            "ano_default": ano_default,
            "cenarios": cenarios,
            "qualificadores": qualificadores_receita,
        }
    )


@router.get('/relatorios/previsao-receita/data', name="relatorio_previsao_receita_data", dependencies=[requer('FC_REL_PREVISAO_RECEITA')])
@handle_exceptions
async def relatorio_previsao_receita_data(request: Request):
    """API JSON para dados do gráfico de Previsão de Receita."""
    params = request.query_params
    ano = inteiro(params.get("ano"), "ano", default=date.today().year)
    cenario_id = inteiro(params.get("cenario"), "cenario")
    qualificadores_ids = lista_de_inteiros(params.get("qualificadores"), "qualificadores")
    meses = lista_de_inteiros(params.get("meses"), "meses") or None
    
    data = get_previsao_receita_data(ano, cenario_id, qualificadores_ids, meses)
    return JSONResponse(data)


@router.get('/relatorios/controle-despesa', name="relatorio_controle_despesa", dependencies=[requer('FC_REL_CONTROLE_DESPESA')])
@handle_exceptions
async def relatorio_controle_despesa(request: Request):
    """Página do relatório de Controle de Despesa."""
    anos_disponiveis = get_available_years()
    ano_default = anos_disponiveis[0] if anos_disponiveis else date.today().year
    cenarios = list_active_simuladores()
    
    # Buscar apenas qualificadores de despesa (folha + tipo despesa)
    todos_qualificadores = list_active_qualificadores(_exercicio_combo())
    qualificadores_despesa = [
        q for q in todos_qualificadores 
        if q.is_folha() and q.tipo_fluxo == 'despesa'
    ]
    
    return templates.TemplateResponse(
        "rel_controle_despesa.html",
        {
            "request": request,
            "anos_disponiveis": anos_disponiveis,
            "ano_default": ano_default,
            "cenarios": cenarios,
            "qualificadores": qualificadores_despesa,
        }
    )


@router.get('/relatorios/controle-despesa/data', name="relatorio_controle_despesa_data", dependencies=[requer('FC_REL_CONTROLE_DESPESA')])
@handle_exceptions
async def relatorio_controle_despesa_data(request: Request):
    """API JSON para dados do gráfico de Controle de Despesa."""
    params = request.query_params
    ano = inteiro(params.get("ano"), "ano", default=date.today().year)
    cenario_id = inteiro(params.get("cenario"), "cenario")
    qualificadores_ids = lista_de_inteiros(params.get("qualificadores"), "qualificadores")
    meses = lista_de_inteiros(params.get("meses"), "meses") or None
    
    data = get_controle_despesa_data(ano, cenario_id, qualificadores_ids, meses)
    return JSONResponse(data)


@router.get('/relatorios/ldo-orcamento', name="relatorio_ldo_orcamento", dependencies=[requer('FC_REL_LDO_ORCAMENTO')])
@handle_exceptions
async def relatorio_ldo_orcamento(request: Request):
    """Página do relatório de LDO & Orçamento."""
    anos_disponiveis = get_available_years()
    ano_default = anos_disponiveis[0] if anos_disponiveis else date.today().year
    
    # Buscar todos os qualificadores folha
    todos_qualificadores = list_active_qualificadores(_exercicio_combo())
    qualificadores_receita = [
        q for q in todos_qualificadores 
        if q.is_folha() and q.tipo_fluxo == 'receita'
    ]
    qualificadores_despesa = [
        q for q in todos_qualificadores 
        if q.is_folha() and q.tipo_fluxo == 'despesa'
    ]
    
    return templates.TemplateResponse(
        "rel_ldo_orcamento.html",
        {
            "request": request,
            "anos_disponiveis": anos_disponiveis,
            "ano_default": ano_default,
            "qualificadores_receita": qualificadores_receita,
            "qualificadores_despesa": qualificadores_despesa,
        }
    )


@router.get('/relatorios/ldo-orcamento/data', name="relatorio_ldo_orcamento_data", dependencies=[requer('FC_REL_LDO_ORCAMENTO')])
@handle_exceptions
async def relatorio_ldo_orcamento_data(request: Request):
    """API JSON para dados do gráfico de LDO & Orçamento."""
    params = request.query_params
    ano = inteiro(params.get("ano"), "ano", default=date.today().year)
    tipo_fluxo = params.get("tipo", "ambos")  # receita, despesa, ambos
    
    data = get_ldo_orcamento_data(ano, tipo_fluxo)
    return JSONResponse(data)



@router.get('/relatorios/previsao-realizado', name="relatorio_previsao_realizado", dependencies=[requer('FC_REL_PREVISAO_REALIZADO')])
@handle_exceptions
async def relatorio_previsao_realizado(request: Request):
    anos_disponiveis = get_available_years()
    ano_default = anos_disponiveis[0] if anos_disponiveis else date.today().year
    cenarios = list_active_simuladores()
    meses = [(i, MONTH_NAME_PT[i]) for i in range(1, 13)]
    qualificadores = [
        q for q in list_active_qualificadores(_exercicio_combo()) if q.is_folha()
    ]
    return templates.TemplateResponse(
        "rel_previsao_realizado.html",
        {
            "request": request,
            "anos_disponiveis": anos_disponiveis,
            "ano_default": ano_default,
            "cenarios": cenarios,
            "meses": meses,
            "qualificadores": qualificadores,
        },
    )


@router.get(
    "/relatorios/previsao-realizado/data",
    name="relatorio_previsao_realizado_data",
    dependencies=[requer('FC_REL_PREVISAO_REALIZADO')],
)
@handle_exceptions

async def relatorio_previsao_realizado_data(request: Request):
    from ..services.previsao_service import get_previsao_realizado_data
    
    params = request.query_params
    ano = inteiro(params.get("ano"), "ano", default=date.today().year)
    cenario_id = inteiro(params.get("cenario"), "cenario")
    meses = lista_de_inteiros(params.get("meses"), "meses")
    qualificadores_ids = lista_de_inteiros(params.get("qualificadores"), "qualificadores")
    
    data = get_previsao_realizado_data(ano, cenario_id, meses, qualificadores_ids)
    return JSONResponse(data)
@router.get('/relatorios/resumo', dependencies=[requer('FC_REL_RESUMO')])
@router.post('/relatorios/resumo', dependencies=[requer('FC_REL_RESUMO')])
@handle_exceptions
async def relatorio_resumo(request: Request):
    anos_disponiveis = get_available_years()
    ano_default = anos_disponiveis[0] if anos_disponiveis else date.today().year
    form = await request.form() if request.method == "POST" else {}
    ano_selecionado = inteiro(form.get("ano"), "ano", default=ano_default)
    estrategia = form.get("estrategia", "realizado")
    cenario_id = form.get("cenario_id")
    cenarios_disponiveis = list_active_simuladores()
    cenario_selecionado_id = inteiro(cenario_id, "cenario_id")
    meses_selecionados_str = form.getlist("meses") if hasattr(form, "getlist") else []
    meses_selecionados = (
        list(range(1, 13))
        if not meses_selecionados_str
        else [int(m) for m in meses_selecionados_str]
    )
    
    data = get_resumo_data(ano_selecionado, meses_selecionados, estrategia, cenario_selecionado_id)

    return templates.TemplateResponse(
        "rel_resumo.html",
        {
            "request": request,
            "saldo_inicial_conta": data["saldo_inicial_conta"],
            "total_entradas_periodo": data["total_entradas_periodo"],
            "total_saidas_periodo": data["total_saidas_periodo"],
            "disponibilidade_periodo": data["disponibilidade_periodo"],
            "saldo_final_conta": data["saldo_final_conta"],
            "cash_flow_data": data["cash_flow_data"],
            "ano_selecionado": ano_selecionado,
            "anos_disponiveis": anos_disponiveis,
            "meses_selecionados": [str(m) for m in meses_selecionados],
            "meses_nomes": data["meses_nomes"],
            "estrategia_selecionada": estrategia,
            "cenario_selecionado_id": cenario_selecionado_id,
            "cenarios_disponiveis": cenarios_disponiveis,
        },
    )


@router.get('/relatorios/indicadores', dependencies=[requer('FC_REL_INDICADORES')])
@router.post('/relatorios/indicadores', dependencies=[requer('FC_REL_INDICADORES')])
@handle_exceptions
async def relatorio_indicadores(request: Request):
    anos_disponiveis = get_available_years()
    ano_default = anos_disponiveis[0] if anos_disponiveis else date.today().year
    form = await request.form() if request.method == "POST" else {}
    ano_selecionado = inteiro(form.get("ano"), "ano", default=ano_default)
    tipo_selecionado = form.get("tipo", "ambos")
    meses_selecionados_str = form.getlist("meses") if hasattr(form, "getlist") else []
    meses_selecionados = (
        list(range(1, 13))
        if not meses_selecionados_str
        else [int(m) for m in meses_selecionados_str]
    )
    
    data = get_indicadores_data(ano_selecionado, meses_selecionados, tipo_selecionado)

    return templates.TemplateResponse(
        "rel_indicadores.html",
        {
            "request": request,
            "area_chart_data": data["area_chart_data"],
            "pie_chart_data": data["pie_chart_data"],
            "projection_chart_data": data["projection_chart_data"],
            "ano_selecionado": ano_selecionado,
            "anos_disponiveis": anos_disponiveis,
            "tipo_selecionado": tipo_selecionado,
            "meses_selecionados": [str(m) for m in meses_selecionados],
            "meses_nomes": data["meses_nomes"],
        },
    )


@router.get('/relatorios/analise-comparativa', dependencies=[requer('FC_REL_ANALISE_COMPARATIVA')])
@router.post('/relatorios/analise-comparativa', dependencies=[requer('FC_REL_ANALISE_COMPARATIVA')])
@handle_exceptions
async def relatorio_analise_comparativa(request: Request):
    form = await request.form() if request.method == "POST" else {}
    tipo_analise = form.get("tipo_analise", "receitas")
    anos_disponiveis = get_available_years()
    ano1_default = (
        anos_disponiveis[1] if len(anos_disponiveis) > 1 else (date.today().year - 1)
    )
    ano2_default = anos_disponiveis[0] if anos_disponiveis else date.today().year
    ano1 = inteiro(form.get("ano1"), "ano1", default=ano1_default)
    ano2 = inteiro(form.get("ano2"), "ano2", default=ano2_default)
    meses_selecionados_str = form.getlist("meses") if hasattr(form, "getlist") else []
    meses_selecionados = (
        list(range(1, 13))
        if not meses_selecionados_str
        else [int(m) for m in meses_selecionados_str]
    )
    
    data = get_analise_comparativa_data(ano1, ano2, meses_selecionados, tipo_analise)

    return templates.TemplateResponse(
        "rel_analise_comparativa.html",
        {
            "request": request,
            "data": data["data"],
            "totals": data["totals"],
            "tipo_analise": tipo_analise,
            "ano1": ano1,
            "ano2": ano2,
            "anos_disponiveis": anos_disponiveis,
            "meses_selecionados": [str(m) for m in meses_selecionados],
            "meses_nomes": data["meses_nomes"],
        },
    )

@router.get('/relatorios/saldos-diarios', name="relatorio_saldos_diarios", dependencies=[requer('FC_REL_SALDOS_DIARIOS')])
@router.post('/relatorios/saldos-diarios', name="relatorio_saldos_diarios", dependencies=[requer('FC_REL_SALDOS_DIARIOS')])
@handle_exceptions
async def relatorio_saldos_diarios(request: Request):
    from ..models import ContaBancaria

    # Filtros por form (POST legado) ou query string (GET — toggle/filtro F5.3)
    params = await request.form() if request.method == "POST" else request.query_params
    data_ref_str = params.get("data_ref")
    hoje = date.today()
    data_ref = data_iso(data_ref_str, "data", default=hoje)
    visao = params.get("visao") or "agregado"
    seq_conta = inteiro(params.get("seq_conta"), "seq_conta")

    data = get_saldos_diarios_data(data_ref, visao=visao, seq_conta=seq_conta)

    contas_disponiveis = (
        ContaBancaria.query.filter_by(ind_status='A')
        .order_by(ContaBancaria.cod_banco, ContaBancaria.num_agencia,
                  ContaBancaria.num_conta)
        .all()
    )
    return templates.TemplateResponse(
        "rel_saldos_diarios.html",
        {
            "request": request,
            "data_ref": data_ref,
            "visao": data["visao"],
            "seq_conta_selecionada": seq_conta,
            "contas_disponiveis": contas_disponiveis,
            "rows": data["rows"],
            "totais": data["totais"],
            "rows_fundo": data["rows_fundo"],
            "totais_fundo": data["totais_fundo"],
            "evolucao_labels": data["evolucao_labels"],
            "evolucao_saldos": data["evolucao_saldos"],
        },
    )


@router.get('/relatorios/dfc', dependencies=[requer('FC_REL_DFC')])
@router.post('/relatorios/dfc', dependencies=[requer('FC_REL_DFC')])
@handle_exceptions
async def relatorio_dfc(request: Request):
    """Tela de Análise de Fluxo (DFC) com dados reais ou projetados."""

    form = await request.form() if request.method == "POST" else {}
    periodo = form.get("periodo", "mes")
    data_sel = form.get("mes_ano")

    lancamento_years = (
        get_available_years()
    )
    anos_disponiveis = sorted(lancamento_years, reverse=True)

    hoje = date.today()
    if periodo == "mes":
        default = f"{hoje.year}-{hoje.month:02d}"
        data_sel = data_sel or default
        ano_selecionado, mes_selecionado = [int(x) for x in data_sel.split("-")]
    else:
        default = str(anos_disponiveis[0] if anos_disponiveis else hoje.year)
        data_sel = data_sel or default
        ano_selecionado = int(data_sel)
        mes_selecionado = None

    estrategia = form.get("estrategia", "realizado")
    cenario_id = form.get("cenario_id")
    cenario_selecionado_id = inteiro(cenario_id, "cenario_id")

    meses_selecionados_str = form.getlist("meses") if hasattr(form, "getlist") else []
    meses_selecionados = (
        [int(m) for m in meses_selecionados_str]
        if meses_selecionados_str
        else list(range(1, 13))
    )

    cenarios_disponiveis = list_active_simuladores()

    data = get_dfc_data(
        periodo,
        ano_selecionado,
        mes_selecionado,
        meses_selecionados,
        estrategia,
        cenario_selecionado_id,
    )

    return templates.TemplateResponse(
        "rel_dfc.html",
        {
            "request": request,
            "periodo": periodo,
            "mes_ano": data_sel,
            "headers": data["headers"],
            "dre_data": data["dre_data"],
            "totals": data["totals"],
            "saldos_banco_anterior": data["saldos_banco_anterior"],
            "saldos_banco_final": data["saldos_banco_final"],
            "resultado_dia": data["resultado_dia"],
            "estrategia_selecionada": estrategia,
            "cenario_selecionado_id": cenario_selecionado_id,
            "cenarios_disponiveis": cenarios_disponiveis,
            "meses_selecionados": [str(m) for m in meses_selecionados],
            "meses_nomes": data["meses_nomes"],
            "anos_disponiveis": anos_disponiveis,
            "meses_projetados": data["meses_projetados"],
            "projecao_origem": data.get("projecao_origem"),
        },
    )


@router.get('/relatorios/dfc/eventos', dependencies=[requer('FC_REL_DFC')])
@handle_exceptions
async def dfc_eventos(request: Request):
    """Retorna os eventos (lançamentos) para um qualificador e coluna."""

    seq = inteiro(request.query_params.get("seq"), "seq", obrigatorio=True)
    periodo = request.query_params.get("periodo", "mes")
    col = inteiro(request.query_params.get("col"), "col", obrigatorio=True)
    mes_ano = request.query_params.get("mes_ano")
    estrategia = request.query_params.get("estrategia", "realizado")
    cenario_id = request.query_params.get("cenario_id")
    # R20: a linha de movimento próprio leva o MESMO seq do qualificador; é este
    # marcador que distingue "só o nó" de "o nó e seus descendentes".
    proprio = request.query_params.get("proprio") in ("1", "true", "True")

    data = get_dfc_eventos(seq, periodo, col, mes_ano, estrategia, cenario_id,
                           proprio=proprio)

    return JSONResponse({"eventos": data["eventos"], "total": data["total"]})


# ==================== BACKTEST ====================

@router.get('/relatorios/backtest', name="relatorio_backtest", dependencies=[requer('FC_REL_BACKTEST')])
@handle_exceptions
async def relatorio_backtest(request: Request):
    """Página do relatório de Backtest de Modelos."""
    from ..services.backtest_service import MODELOS_DISPONIVEIS

    anos_disponiveis = get_available_years()
    qualificadores = list_active_qualificadores(_exercicio_combo())

    # Agrupar qualificadores por pai
    grupos = {}
    filhos = []
    por_seq = {q.seq_qualificador: q for q in qualificadores}

    for q in qualificadores:
        if q.cod_qualificador_pai is not None:
            pai = por_seq.get(q.cod_qualificador_pai)
            # Folha pela ORIGEM ÚNICA (F6.4). A varredura anterior sobre a
            # lista local ignorava o `ind_status` do filho: um nó cujo único
            # filho estava INATIVO era tratado como não-folha e sumia do
            # agrupamento, embora o resto do sistema o oferecesse.
            if q.is_folha():
                pai_nome = pai.dsc_qualificador if pai else 'Outros'
                if pai_nome not in grupos:
                    grupos[pai_nome] = []
                grupos[pai_nome].append(q)
                filhos.append(q)

    modelos = [
        {'codigo': k, 'nome': v['nome']}
        for k, v in MODELOS_DISPONIVEIS.items()
    ]

    return templates.TemplateResponse(
        "rel_backtest.html",
        {
            "request": request,
            "anos_disponiveis": sorted(anos_disponiveis),
            "modelos_disponiveis": modelos,
            "grupos_qualificadores": grupos,
            "filhos": filhos,
        },
    )


@router.post('/relatorios/backtest/executar', name="relatorio_backtest_executar", dependencies=[requer('FC_REL_BACKTEST')])
@handle_exceptions
async def relatorio_backtest_executar(request: Request):
    """Executa o backtest e retorna resultados JSON."""
    from ..services.backtest_service import executar_backtest

    data = await request.json()

    anos_treino = data.get('anos_treino', [])
    anos_teste = data.get('anos_teste', [])
    modelos = data.get('modelos', [])
    qualificadores_ids = data.get('qualificadores_ids')

    if not anos_treino:
        return JSONResponse({'error': 'Selecione pelo menos um ano de treino'}, status_code=400)
    if not anos_teste:
        return JSONResponse({'error': 'Selecione pelo menos um ano de teste'}, status_code=400)
    if not modelos:
        return JSONResponse({'error': 'Selecione pelo menos um modelo'}, status_code=400)

    try:
        resultado = executar_backtest(
            anos_treino=[int(a) for a in anos_treino],
            anos_teste=[int(a) for a in anos_teste],
            modelos=modelos,
            qualificadores_ids=[int(q) for q in qualificadores_ids] if qualificadores_ids else None,
        )
        return JSONResponse(resultado)
    except ValueError as e:
        # erro de negócio do backtest — a mensagem é para o usuário
        return JSONResponse({'error': str(e)}, status_code=400)
    except Exception:
        # NUNCA str(e) de exceção arbitrária: vaza caminho/SQL/schema (R15)
        logger.exception("Erro interno ao executar o backtest")
        return JSONResponse(
            {'error': 'Erro interno ao executar o backtest — consulte o log '
                      'do servidor'}, status_code=500)


@router.post('/relatorios/backtest/salvar-recomendacao', name="backtest_salvar_recomendacao", dependencies=[requer('FC_INS_BACKTEST')])
@handle_exceptions
async def backtest_salvar_recomendacao(request: Request):
    """Salva recomendações do backtest e retorna contagem."""
    from ..services.backtest_service import salvar_recomendacoes

    data = await request.json()

    count = salvar_recomendacoes(data)
    return JSONResponse({
        'mensagem': f'{count} recomendações salvas com sucesso',
        'count': count,
        'redirect_url': '/simulador/novo?usar_recomendacao=1',
    })


# ---------------------------------------------------------------------------
# KPIs (spec relatorios R1–R8, feature F5.1)
# ---------------------------------------------------------------------------

def _param_data(params, nome: str):
    bruto = params.get(nome)
    if not bruto:
        return None
    try:
        return date.fromisoformat(bruto)
    except ValueError:
        from ..services.validacao import RegraNegocioError

        raise RegraNegocioError(f"Data inválida no filtro '{nome}'.")


@router.get('/relatorios/kpis', name="relatorio_kpis", dependencies=[requer('FC_REL_KPIS')])
@handle_exceptions
async def relatorio_kpis(request: Request):
    """Página do relatório de KPIs (seis blocos + filtros)."""
    from ..models import ContaBancaria

    contas = (
        ContaBancaria.query.filter_by(ind_status='A')
        .order_by(ContaBancaria.cod_banco, ContaBancaria.num_agencia, ContaBancaria.num_conta)
        .all()
    )
    bancos = sorted({c.cod_banco for c in contas})
    return templates.TemplateResponse(
        "rel_kpis.html",
        {
            "request": request,
            "contas": contas,
            "bancos": bancos,
            "hoje": date.today().isoformat(),
        },
    )


@router.get('/relatorios/kpis/data', name="relatorio_kpis_data", dependencies=[requer('FC_REL_KPIS')])
@handle_exceptions
async def relatorio_kpis_data(request: Request):
    """Dados JSON dos seis blocos do relatório de KPIs."""
    from ..services import get_kpis_data

    params = request.query_params
    seq_conta = inteiro(params.get("seq_conta"), "seq_conta")
    cod_banco = params.get("cod_banco") or None
    data = get_kpis_data(
        data_referencia=_param_data(params, "data_referencia"),
        data_inicio=_param_data(params, "data_inicio"),
        data_fim=_param_data(params, "data_fim"),
        seq_conta=seq_conta,
        cod_banco=cod_banco,
    )
    return JSONResponse(data)


@router.get('/relatorios/analitico-desembolso', name="relatorio_analitico_desembolso",
            dependencies=[requer('FC_REL_ANALITICO_DESEMBOLSO')])
@handle_exceptions
async def relatorio_analitico_desembolso(request: Request):
    """Painel analítico do desembolso (spec desembolso R26) — derivado."""
    from datetime import date as _date

    from ..models import Orgao
    from ..services.relatorio.analitico_desembolso_service import dados_analitico

    ano_raw = request.query_params.get('ano') or ''
    ano = int(ano_raw) if ano_raw.isdigit() else _date.today().year
    return templates.TemplateResponse('rel_analitico_desembolso.html', {
        'request': request,
        'dados': dados_analitico(ano),
        'nomes_orgaos': {o.cod_orgao: o.nom_orgao
                         for o in Orgao.query.filter_by(ind_status='A').all()},
    })
