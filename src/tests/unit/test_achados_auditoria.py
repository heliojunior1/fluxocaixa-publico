"""Unitários — achados da auditoria da previsão (change
corrigir-achados-auditoria-previsao; previsao R22–R28, cadastros-nucleo R30).

Os cenários de ponta a ponta vivem no BDD `previsao/achados_auditoria.feature`;
aqui ficam as bordas dos cálculos. Imports de app sempre tardios.
"""
import inspect
from datetime import date

import pandas as pd
import pytest


# ------------------------------------------------------------ R22 periodicidade

def _mensal(valores, seq=None, ano=2124):
    linhas = [{'data': date(ano, m, 1), 'valor_projetado': v}
              for m, v in zip(range(1, 13), valores)]
    df = pd.DataFrame(linhas)
    if seq is not None:
        df['seq_qualificador'] = seq
    return df


def test_anual_soma_o_ano_por_qualificador_e_preserva_attrs():
    from fluxocaixa.services.simulador_cenario_service import _converter_para_periodicidade

    df = pd.concat([_mensal([10.0] * 12, seq=1), _mensal([5.0] * 12, seq=2)])
    df.attrs['degradacao'] = 'aviso'
    anual = _converter_para_periodicidade(df, 'ANUAL', 2124, 1)
    assert sorted(zip(anual['seq_qualificador'], anual['valor_projetado'])) == [
        (1, 120.0), (2, 60.0)]
    assert anual.attrs['degradacao'] == 'aviso'


def test_semanal_rateia_o_mes_e_preserva_o_total_do_ano():
    from fluxocaixa.services.periodo_resolver import serie_de_datas
    from fluxocaixa.services.simulador_cenario_service import (
        _converter_para_periodicidade,
        _meses_do_horizonte,
    )

    semanas = len([d for d in serie_de_datas('SEMANAL', 2124, 52) if d.year == 2124])
    assert _meses_do_horizonte('SEMANAL', 2124, semanas) == 12
    semanal = _converter_para_periodicidade(_mensal([100.0] * 12), 'SEMANAL', 2124, semanas)
    assert len(semanal) == semanas
    assert round(float(semanal['valor_projetado'].sum()), 2) == 1200.0


def test_mensal_nao_e_convertido_e_horizonte_mensal_e_o_numero_de_periodos():
    from fluxocaixa.services.simulador_cenario_service import (
        _converter_para_periodicidade,
        _meses_do_horizonte,
    )

    df = _mensal([1.0] * 12)
    assert _converter_para_periodicidade(df, 'MENSAL', 2124, 12) is df
    assert _meses_do_horizonte('MENSAL', 2124, 12) == 12
    assert _meses_do_horizonte('ANUAL', 2124, 1) == 12
    assert _meses_do_horizonte('QUINZENAL', 2124, 24) == 12


# ------------------------------------------------------------ R23 crescimento

def _crescimento(monkeypatch, realizado_mes, total, perfil, mes_ref=6):
    from fluxocaixa.services import formula_engine

    monkeypatch.setattr(formula_engine, "_soma_acumulada",
                        lambda _s, _a, mes, _f: realizado_mes)
    return formula_engine._projecao_que_conserva_o_total([1], 2124, mes_ref, total, perfil)


def test_saldo_negativo_zera_os_meses_futuros_e_declara(monkeypatch):
    df = _crescimento(monkeypatch, 300.0, 1000.0, {m: 1 / 12 for m in range(1, 13)})
    assert df['valor_projetado'].tolist()[6:] == [0.0] * 6
    assert "supera o total" in df.attrs['degradacao']


def test_perfil_sem_peso_nos_futuros_reparte_igual_com_centavos_exatos(monkeypatch):
    perfil = {m: (1 / 6 if m <= 6 else 0.0) for m in range(1, 13)}
    df = _crescimento(monkeypatch, 100.0, 1000.0, perfil)
    futuros = df['valor_projetado'].tolist()[6:]
    assert round(sum(futuros), 2) == 400.0
    assert max(futuros) - min(futuros) <= 0.02


# ------------------------------------------------------------ R25/R26

def test_janela_unica_nas_tres_portas():
    from fluxocaixa.services import modelos_economicos_service as modelos
    from fluxocaixa.services import simulador_cenario_service
    from fluxocaixa.services.metodo_qualificador_service import MODELOS_DE_SERIE

    for modelo, janela in modelos.JANELA_EM_ANOS.items():
        assert MODELOS_DE_SERIE[modelo][0] == janela, modelo
    assert "JANELA_EM_ANOS" in inspect.getsource(modelos.calcular_projecao)
    assert "JANELA_EM_ANOS" in inspect.getsource(simulador_cenario_service._projetar_perna)


def test_lightgbm_respeita_min_child_samples_configurado():
    from fluxocaixa.services import modelos_economicos_service as modelos

    if not modelos.HAS_LIGHTGBM:
        pytest.skip("lightgbm indisponível")
    serie = pd.DataFrame({'data': pd.date_range('2090-01-01', periods=36, freq='MS'),
                          'valor': [100.0 + 5 * t for t in range(36)]})
    # mínimo por folha acima das 24 linhas de treino: nenhuma divisão possível
    df = modelos.projetar_lightgbm(serie, 12, {'min_child_samples': 30}, 2093)
    assert "sem divisões" in df.attrs['degradacao']


# ------------------------------------------------------------ R27/R28 backtest

def test_ultimo_mes_encerrado():
    from fluxocaixa.services.backtest_service import _ultimo_mes_encerrado

    hoje = date(2124, 9, 20)
    assert _ultimo_mes_encerrado(2123, hoje) == 12
    assert _ultimo_mes_encerrado(2124, hoje) == 8
    assert _ultimo_mes_encerrado(2124, date(2124, 1, 5)) == 0
    assert _ultimo_mes_encerrado(2130, hoje) == 12  # massa de teste no futuro


def test_ranking_pondera_pelo_volume():
    from fluxocaixa.services.backtest_service import _rankear_modelos

    def _folha(real, proj):
        return {'modelos': {'MEDIA_HISTORICA': {'detalhes_por_ano': [
            {'projecao': {'1': proj}, 'real': {'1': real}}]}},
            'melhor_modelo': 'MEDIA_HISTORICA'}

    # rubrica pequena erra 100%, grande acerta: agregado ≈ 0,01%, não 50%
    ranking = _rankear_modelos([_folha(100.0, 200.0), _folha(1_000_000.0, 1_000_000.0)],
                               ['MEDIA_HISTORICA'])
    assert ranking['ranking'][0]['wmape_medio'] == 0.01
    assert ranking['ranking'][0]['total_testados'] == 2


# ------------------------------------------------------------ recomendações

ANOS = (2121, 2122)


@pytest.fixture()
def _ilha_recomendacao(app):
    from fluxocaixa.models import BacktestRecomendacao, Qualificador, SimuladorCenario
    from fluxocaixa.models.base import db

    def _limpar():
        db.session.rollback()
        seqs = [q.seq_qualificador for q in
                Qualificador.query.filter(Qualificador.num_ano_exercicio.in_(ANOS)).all()]
        if seqs:
            BacktestRecomendacao.query.filter(
                BacktestRecomendacao.seq_qualificador.in_(seqs)).delete(
                    synchronize_session=False)
        for c in SimuladorCenario.query.filter(
                SimuladorCenario.nom_cenario.like("CEN_UT_AA%")).all():
            db.session.delete(c)
        db.session.flush()
        for q in Qualificador.query.filter(Qualificador.num_ano_exercicio.in_(ANOS)).all():
            q.cod_qualificador_pai = None
        db.session.flush()
        for q in Qualificador.query.filter(Qualificador.num_ano_exercicio.in_(ANOS)).all():
            db.session.delete(q)
        db.session.commit()

    _limpar()
    yield
    _limpar()


def test_recomendacao_de_outro_exercicio_chega_pela_raiz_e_erro_e_o_wmape(_ilha_recomendacao):
    from fluxocaixa.models import BacktestRecomendacao
    from fluxocaixa.models.base import db
    from fluxocaixa.services.metodo_qualificador_service import recomendacoes_aplicaveis
    from fluxocaixa.services.qualificador_service import create_qualificador
    from fluxocaixa.services.simulador_cenario_service import criar_simulador_cenario

    bloco = create_qualificador("1.83", "Bloco UT", num_ano_exercicio=2121)
    folha = create_qualificador("1.83.1", "Folha UT", num_ano_exercicio=2121,
                                cod_qualificador_pai=bloco.seq_qualificador)
    bloco_novo = create_qualificador("1.83", "Bloco UT", num_ano_exercicio=2122,
                                     cod_rubrica_raiz=bloco.cod_rubrica_raiz)
    folha_nova = create_qualificador("1.83.1", "Folha UT", num_ano_exercicio=2122,
                                     cod_qualificador_pai=bloco_novo.seq_qualificador,
                                     cod_rubrica_raiz=folha.cod_rubrica_raiz)
    db.session.add(BacktestRecomendacao(
        seq_qualificador=folha_nova.seq_qualificador, cod_modelo='MEDIA_HISTORICA',
        val_mape=1.0, val_wmape=7.5, anos_teste='[2121]', dat_execucao=date.today()))
    db.session.commit()
    cenario = criar_simulador_cenario(
        nom_cenario="CEN_UT_AA_REC", dsc_cenario="ut", ano_base=2121, num_periodos=12,
        tipo_cenario_receita='', config_receita={}, tipo_cenario_despesa='',
        config_despesa={}, user_id=1)

    recomendadas = [r for r in recomendacoes_aplicaveis(cenario)
                    if r['num_qualificador'] == "1.83.1"]
    assert [(r['seq_qualificador'], r['erro']) for r in recomendadas] == [
        (folha.seq_qualificador, 7.5)]
