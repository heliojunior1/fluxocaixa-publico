"""Atributos de ML sem vazamento e com defasagens corretas (previsao R19).

Unitários puros, massa sintética. Import tardio de `fluxocaixa`.
"""
import numpy as np
import pandas as pd


def _serie(valores, inicio="2082-01-01"):
    return pd.DataFrame({"data": pd.date_range(inicio, periods=len(valores), freq="MS"),
                         "valor": [float(v) for v in valores]})


def test_nenhum_atributo_do_mes_depende_do_proprio_valor():
    """Propriedade em série aleatória (seed fixa): mudar o valor do mês t não
    muda nenhum atributo do mês t — e muda os dos meses seguintes."""
    from fluxocaixa.services.feature_engineering import montar_treino

    rng = np.random.default_rng(42)
    base = _serie(rng.uniform(100, 1000, 40))
    X_base, _ = montar_treino(base)
    for t in (12, 20, 39):
        alterada = base.copy()
        alterada.loc[t, "valor"] = 1e9
        X_alt, _ = montar_treino(alterada)
        data_t = base.loc[t, "data"]
        assert X_base.loc[data_t].equals(X_alt.loc[data_t]), f"mês {t} vazou"
        if t < 39:
            data_seguinte = base.loc[t + 1, "data"]
            assert not X_base.loc[data_seguinte].equals(X_alt.loc[data_seguinte])


def test_treino_comeca_no_decimo_terceiro_mes():
    from fluxocaixa.services.feature_engineering import montar_treino

    X, y = montar_treino(_serie(range(1, 15)))
    assert len(X) == 2 and list(y) == [13.0, 14.0]
    assert X.iloc[0]["lag_1"] == 12.0 and X.iloc[0]["lag_12"] == 1.0


def test_defasagens_na_recursao():
    from fluxocaixa.services.feature_engineering import atributos_do_mes

    historico = [float(v) for v in range(1, 37)]
    # 1º passo: só histórico
    a = atributos_do_mes(historico, "2085-01-01")
    assert (a["lag_1"], a["lag_2"], a["lag_12"]) == (36.0, 35.0, 25.0)
    # 2º passo: lag_1 é a previsão anterior
    a = atributos_do_mes(historico + [100.0], "2085-02-01")
    assert (a["lag_1"], a["lag_2"]) == (100.0, 36.0)
    # 13º passo: lag_12 já é a 1ª previsão
    previstos = [100.0 + k for k in range(12)]
    a = atributos_do_mes(historico + previstos, "2086-01-01")
    assert a["lag_1"] == 111.0 and a["lag_12"] == 100.0


def test_variacoes_usam_so_meses_anteriores():
    from fluxocaixa.services.feature_engineering import atributos_do_mes

    a = atributos_do_mes([100.0] * 12 + [110.0], "2083-02-01")
    assert round(a["variacao_mensal"], 4) == 0.1
    assert round(a["variacao_anual"], 4) == 0.1
    assert a["media_movel_3"] == (100 + 100 + 110) / 3
