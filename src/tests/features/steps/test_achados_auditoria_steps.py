"""Steps BDD — achados da auditoria da previsão (change
corrigir-achados-auditoria-previsao; spec previsao R22–R29, cadastros-nucleo
R30).

Ilha: exercícios 2121–2124, receita "1.83", despesa "2.83". Os cenários de
métrica e de modelo usam dados em memória; os demais, a massa da ilha.
Import tardio de `fluxocaixa` (isolamento de banco da suíte).
"""
from datetime import date
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../previsao/achados_auditoria.feature")

ANOS_DA_ILHA = (2121, 2122, 2123, 2124)
PREFIXO_CENARIO = "CEN_AA_"


@pytest.fixture()
def contexto():
    return {"modelos": {}}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from fluxocaixa.models import Lancamento, Qualificador, SimuladorCenario

    db = _db()
    db.session.rollback()
    for c in SimuladorCenario.query.filter(
            SimuladorCenario.nom_cenario.like(f"{PREFIXO_CENARIO}%")).all():
        db.session.delete(c)
    db.session.flush()
    quals = Qualificador.query.filter(
        Qualificador.num_ano_exercicio.in_(ANOS_DA_ILHA)).all()
    seqs = [q.seq_qualificador for q in quals]
    if seqs:
        Lancamento.query.filter(Lancamento.seq_qualificador.in_(seqs)).delete(
            synchronize_session=False)
        for q in quals:
            q.cod_qualificador_pai = None
        db.session.flush()
        for q in quals:
            db.session.delete(q)
    db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


def _criar_q(codigo, ano, raiz=None, pai=None):
    from fluxocaixa.services.qualificador_service import create_qualificador

    return create_qualificador(
        codigo, f"Ilha AA {codigo} {ano}", num_ano_exercicio=ano,
        cod_rubrica_raiz=raiz, cod_qualificador_pai=pai)


def _lancar(q, dia, valor):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.lancamento import TIPO_CREDITO, TIPO_DEBITO
    from fluxocaixa.services.dominio_lancamento import resolver_origem

    _db().session.add(Lancamento(
        dat_lancamento=dia, seq_qualificador=q.seq_qualificador,
        val_lancamento=Decimal(str(valor)),
        cod_tipo_lancamento=TIPO_CREDITO if q.num_qualificador.startswith("1")
        else TIPO_DEBITO,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        cod_pessoa_inclusao=1, ind_status='A'))


def _valores(texto):
    return [float(v) for v in texto.split(";")]


def _por_mes(texto):
    return {i + 1: v for i, v in enumerate(_valores(texto))}


def _serie(valores, inicio="2090-01-01"):
    return pd.DataFrame({"data": pd.date_range(inicio, periods=len(valores), freq="MS"),
                         "valor": valores})


# ---------------------------------------------------------------------------
# Massa
# ---------------------------------------------------------------------------

@given(parsers.parse('uma despesa com saída de "{valor}" em todos os meses de '
                     '{inicio:d} a {fim:d}'), target_fixture="rubrica")
def despesa_mensal(app, valor, inicio, fim):
    q = _criar_q("2.83", fim)
    for ano in range(inicio, fim + 1):
        for mes in range(1, 13):
            _lancar(q, date(ano, mes, 10), valor)
    _db().session.commit()
    return q


@given(parsers.parse('uma receita com entrada de "{valor}" em todos os meses de '
                     '{inicio:d} a {fim:d}'), target_fixture="rubrica")
def receita_mensal(app, valor, inicio, fim):
    """Folha sob um bloco: o backtest mede FOLHAS com ancestral (R16)."""
    bloco = _criar_q("1.83", fim)
    q = _criar_q("1.83.1", fim, pai=bloco.seq_qualificador)
    for ano in range(inicio, fim + 1):
        for mes in range(1, 13):
            _lancar(q, date(ano, mes, 10), valor)
    _db().session.commit()
    return q


@given("uma receita com realizado mensal", target_fixture="rubrica")
def receita_por_semestre(app, datatable):
    _cab, *linhas = datatable
    q = _criar_q("1.83", 2123)
    for ano, jan_jun, jul_dez in linhas:
        for mes in range(1, 13):
            valor = jan_jun if mes <= 6 else jul_dez
            if valor:
                _lancar(q, date(int(ano), mes, 10), valor)
    _db().session.commit()
    return q


@given(parsers.parse('uma receita do plano de {ano:d} com "{valor}" em cada mês de '
                     '{ano_lanc:d}'), target_fixture="rubrica")
def receita_do_plano(app, contexto, ano, valor, ano_lanc):
    q = _criar_q("1.83", ano)
    for mes in range(1, 13):
        _lancar(q, date(ano_lanc, mes, 10), valor)
    _db().session.commit()
    contexto["origem"] = q
    return q


@given(parsers.parse('a mesma rubrica, herdada, no plano de {ano:d}'))
def rubrica_herdada(contexto, rubrica, ano):
    contexto["herdeira"] = _criar_q("1.83", ano, raiz=rubrica.cod_rubrica_raiz)


@given(parsers.parse('uma despesa "{codigo}" no plano de {ano:d}'))
def despesa_no_plano(contexto, codigo, ano):
    contexto["despesa"] = _criar_q(codigo, ano)


@given(parsers.parse('uma série de 24 meses de "{a}" seguidos de 12 meses de "{b}"'))
def serie_com_degrau(contexto, a, b):
    contexto["serie"] = _serie([float(a)] * 24 + [float(b)] * 12)


@given("a série de 36 meses com tendência e sazonalidade")
def serie_tendencia(contexto):
    t = np.arange(36)
    contexto["serie"] = _serie(list(100 + 5 * t + 50 * np.sin(2 * np.pi * t / 12)))


@given(parsers.parse('uma série de 14 meses de "{valor}" com um pico de "{pico}" no '
                     'último mês'))
def serie_curta(contexto, valor, pico):
    contexto["serie"] = _serie([float(valor)] * 13 + [float(pico)])


@given(parsers.parse('o realizado "{valores}"'))
def realizado(contexto, valores):
    contexto["real"] = _por_mes(valores)


@given(parsers.parse('o modelo "{a}" com previsão "{pa}" e o modelo "{b}" com "{pb}"'))
def dois_modelos(contexto, a, pa, b, pb):
    contexto["modelos"][a] = {"projecao": _por_mes(pa), "anos": 1, "degradado": False}
    contexto["modelos"][b] = {"projecao": _por_mes(pb), "anos": 1, "degradado": False}


@given(parsers.parse('o modelo "{nome}" caiu para o fallback'))
def modelo_degradado(contexto, nome):
    contexto["modelos"][nome]["degradado"] = True


@given(parsers.parse('o modelo "{a}" foi medido em {na:d} ano e o modelo "{b}" em '
                     '{nb:d} anos'))
def coberturas(contexto, a, na, b, nb):
    contexto["modelos"][a]["anos"] = na
    contexto["modelos"][b]["anos"] = nb


@given(parsers.parse('a folha "{nome}" com realizado "{real}" e previsão "{prev}"'))
def folha_do_pai(contexto, nome, real, prev):
    contexto.setdefault("folhas", []).append((_por_mes(prev), _por_mes(real)))


# ---------------------------------------------------------------------------
# Ações
# ---------------------------------------------------------------------------

@when(parsers.parse('executo um cenário "{periodicidade}" de {ano:d} com {n:d} '
                    '{rotulo} e média histórica na despesa'))
def executa_cenario(contexto, rubrica, periodicidade, ano, n, rotulo):
    from fluxocaixa.services.simulador_cenario_service import (
        criar_simulador_cenario,
        executar_simulacao,
    )

    cenario = criar_simulador_cenario(
        nom_cenario=f"{PREFIXO_CENARIO}{periodicidade}", dsc_cenario="bdd",
        ano_base=ano, num_periodos=n, tipo_cenario_receita='', config_receita={},
        tipo_cenario_despesa='MEDIA_HISTORICA',
        config_despesa={"seq_qualificadores": [rubrica.seq_qualificador]},
        user_id=1, cod_periodicidade=periodicidade)
    contexto["projecao"] = executar_simulacao(cenario.seq_simulador_cenario)[
        "projecao_despesa"]


@when(parsers.parse('projeto {ano:d} por média de crescimento de {a:d} e {b:d} com '
                    'referência em junho'))
def projeta_media_crescimento(contexto, rubrica, ano, a, b):
    from fluxocaixa.services.formula_engine import projetar_media_crescimento_anos

    contexto["projecao"] = projetar_media_crescimento_anos(
        [rubrica.seq_qualificador], ano, [a, b], 6, 12)


@when("projeto por média histórica sazonal com período-base de 12 meses")
def projeta_media_historica(contexto):
    from fluxocaixa.services.modelos_economicos_service import projetar_media_historica

    contexto["projecao"] = projetar_media_historica(
        contexto["serie"], 12, {"periodo_meses": 12, "considerar_sazonalidade": True},
        2093)


@when("projeto 12 meses com LightGBM")
def projeta_lightgbm(contexto):
    from fluxocaixa.services import modelos_economicos_service as modelos

    if not modelos.HAS_LIGHTGBM:
        pytest.skip("lightgbm indisponível")
    ano = pd.Timestamp(contexto["serie"]["data"].max()).year + 1
    contexto["projecao"] = modelos.projetar_lightgbm(contexto["serie"], 12, {}, ano)


@when("consulto a janela do SARIMA nas três portas")
def janelas_sarima(contexto):
    import inspect

    from fluxocaixa.services import modelos_economicos_service as modelos
    from fluxocaixa.services import simulador_cenario_service
    from fluxocaixa.services.metodo_qualificador_service import MODELOS_DE_SERIE

    assert "JANELA_EM_ANOS" in inspect.getsource(modelos.calcular_projecao)
    assert "JANELA_EM_ANOS" in inspect.getsource(simulador_cenario_service._projetar_perna)
    contexto["janelas"] = [modelos.JANELA_EM_ANOS["SARIMA"],
                           MODELOS_DE_SERIE["SARIMA"][0],
                           modelos.janela_do_modelo("SARIMA")]


@when(parsers.parse('executo o backtest de {ano:d} com média histórica e data de corte '
                    '"{corte}"'))
def executa_backtest(contexto, rubrica, ano, corte):
    from fluxocaixa.services.backtest_service import executar_backtest

    contexto["backtest"] = executar_backtest(
        anos_treino=[ano - 3, ano - 2, ano - 1], anos_teste=[ano],
        modelos=['MEDIA_HISTORICA'], qualificadores_ids=[rubrica.seq_qualificador],
        hoje=date.fromisoformat(corte))


@when("comparo os modelos")
def compara_modelos(contexto):
    from fluxocaixa.services.backtest_service import _calcular_metricas, _escolher_melhor

    candidatos = {}
    for nome, dados in contexto["modelos"].items():
        metricas = _calcular_metricas(dados["projecao"], contexto["real"])
        candidatos[nome] = {**metricas, "anos_medidos": dados["anos"],
                            "degradacoes": ["fallback"] if dados["degradado"] else []}
    contexto["candidatos"] = candidatos
    contexto["melhor"] = _escolher_melhor(candidatos)


@when("agrego o pai das duas folhas")
def agrega_pai(contexto):
    from fluxocaixa.services.backtest_service import _metricas_da_soma

    contexto["metricas_pai"] = _metricas_da_soma(contexto["folhas"])


@when(parsers.parse('consulto Previsão × Realizado de {ano:d} para a rubrica de {ano_rubrica:d} '
                    'sem cenário'))
def consulta_previsao_realizado(contexto, ano, ano_rubrica):
    from fluxocaixa.services.previsao_service import get_previsao_realizado_data

    contexto["relatorio"] = get_previsao_realizado_data(
        ano, None, list(range(1, 13)), [contexto["herdeira"].seq_qualificador])


@when("uma despesa do plano de 2122 tenta herdar a raiz da receita")
def despesa_herda_receita(contexto, rubrica):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        _criar_q("2.83", 2122, raiz=rubrica.cod_rubrica_raiz)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        _db().session.rollback()
        contexto["erro"] = exc


@when("reaponto a rubrica de 2122 para a despesa")
def reaponta(contexto):
    from fluxocaixa.services.qualificador_service import update_qualificador
    from fluxocaixa.services.validacao import RegraNegocioError

    herdeira = contexto["herdeira"]
    try:
        update_qualificador(herdeira.seq_qualificador, "2.83.1", herdeira.dsc_qualificador,
                            cod_qualificador_pai=contexto["despesa"].seq_qualificador,
                            confirmado=True)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        _db().session.rollback()
        contexto["erro"] = exc


# ---------------------------------------------------------------------------
# Verificações
# ---------------------------------------------------------------------------

@then(parsers.parse('a projeção tem {n:d} {rotulo}, todos em {ano:d}, somando "{total}"'))
def cenario_projetado(contexto, n, rotulo, ano, total):
    df = contexto["projecao"]
    assert len(df) == n, df
    assert {pd.Timestamp(d).year for d in df["data"]} == {ano}
    assert round(float(df["valor_projetado"].sum()), 2) == float(total)


@then(parsers.parse('a soma dos doze meses é "{total}"'))
def soma_doze(contexto, total):
    assert round(float(contexto["projecao"]["valor_projetado"].sum()), 2) == float(total)


@then(parsers.parse('janeiro a junho valem "{valor}"'))
def primeiro_semestre(contexto, valor):
    valores = contexto["projecao"]["valor_projetado"].tolist()[:6]
    assert valores == [float(valor)] * 6


@then(parsers.parse('todos os meses projetados valem "{valor}"'))
def todos_valem(contexto, valor):
    valores = [round(float(v), 2) for v in contexto["projecao"]["valor_projetado"]]
    assert valores == [float(valor)] * 12, valores


@then("a projeção não é constante")
def nao_constante(contexto):
    valores = contexto["projecao"]["valor_projetado"].round(2)
    assert valores.nunique() > 1, valores.tolist()
    assert not contexto["projecao"].attrs.get("degradacao")


@then(parsers.parse('o resultado declara a degradação "{trecho}"'))
def declara_degradacao(contexto, trecho):
    assert trecho in (contexto["projecao"].attrs.get("degradacao") or "")


@then(parsers.parse("as três usam {anos:d} anos"))
def tres_janelas(contexto, anos):
    assert contexto["janelas"] == [anos] * 3


@then(parsers.parse("os meses medidos de {ano:d} são de janeiro a agosto"))
def meses_medidos(contexto, ano):
    filho = contexto["backtest"]["resultados_filho"][0]
    detalhe = filho["modelos"]["MEDIA_HISTORICA"]["detalhes_por_ano"][0]
    assert detalhe["ano_teste"] == ano
    assert detalhe["meses_avaliados"] == list(range(1, 9))


@then(parsers.parse('o resultado informa a data de corte "{corte}"'))
def data_de_corte(contexto, corte):
    assert contexto["backtest"]["data_corte"] == corte


@then(parsers.parse('o WMAPE de "{a}" é "{wa}" e o de "{b}" é "{wb}"'))
def wmapes(contexto, a, wa, b, wb):
    assert contexto["candidatos"][a]["wmape"] == float(wa)
    assert contexto["candidatos"][b]["wmape"] == float(wb)


@then(parsers.parse('o WMAPE de "{a}" é nulo e o MAE é "{mae}"'))
def wmape_nulo(contexto, a, mae):
    assert contexto["candidatos"][a]["wmape"] is None
    assert contexto["candidatos"][a]["mae"] == float(mae)


@then(parsers.parse('o melhor modelo é "{nome}"'))
def melhor(contexto, nome):
    assert contexto["melhor"] == nome


@then(parsers.parse('o WMAPE do pai é "{valor}"'))
def wmape_pai(contexto, valor):
    assert contexto["metricas_pai"]["wmape"] == float(valor)


@then(parsers.parse('a previsão inicial soma "{total}"'))
def previsao_inicial(contexto, total):
    from fluxocaixa.utils import format_currency

    linha = contexto["relatorio"]["tabela"][0]
    assert linha["previsao_inicial"] == format_currency(float(total))


@then("a operação é recusada citando a natureza")
def recusada_natureza(contexto):
    assert contexto["erro"] is not None
    assert "natureza" in str(contexto["erro"]).lower()
