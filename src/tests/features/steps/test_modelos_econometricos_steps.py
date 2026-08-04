"""Steps BDD — modelos econométricos corrigidos (spec previsao R12).

Massa sintética, sem banco. Cenários de Holt-Winters pulam quando
statsmodels não está instalado (import guard do módulo).
"""
from datetime import date

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../previsao/modelos_econometricos.feature")

ANO = 2063


@pytest.fixture()
def contexto():
    return {}


def _serie_mensal(valores, ano_inicial=2060):
    import pandas as pd

    datas, ano, mes = [], ano_inicial, 1
    for _ in valores:
        datas.append(date(ano, mes, 1))
        mes += 1
        if mes > 12:
            mes, ano = 1, ano + 1
    return pd.DataFrame({"data": datas, "valor": valores})


@given(parsers.parse("uma série mensal de 24 pontos em torno de {centro} com um "
                     "mês negativo de {negativo}"),
       target_fixture="serie")
def serie_com_negativo(centro, negativo):
    valores = [float(centro) + (i % 12) for i in range(24)]
    valores[5] = float(negativo)
    return _serie_mensal(valores)


@given("uma série histórica mensal válida", target_fixture="serie")
def serie_valida():
    return _serie_mensal([100.0 + (i % 12) * 10 for i in range(24)])


@given("que o treino do Holt-Winters configurado falhará", target_fixture="serie")
def treino_falha(monkeypatch):
    from fluxocaixa.services import modelos_economicos_service as modelos

    if not modelos.HAS_STATSMODELS:
        pytest.skip("statsmodels não instalado")

    real = modelos.ExponentialSmoothing
    chamadas = {"n": 0}

    class _PrimeiraFalha:
        def __new__(cls, *args, **kwargs):
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                raise ValueError("falha simulada no treino configurado")
            return real(*args, **kwargs)

    monkeypatch.setattr(modelos, "ExponentialSmoothing", _PrimeiraFalha)
    return _serie_mensal([100.0 + (i % 12) for i in range(24)])


@when("projeto com Holt-Winters sazonal multiplicativo")
def projeta_hw(contexto, serie):
    from fluxocaixa.services import modelos_economicos_service as modelos

    if not modelos.HAS_STATSMODELS:
        pytest.skip("statsmodels não instalado")
    contexto["resultado"] = modelos.projetar_holt_winters(
        serie, 12, {"seasonal": "mul", "trend": "add"}, ano_base=ANO)


@when(parsers.parse("projeto {n:d} períodos de média histórica com ano-base "
                    "{ano:d}"))
def projeta_media(contexto, serie, n, ano):
    from fluxocaixa.services import modelos_economicos_service as modelos

    try:
        contexto["resultado"] = modelos.projetar_media_historica(
            serie, n, {}, ano_base=ano)
        contexto["erro"] = None
    except ValueError as exc:
        contexto["erro"] = exc


@given(parsers.parse('a fórmula "{expressao}" com base fixa de {base}'),
       target_fixture="formula")
def formula_com_base(expressao, base):
    return {"expressao": expressao, "base": float(base)}


@when(parsers.parse('projeto com a fórmula sem informar "{param}"'))
def projeta_formula(contexto, formula, param):
    from fluxocaixa.services import formula_engine
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        contexto["resultado"] = formula_engine.projetar_com_formula(
            seq_qualificador=1, ano_base=ANO, meses=3,
            expressao=formula["expressao"], metodo_base="VALOR_FIXO",
            config_base={"valor": formula["base"]}, parametros={})
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc


@when(parsers.parse('valido a fórmula "{expressao}"'))
def valida_formula(contexto, expressao):
    from fluxocaixa.services import formula_engine

    contexto["valida"], contexto["mensagem"] = formula_engine.validar_formula(
        expressao)


@then("a projeção fica na ordem de grandeza da série original")
def ordem_de_grandeza(contexto):
    resultado = contexto["resultado"]
    media = float(resultado["valor_projetado"].mean())
    # Com o bug, a projeção sai inflada em (1 - min) = 51: média ~150+.
    # Sem o bug, fica na ordem da série (~100 ± sazonalidade).
    assert media < 135.0, (
        f"projeção média {media:.2f} — inflada pelo deslocamento não revertido")
    assert media > 0.0


@then(parsers.parse("as datas projetadas cobrem {ano1:d} e {ano2:d}"))
def datas_cobrem(contexto, ano1, ano2):
    anos = {d.year for d in contexto["resultado"]["data"]}
    assert anos == {ano1, ano2}, anos


@then("nenhum erro de mês inválido é levantado")
def sem_erro_mes(contexto):
    assert contexto["erro"] is None, contexto["erro"]


@then("o resultado carrega a degradação citando o fallback")
def degradacao_visivel(contexto):
    degradacao = contexto["resultado"].attrs.get("degradacao")
    assert degradacao, (
        "o fallback rodou em silêncio — nenhuma degradação registrada no "
        "resultado")
    assert "Holt-Winters" in degradacao


@then(parsers.parse('recebo erro de negócio citando "{param}"'))
def erro_citando(contexto, param):
    assert contexto["erro"] is not None, (
        f"a fórmula projetou {contexto.get('resultado')} em vez de falhar — "
        "parâmetro faltante virou base em silêncio")
    assert param in str(contexto["erro"])


@then("ela é aceita como sintaticamente válida")
def formula_valida(contexto):
    assert contexto["valida"] is True, contexto["mensagem"]
