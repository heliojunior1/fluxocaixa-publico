"""Steps BDD — motores de previsão corrigidos (spec previsao R12/R17/R18/R19).

Massa sintética para os motores; ilhas 2081–2086 e ramo "8.9" para os
cenários com banco. Import tardio de `fluxocaixa`. Cenários que dependem de
lib opcional pulam quando ela não carrega (guards do módulo).
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../previsao/motores_corrigidos.feature")

RAMO = "8.9"


@pytest.fixture()
def contexto():
    return {}


# ----------------------------------------------------------------- massa

def _serie(valores, inicio=date(2082, 1, 1)):
    import pandas as pd

    datas = pd.date_range(inicio, periods=len(valores), freq="MS")
    return pd.DataFrame({"data": datas, "valor": [float(v) for v in valores]})


def _modelos():
    from fluxocaixa.services import modelos_economicos_service as modelos

    return modelos


def _exigir(flag, nome):
    if not getattr(_modelos(), flag):
        pytest.skip(f"{nome} indisponível")


def _limpar():
    from fluxocaixa.models import Lancamento, Qualificador
    from fluxocaixa.models.base import db

    db.session.rollback()
    quals = Qualificador.query.filter(
        Qualificador.num_qualificador.like(f"{RAMO}%")).all()
    seqs = [q.seq_qualificador for q in quals]
    if seqs:
        Lancamento.query.filter(Lancamento.seq_qualificador.in_(seqs)).delete(
            synchronize_session=False)
    for q in sorted(quals, key=lambda x: -len(x.num_qualificador)):
        db.session.delete(q)
    db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


def _rubrica(ano, raiz=None):
    from fluxocaixa.services import qualificador_service

    return qualificador_service.create_qualificador(
        RAMO, "Rubrica Sonda Motores", num_ano_exercicio=ano,
        cod_rubrica_raiz=raiz)


def _lancar(q, dia, valor, tipo="Entrada"):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.base import db
    from fluxocaixa.services.dominio_lancamento import resolver_origem, resolver_tipo

    db.session.add(Lancamento(
        dat_lancamento=dia, seq_qualificador=q.seq_qualificador,
        val_lancamento=Decimal(str(valor)),
        cod_tipo_lancamento=resolver_tipo(tipo).cod_tipo_lancamento,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        cod_pessoa_inclusao=1, ind_status="A"))
    db.session.commit()


def _data(texto):
    return date.fromisoformat(texto)


# ------------------------------------------------------------ séries puras

@given(parsers.parse("uma série mensal de 12 meses com pico de {pico} em "
                     "dezembro e {base} nos demais"), target_fixture="serie")
def serie_12_pico(pico, base):
    return _serie([float(pico) if m == 12 else float(base) for m in range(1, 13)],
                  inicio=date(2084, 1, 1))


@given(parsers.parse("uma série mensal de {n:d} meses em torno de {centro}"),
       target_fixture="serie")
def serie_em_torno(n, centro):
    valores = [float(centro) + (i % 5) * 10 for i in range(n)]
    fim = date(2084, 12, 1)
    from dateutil.relativedelta import relativedelta

    return _serie(valores, inicio=fim - relativedelta(months=n - 1))


@given(parsers.parse("uma série mensal de {n:d} meses com {valor} em todos os "
                     "meses"), target_fixture="serie")
def serie_constante(n, valor):
    from dateutil.relativedelta import relativedelta

    return _serie([float(valor)] * n,
                  inicio=date(2084, 12, 1) - relativedelta(months=n - 1))


@given(parsers.parse("uma série mensal de 36 meses com valores 1.00 a 36.00"),
       target_fixture="serie")
def serie_sequencial():
    return _serie(list(range(1, 37)))


@given(parsers.parse("uma série de janeiro de 2082 a setembro de 2084 com "
                     "{pico} em dezembro e {base} nos demais meses"),
       target_fixture="serie")
def serie_ate_setembro(pico, base):
    serie = _serie([0.0] * 33)
    serie["valor"] = [float(pico) if d.month == 12 else float(base)
                      for d in serie["data"]]
    return serie


# ----------------------------------------------------------------- motores

def _projetar(contexto, motor, serie, config, flag, nome):
    _exigir(flag, nome)
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        contexto["resultado"] = motor(serie, 12, config, 2085)
    except RegraNegocioError as exc:
        contexto["erro"] = exc


@when("projeto 12 meses de 2085 com Holt-Winters sazonal")
def projeta_hw(contexto, serie):
    _projetar(contexto, _modelos().projetar_holt_winters, serie,
              {"seasonal": "add", "trend": "add"}, "HAS_STATSMODELS", "statsmodels")


@when("projeto 12 meses de 2085 com SARIMA sazonal")
def projeta_sarima(contexto, serie):
    _projetar(contexto, _modelos().projetar_sarima, serie,
              {"P": 1, "D": 1, "Q": 1, "s": 12}, "HAS_STATSMODELS", "statsmodels")


@when(parsers.parse("projeto 12 meses de 2085 com ARIMA automático e "
                    "diferenciação {d:d}"))
def projeta_arima(contexto, serie, d):
    _projetar(contexto, _modelos().projetar_arima, serie,
              {"auto_order": True, "d": d}, "HAS_STATSMODELS", "statsmodels")


@when("projeto 12 meses de 2085 com XGBoost")
def projeta_xgb(contexto, serie):
    _projetar(contexto, _modelos().projetar_xgboost, serie, {},
              "HAS_XGBOOST", "xgboost")


@when("projeto 12 meses de 2085 com LightGBM")
def projeta_lgbm(contexto, serie):
    _projetar(contexto, _modelos().projetar_lightgbm, serie, {},
              "HAS_LIGHTGBM", "lightgbm")


@then("a projeção não tem padrão sazonal")
def sem_padrao_sazonal(contexto):
    valores = list(contexto["resultado"]["valor_projetado"])
    difs = [b - a for a, b in zip(valores, valores[1:])]
    # Sem componente sazonal a projeção é monótona (nível + tendência)
    assert all(d >= -1e-6 for d in difs) or all(d <= 1e-6 for d in difs), valores


@then(parsers.parse('o resultado carrega a degradação citando "{trecho}"'))
def degradacao_cita(contexto, trecho):
    degradacao = contexto["resultado"].attrs.get("degradacao") or ""
    assert trecho in degradacao, degradacao


@then(parsers.parse("a ordem escolhida tem diferenciação {d:d}"))
def ordem_com_d(contexto, d):
    assert contexto["resultado"].attrs["ordem"][1] == d


@then("o maior valor projetado está em dezembro de 2085")
def pico_em_dezembro(contexto):
    df = contexto["resultado"]
    linha = df.loc[df["valor_projetado"].idxmax()]
    data = linha["data"]
    assert (data.year, data.month) == (2085, 12), list(zip(df["data"], df["valor_projetado"]))


@then(parsers.parse("todos os meses projetados ficam a menos de 1% de {valor}"))
def constante(contexto, valor):
    alvo = float(valor)
    for v in contexto["resultado"]["valor_projetado"]:
        assert abs(v - alvo) / alvo < 0.01, list(contexto["resultado"]["valor_projetado"])


@then(parsers.parse('recebo erro de negócio citando "{a}" e "{b}"'))
def erro_cita(contexto, a, b):
    assert "erro" in contexto, "esperava erro de negócio"
    mensagem = str(contexto["erro"])
    assert a in mensagem and b in mensagem, mensagem


# ------------------------------------------------------- atributos de ML

@when(parsers.parse("altero o valor do mês 18 para {valor}"))
def altera_mes_18(contexto, serie, valor):
    from fluxocaixa.services.feature_engineering import montar_treino

    alterada = serie.copy()
    alterada.loc[17, "valor"] = float(valor)
    contexto["original"], _ = montar_treino(serie)
    contexto["alterada"], _ = montar_treino(alterada)
    contexto["data_18"] = serie.loc[17, "data"]


@then("nenhum atributo de treino do mês 18 muda")
def atributos_iguais(contexto):
    antes = contexto["original"].loc[contexto["data_18"]]
    depois = contexto["alterada"].loc[contexto["data_18"]]
    assert antes.equals(depois), (antes - depois)[antes != depois]


@when(parsers.parse("monto os atributos do mês seguinte a duas previsões de "
                    "{p1} e {p2}"))
def atributos_recursivos(contexto, serie, p1, p2):
    from fluxocaixa.services.feature_engineering import atributos_do_mes

    anteriores = list(serie["valor"]) + [float(p1), float(p2)]
    contexto["atributos"] = atributos_do_mes(anteriores, date(2085, 3, 1))


@then(parsers.parse("a defasagem 1 é {l1}, a defasagem 2 é {l2} e a defasagem "
                    "3 é {l3}"))
def defasagens(contexto, l1, l2, l3):
    a = contexto["atributos"]
    assert (a["lag_1"], a["lag_2"], a["lag_3"]) == (float(l1), float(l2), float(l3))


# ------------------------------------------------------------ com banco

@given(parsers.parse('a rubrica "8.9" com {v1} por mês no plano de {a1:d} e '
                     '{v2} por mês de janeiro a junho no plano de {a2:d}, com '
                     'a mesma raiz'), target_fixture="rubricas")
def rubrica_dois_planos(v1, a1, v2, a2):
    qa = _rubrica(a1)
    qb = _rubrica(a2, raiz=qa.cod_rubrica_raiz)
    for mes in range(1, 13):
        _lancar(qa, date(a1, mes, 15), v1)
    for mes in range(1, 7):
        _lancar(qb, date(a2, mes, 15), v2)
    return {a1: qa, a2: qb}


@when(parsers.parse("projeto {ano:d} com o crescimento sobre {ref:d} e mês de "
                    "referência {mes:d} pela folha do plano de {plano:d}"))
def projeta_crescimento(contexto, rubricas, ano, ref, mes, plano):
    from fluxocaixa.services.formula_engine import projetar_crescimento_ultimo_ano

    contexto["resultado"] = projetar_crescimento_ultimo_ano(
        [rubricas[plano].seq_qualificador], ano, ref, mes)


@then(parsers.parse("cada mês de julho a dezembro é projetado em {valor}"))
def meses_projetados(contexto, valor):
    df = contexto["resultado"]
    for _, linha in df.iterrows():
        if linha["data"].month >= 7:
            assert round(linha["valor_projetado"], 2) == float(valor), list(df["valor_projetado"])


@then(parsers.parse("o total do ano é {total}"))
def total_do_ano(contexto, total):
    assert round(float(contexto["resultado"]["valor_projetado"].sum()), 2) == float(total)


@given(parsers.parse('a rubrica "8.9" de receita com crédito de {credito} e '
                     'estorno de {estorno} em março de {ano:d}'),
       target_fixture="rubrica")
def rubrica_com_estorno(credito, estorno, ano):
    q = _rubrica(ano)
    _lancar(q, date(ano, 3, 10), credito, "Entrada")
    _lancar(q, date(ano, 3, 20), estorno, "Saída")
    return q


@when(parsers.parse("calculo o acumulado de março de {ano:d} para o crescimento"))
def calcula_acumulado(contexto, rubrica, ano):
    from fluxocaixa.services.formula_engine import _soma_acumulada

    contexto["acumulado"] = _soma_acumulada([rubrica.seq_qualificador], ano, 3, 3)


@then(parsers.parse("o acumulado é {valor}"))
def acumulado(contexto, valor):
    assert round(contexto["acumulado"], 2) == float(valor)


@given(parsers.parse('a rubrica "8.9" com {valor} em todos os meses de {ano:d} '
                     'exceto março'), target_fixture="rubrica")
def rubrica_sem_marco(valor, ano):
    q = _rubrica(ano)
    for mes in range(1, 13):
        if mes != 3:
            _lancar(q, date(ano, mes, 15), valor)
    return q


@given(parsers.parse('a rubrica "8.9" com {valor} em todos os meses de {a1:d} '
                     'e de janeiro a setembro de {a2:d}'), target_fixture="rubrica")
def rubrica_ate_setembro(valor, a1, a2):
    q = _rubrica(a1)
    for mes in range(1, 13):
        _lancar(q, date(a1, mes, 15), valor)
    for mes in range(1, 10):
        _lancar(q, date(a2, mes, 15), valor)
    return q


@given(parsers.re(r'a rubrica "8\.9" com (?P<v1>[\d.]+) em (?P<d1>\d{4}-\d{2}-\d{2}) '
                  r'e (?P<v2>[\d.]+) em (?P<d2>\d{4}-\d{2}-\d{2})'),
       target_fixture="rubrica")
def rubrica_duas_datas(v1, d1, v2, d2):
    q = _rubrica(_data(d1).year)
    _lancar(q, _data(d1), v1)
    _lancar(q, _data(d2), v2)
    return q


@when(parsers.parse("obtenho a série mensal de {ano:d} com execução em {hoje}"))
def serie_do_ano(contexto, rubrica, ano, hoje):
    contexto["serie"] = _modelos().obter_dados_historicos(
        rubrica.seq_qualificador, date(ano, 1, 1), date(ano, 12, 31),
        hoje=_data(hoje))


@when(parsers.parse("obtenho a série para o ano-base {ano:d} com janela de "
                    "{janela:d} anos e execução em {hoje}"))
def serie_do_ano_base(contexto, rubrica, ano, janela, hoje):
    contexto["serie"] = _modelos().obter_serie_do_ano_base(
        [rubrica.seq_qualificador], ano, janela, hoje=_data(hoje))


@then(parsers.parse("a série tem {n:d} pontos"))
def serie_tem(contexto, n):
    assert len(contexto["serie"]) == n, contexto["serie"]


@then(parsers.parse("o ponto de março de {ano:d} vale {valor}"))
def ponto_marco(contexto, ano, valor):
    df = contexto["serie"]
    linha = df[df["data"] == f"{ano}-03-01"]
    assert len(linha) == 1, df
    assert round(float(linha["valor"].iloc[0]), 2) == float(valor)


def _mes_por_extenso(texto):
    nomes = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
             "agosto", "setembro", "outubro", "novembro", "dezembro"]
    return nomes.index(texto) + 1


@then(parsers.parse("o último ponto da série é {mes} de {ano:d}"))
def ultimo_ponto(contexto, mes, ano):
    d = contexto["serie"]["data"].max()
    assert (d.year, d.month) == (ano, _mes_por_extenso(mes)), contexto["serie"]


@then(parsers.parse("o primeiro ponto da série é {mes} de {ano:d}"))
def primeiro_ponto(contexto, mes, ano):
    d = contexto["serie"]["data"].min()
    assert (d.year, d.month) == (ano, _mes_por_extenso(mes)), contexto["serie"]
