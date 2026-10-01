"""Service for economic forecasting models."""

import logging
import warnings
from contextlib import contextmanager
from datetime import date

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

from .serie_historica import serie_mensal

logger = logging.getLogger(__name__)


@contextmanager
def _sem_avisos_de_convergencia():
    """Confina a supressão de warnings aos `fit()` (previsao R12).

    O `filterwarnings('ignore')` global no import silenciava UserWarning e
    FutureWarning do PROCESSO INTEIRO (pandas, SQLAlchemy, pydantic) como
    efeito colateral de importar este módulo.
    """
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        warnings.simplefilter('ignore', FutureWarning)
        warnings.simplefilter('ignore', RuntimeWarning)
        yield

# Statistical models
HAS_STATSMODELS = False
HAS_SKLEARN = False

# ⚠️ `except Exception`, não `except ImportError`: a lib pode estar INSTALADA e
# ainda assim não carregar — o XGBoost levanta `XGBoostError` quando o
# `libxgboost.dylib` não acha o OpenMP (`libomp`), caso comum no macOS. Com
# `ImportError` o guard não pegava, o módulo inteiro morria no import e levava
# junto os modelos que não têm nada a ver com ML (MEDIA_HISTORICA, LOA) e a
# própria `executar_simulacao`. A degradação graciosa era a intenção original.
try:
    from statsmodels.tsa.arima.model import ARIMA
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    HAS_STATSMODELS = True
except Exception as e:  # noqa: BLE001 - ver nota acima
    logger.warning("statsmodels indisponível: %s", e)

try:
    HAS_SKLEARN = True
except Exception as e:  # noqa: BLE001 - ver nota acima
    logger.warning("sklearn indisponível: %s", e)

HAS_XGBOOST = False
HAS_LIGHTGBM = False

try:
    from xgboost import XGBRegressor
    HAS_XGBOOST = True
except Exception as e:  # noqa: BLE001 - ver nota acima
    logger.warning("xgboost indisponível: %s", e)

try:
    from lightgbm import LGBMRegressor
    HAS_LIGHTGBM = True
except Exception as e:  # noqa: BLE001 - ver nota acima
    logger.warning("lightgbm indisponível: %s", e)



# Mínimo de meses da série REGULAR por modelo — ORIGEM ÚNICA dos quatro pontos
# de despacho (rota avulsa, cenário por perna, método por qualificador,
# backtest). ML: 12 defasagens + 2 linhas de treino = 14 (previsao R19).
MINIMO_DE_MESES = {
    'HOLT_WINTERS': 12,
    'ARIMA': 12,
    'SARIMA': 12,
    'XGBOOST': 14,
    'LIGHTGBM': 14,
    'MEDIA_HISTORICA': 1,
}

# Janela de treino (anos antes do ano-base) por modelo — ORIGEM ÚNICA das três
# portas (rota avulsa, cenário por perna, método por qualificador). A perna
# usava 3 anos para todo modelo e o SARIMA divergia das outras portas (4).
JANELA_EM_ANOS = {
    'HOLT_WINTERS': 3,
    'ARIMA': 3,
    'SARIMA': 4,
    'XGBOOST': 3,
    'LIGHTGBM': 3,
    'MEDIA_HISTORICA': 3,
}


def janela_do_modelo(modelo: str) -> int:
    """Anos de treino do modelo (default 3 para quem não está na tabela)."""
    return JANELA_EM_ANOS.get(modelo, 3)


# ==================== Helper Functions ====================

def _datas_do_ano_base(ano_base: int, num_periodos: int) -> list[date]:
    """Datas mensais a partir de jan/ano_base, por aritmética de calendário.

    A forma antiga (mês = i+1 fixo no ano-base) estourava com 13+ períodos
    (`ValueError: month must be in 1..12`) — e quinzenal/semanal usam até 52.
    Com relativedelta os períodos atravessam para os anos seguintes.
    """
    inicio = date(ano_base, 1, 1)
    return [inicio + relativedelta(months=i) for i in range(num_periodos)]


def janela_do_ano_base(ano_base: int, janela_anos: int) -> tuple[date, date]:
    """Janela de `janela_anos` anos ANTES do ano-base: 1º de janeiro do ano
    −N a 31 de dezembro do ano −1 (previsao R18).

    A forma antiga (`fim - relativedelta(years=N)`) começava em 31/12 do ano
    −N−1 — um "mês" de um dia só no início da série.
    """
    return date(ano_base - janela_anos, 1, 1), date(ano_base - 1, 12, 31)


def _fim_da_serie(data_inicio: date, data_fim: date, ultimo_com_movimento,
                  hoje: date | None):
    """Mês final da série regular (previsao R18), como Timestamp de 1º dia.

    - janela encerrada → último mês da janela (zeros finais são dado real);
    - execução dentro da janela → mês ANTERIOR ao da execução: o mês em curso
      é parcial e os seguintes não aconteceram — zero neles seria inventado;
    - janela inteira depois da execução (só massa de teste) → último mês com
      movimento.
    """
    hoje = hoje or date.today()
    if hoje > data_fim:
        return pd.Timestamp(data_fim.year, data_fim.month, 1)
    if hoje >= data_inicio:
        return pd.Timestamp(hoje.year, hoje.month, 1) - pd.DateOffset(months=1)
    return ultimo_com_movimento


def _regularizar(mensal: pd.Series, data_inicio: date, data_fim: date,
                 hoje: date | None) -> pd.DataFrame:
    """Série mensal COM SINAL, mês a mês e sem buracos (previsao R18).

    Os modelos tratam os pontos como meses consecutivos: um mês sem movimento
    que sumisse da série deslocava a sazonalidade e o calendário da projeção.
    A série começa no primeiro mês com movimento — zeros à esquerda de uma
    rubrica criada no meio da janela pareceriam queda real.
    """
    vazio = pd.DataFrame(columns=['data', 'valor'])
    if mensal.empty:
        return vazio
    mensal = mensal.sort_index()
    fim = _fim_da_serie(data_inicio, data_fim, mensal.index.max(), hoje)
    mensal = mensal[mensal.index <= fim]
    if mensal.empty:
        return vazio
    meses = pd.date_range(mensal.index.min(), fim, freq='MS')
    regular = mensal.reindex(meses, fill_value=0.0)
    return pd.DataFrame({'data': regular.index, 'valor': regular.values})


def _serie_mensal_regular(lancamentos, data_inicio: date, data_fim: date,
                          hoje: date | None) -> pd.DataFrame:
    """Série regular a partir de lançamentos em memória (unitários puros)."""
    if not lancamentos:
        return pd.DataFrame(columns=['data', 'valor'])
    df = pd.DataFrame(
        [{'data': lanc.dat_lancamento, 'valor': float(lanc.valor_com_sinal)}
         for lanc in lancamentos])
    df['data'] = pd.to_datetime(df['data']).dt.to_period('M').dt.to_timestamp()
    return _regularizar(df.groupby('data')['valor'].sum(), data_inicio, data_fim, hoje)


def obter_dados_historicos(
    seq_qualificador: int,
    data_inicio: date,
    data_fim: date,
    agregacao: str = 'mensal',  # 'mensal' ou 'diario'
    hoje: date | None = None,
) -> pd.DataFrame:
    """Série histórica de um qualificador: colunas `data`, `valor` (com sinal).

    F10.2 (previsao R17): a série é da RUBRICA (raiz), não do seq — costura
    entre exercícios. Mensal é REGULAR (R18, ver `_serie_mensal_regular`);
    `hoje` é injetável para os testes do corte do mês em curso.
    """
    return obter_dados_historicos_agregados(
        [seq_qualificador], data_inicio, data_fim, agregacao, hoje)


def obter_dados_historicos_multiplos(
    seq_qualificadores: list[int],
    data_inicio: date,
    data_fim: date,
) -> dict[int, pd.DataFrame]:
    """Obtém dados históricos para múltiplos qualificadores."""
    resultado = {}
    for seq_q in seq_qualificadores:
        resultado[seq_q] = obter_dados_historicos(seq_q, data_inicio, data_fim)
    return resultado


# ==================== Revenue Forecast Models ====================

def _horizonte(dados_historicos: pd.DataFrame, ano_base: int | None,
               num_periodos: int) -> tuple[int, int, list[date]]:
    """(passos, descarte, datas) da projeção ancorada no calendário (R18).

    O modelo prevê a partir do mês SEGUINTE ao último observado. Com ano-base,
    os meses entre o último observado e janeiro do ano-base são previstos e
    DESCARTADOS — antes a posição 1 do forecast era rotulada jan/ano-base
    mesmo quando o histórico acabava em setembro, e o pico de dezembro saía
    em março. `datas` são as dos `num_periodos` devolvidos.
    """
    ultima = pd.Timestamp(pd.to_datetime(dados_historicos['data']).max())
    ultima = pd.Timestamp(ultima.year, ultima.month, 1)
    descarte = 0
    if ano_base:
        descarte = max(0, (ano_base - ultima.year) * 12 + (1 - ultima.month) - 1)
    datas = [(ultima + pd.DateOffset(months=descarte + i + 1)).date()
             for i in range(num_periodos)]
    return descarte + num_periodos, descarte, datas


def _serie_indexada(dados_historicos: pd.DataFrame) -> pd.Series:
    """Série com índice mensal (frequência declarada quando regular)."""
    df = dados_historicos.sort_values('data')
    indice = pd.DatetimeIndex(pd.to_datetime(df['data']))
    try:
        indice = pd.DatetimeIndex(indice, freq='MS')
    except ValueError:
        pass  # série irregular vinda de chamador avulso: sem frequência
    return pd.Series(df['valor'].astype(float).values, index=indice)


def _resultado(datas, valores, avisos: list[str], **attrs) -> pd.DataFrame:
    resultado = pd.DataFrame({
        'data': datas,
        'valor_projetado': np.maximum(np.asarray(valores, dtype=float), 0),
    })
    if avisos:
        resultado.attrs['degradacao'] = '; '.join(avisos)
    resultado.attrs.update(attrs)
    return resultado


def projetar_holt_winters(
    dados_historicos: pd.DataFrame,
    num_periodos: int,
    config: dict,
    ano_base: int = None,
) -> pd.DataFrame:
    """Holt-Winters (suavização exponencial).

    config: seasonal_periods (12), trend ('add'), seasonal ('add'),
    damped_trend (False), use_boxcox (False). Devolve `data`,
    `valor_projetado`; degradações em `attrs['degradacao']` (R12).

    ⚠️ Sazonalidade exige DOIS ciclos (R12): com menos de
    `2 × seasonal_periods` meses o modelo roda sem componente sazonal e avisa.
    Antes o período era reduzido a `n // 2` — sazonalidade semestral
    inventada numa série mensal.
    """
    if not HAS_STATSMODELS:
        raise ValueError("Biblioteca statsmodels não está instalada. Execute: pip install statsmodels")

    n = len(dados_historicos)
    if n < 12:
        raise ValueError("Holt-Winters requer pelo menos 12 meses de dados históricos")

    seasonal_periods = int(config.get('seasonal_periods', 12))
    trend = config.get('trend', 'add')
    seasonal = config.get('seasonal', 'add')
    damped_trend = config.get('damped_trend', False)
    use_boxcox = config.get('use_boxcox', False)

    avisos = []
    if seasonal and n < 2 * seasonal_periods:
        avisos.append(
            f"Holt-Winters sem sazonalidade: a sazonalidade exige "
            f"{2 * seasonal_periods} meses de histórico (encontrados {n})")
        seasonal = None

    series = _serie_indexada(dados_historicos)
    passos, descarte, datas = _horizonte(dados_historicos, ano_base, num_periodos)

    # Garantir valores positivos para multiplicativo ou Box-Cox. O
    # deslocamento é REVERTIDO depois do forecast (previsao R12) — inclusive
    # no fallback, que retreina a série já deslocada.
    deslocamento = 0.0
    if seasonal == 'mul' or use_boxcox:
        min_val = series.min()
        if min_val <= 0:
            series = series - min_val + 1
            deslocamento = float(min_val) - 1.0  # original = deslocada + (min−1)

    def _ajustar(trend_, seasonal_, **extra):
        modelo = ExponentialSmoothing(
            series,
            seasonal_periods=seasonal_periods if seasonal_ else None,
            trend=trend_,
            seasonal=seasonal_,
            **extra,
        )
        with _sem_avisos_de_convergencia():
            return modelo.fit(**({'optimized': True} if extra else {}))

    try:
        fitted_model = _ajustar(trend, seasonal, damped_trend=damped_trend,
                                use_boxcox=use_boxcox)
        forecast = fitted_model.forecast(steps=passos)
    except Exception as e:
        # Fallback NUNCA silencioso (R12): a degradação viaja no resultado
        sazonal_fallback = 'add' if seasonal else None
        mensagem = (f"Holt-Winters (trend={trend}, seasonal={seasonal}) "
                    f"falhou: {e}; usado Holt-Winters aditivo simples")
        logger.warning("%s", mensagem)
        avisos.append(mensagem)
        fitted_model = _ajustar('add', sazonal_fallback)
        forecast = fitted_model.forecast(steps=passos)

    # Reverter o deslocamento ANTES do clamp de não-negatividade
    valores = np.asarray(forecast, dtype=float)[descarte:] + deslocamento
    return _resultado(datas, valores, avisos)


def projetar_arima(
    dados_historicos: pd.DataFrame,
    num_periodos: int,
    config: dict,
    ano_base: int = None,
) -> pd.DataFrame:
    """ARIMA(p, d, q).

    config: p (1), d (1), q (1), auto_order (False). A ordem usada viaja em
    `attrs['ordem']`.

    ⚠️ `auto_order` varia só p e q, com o `d` configurado (R12): o AIC de
    modelos com diferenciações diferentes é calculado sobre séries diferentes
    e não é comparável.
    """
    if not HAS_STATSMODELS:
        raise ValueError("Biblioteca statsmodels não está instalada. Execute: pip install statsmodels")

    if len(dados_historicos) < 12:
        raise ValueError("ARIMA requer pelo menos 12 meses de dados históricos")

    p = int(config.get('p', 1))
    d = int(config.get('d', 1))
    q = int(config.get('q', 1))
    auto_order = config.get('auto_order', False)

    series = _serie_indexada(dados_historicos)
    passos, descarte, datas = _horizonte(dados_historicos, ano_base, num_periodos)

    avisos = []
    try:
        with _sem_avisos_de_convergencia():
            if auto_order:
                melhor_aic, melhor = float('inf'), (p, q)
                for p_try in range(4):
                    for q_try in range(4):
                        try:
                            aic = ARIMA(series, order=(p_try, d, q_try)).fit().aic
                        except Exception:
                            # nunca `except:` nu — capturaria KeyboardInterrupt
                            continue
                        if aic < melhor_aic:
                            melhor_aic, melhor = aic, (p_try, q_try)
                p, q = melhor
            fitted_model = ARIMA(series, order=(p, d, q)).fit()
        forecast = fitted_model.forecast(steps=passos)
    except Exception as e:
        # Fallback NUNCA silencioso (R12)
        mensagem = f"ARIMA({p},{d},{q}) falhou: {e}; usado ARIMA(1,1,1)"
        logger.warning("%s", mensagem)
        avisos.append(mensagem)
        p, d, q = 1, 1, 1
        with _sem_avisos_de_convergencia():
            fitted_model = ARIMA(series, order=(p, d, q)).fit()
        forecast = fitted_model.forecast(steps=passos)

    valores = np.asarray(forecast, dtype=float)[descarte:]
    return _resultado(datas, valores, avisos, ordem=(p, d, q))


def projetar_sarima(
    dados_historicos: pd.DataFrame,
    num_periodos: int,
    config: dict,
    ano_base: int = None,
) -> pd.DataFrame:
    """SARIMA(p, d, q)(P, D, Q, s).

    config: p, d, q (1, 1, 1); P, D, Q (1, 1, 1); s (12);
    enforce_stationarity e enforce_invertibility (default **False** — o
    código sempre usou False; a docstring antiga dizia True).

    ⚠️ Sazonalidade exige DOIS ciclos (R12): com menos de `2 × s` meses o
    SARIMA roda sem a parte sazonal e avisa — diferença sazonal sobre menos
    de dois ciclos deixa quase nada para estimar.
    """
    if not HAS_STATSMODELS:
        raise ValueError("Biblioteca statsmodels não está instalada. Execute: pip install statsmodels")

    n = len(dados_historicos)
    if n < 12:
        raise ValueError("SARIMA requer pelo menos 12 meses de dados históricos")

    p = int(config.get('p', 1))
    d = int(config.get('d', 1))
    q = int(config.get('q', 1))
    P = int(config.get('P', 1))
    D = int(config.get('D', 1))
    Q = int(config.get('Q', 1))
    s = int(config.get('s', 12))
    enforce_stationarity = config.get('enforce_stationarity', False)
    enforce_invertibility = config.get('enforce_invertibility', False)

    avisos = []
    if (P or D or Q) and n < 2 * s:
        avisos.append(
            f"SARIMA sem componente sazonal: a sazonalidade exige {2 * s} "
            f"meses de histórico (encontrados {n})")
        P = D = Q = 0
    ordem_sazonal = (P, D, Q, s) if (P or D or Q) else (0, 0, 0, 0)

    series = _serie_indexada(dados_historicos)
    passos, descarte, datas = _horizonte(dados_historicos, ano_base, num_periodos)

    try:
        model = SARIMAX(
            series,
            order=(p, d, q),
            seasonal_order=ordem_sazonal,
            enforce_stationarity=enforce_stationarity,
            enforce_invertibility=enforce_invertibility,
        )
        with _sem_avisos_de_convergencia():
            fitted_model = model.fit(disp=False, maxiter=200)
        forecast = np.asarray(fitted_model.forecast(steps=passos), dtype=float)
    except Exception as e:
        # Fallback NUNCA silencioso (R12) — dois níveis, ambos registrados
        mensagem = f"SARIMA falhou: {e}; usado ARIMA(1,1,1)"
        try:
            with _sem_avisos_de_convergencia():
                fitted_model = ARIMA(series, order=(1, 1, 1)).fit()
            forecast = np.asarray(fitted_model.forecast(steps=passos), dtype=float)
        except Exception as e2:
            mensagem = (f"SARIMA falhou: {e}; ARIMA(1,1,1) também falhou: "
                        f"{e2}; usada a média dos últimos 12 meses")
            forecast = np.full(passos, float(series.tail(12).mean()))
        logger.warning("%s", mensagem)
        avisos.append(mensagem)

    return _resultado(datas, forecast[descarte:], avisos)


def projetar_regressao_multipla(
    num_periodos: int,
    config: dict,
    ano_base: int = None,
) -> pd.DataFrame:
    """
    Projeta valores usando Regressão Linear Múltipla com parâmetros fornecidos pelo usuário.
    
    Fórmula: Receita = α + β₁(Variável₁) + β₂(Variável₂) + ... + βₙ(Variávelₙ)
    
    Args:
        num_periodos: Número de meses a projetar
        config: Dicionário com:
            - alpha: intercepto (α)
            - parametros: List[Dict] com:
                - nome: nome da variável
                - coeficiente: valor do β
                - valores_projetados: List[float] com valores para cada mês
        ano_base: Ano base para projeção (opcional)
    
    Returns:
        DataFrame com colunas: data, valor_projetado
    """
    try:
        alpha = float(config.get('alpha', 0) or 0)
    except (ValueError, TypeError):
        alpha = 0
    
    parametros = config.get('parametros', [])
    
    # Se não há parâmetros mas há alpha, retornar alpha para todos os meses
    if not parametros and alpha == 0:
        raise ValueError("Regressão Linear requer intercepto ou pelo menos uma variável independente")
    
    # Calcular projeções mês a mês
    projecoes = []
    
    for mes in range(num_periodos):
        # Receita = α + Σ(βᵢ × Variávelᵢ)
        valor = alpha
        
        for param in parametros:
            try:
                coef = float(param.get('coeficiente', 0) or 0)
            except (ValueError, TypeError):
                coef = 0
            
            valores = param.get('valores_projetados', [])
            
            if mes < len(valores):
                try:
                    val = float(valores[mes] or 0)
                except (ValueError, TypeError):
                    val = 0
                valor += coef * val
            else:
                # Se não há valor projetado, usar o último disponível
                if valores:
                    try:
                        val = float(valores[-1] or 0)
                    except (ValueError, TypeError):
                        val = 0
                    valor += coef * val
        
        # Garantir valor não-negativo
        projecoes.append(max(valor, 0))
    
    # Criar DataFrame de resultado
    if ano_base:
        datas_futuras = _datas_do_ano_base(ano_base, num_periodos)
    else:
        data_base = date.today().replace(day=1)
        datas_futuras = [data_base + relativedelta(months=i) for i in range(num_periodos)]
    
    resultado = pd.DataFrame({
        'data': datas_futuras,
        'valor_projetado': projecoes
    })
    
    return resultado


def _projetar_ml(chave: str, nome: str, fabricar, dados_historicos: pd.DataFrame,
                 num_periodos: int, ano_base: int | None,
                 diagnosticar=None) -> pd.DataFrame:
    """Treino + previsão recursiva comuns a XGBoost e LightGBM (R19).

    Atributos pela origem única `feature_engineering.atributos_do_mes`: o
    treino nunca vê o próprio alvo e a defasagem k do mês previsto é o valor
    (observado ou previsto) de k meses antes dele. `fabricar(n_treino)` recebe
    o número de linhas de treino (complexidade proporcional à amostra — R25);
    `diagnosticar(modelo)` devolve um aviso de degradação ou `None`.
    """
    from .feature_engineering import atributos_do_mes, get_feature_columns, montar_treino
    from .validacao import RegraNegocioError

    n = len(dados_historicos)
    minimo = MINIMO_DE_MESES[chave]
    if n < minimo:
        raise RegraNegocioError(
            f"{nome} requer pelo menos {minimo} meses de dados históricos "
            f"(12 defasagens + 2 meses de treino); encontrados {n}")

    X_train, y_train = montar_treino(dados_historicos)
    model = fabricar(len(y_train))
    model.fit(X_train, y_train)
    avisos = []
    aviso = diagnosticar(model) if diagnosticar else None
    if aviso:
        logger.warning("%s", aviso)
        avisos.append(aviso)

    serie = dados_historicos.sort_values('data')
    ultima = pd.Timestamp(pd.to_datetime(serie['data']).max())
    ultima = pd.Timestamp(ultima.year, ultima.month, 1)
    passos, descarte, datas = _horizonte(dados_historicos, ano_base, num_periodos)
    colunas = get_feature_columns()
    valores = [float(v) for v in serie['valor']]
    previstos: list[float] = []
    for k in range(passos):
        data_k = ultima + pd.DateOffset(months=k + 1)
        linha = atributos_do_mes(valores + previstos, data_k)
        X_pred = pd.DataFrame([linha])[colunas].replace([np.inf, -np.inf], 0).fillna(0)
        previstos.append(max(float(model.predict(X_pred)[0]), 0.0))

    return _resultado(datas, previstos[descarte:], avisos)


def projetar_xgboost(
    dados_historicos: pd.DataFrame,
    num_periodos: int,
    config: dict,
    ano_base: int = None,
) -> pd.DataFrame:
    """XGBoost com previsão recursiva mês a mês.

    config: n_estimators (100), max_depth (6), learning_rate (0.1).
    """
    if not HAS_XGBOOST:
        raise ValueError("Biblioteca xgboost não está instalada. Execute: pip install xgboost")

    def _fabricar(_n_treino):
        return XGBRegressor(
            n_estimators=int(config.get('n_estimators', 100)),
            max_depth=int(config.get('max_depth', 6)),
            learning_rate=float(config.get('learning_rate', 0.1)),
            random_state=42,
            verbosity=0,
        )

    return _projetar_ml('XGBOOST', 'XGBoost', _fabricar, dados_historicos,
                        num_periodos, ano_base)


def projetar_lightgbm(
    dados_historicos: pd.DataFrame,
    num_periodos: int,
    config: dict,
    ano_base: int = None,
) -> pd.DataFrame:
    """LightGBM com previsão recursiva mês a mês.

    config: n_estimators (100), max_depth (-1), learning_rate (0.1),
    num_leaves (31), min_child_samples (default proporcional à amostra).

    ⚠️ Mínimo por folha proporcional às linhas de treino (R25): com o default
    da biblioteca (20) e a janela de 3 anos (24 linhas), nenhuma divisão era
    possível — o modelo era uma árvore de UMA folha e previa a média do treino
    em todos os meses (medido: 217,50 constante numa série com tendência e
    sazonalidade). `max(3, n // 5)` levou o WMAPE da sonda de ~28% para ~12%;
    modelo que ainda assim não divide declara a degradação.
    """
    if not HAS_LIGHTGBM:
        raise ValueError("Biblioteca lightgbm não está instalada. Execute: pip install lightgbm")

    def _fabricar(n_treino):
        return LGBMRegressor(
            n_estimators=int(config.get('n_estimators', 100)),
            max_depth=int(config.get('max_depth', -1)),
            learning_rate=float(config.get('learning_rate', 0.1)),
            num_leaves=int(config.get('num_leaves', 31)),
            min_child_samples=int(config.get('min_child_samples',
                                             max(3, n_treino // 5))),
            random_state=42,
            verbosity=-1,
        )

    def _sem_divisoes(modelo):
        arvores = modelo.booster_.dump_model().get('tree_info', [])
        if all(arvore.get('num_leaves', 1) <= 1 for arvore in arvores):
            return ("LightGBM sem divisões (amostra pequena demais para o mínimo "
                    "por folha): a previsão é a média do treino")
        return None

    return _projetar_ml('LIGHTGBM', 'LightGBM', _fabricar, dados_historicos,
                        num_periodos, ano_base, diagnosticar=_sem_divisoes)


# ==================== Expense Forecast Models ====================

def projetar_loa(
    num_periodos: int,
    config: dict,
    ano_base: int | None = None,
) -> pd.DataFrame:
    """
    Projeta despesas usando valores da LOA (Lei Orçamentária Anual).
    
    Args:
        num_periodos: Número de meses a projetar
        config: Dicionário com:
            - valores_mensais: List[float] com valores para cada mês
            - distribuicao: 'uniforme' ou 'especifica'
            - valor_anual: float (se distribuição uniforme)
    
    Returns:
        DataFrame com colunas: data, valor_projetado
    """
    distribuicao = config.get('distribuicao', 'uniforme')
    
    if distribuicao == 'uniforme':
        # Distribuir valor anual uniformemente
        valor_anual = config.get('valor_anual', 0)
        valor_mensal = valor_anual / 12
        projecoes = [valor_mensal] * num_periodos
    else:
        # Usar valores específicos fornecidos
        valores_mensais = config.get('valores_mensais', [])
        projecoes = []
        
        for mes in range(num_periodos):
            if mes < len(valores_mensais):
                projecoes.append(valores_mensais[mes])
            else:
                # Repetir padrão se necessário
                projecoes.append(valores_mensais[mes % len(valores_mensais)] if valores_mensais else 0)
    
    # Datas do ANO-BASE do cenário. O fallback no relógio é só para chamada
    # avulsa sem cenário: dentro do simulador, `date.today()` deslocava a
    # projeção um mês a cada mês corrido.
    if ano_base:
        datas_futuras = _datas_do_ano_base(ano_base, num_periodos)
    else:
        data_base = date.today().replace(day=1)
        datas_futuras = [data_base + relativedelta(months=i) for i in range(num_periodos)]
    
    resultado = pd.DataFrame({
        'data': datas_futuras,
        'valor_projetado': projecoes
    })
    
    return resultado


def projetar_media_historica(
    dados_historicos: pd.DataFrame,
    num_periodos: int,
    config: dict,
    ano_base: int = None,
) -> pd.DataFrame:
    """Média histórica, com ou sem perfil por mês do ano.

    config: periodo_meses (sem valor = a janela de treino inteira),
    fator_ajuste (1.0), considerar_sazonalidade (True). Datas pelo horizonte
    ancorado (R18).
    """
    # Período-base INFORMADO recorta nível e sazonalidade (R24 — a tela sempre
    # envia, default 12). Sem ele (backtest, marcação sem parâmetro) vale a
    # janela de treino inteira: a média de vários anos que esses chamadores
    # sempre usaram — o default 12 só afetava o nível sem sazonalidade.
    try:
        periodo_meses = int(config.get('periodo_meses') or len(dados_historicos) or 12)
    except (ValueError, TypeError):
        periodo_meses = len(dados_historicos) or 12

    try:
        fator_ajuste = float(config.get('fator_ajuste', 1.0) or 1.0)
    except (ValueError, TypeError):
        fator_ajuste = 1.0

    considerar_sazonalidade = config.get('considerar_sazonalidade', True)

    if len(dados_historicos) == 0:
        raise ValueError("Não há dados históricos disponíveis")

    df = dados_historicos.sort_values('data').copy()
    df_recente = df.tail(periodo_meses).copy()
    _, _, datas = _horizonte(df, ano_base, num_periodos)

    # ⚠️ O período-base vale para a sazonalidade também (R24): a média por mês
    # do ano era calculada sobre a série INTEIRA e `periodo_meses` só afetava o
    # nível sem sazonalidade — 24 meses de 100 + 12 de 300 com período-base 12
    # projetavam 166,67. Janela menor que 12 meses não tem sazonalidade.
    if considerar_sazonalidade and len(df_recente) >= 12:
        # Média por mês do ano (sazonalidade) — série regular: mês sem
        # movimento entra como zero na média (R18)
        df_recente['mes'] = pd.to_datetime(df_recente['data']).dt.month
        media_por_mes = df_recente.groupby('mes')['valor'].mean().to_dict()
        media_recente = df_recente['valor'].mean()
        projecoes = [media_por_mes.get(d.month, media_recente) * fator_ajuste
                     for d in datas]
    else:
        projecoes = [df_recente['valor'].mean() * fator_ajuste] * num_periodos

    return _resultado(datas, projecoes, [])


# ==================== Aggregated Historical Data ====================

def obter_dados_historicos_agregados(
    seq_qualificadores: list[int],
    data_inicio: date,
    data_fim: date,
    agregacao: str = 'mensal',
    hoje: date | None = None,
) -> pd.DataFrame:
    """Série histórica SOMADA de vários qualificadores (com sinal), mês a mês
    e regular (R18), pela ORIGEM ÚNICA `serie_historica.serie_mensal` — raiz
    (R17) e correspondência entre exercícios (R31).

    `attrs` declara o que a série contém: `meses_estimados` (rateio de
    desdobramento), `pendencias` (desdobramento sem divisão cujos destinos não
    estão todos no conjunto) e `versao_de_para`. Só existe agregação mensal.
    """
    if agregacao != 'mensal':
        raise ValueError("A série de previsão é mensal")
    if not seq_qualificadores:
        return pd.DataFrame(columns=['data', 'valor'])
    serie = serie_mensal(list(seq_qualificadores), data_inicio, data_fim)
    mensal = pd.Series(
        {pd.Timestamp(ano, mes, 1): valor for (ano, mes), valor in serie.valores.items()},
        dtype=float)
    resultado = _regularizar(mensal, data_inicio, data_fim, hoje)
    resultado.attrs['meses_estimados'] = sorted(
        f"{ano}-{mes:02d}" for ano, mes in serie.estimados)
    resultado.attrs['pendencias'] = serie.pendencias
    resultado.attrs['versao_de_para'] = serie.versao
    return resultado


def obter_serie_do_ano_base(seq_qualificadores: list[int], ano_base: int,
                            janela_anos: int, hoje: date | None = None) -> pd.DataFrame:
    """ORIGEM ÚNICA da série de treino das três portas (rota avulsa, cenário
    por perna, método por qualificador): janela de 1º de janeiro (R18),
    série regular costurada pela raiz e em MAGNITUDE (R20).

    ⚠️ A magnitude é daqui, não das portas: os motores assumem série positiva
    (piso de não-negatividade em `_resultado`) e cada porta aplicava o próprio
    `abs()` — a rota avulsa não aplicava e projetava despesa ZERO. O valor do
    mês é o absoluto da SOMA com sinal (estorno reduz o mês).
    """
    inicio, fim = janela_do_ano_base(ano_base, janela_anos)
    serie = obter_dados_historicos_agregados(
        list(seq_qualificadores), inicio, fim, 'mensal', hoje)
    if len(serie):
        serie = serie.copy()
        serie['valor'] = serie['valor'].abs()
    return serie


def obter_dados_historicos_por_qualificador(
    seq_qualificadores: list[int],
    data_inicio: date,
    data_fim: date,
) -> dict[int, pd.DataFrame]:
    """
    Obtém dados históricos separados por qualificador.
    
    Args:
        seq_qualificadores: Lista de IDs de qualificadores
        data_inicio: Data inicial do período
        data_fim: Data final do período
    
    Returns:
        Dicionário com seq_qualificador como chave e DataFrame como valor
    """
    resultado = {}
    for seq_q in seq_qualificadores:
        resultado[seq_q] = obter_dados_historicos(seq_q, data_inicio, data_fim)
    return resultado


# ==================== Despacho por modelo (previsao R14) ====================

def calcular_projecao(tipo_modelo: str, seq_qualificadores: list[int],
                      num_periodos: int, ano_base: int, config: dict,
                      anos_selecionados: list[int] | None = None):
    """Despacho ÚNICO modelo → (janela, mínimo, motor) — antes eram 160
    linhas na rota, com o bloco "busca histórico + valida mínimo" repetido
    seis vezes (achado A2). Dados insuficientes e modelo desconhecido são
    erro de NEGÓCIO, nunca 500.
    """
    from .validacao import RegraNegocioError

    config = config or {}

    # modelo -> motor; janela em JANELA_EM_ANOS, mínimo em MINIMO_DE_MESES
    tabela = {
        'HOLT_WINTERS': projetar_holt_winters,
        'ARIMA': projetar_arima,
        'SARIMA': projetar_sarima,
        'MEDIA_HISTORICA': projetar_media_historica,
        'XGBOOST': projetar_xgboost,
        'LIGHTGBM': projetar_lightgbm,
    }

    if tipo_modelo in tabela:
        janela, motor = JANELA_EM_ANOS[tipo_modelo], tabela[tipo_modelo]
        minimo = MINIMO_DE_MESES[tipo_modelo]
        dados_hist = obter_serie_do_ano_base(seq_qualificadores, ano_base, janela)
        if len(dados_hist) < minimo:
            raise RegraNegocioError(
                f"Dados históricos insuficientes para {tipo_modelo}: "
                f"encontrados {len(dados_hist)} meses, mínimo {minimo}")
        resultado = motor(dados_hist, num_periodos, config, ano_base)
        # F10.2 (previsao R17): a projeção DECLARA com quanto treinou — série
        # curta indevida (raiz mal propagada) fica visível em vez de sumir no
        # resultado. Viaja em attrs, como 'degradacao' (R12).
        try:
            resultado.attrs['serie_info'] = {
                'pontos': int(len(dados_hist)),
                'anos': sorted({d.year for d in dados_hist['data']}),
            }
        except Exception:  # attrs é cosmético — nunca derruba a projeção
            pass
        return resultado

    if tipo_modelo == 'REGRESSAO':
        return projetar_regressao_multipla(num_periodos, config, ano_base)

    if tipo_modelo in ('CRESCIMENTO_ANO', 'MEDIA_CRESCIMENTO'):
        from .formula_engine import (
            projetar_crescimento_ultimo_ano,
            projetar_media_crescimento_anos,
        )

        mes_referencia = int(config.get('mes_referencia', 6))
        anos = anos_selecionados or []
        if tipo_modelo == 'CRESCIMENTO_ANO':
            return projetar_crescimento_ultimo_ano(
                seq_qualificadores=seq_qualificadores,
                ano_projecao=ano_base,
                ano_referencia=max(anos) if anos else ano_base - 1,
                mes_referencia=mes_referencia,
                num_periodos=num_periodos)
        if not anos:
            raise RegraNegocioError(
                "Selecione pelo menos um ano na Base Histórica")
        return projetar_media_crescimento_anos(
            seq_qualificadores=seq_qualificadores,
            ano_projecao=ano_base,
            anos_referencia=anos,
            mes_referencia=mes_referencia,
            num_periodos=num_periodos)

    raise RegraNegocioError(
        f"Modelo '{tipo_modelo}' não suportado para cálculo automático")
