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


def _ultimo_mes_encerrado(ano: int, hoje: date) -> int:
    """Último mês ENCERRADO do ano na data de corte (R27): ano passado → 12;
    ano corrente → mês anterior ao corte; ano futuro → 12 (só massa de teste,
    mesmo caso da "janela inteira no futuro" do R18)."""
    if ano == hoje.year:
        return hoje.month - 1
    return 12


def _obter_real(seq_qualificador: int, ano: int, hoje: date) -> dict[int, float]:
    """Realizado do ano de teste em MAGNITUDE, só dos meses ENCERRADOS na data
    de corte (R27); mês encerrado sem movimento = 0.0. Vazio quando o ano não
    tem movimento ou mês encerrado nenhum.

    ⚠️ Antes preenchia os 12 meses: com o ano corrente como ano de teste, os
    meses em curso e futuros entravam como realizado ZERO — previsão exata
    nos meses observados saía com WMAPE e viés de 50%.
    """
    from . import modelos_economicos_service as modelos

    ultimo = _ultimo_mes_encerrado(ano, hoje)
    if ultimo < 1:
        return {}
    serie = modelos.obter_dados_historicos(
        seq_qualificador, date(ano, 1, 1), date(ano, 12, 31), hoje=hoje)
    if not len(serie):
        return {}
    por_mes = {d.month: abs(float(v)) for d, v in zip(serie['data'], serie['valor'])}
    return {mes: por_mes.get(mes, 0.0) for mes in range(1, ultimo + 1)}


def _executar_modelo(modelo: str, dados_treino, ano_teste: int):
    """`(projeção mensal do ano de teste, degradação)` de um modelo do ano
    inteiro, ou `(None, None)` quando o modelo não se aplica (série curta, lib
    ausente, falha). A degradação (fallback, sazonalidade removida, LightGBM
    sem divisões) VIAJA no resultado: antes era descartada e um ARIMA de
    fallback concorria rotulado SARIMA."""
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
        return None, None
    try:
        resultado = motor(dados_treino, 12, {}, ano_teste)
    except Exception as e:  # modelo inaplicável não derruba o backtest
        logger.warning("Backtest: %s falhou: %s", modelo, e)
        return None, None
    projecao = {
        (row['data'] if isinstance(row['data'], date) else row['data'].date()).month:
            float(row['valor_projetado'])
        for _, row in resultado.iterrows()
    }
    return projecao, getattr(resultado, 'attrs', {}).get('degradacao')


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
    """Métricas de acurácia sobre TODOS os meses medidos (R28).

    WMAPE (Σ|erro| / Σ|real|), MAE e viés usam todos os meses — inclusive os
    de realizado zero, onde errar custa dinheiro. O MAPE continua informativo,
    só sobre meses de realizado não nulo. Realizado todo zero: WMAPE, viés e
    MAPE indefinidos (`None`), MAE definido.

    ⚠️ Antes os meses de realizado zero saíam de TODAS as métricas e o melhor
    modelo era escolhido pelo MAPE: realizado `[100, 0]`, previsão
    `[100, 1000]` vencia `[110, 0]` com erro monetário cem vezes maior.
    """
    meses_comuns = sorted(set(projecao.keys()) & set(real.keys()))
    vazio = {'mape': None, 'wmape': None, 'bias': None, 'mae': None}
    if not meses_comuns:
        return vazio

    proj_vals = np.array([projecao[m] for m in meses_comuns], dtype=float)
    real_vals = np.array([real[m] for m in meses_comuns], dtype=float)
    erros = proj_vals - real_vals
    volume = float(np.sum(np.abs(real_vals)))
    mask = real_vals != 0

    mape = (float(np.mean(np.abs(erros[mask]) / np.abs(real_vals[mask]) * 100))
            if mask.any() else None)
    wmape = float(np.sum(np.abs(erros)) / volume * 100) if volume else None
    # Viés: positivo = superestima
    bias = float(np.mean(erros) / np.mean(np.abs(real_vals)) * 100) if volume else None
    mae = float(np.mean(np.abs(erros)))

    def _r(valor):
        return round(valor, 2) if valor is not None else None

    return {
        'meses_avaliados': [int(m) for m in meses_comuns],
        'mape': _r(mape),
        'wmape': _r(wmape),
        'bias': _r(bias),
        'mae': _r(mae),
    }


def _escolher_melhor(candidatos: dict[str, dict]) -> str | None:
    """Melhor modelo (R28): menor WMAPE; sem WMAPE (realizado todo zero),
    menor MAE. Só concorrem candidatos SEM degradação e com a MAIOR cobertura
    de anos entre eles — média de erros sobre anos diferentes não é
    comparável, e um modelo que degradou não foi o modelo medido.

    `candidatos`: {código: {'wmape', 'mae', 'anos_medidos', 'degradacoes'}}.
    """
    elegiveis = {cod: c for cod, c in candidatos.items()
                 if not c.get('degradacoes')
                 and (c.get('wmape') is not None or c.get('mae') is not None)}
    if not elegiveis:
        return None
    cobertura = max(c.get('anos_medidos', 1) for c in elegiveis.values())
    elegiveis = {cod: c for cod, c in elegiveis.items()
                 if c.get('anos_medidos', 1) == cobertura}

    def _chave(cod):
        c = elegiveis[cod]
        wmape = c.get('wmape')
        mae = c.get('mae')
        return (wmape is None, wmape if wmape is not None else 0.0,
                mae if mae is not None else float('inf'))

    return min(elegiveis, key=_chave)


def _metricas_da_soma(pares: list[tuple[dict, dict]]) -> dict:
    """Métricas da série SOMADA (R28): `pares` = [(projeção, realizado)] por
    folha, mês → valor. O erro de um pai é o erro do seu total mensal — a
    média das métricas das folhas dá o mesmo peso a rubrica de R$ 100 e de
    R$ 1 milhão e não mede o agregado."""
    projecao: dict[int, float] = {}
    real: dict[int, float] = {}
    for proj, rea in pares:
        for mes in set(proj) & set(rea):
            projecao[mes] = projecao.get(mes, 0.0) + float(proj[mes])
            real[mes] = real.get(mes, 0.0) + float(rea[mes])
    return _calcular_metricas(projecao, real)


def _determinar_semaforo(mape: float | None) -> str:
    """Determina o semáforo de acurácia pelo erro do critério de seleção
    (WMAPE desde o R28).

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
    hoje: date | None = None,
) -> dict:
    """Backtest por folha (previsao R16, R27, R28).

    `hoje` é a DATA DE CORTE (injetável; default o relógio): só meses
    encerrados nela são medidos, e ela volta no resultado (`data_corte`).

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

    hoje = hoje or date.today()
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
        reais = {ano: _obter_real(seq_q, ano, hoje) for ano in anos_teste}
        treinos = {ano: _obter_dados_treino(seq_q, inicio_treino, ano - 1)
                   for ano in anos_teste}

        for modelo in modelos_validos:
            metricas_por_ano = []
            degradacoes = []
            for ano_teste in anos_teste:
                if not reais[ano_teste]:
                    continue
                projecao, degradacao = _executar_modelo(
                    modelo, treinos[ano_teste], ano_teste)
                if projecao is None:
                    continue
                metricas = _calcular_metricas(projecao, reais[ano_teste])
                metricas['ano_teste'] = ano_teste
                metricas['projecao'] = {str(k): v for k, v in projecao.items()}
                metricas['real'] = {str(k): v for k, v in reais[ano_teste].items()}
                metricas['degradacao'] = degradacao
                if degradacao:
                    degradacoes.append(f"{ano_teste}: {degradacao}")
                metricas_por_ano.append(metricas)
            if metricas_por_ano:
                resultado_qualificador['modelos'][modelo] = {
                    'nome': MODELOS_DISPONIVEIS[modelo]['nome'],
                    **_medias(metricas_por_ano),
                    'anos_medidos': len(metricas_por_ano),
                    'degradacoes': degradacoes,
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

        # Melhor modelo (R28) — só entre os que preveem o ano inteiro
        _definir_melhor(resultado_qualificador)
        resultados_filho.append(resultado_qualificador)

    resultados_pai = _agregar_pais(resultados_filho, hierarquia, modelos_validos)
    ranking_geral = _rankear_modelos(resultados_filho, modelos_validos)

    return {
        'data_corte': hoje.isoformat(),
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


def _definir_melhor(resultado: dict) -> None:
    """Grava melhor modelo, erro e semáforo de uma folha ou pai (R28)."""
    melhor = _escolher_melhor(resultado['modelos'])
    dados = resultado['modelos'].get(melhor, {}) if melhor else {}
    resultado['melhor_modelo'] = melhor
    resultado['melhor_wmape'] = dados.get('wmape')
    resultado['melhor_mape'] = dados.get('mape')
    resultado['semaforo'] = _determinar_semaforo(dados.get('wmape'))


def _por_mes(mapa: dict) -> dict[int, float]:
    return {int(mes): float(valor) for mes, valor in (mapa or {}).items()}


def _agregar_pais(
    resultados_filho: list[dict],
    hierarquia: dict,
    modelos_validos: list[str],
) -> list[dict]:
    """Métricas do pai sobre a série SOMADA das folhas (R28).

    Por modelo e ano de teste, soma mês a mês o previsto e o realizado das
    folhas — só quando TODAS as folhas com resultado têm aquele modelo naquele
    ano (senão o total seria parcial). Antes era a média das métricas das
    folhas, que não mede o erro do total financeiro do pai.
    """
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
            detalhes_por_folha = []
            for filho_r in filhos_com_resultado:
                dados = filho_r['modelos'].get(modelo)
                detalhes_por_folha.append(
                    {d['ano_teste']: d for d in dados['detalhes_por_ano']} if dados else {})
            anos = set.intersection(*(set(d) for d in detalhes_por_folha))
            metricas_por_ano = []
            degradacoes = []
            for ano in sorted(anos):
                pares = [(_por_mes(d[ano]['projecao']), _por_mes(d[ano]['real']))
                         for d in detalhes_por_folha]
                metricas = _metricas_da_soma(pares)
                metricas['ano_teste'] = ano
                metricas_por_ano.append(metricas)
                degradacoes += [f"{ano}: {d[ano]['degradacao']}"
                                for d in detalhes_por_folha if d[ano].get('degradacao')]
            if metricas_por_ano:
                resultado_pai['modelos'][modelo] = {
                    'nome': MODELOS_DISPONIVEIS[modelo]['nome'],
                    **_medias(metricas_por_ano),
                    'anos_medidos': len(metricas_por_ano),
                    'degradacoes': degradacoes,
                }

        _definir_melhor(resultado_pai)
        resultados_pai.append(resultado_pai)

    return resultados_pai


def _rankear_modelos(
    resultados_filho: list[dict],
    modelos_validos: list[str],
) -> dict:
    """Ranking geral pelo WMAPE AGREGADO por volume (R28): Σ|erro| / Σ|real|
    sobre folhas × anos. A média simples dos WMAPEs dava a uma rubrica de
    R$ 100 o mesmo peso de uma de R$ 1 milhão."""
    ranking = []

    for modelo in modelos_validos:
        erro = volume = 0.0
        vitorias = testados = 0

        for filho_r in resultados_filho:
            dados = filho_r['modelos'].get(modelo)
            if dados:
                testados += 1
                for detalhe in dados['detalhes_por_ano']:
                    proj, real = _por_mes(detalhe['projecao']), _por_mes(detalhe['real'])
                    for mes in set(proj) & set(real):
                        erro += abs(proj[mes] - real[mes])
                        volume += abs(real[mes])
            if filho_r.get('melhor_modelo') == modelo:
                vitorias += 1

        ranking.append({
            'modelo': modelo,
            'nome': MODELOS_DISPONIVEIS[modelo]['nome'],
            'wmape_medio': round(erro / volume * 100, 2) if volume else None,
            'qualificadores_vencidos': vitorias,
            'total_testados': testados,
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
