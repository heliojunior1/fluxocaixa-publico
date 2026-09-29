"""Serviço de Backtest para comparação de modelos de projeção.

Este módulo executa backtestes walk-forward: treina modelos com dados históricos
selecionados pelo usuário e compara as projeções com os valores reais.
Calcula métricas de acurácia (MAPE, WMAPE, Viés) e gera rankings.
"""

import json
import logging
from datetime import date

import numpy as np
from sqlalchemy import text

from ..models import Qualificador, db

logger = logging.getLogger(__name__)

# Modelos que PREVEEM O ANO INTEIRO e disputam o melhor modelo. O mínimo de
# meses vem da origem única `modelos_economicos_service.MINIMO_DE_MESES`.
MODELOS_DISPONIVEIS = {
    'HOLT_WINTERS': {'nome': 'Holt-Winters'},
    'ARIMA': {'nome': 'ARIMA'},
    'SARIMA': {'nome': 'SARIMA'},
    'XGBOOST': {'nome': 'XGBoost'},
    'LIGHTGBM': {'nome': 'LightGBM'},
    'MEDIA_HISTORICA': {'nome': 'Média Histórica'},
}

# Métodos de REPROJEÇÃO INTRA-ANO (previsao R16): usam o realizado do próprio
# ano até o mês de referência. Avaliados só nos meses posteriores e exibidos à
# parte — nunca disputam o melhor modelo. Antes o crescimento rodava com mês de
# referência 12, recebia o realizado do ano de teste inteiro e "acertava" com
# MAPE ≈ 0, vencendo toda receita.
METODOS_INTRA_ANO = {
    'CRESCIMENTO_ANO': {'nome': 'Crescimento Último Ano'},
}

MES_REFERENCIA_PADRAO = 6


def _obter_dados_treino(seq_qualificador: int, ano_inicio: int, ano_fim: int):
    """Série de treino em MAGNITUDE (R6/R16), contígua de `ano_inicio` a
    `ano_fim`: a mesma série regular e costurada pela raiz (R17/R18) que a
    produção usa. Antes vinha com sinal — a despesa chegava negativa aos
    motores, que devolvem magnitude, e todo modelo errava ~100%."""
    from . import modelos_economicos_service as modelos

    serie = modelos.obter_dados_historicos(
        seq_qualificador, date(ano_inicio, 1, 1), date(ano_fim, 12, 31))
    if len(serie):
        serie = serie.copy()
        serie['valor'] = serie['valor'].abs()
    return serie


def _obter_real(seq_qualificador: int, ano: int) -> dict[int, float]:
    """Realizado do ano de teste em MAGNITUDE, os 12 meses (mês sem movimento
    = 0.0). Vazio quando o ano não tem movimento nenhum."""
    from . import modelos_economicos_service as modelos

    serie = modelos.obter_dados_historicos(
        seq_qualificador, date(ano, 1, 1), date(ano, 12, 31))
    if not len(serie):
        return {}
    por_mes = {d.month: abs(float(v)) for d, v in zip(serie['data'], serie['valor'])}
    return {mes: por_mes.get(mes, 0.0) for mes in range(1, 13)}


def _executar_modelo(modelo: str, dados_treino, ano_teste: int) -> dict[int, float] | None:
    """Projeção mensal do ano de teste por um modelo do ano inteiro, ou None
    quando o modelo não se aplica (série curta, lib ausente, falha)."""
    from . import modelos_economicos_service as modelos

    motor = {
        'HOLT_WINTERS': modelos.projetar_holt_winters,
        'ARIMA': modelos.projetar_arima,
        'SARIMA': modelos.projetar_sarima,
        'XGBOOST': modelos.projetar_xgboost,
        'LIGHTGBM': modelos.projetar_lightgbm,
        'MEDIA_HISTORICA': modelos.projetar_media_historica,
    }[modelo]
    if len(dados_treino) < modelos.MINIMO_DE_MESES[modelo]:
        return None
    try:
        resultado = motor(dados_treino, 12, {}, ano_teste)
    except Exception as e:  # modelo inaplicável não derruba o backtest
        logger.warning("Backtest: %s falhou: %s", modelo, e)
        return None
    return {
        (row['data'] if isinstance(row['data'], date) else row['data'].date()).month:
            float(row['valor_projetado'])
        for _, row in resultado.iterrows()
    }


def _executar_intra_ano(seq_qualificador: int, ano_teste: int,
                        mes_referencia: int) -> dict[int, float] | None:
    """Crescimento como reprojeção intra-ano: realizado até `mes_referencia`
    do ano de teste, projeção dos meses seguintes. Devolve SÓ os meses
    projetados — os meses até a referência são o próprio realizado e não
    medem nada."""
    from .formula_engine import projetar_crescimento_ultimo_ano

    try:
        resultado = projetar_crescimento_ultimo_ano(
            seq_qualificadores=[seq_qualificador], ano_projecao=ano_teste,
            ano_referencia=ano_teste - 1, mes_referencia=mes_referencia,
            num_periodos=12)
    except Exception as e:
        logger.warning("Backtest: crescimento falhou: %s", e)
        return None
    return {
        row['data'].month: float(row['valor_projetado'])
        for _, row in resultado.iterrows() if row['data'].month > mes_referencia
    }


def _calcular_metricas(
    projecao: dict[int, float],
    real: dict[int, float],
) -> dict[str, float]:
    """Calcula métricas de acurácia entre projeção e valores reais.

    Returns:
        Dict com 'mape', 'wmape', 'bias', 'mae'
    """
    meses_comuns = sorted(set(projecao.keys()) & set(real.keys()))

    if not meses_comuns:
        return {'mape': None, 'wmape': None, 'bias': None, 'mae': None}

    proj_vals = np.array([projecao[m] for m in meses_comuns])
    real_vals = np.array([real[m] for m in meses_comuns])

    # Filtrar zeros nos reais (evitar divisão por zero no MAPE)
    mask = real_vals != 0
    if not mask.any():
        return {'mape': None, 'wmape': None, 'bias': None, 'mae': None}

    proj_nz = proj_vals[mask]
    real_nz = real_vals[mask]

    # MAPE: Mean Absolute Percentage Error
    ape = np.abs(proj_nz - real_nz) / np.abs(real_nz) * 100
    mape = float(np.mean(ape))

    # WMAPE: Weighted MAPE (pondera por volume)
    wmape = float(np.sum(np.abs(proj_vals - real_vals)) / np.sum(np.abs(real_vals)) * 100)

    # Viés: positivo = superestima
    bias = float(np.mean(proj_vals - real_vals) / np.mean(np.abs(real_vals)) * 100)

    # MAE: Mean Absolute Error (em R$)
    mae = float(np.mean(np.abs(proj_vals - real_vals)))

    return {
        'meses_avaliados': [int(m) for m in meses_comuns],
        'mape': round(mape, 2),
        'wmape': round(wmape, 2),
        'bias': round(bias, 2),
        'mae': round(mae, 2),
    }


def _determinar_semaforo(mape: float | None) -> str:
    """Determina o semáforo de acurácia.

    Returns:
        'verde' (≤5%), 'amarelo' (5-15%), 'vermelho' (>15%), 'cinza' (sem dados)
    """
    if mape is None:
        return 'cinza'
    if mape <= 5:
        return 'verde'
    if mape <= 15:
        return 'amarelo'
    return 'vermelho'


def _obter_hierarquia_qualificadores() -> dict:
    """Ancestral → FOLHAS descendentes, em qualquer profundidade (R16).

    A forma antiga agrupava pelo pai IMEDIATO: numa árvore de 3+ níveis o
    pai de nível 1 mediava só os filhos de nível 2 (sem lançamentos) e nunca
    alcançava as folhas — o agregado ficava vazio. E o backtest treinava
    modelos em nós intermediários, sem dados, para produzir métricas nulas.
    Folha via `is_folha()` — origem única (F6.4).

    Returns:
        {
          seq_ancestral: {
            'qualificador': Qualificador,
            'filhos': [Qualificador folha, ...],  # folhas descendentes
          }
        }
    """
    todos = Qualificador.query.filter_by(ind_status='A').all()
    por_seq = {q.seq_qualificador: q for q in todos}
    folhas = [q for q in todos if q.is_folha()]

    hierarquia: dict = {}
    for folha in folhas:
        vistos = {folha.seq_qualificador}
        pai_seq = folha.cod_qualificador_pai
        while pai_seq is not None and pai_seq not in vistos:
            vistos.add(pai_seq)
            ancestral = por_seq.get(pai_seq)
            if ancestral is None:
                break
            balde = hierarquia.setdefault(pai_seq, {
                'qualificador': ancestral,
                'filhos': [],
            })
            balde['filhos'].append(folha)
            pai_seq = ancestral.cod_qualificador_pai

    return hierarquia


def _uma_por_raiz(folhas: list) -> list:
    """Uma folha por identidade estável de rubrica (R16/R17): a mesma rubrica
    em vários exercícios tem a mesma série — treiná-la duas vezes duplicava a
    linha do resultado e o peso dela no ranking. Fica a do exercício mais
    recente, a que o usuário vê."""
    por_raiz: dict = {}
    for folha in folhas:
        chave = folha.cod_rubrica_raiz or folha.seq_qualificador
        atual = por_raiz.get(chave)
        if atual is None or folha.num_ano_exercicio > atual.num_ano_exercicio:
            por_raiz[chave] = folha
    return [f for f in folhas if por_raiz.get(f.cod_rubrica_raiz or f.seq_qualificador) is f]


def _medias(metricas_por_ano: list[dict]) -> dict:
    def _media(chave):
        valores = [m[chave] for m in metricas_por_ano if m[chave] is not None]
        return round(np.mean(valores), 2) if valores else None

    return {chave: _media(chave) for chave in ('mape', 'wmape', 'bias', 'mae')}


def executar_backtest(
    anos_treino: list[int],
    anos_teste: list[int],
    modelos: list[str],
    qualificadores_ids: list[int] | None = None,
    mes_referencia: int = MES_REFERENCIA_PADRAO,
) -> dict:
    """Backtest por folha (previsao R16).

    Origem móvel: cada ano de teste T é previsto com a série CONTÍGUA de
    `min(anos_treino)` até T−1 — antes a mesma projeção (treinada até o último
    ano de treino) era comparada com todos os anos de teste. Série e realizado
    em magnitude; uma folha por raiz; métodos intra-ano (crescimento) avaliados
    à parte, fora do melhor modelo e do ranking.
    """
    max_treino = max(anos_treino)
    min_teste = min(anos_teste)
    if max_treino >= min_teste:
        raise ValueError(
            f'Ano de treino ({max_treino}) deve ser anterior ao ano de teste ({min_teste})'
        )
    if not 1 <= int(mes_referencia) <= 11:
        raise ValueError('O mês de referência da reprojeção intra-ano deve estar entre 1 e 11')

    hierarquia = _obter_hierarquia_qualificadores()

    filhos_validos = []
    vistos = set()
    for pai_data in hierarquia.values():
        for filho in pai_data['filhos']:
            # a MESMA folha aparece sob todos os seus ancestrais (R16) —
            # o backtest roda uma vez por folha
            if filho.seq_qualificador in vistos:
                continue
            if qualificadores_ids is None or filho.seq_qualificador in qualificadores_ids:
                filhos_validos.append(filho)
                vistos.add(filho.seq_qualificador)
    filhos_validos = _uma_por_raiz(filhos_validos)

    if not filhos_validos:
        raise ValueError('Nenhum qualificador-filho selecionado')

    modelos_validos = [m for m in modelos if m in MODELOS_DISPONIVEIS]
    metodos_intra = [m for m in modelos if m in METODOS_INTRA_ANO]
    if not modelos_validos and not metodos_intra:
        raise ValueError('Nenhum modelo válido selecionado')

    logger.info("Backtest: %d qualificadores × %d modelos × %d anos de teste",
                len(filhos_validos), len(modelos_validos) + len(metodos_intra),
                len(anos_teste))

    inicio_treino = min(anos_treino)
    resultados_filho = []
    for filho in filhos_validos:
        seq_q = filho.seq_qualificador
        resultado_qualificador = {
            'seq_qualificador': seq_q,
            'num_qualificador': filho.num_qualificador,
            'dsc_qualificador': filho.dsc_qualificador,
            'pai_seq': filho.cod_qualificador_pai,
            'modelos': {},
            'intra_ano': {},
        }
        reais = {ano: _obter_real(seq_q, ano) for ano in anos_teste}
        treinos = {ano: _obter_dados_treino(seq_q, inicio_treino, ano - 1)
                   for ano in anos_teste}

        for modelo in modelos_validos:
            metricas_por_ano = []
            for ano_teste in anos_teste:
                if not reais[ano_teste]:
                    continue
                projecao = _executar_modelo(modelo, treinos[ano_teste], ano_teste)
                if projecao is None:
                    continue
                metricas = _calcular_metricas(projecao, reais[ano_teste])
                metricas['ano_teste'] = ano_teste
                metricas['projecao'] = {str(k): v for k, v in projecao.items()}
                metricas['real'] = {str(k): v for k, v in reais[ano_teste].items()}
                metricas_por_ano.append(metricas)
            if metricas_por_ano:
                resultado_qualificador['modelos'][modelo] = {
                    'nome': MODELOS_DISPONIVEIS[modelo]['nome'],
                    **_medias(metricas_por_ano),
                    'detalhes_por_ano': metricas_por_ano,
                }

        for metodo in metodos_intra:
            metricas_por_ano = []
            for ano_teste in anos_teste:
                if not reais[ano_teste]:
                    continue
                projecao = _executar_intra_ano(seq_q, ano_teste, int(mes_referencia))
                if not projecao:
                    continue
                real = {m: v for m, v in reais[ano_teste].items() if m in projecao}
                metricas = _calcular_metricas(projecao, real)
                metricas['ano_teste'] = ano_teste
                metricas['projecao'] = {str(k): v for k, v in projecao.items()}
                metricas['real'] = {str(k): v for k, v in real.items()}
                metricas_por_ano.append(metricas)
            if metricas_por_ano:
                resultado_qualificador['intra_ano'][metodo] = {
                    'nome': METODOS_INTRA_ANO[metodo]['nome'],
                    'mes_referencia': int(mes_referencia),
                    **_medias(metricas_por_ano),
                    'detalhes_por_ano': metricas_por_ano,
                }

        # Melhor modelo (menor MAPE) — só entre os que preveem o ano inteiro
        melhor = None
        melhor_mape = float('inf')
        for cod_modelo, dados_modelo in resultado_qualificador['modelos'].items():
            if dados_modelo['mape'] is not None and dados_modelo['mape'] < melhor_mape:
                melhor_mape = dados_modelo['mape']
                melhor = cod_modelo

        resultado_qualificador['melhor_modelo'] = melhor
        resultado_qualificador['melhor_mape'] = melhor_mape if melhor else None
        resultado_qualificador['semaforo'] = _determinar_semaforo(
            melhor_mape if melhor else None
        )
        resultados_filho.append(resultado_qualificador)

    resultados_pai = _agregar_pais(resultados_filho, hierarquia, modelos_validos)
    ranking_geral = _rankear_modelos(resultados_filho, modelos_validos)

    return {
        'resultados_filho': resultados_filho,
        'resultados_pai': resultados_pai,
        'ranking_geral': ranking_geral,
        'anos_treino': anos_treino,
        'anos_teste': anos_teste,
        'mes_referencia': int(mes_referencia),
        'modelos_testados': [
            {'codigo': m, 'nome': MODELOS_DISPONIVEIS[m]['nome']}
            for m in modelos_validos
        ],
        'metodos_intra_ano': [
            {'codigo': m, 'nome': METODOS_INTRA_ANO[m]['nome']}
            for m in metodos_intra
        ],
    }


def _agregar_pais(
    resultados_filho: list[dict],
    hierarquia: dict,
    modelos_validos: list[str],
) -> list[dict]:
    """Agrega resultados dos filhos para calcular métricas dos pais."""
    resultados_pai = []

    for pai_seq, pai_data in hierarquia.items():
        pai_q = pai_data['qualificador']

        # Folhas descendentes com resultado — em qualquer profundidade (R16)
        seqs_folhas = {f.seq_qualificador for f in pai_data['filhos']}
        filhos_com_resultado = [
            r for r in resultados_filho
            if r['seq_qualificador'] in seqs_folhas and r['modelos']
        ]

        if not filhos_com_resultado:
            continue

        resultado_pai = {
            'seq_qualificador': pai_seq,
            'num_qualificador': pai_q.num_qualificador,
            'dsc_qualificador': pai_q.dsc_qualificador,
            'modelos': {},
            'filhos': [r['seq_qualificador'] for r in filhos_com_resultado],
        }

        for modelo in modelos_validos:
            mapes = []
            wmapes = []
            maes = []
            biases = []

            for filho_r in filhos_com_resultado:
                if modelo in filho_r['modelos']:
                    m_data = filho_r['modelos'][modelo]
                    if m_data['mape'] is not None:
                        mapes.append(m_data['mape'])
                    if m_data['wmape'] is not None:
                        wmapes.append(m_data['wmape'])
                    if m_data['mae'] is not None:
                        maes.append(m_data['mae'])
                    if m_data['bias'] is not None:
                        biases.append(m_data['bias'])

            if mapes:
                resultado_pai['modelos'][modelo] = {
                    'nome': MODELOS_DISPONIVEIS[modelo]['nome'],
                    'mape': round(np.mean(mapes), 2),
                    'wmape': round(np.mean(wmapes), 2) if wmapes else None,
                    'bias': round(np.mean(biases), 2) if biases else None,
                    'mae': round(np.mean(maes), 2) if maes else None,
                }

        # Melhor modelo do pai
        melhor = None
        melhor_mape = float('inf')
        for cod_modelo, dados_modelo in resultado_pai['modelos'].items():
            if dados_modelo['mape'] is not None and dados_modelo['mape'] < melhor_mape:
                melhor_mape = dados_modelo['mape']
                melhor = cod_modelo

        resultado_pai['melhor_modelo'] = melhor
        resultado_pai['melhor_mape'] = melhor_mape if melhor else None
        resultado_pai['semaforo'] = _determinar_semaforo(
            melhor_mape if melhor else None
        )

        resultados_pai.append(resultado_pai)

    return resultados_pai


def _rankear_modelos(
    resultados_filho: list[dict],
    modelos_validos: list[str],
) -> dict:
    """Gera ranking geral: melhor modelo globalmente."""
    ranking = []

    for modelo in modelos_validos:
        wmapes = []
        vitorias = 0

        for filho_r in resultados_filho:
            if modelo in filho_r['modelos']:
                m_data = filho_r['modelos'][modelo]
                if m_data['wmape'] is not None:
                    wmapes.append(m_data['wmape'])

            # Contar vitórias
            if filho_r.get('melhor_modelo') == modelo:
                vitorias += 1

        ranking.append({
            'modelo': modelo,
            'nome': MODELOS_DISPONIVEIS[modelo]['nome'],
            'wmape_medio': round(np.mean(wmapes), 2) if wmapes else None,
            'qualificadores_vencidos': vitorias,
            'total_testados': len([
                r for r in resultados_filho
                if modelo in r['modelos'] and r['modelos'][modelo]['mape'] is not None
            ]),
        })

    # Ordenar por WMAPE (menor = melhor)
    ranking.sort(key=lambda x: x['wmape_medio'] if x['wmape_medio'] is not None else float('inf'))

    return {
        'melhor_modelo': ranking[0]['modelo'] if ranking and ranking[0]['wmape_medio'] is not None else None,
        'melhor_nome': ranking[0]['nome'] if ranking and ranking[0]['wmape_medio'] is not None else None,
        'wmape_medio': ranking[0]['wmape_medio'] if ranking else None,
        'ranking': ranking,
    }


# ==================== RECOMENDAÇÕES ====================

def salvar_recomendacoes(resultados_backtest: dict) -> int:
    """Salva o melhor modelo por qualificador na tabela de recomendações.

    Args:
        resultados_backtest: Resultado de executar_backtest()

    Returns:
        Número de recomendações salvas
    """

    # Limpar + inserir é ATÔMICO (previsao R13): falha no meio faz rollback —
    # a sessão é global/scoped, e um DELETE pendente seria efetivado pelo
    # commit da PRÓXIMA operação, apagando tudo sem gravar nada. (`db.text`
    # nem existia no helper _DB — a função quebrava na primeira linha; a
    # tabela tampouco tinha migração: model + 0034 entraram neste change.)
    try:
        db.session.execute(
            text('DELETE FROM flc_backtest_recomendacao')
        )

        count = 0
        anos_json = json.dumps(resultados_backtest.get('anos_teste', []))

        for filho_r in resultados_backtest.get('resultados_filho', []):
            melhor = filho_r.get('melhor_modelo')
            if melhor and melhor in filho_r.get('modelos', {}):
                m_data = filho_r['modelos'][melhor]
                db.session.execute(
                    text(
                        '''INSERT INTO flc_backtest_recomendacao
                        (seq_qualificador, cod_modelo, val_mape, val_wmape,
                         val_bias, anos_teste, dat_execucao)
                        VALUES (:seq_q, :modelo, :mape, :wmape, :bias,
                                :anos, :data)'''
                    ),
                    {
                        'seq_q': filho_r['seq_qualificador'],
                        'modelo': melhor,
                        'mape': m_data.get('mape'),
                        'wmape': m_data.get('wmape'),
                        'bias': m_data.get('bias'),
                        'anos': anos_json,
                        'data': date.today().isoformat(),
                    },
                )
                count += 1

        db.session.commit()
        return count
    except Exception:
        db.session.rollback()
        raise


def obter_recomendacoes() -> dict[int, dict]:
    """Obtém recomendações salvas do último backtest.

    Returns:
        Dict {seq_qualificador: {modelo, nome, mape, wmape, bias}}
    """
    rows = db.session.execute(
        text(
            '''SELECT seq_qualificador, cod_modelo, val_mape, val_wmape, val_bias,
                      anos_teste, dat_execucao
               FROM flc_backtest_recomendacao
               ORDER BY seq_qualificador'''
        )
    ).fetchall()

    resultado = {}
    for row in rows:
        cod_modelo = row[1]
        resultado[row[0]] = {
            'modelo': cod_modelo,
            'nome': MODELOS_DISPONIVEIS.get(cod_modelo, {}).get('nome', cod_modelo),
            # `is not None` (R16): viés 0.0 é MEDIÇÃO — a sentinela falsy o
            # exibia como ausência
            'mape': float(row[2]) if row[2] is not None else None,
            'wmape': float(row[3]) if row[3] is not None else None,
            'bias': float(row[4]) if row[4] is not None else None,
            'anos_teste': json.loads(row[5]) if row[5] else [],
            'dat_execucao': row[6],
        }

    return resultado
