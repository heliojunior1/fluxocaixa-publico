"""Service for economic forecasting models."""

import logging
import warnings
from contextlib import contextmanager
from datetime import date

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

from ..models import Lancamento

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



# ==================== Helper Functions ====================

def _datas_do_ano_base(ano_base: int, num_periodos: int) -> list[date]:
    """Datas mensais a partir de jan/ano_base, por aritmética de calendário.

    A forma antiga (mês = i+1 fixo no ano-base) estourava com 13+ períodos
    (`ValueError: month must be in 1..12`) — e quinzenal/semanal usam até 52.
    Com relativedelta os períodos atravessam para os anos seguintes.
    """
    inicio = date(ano_base, 1, 1)
    return [inicio + relativedelta(months=i) for i in range(num_periodos)]


def obter_dados_historicos(
    seq_qualificador: int,
    data_inicio: date,
    data_fim: date,
    agregacao: str = 'mensal'  # 'mensal' ou 'diario'
) -> pd.DataFrame:
    """
    Obtém dados históricos de lançamentos para um qualificador.
    
    Args:
        seq_qualificador: ID do qualificador
        data_inicio: Data inicial do período
        data_fim: Data final do período
        agregacao: 'mensal' ou 'diario'
    
    Returns:
        DataFrame com colunas: data, valor
    """
    # Buscar lançamentos no período. F10.2 (previsao R17): a série é da
    # RUBRICA (raiz), não do seq — costura entre exercícios.
    from .serie_historica import seqs_da_rubrica

    lancamentos = (
        Lancamento.query
        .filter(
            Lancamento.seq_qualificador.in_(seqs_da_rubrica(seq_qualificador)),
            Lancamento.dat_lancamento >= data_inicio,
            Lancamento.dat_lancamento <= data_fim,
            Lancamento.ind_status == 'A',
        )
        .all()
    )
    
    if not lancamentos:
        return pd.DataFrame(columns=['data', 'valor'])
    
    # Converter para DataFrame
    data = []
    for lanc in lancamentos:
        data.append({
            'data': lanc.dat_lancamento,
            'valor': float(lanc.valor_com_sinal)
        })
    
    df = pd.DataFrame(data)
    
    # Agregar se necessário
    if agregacao == 'mensal':
        df['ano_mes'] = df['data'].apply(lambda x: x.strftime('%Y-%m'))
        df_agregado = df.groupby('ano_mes')['valor'].sum().reset_index()
        df_agregado.columns = ['data', 'valor']
        df_agregado['data'] = pd.to_datetime(df_agregado['data'] + '-01')
        return df_agregado.sort_values('data')
    
    return df.sort_values('data')


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

def projetar_holt_winters(
    dados_historicos: pd.DataFrame,
    num_periodos: int,
    config: dict,
    ano_base: int = None,
) -> pd.DataFrame:
    """
    Projeta valores usando Holt-Winters (Suavização Exponencial).
    
    Args:
        dados_historicos: DataFrame com colunas 'data' e 'valor'
        num_periodos: Número de meses a projetar
        config: Dicionário com parâmetros:
            - seasonal_periods: Período sazonal (default: 12 para mensal)
            - trend: 'add' ou 'mul' (default: 'add')
            - seasonal: 'add' ou 'mul' (default: 'add')
            - damped_trend: bool (default: False) - Amortecer tendência
            - use_boxcox: bool (default: False) - Transformação Box-Cox
        ano_base: Ano base para projeção (opcional)
    
    Returns:
        DataFrame com colunas: data, valor_projetado
    """
    if not HAS_STATSMODELS:
        raise ValueError("Biblioteca statsmodels não está instalada. Execute: pip install statsmodels")
    
    if len(dados_historicos) < 24:  # Mínimo de 2 anos de dados
        # Tentar com menos dados se houver pelo menos 12 meses
        if len(dados_historicos) >= 12:
            logger.info("Usando Holt-Winters com menos de 24 meses de dados")
        else:
            raise ValueError("Holt-Winters requer pelo menos 12 meses de dados históricos")
    
    # Parâmetros
    seasonal_periods = int(config.get('seasonal_periods', 12))
    trend = config.get('trend', 'add')
    seasonal = config.get('seasonal', 'add')
    damped_trend = config.get('damped_trend', False)
    use_boxcox = config.get('use_boxcox', False)
    
    # Garantir que o período sazonal não seja maior que os dados
    if seasonal_periods >= len(dados_historicos):
        seasonal_periods = len(dados_historicos) // 2
    
    # Criar série temporal
    df_sorted = dados_historicos.sort_values('data')
    series = df_sorted.set_index('data')['valor']
    
    # Garantir valores positivos para multiplicativo ou Box-Cox.
    # O deslocamento é REVERTIDO depois do forecast (previsao R12): treinar
    # no espaço deslocado e devolver sem subtrair inflava toda projeção em
    # (1 - min) — inclusive no fallback, que retreina a série já deslocada.
    deslocamento = 0.0
    if seasonal == 'mul' or use_boxcox:
        min_val = series.min()
        if min_val <= 0:
            series = series - min_val + 1  # Ajustar para valores positivos
            deslocamento = float(min_val) - 1.0  # original = deslocada + (min−1)

    degradacao = None
    try:
        # Treinar modelo
        model = ExponentialSmoothing(
            series,
            seasonal_periods=seasonal_periods,
            trend=trend,
            seasonal=seasonal,
            damped_trend=damped_trend,
            use_boxcox=use_boxcox,
        )
        with _sem_avisos_de_convergencia():
            fitted_model = model.fit(optimized=True)

        # Fazer projeção
        forecast = fitted_model.forecast(steps=num_periodos)

    except Exception as e:
        # Fallback NUNCA silencioso (R12): a degradação viaja no resultado
        degradacao = (f"Holt-Winters (trend={trend}, seasonal={seasonal}) "
                      f"falhou: {e}; usado Holt-Winters aditivo simples")
        logger.warning("%s", degradacao)
        model = ExponentialSmoothing(
            series,
            seasonal_periods=seasonal_periods,
            trend='add',
            seasonal='add',
        )
        with _sem_avisos_de_convergencia():
            fitted_model = model.fit()
        forecast = fitted_model.forecast(steps=num_periodos)

    # Reverter o deslocamento ANTES do clamp de não-negatividade
    if deslocamento:
        forecast = forecast + deslocamento
    
    # Criar DataFrame de resultado
    if ano_base:
        # Usar ano base especificado
        datas_futuras = _datas_do_ano_base(ano_base, num_periodos)
    else:
        ultima_data = df_sorted['data'].max()
        datas_futuras = [ultima_data + relativedelta(months=i+1) for i in range(num_periodos)]
    
    # Garantir valores não-negativos
    valores = forecast.values
    valores = np.maximum(valores, 0)
    
    resultado = pd.DataFrame({
        'data': datas_futuras,
        'valor_projetado': valores
    })
    if degradacao:
        resultado.attrs['degradacao'] = degradacao
    return resultado


def projetar_arima(
    dados_historicos: pd.DataFrame,
    num_periodos: int,
    config: dict,
    ano_base: int = None,
) -> pd.DataFrame:
    """
    Projeta valores usando ARIMA (AutoRegressive Integrated Moving Average).
    
    Args:
        dados_historicos: DataFrame com colunas 'data' e 'valor'
        num_periodos: Número de meses a projetar
        config: Dicionário com parâmetros:
            - p: ordem autoregressiva (default: 1)
            - d: ordem de diferenciação (default: 1)
            - q: ordem de média móvel (default: 1)
            - auto_order: bool (default: False) - Seleção automática de ordem
        ano_base: Ano base para projeção (opcional)
    
    Returns:
        DataFrame com colunas: data, valor_projetado
    """
    if not HAS_STATSMODELS:
        raise ValueError("Biblioteca statsmodels não está instalada. Execute: pip install statsmodels")
    
    if len(dados_historicos) < 12:
        raise ValueError("ARIMA requer pelo menos 12 meses de dados históricos")
    
    # Parâmetros
    p = int(config.get('p', 1))
    d = int(config.get('d', 1))
    q = int(config.get('q', 1))
    auto_order = config.get('auto_order', False)
    
    # Criar série temporal
    df_sorted = dados_historicos.sort_values('data')
    series = df_sorted.set_index('data')['valor']

    degradacao = None
    try:
        if auto_order:
            # Tentar encontrar melhor ordem automaticamente
            best_aic = float('inf')
            best_order = (p, d, q)
            
            for p_try in range(4):
                for d_try in range(3):
                    for q_try in range(4):
                        try:
                            model = ARIMA(series, order=(p_try, d_try, q_try))
                            fitted = model.fit()
                            if fitted.aic < best_aic:
                                best_aic = fitted.aic
                                best_order = (p_try, d_try, q_try)
                        except Exception:
                            # nunca `except:` nu — capturaria KeyboardInterrupt
                            # bem onde o usuário interromperia por lentidão
                            continue
            
            p, d, q = best_order
        
        # Treinar modelo
        model = ARIMA(series, order=(p, d, q))
        with _sem_avisos_de_convergencia():
            fitted_model = model.fit()

        # Fazer projeção
        forecast = fitted_model.forecast(steps=num_periodos)

    except Exception as e:
        # Fallback NUNCA silencioso (R12)
        degradacao = (f"ARIMA({p},{d},{q}) falhou: {e}; usado ARIMA(1,1,1)")
        logger.warning("%s", degradacao)
        model = ARIMA(series, order=(1, 1, 1))
        with _sem_avisos_de_convergencia():
            fitted_model = model.fit()
        forecast = fitted_model.forecast(steps=num_periodos)
    
    # Criar DataFrame de resultado
    if ano_base:
        datas_futuras = _datas_do_ano_base(ano_base, num_periodos)
    else:
        ultima_data = df_sorted['data'].max()
        datas_futuras = [ultima_data + relativedelta(months=i+1) for i in range(num_periodos)]
    
    # Garantir valores não-negativos
    valores = forecast.values
    valores = np.maximum(valores, 0)
    
    resultado = pd.DataFrame({
        'data': datas_futuras,
        'valor_projetado': valores
    })
    if degradacao:
        resultado.attrs['degradacao'] = degradacao
    return resultado


def projetar_sarima(
    dados_historicos: pd.DataFrame,
    num_periodos: int,
    config: dict,
    ano_base: int = None,
) -> pd.DataFrame:
    """
    Projeta valores usando SARIMA (Seasonal ARIMA).
    
    Args:
        dados_historicos: DataFrame com colunas 'data' e 'valor'
        num_periodos: Número de meses a projetar
        config: Dicionário com parâmetros:
            - p, d, q: ordens não-sazonais
            - P, D, Q, s: ordens sazonais (s = período sazonal, default 12)
            - enforce_stationarity: bool (default: True)
            - enforce_invertibility: bool (default: True)
        ano_base: Ano base para projeção (opcional)
    
    Returns:
        DataFrame com colunas: data, valor_projetado
    """
    if not HAS_STATSMODELS:
        raise ValueError("Biblioteca statsmodels não está instalada. Execute: pip install statsmodels")
    
    if len(dados_historicos) < 24:
        # Tentar com menos dados se houver pelo menos 12 meses
        if len(dados_historicos) >= 12:
            logger.info("Usando SARIMA com menos de 24 meses de dados")
        else:
            raise ValueError("SARIMA requer pelo menos 12 meses de dados históricos")
    
    # Parâmetros não-sazonais
    p = int(config.get('p', 1))
    d = int(config.get('d', 1))
    q = int(config.get('q', 1))
    
    # Parâmetros sazonais
    P = int(config.get('P', 1))
    D = int(config.get('D', 1))
    Q = int(config.get('Q', 1))
    s = int(config.get('s', 12))
    
    enforce_stationarity = config.get('enforce_stationarity', False)
    enforce_invertibility = config.get('enforce_invertibility', False)
    
    # Criar série temporal
    df_sorted = dados_historicos.sort_values('data')
    series = df_sorted.set_index('data')['valor']
    
    degradacao = None
    try:
        # Treinar modelo SARIMA
        model = SARIMAX(
            series,
            order=(p, d, q),
            seasonal_order=(P, D, Q, s),
            enforce_stationarity=enforce_stationarity,
            enforce_invertibility=enforce_invertibility,
        )
        with _sem_avisos_de_convergencia():
            fitted_model = model.fit(disp=False, maxiter=200)

        # Fazer projeção
        forecast = fitted_model.forecast(steps=num_periodos)

    except Exception as e:
        # Fallback NUNCA silencioso (R12) — dois níveis, ambos registrados
        degradacao = f"SARIMA falhou: {e}; usado ARIMA(1,1,1)"
        logger.warning("%s", degradacao)
        try:
            model = ARIMA(series, order=(1, 1, 1))
            with _sem_avisos_de_convergencia():
                fitted_model = model.fit()
            forecast = fitted_model.forecast(steps=num_periodos)
        except Exception as e2:
            degradacao = (f"SARIMA falhou: {e}; ARIMA(1,1,1) também falhou: "
                          f"{e2}; usada a média dos últimos 12 meses")
            logger.warning("%s", degradacao)
            # Fallback final: média dos últimos 12 meses
            media = series.tail(12).mean()
            forecast = pd.Series([media] * num_periodos)
    
    # Criar DataFrame de resultado
    if ano_base:
        datas_futuras = _datas_do_ano_base(ano_base, num_periodos)
    else:
        ultima_data = df_sorted['data'].max()
        datas_futuras = [ultima_data + relativedelta(months=i+1) for i in range(num_periodos)]
    
    # Garantir valores não-negativos
    valores = forecast.values if hasattr(forecast, 'values') else list(forecast)
    valores = np.maximum(valores, 0)
    
    resultado = pd.DataFrame({
        'data': datas_futuras,
        'valor_projetado': valores
    })
    if degradacao:
        resultado.attrs['degradacao'] = degradacao
    return resultado


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


def projetar_xgboost(
    dados_historicos: pd.DataFrame,
    num_periodos: int,
    config: dict,
    ano_base: int = None,
) -> pd.DataFrame:
    """
    Projeta valores usando XGBoost (Gradient Boosting).
    
    Uses feature engineering with lag values, cyclical month encoding,
    rolling statistics, and trend. Prediction is done recursively:
    each predicted month becomes a lag input for the next.
    
    Args:
        dados_historicos: DataFrame with columns 'data' and 'valor'
        num_periodos: Number of months to project
        config: Dict with parameters:
            - n_estimators: number of trees (default: 100)
            - max_depth: max tree depth (default: 6)
            - learning_rate: learning rate (default: 0.1)
        ano_base: Base year for projection (optional)
    
    Returns:
        DataFrame with columns: data, valor_projetado
    """
    if not HAS_XGBOOST:
        raise ValueError("Biblioteca xgboost não está instalada. Execute: pip install xgboost")
    
    if len(dados_historicos) < 24:
        if len(dados_historicos) >= 13:
            logger.info("Usando XGBoost com menos de 24 meses de dados")
        else:
            raise ValueError("XGBoost requer pelo menos 13 meses de dados históricos (12 para lags + 1 para treino)")
    
    from .feature_engineering import (
        atualizar_lags_recursivo,
        criar_features_futuras,
        criar_features_serie_temporal,
        get_feature_columns,
        preparar_dados_treino,
    )
    
    # Parameters
    n_estimators = int(config.get('n_estimators', 100))
    max_depth = int(config.get('max_depth', 6))
    learning_rate = float(config.get('learning_rate', 0.1))
    
    # Generate features from historical data
    df_features = criar_features_serie_temporal(dados_historicos)
    
    # Prepare training data
    X_train, y_train = preparar_dados_treino(df_features)
    
    if len(X_train) < 2:
        raise ValueError("Dados insuficientes para treinar XGBoost após remoção de NaN nos lags")
    
    # Train model
    model = XGBRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        random_state=42,
        verbosity=0,
    )
    model.fit(X_train, y_train)
    
    # Generate future features
    df_futuro = criar_features_futuras(df_features, num_periodos, ano_base)
    feature_cols = get_feature_columns()
    
    # Recursive prediction
    valores_previstos = []
    valores_historicos = df_features['valor'].values
    
    for i in range(num_periodos):
        row = df_futuro.iloc[i].to_dict()
        
        # Update lags with previously predicted values
        row = atualizar_lags_recursivo(row, valores_previstos, valores_historicos, i)
        
        # Predict
        X_pred = pd.DataFrame([row])[feature_cols]
        X_pred = X_pred.replace([np.inf, -np.inf], 0).fillna(0)
        pred = float(model.predict(X_pred)[0])
        pred = max(pred, 0)  # Ensure non-negative
        
        valores_previstos.append(pred)
    
    # Build result DataFrame
    resultado = pd.DataFrame({
        'data': df_futuro['data'].values[:num_periodos],
        'valor_projetado': valores_previstos
    })
    
    return resultado


def projetar_lightgbm(
    dados_historicos: pd.DataFrame,
    num_periodos: int,
    config: dict,
    ano_base: int = None,
) -> pd.DataFrame:
    """
    Projeta valores usando LightGBM (Microsoft Gradient Boosting).
    
    Uses the same feature engineering approach as XGBoost with recursive prediction.
    LightGBM is generally faster and more memory-efficient than XGBoost.
    
    Args:
        dados_historicos: DataFrame with columns 'data' and 'valor'
        num_periodos: Number of months to project
        config: Dict with parameters:
            - n_estimators: number of trees (default: 100)
            - max_depth: max tree depth (default: -1 = no limit)
            - learning_rate: learning rate (default: 0.1)
            - num_leaves: max number of leaves per tree (default: 31)
        ano_base: Base year for projection (optional)
    
    Returns:
        DataFrame with columns: data, valor_projetado
    """
    if not HAS_LIGHTGBM:
        raise ValueError("Biblioteca lightgbm não está instalada. Execute: pip install lightgbm")
    
    if len(dados_historicos) < 24:
        if len(dados_historicos) >= 13:
            logger.info("Usando LightGBM com menos de 24 meses de dados")
        else:
            raise ValueError("LightGBM requer pelo menos 13 meses de dados históricos (12 para lags + 1 para treino)")
    
    from .feature_engineering import (
        atualizar_lags_recursivo,
        criar_features_futuras,
        criar_features_serie_temporal,
        get_feature_columns,
        preparar_dados_treino,
    )
    
    # Parameters
    n_estimators = int(config.get('n_estimators', 100))
    max_depth = int(config.get('max_depth', -1))
    learning_rate = float(config.get('learning_rate', 0.1))
    num_leaves = int(config.get('num_leaves', 31))
    
    # Generate features from historical data
    df_features = criar_features_serie_temporal(dados_historicos)
    
    # Prepare training data
    X_train, y_train = preparar_dados_treino(df_features)
    
    if len(X_train) < 2:
        raise ValueError("Dados insuficientes para treinar LightGBM após remoção de NaN nos lags")
    
    # Train model
    model = LGBMRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        num_leaves=num_leaves,
        random_state=42,
        verbosity=-1,
    )
    model.fit(X_train, y_train)
    
    # Generate future features
    df_futuro = criar_features_futuras(df_features, num_periodos, ano_base)
    feature_cols = get_feature_columns()
    
    # Recursive prediction
    valores_previstos = []
    valores_historicos = df_features['valor'].values
    
    for i in range(num_periodos):
        row = df_futuro.iloc[i].to_dict()
        
        # Update lags with previously predicted values
        row = atualizar_lags_recursivo(row, valores_previstos, valores_historicos, i)
        
        # Predict
        X_pred = pd.DataFrame([row])[feature_cols]
        X_pred = X_pred.replace([np.inf, -np.inf], 0).fillna(0)
        pred = float(model.predict(X_pred)[0])
        pred = max(pred, 0)  # Ensure non-negative
        
        valores_previstos.append(pred)
    
    # Build result DataFrame
    resultado = pd.DataFrame({
        'data': df_futuro['data'].values[:num_periodos],
        'valor_projetado': valores_previstos
    })
    
    return resultado


# ==================== Expense Forecast Models ====================

def projetar_loa(
    num_periodos: int,
    config: dict,
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
    
    # Criar DataFrame de resultado
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
    """
    Projeta despesas usando média histórica ajustada.
    
    Args:
        dados_historicos: DataFrame com colunas 'data' e 'valor'
        num_periodos: Número de meses a projetar
        config: Dicionário com:
            - periodo_meses: quantos meses usar para média (default: 12)
            - fator_ajuste: multiplicador para ajuste (default: 1.0)
            - considerar_sazonalidade: bool (default: True)
        ano_base: Ano base para projeção (opcional)
    
    Returns:
        DataFrame com colunas: data, valor_projetado
    """
    try:
        periodo_meses = int(config.get('periodo_meses', 12) or 12)
    except (ValueError, TypeError):
        periodo_meses = 12
    
    try:
        fator_ajuste = float(config.get('fator_ajuste', 1.0) or 1.0)
    except (ValueError, TypeError):
        fator_ajuste = 1.0
    
    considerar_sazonalidade = config.get('considerar_sazonalidade', True)
    
    if len(dados_historicos) == 0:
        raise ValueError("Não há dados históricos disponíveis")
    
    # Fazer cópia para não modificar original
    df = dados_historicos.copy()
    
    # Usar últimos N meses
    df_recente = df.tail(periodo_meses)
    
    if considerar_sazonalidade and len(df) >= 12:
        # Calcular média por mês do ano (sazonalidade)
        df['mes'] = pd.to_datetime(df['data']).dt.month
        media_por_mes = df.groupby('mes')['valor'].mean().to_dict()
        
        # Projetar com padrão sazonal
        data_base = df['data'].max()
        projecoes = []
        
        for i in range(num_periodos):
            if ano_base:
                mes = (i % 12) + 1
            else:
                data_futura = data_base + relativedelta(months=i+1)
                mes = data_futura.month
            valor = media_por_mes.get(mes, df_recente['valor'].mean()) * fator_ajuste
            projecoes.append(max(valor, 0))
    else:
        # Média simples
        media = df_recente['valor'].mean() * fator_ajuste
        projecoes = [max(media, 0)] * num_periodos
    
    # Criar DataFrame de resultado
    if ano_base:
        datas_futuras = _datas_do_ano_base(ano_base, num_periodos)
    else:
        ultima_data = df['data'].max()
        datas_futuras = [ultima_data + relativedelta(months=i+1) for i in range(num_periodos)]
    
    resultado = pd.DataFrame({
        'data': datas_futuras,
        'valor_projetado': projecoes
    })
    
    return resultado


# ==================== Aggregated Historical Data ====================

def obter_dados_historicos_agregados(
    seq_qualificadores: list[int],
    data_inicio: date,
    data_fim: date,
    agregacao: str = 'mensal'
) -> pd.DataFrame:
    """
    Obtém dados históricos agregados de múltiplos qualificadores.
    
    Args:
        seq_qualificadores: Lista de IDs de qualificadores
        data_inicio: Data inicial do período
        data_fim: Data final do período
        agregacao: 'mensal' ou 'diario'
    
    Returns:
        DataFrame com colunas: data, valor (agregado de todos os qualificadores)
    """
    if not seq_qualificadores:
        return pd.DataFrame(columns=['data', 'valor'])
    
    # Buscar lançamentos de todos os qualificadores. F10.2 (R17): cada seq é
    # expandido para a sua rubrica (raiz) — costura entre exercícios.
    from .serie_historica import seqs_das_rubricas

    lancamentos = (
        Lancamento.query
        .filter(
            Lancamento.seq_qualificador.in_(seqs_das_rubricas(seq_qualificadores)),
            Lancamento.dat_lancamento >= data_inicio,
            Lancamento.dat_lancamento <= data_fim,
            Lancamento.ind_status == 'A',
        )
        .all()
    )
    
    if not lancamentos:
        return pd.DataFrame(columns=['data', 'valor'])
    
    # Converter para DataFrame
    data = []
    for lanc in lancamentos:
        data.append({
            'data': lanc.dat_lancamento,
            'valor': float(lanc.valor_com_sinal),
            'seq_qualificador': lanc.seq_qualificador
        })
    
    df = pd.DataFrame(data)
    
    # Agregar por data (soma de todos os qualificadores)
    if agregacao == 'mensal':
        df['ano_mes'] = df['data'].apply(lambda x: x.strftime('%Y-%m'))
        df_agregado = df.groupby('ano_mes')['valor'].sum().reset_index()
        df_agregado.columns = ['data', 'valor']
        df_agregado['data'] = pd.to_datetime(df_agregado['data'] + '-01')
        return df_agregado.sort_values('data')
    
    # Diário
    df_agregado = df.groupby('data')['valor'].sum().reset_index()
    return df_agregado.sort_values('data')


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
    data_fim = date(ano_base - 1, 12, 31)

    def _historico(janela_anos: int):
        data_inicio = data_fim - relativedelta(years=janela_anos)
        if len(seq_qualificadores) > 1:
            return obter_dados_historicos_agregados(
                seq_qualificadores, data_inicio, data_fim)
        return obter_dados_historicos(
            seq_qualificadores[0], data_inicio, data_fim)

    # modelo -> (janela em anos, mínimo de observações, motor)
    tabela = {
        'HOLT_WINTERS': (3, 12, projetar_holt_winters),
        'ARIMA': (3, 12, projetar_arima),
        'SARIMA': (4, 12, projetar_sarima),
        'MEDIA_HISTORICA': (3, 1, projetar_media_historica),
        'XGBOOST': (3, 13, projetar_xgboost),
        'LIGHTGBM': (3, 13, projetar_lightgbm),
    }

    if tipo_modelo in tabela:
        janela, minimo, motor = tabela[tipo_modelo]
        dados_hist = _historico(janela)
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
