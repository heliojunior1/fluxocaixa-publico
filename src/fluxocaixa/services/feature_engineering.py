"""Atributos dos modelos de aprendizado de máquina (XGBoost, LightGBM).

ORIGEM ÚNICA (previsao R19, change corrigir-motores-de-previsao):
`atributos_do_mes(anteriores, data)` calcula os atributos de UM mês-alvo só
com os valores dos meses ANTERIORES a ele, e serve às duas fases:

- treino — `montar_treino` chama para cada mês t com `serie[:t]`;
- previsão recursiva — o motor chama com `histórico + previsões já feitas`.

Antes eram dois cálculos (vetorizado no treino, manual na recursão) e eles
divergiram duas vezes: as médias/desvio móveis e as variações do treino
incluíam o PRÓPRIO mês (o modelo aprendia `y = 3·media_movel_3 − lag_1 −
lag_2` exatamente — vazamento do alvo) e a recursão tinha as defasagens
deslocadas em uma posição (`lag_1 = 0` a partir do 2º mês previsto). Com um
cálculo só, os dois defeitos deixam de ser possíveis por construção.
"""
from collections.abc import Sequence

import numpy as np
import pandas as pd

# Defasagens exigidas para uma linha de treino — o 1º mês treinável é o 13º.
DEFASAGENS = 12

_COLUNAS = [
    'mes', 'mes_sin', 'mes_cos', 'ano', 'trimestre', 'tendencia',
    *[f'lag_{k}' for k in range(1, DEFASAGENS + 1)],
    'media_movel_3', 'media_movel_6', 'media_movel_12', 'std_movel_3',
    'variacao_mensal', 'variacao_anual',
]


def get_feature_columns() -> list:
    """Colunas de atributo, na ordem usada no treino e na previsão."""
    return list(_COLUNAS)


def _variacao(atual: float, anterior: float | None) -> float:
    if anterior is None or anterior == 0:
        return 0.0
    return (atual - anterior) / abs(anterior)


def atributos_do_mes(anteriores: Sequence[float], data) -> dict:
    """Atributos do mês `data` a partir dos valores dos meses anteriores a ele
    (o último elemento de `anteriores` é o mês imediatamente anterior).

    Nenhum atributo depende do valor do próprio mês-alvo. Defasagem sem valor
    disponível fica NaN — o treino só usa meses com as 12 defasagens.
    """
    data = pd.Timestamp(data)
    valores = [float(v) for v in anteriores]
    n = len(valores)
    atributos = {
        'mes': data.month,
        'mes_sin': float(np.sin(2 * np.pi * data.month / 12)),
        'mes_cos': float(np.cos(2 * np.pi * data.month / 12)),
        'ano': data.year,
        'trimestre': (data.month - 1) // 3 + 1,
        'tendencia': n,
    }
    for k in range(1, DEFASAGENS + 1):
        atributos[f'lag_{k}'] = valores[-k] if n >= k else np.nan

    def _media(janela):
        ultimos = valores[-janela:]
        return float(np.mean(ultimos)) if ultimos else 0.0

    atributos['media_movel_3'] = _media(3)
    atributos['media_movel_6'] = _media(6)
    atributos['media_movel_12'] = _media(12)
    ultimos_3 = valores[-3:]
    atributos['std_movel_3'] = float(np.std(ultimos_3, ddof=1)) if len(ultimos_3) >= 2 else 0.0
    ultimo = valores[-1] if n else 0.0
    atributos['variacao_mensal'] = _variacao(ultimo, valores[-2] if n >= 2 else None)
    atributos['variacao_anual'] = _variacao(ultimo, valores[-13] if n >= 13 else None)
    return atributos


def montar_treino(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """(X, y) de treino a partir da série mensal regular (`data`, `valor`).

    Uma linha por mês que tenha as 12 defasagens; o índice é a data do mês —
    o que permite conferir, linha a linha, que o valor do mês não entra nos
    seus atributos.
    """
    serie = df.sort_values('data').reset_index(drop=True)
    datas = pd.to_datetime(serie['data'])
    valores = [float(v) for v in serie['valor']]
    linhas, alvos, indice = [], [], []
    for t in range(DEFASAGENS, len(valores)):
        linhas.append(atributos_do_mes(valores[:t], datas[t]))
        alvos.append(valores[t])
        indice.append(datas[t])
    X = pd.DataFrame(linhas, columns=_COLUNAS, index=pd.DatetimeIndex(indice))
    X = X.replace([np.inf, -np.inf], 0).fillna(0)
    y = pd.Series(alvos, index=X.index)
    return X, y
