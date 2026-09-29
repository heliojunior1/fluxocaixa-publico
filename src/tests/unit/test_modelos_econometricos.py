"""Unitários dos modelos econométricos corrigidos (previsao R12).

Import tardio de `fluxocaixa` dentro dos testes (isolamento de banco).
"""
import inspect
from datetime import date


def test_datas_do_ano_base_12_periodos():
    from fluxocaixa.services.modelos_economicos_service import _datas_do_ano_base

    datas = _datas_do_ano_base(2063, 12)
    assert datas[0] == date(2063, 1, 1)
    assert datas[-1] == date(2063, 12, 1)


def test_datas_do_ano_base_13_periodos_atravessa_o_ano():
    """`date(ano, 13, 1)` estourava — o 13º período é jan do ano seguinte."""
    from fluxocaixa.services.modelos_economicos_service import _datas_do_ano_base

    datas = _datas_do_ano_base(2063, 13)
    assert datas[12] == date(2064, 1, 1)


def test_datas_do_ano_base_52_periodos():
    """Quinzenal/semanal usam até 52 períodos (previsao R9)."""
    from fluxocaixa.services.modelos_economicos_service import _datas_do_ano_base

    datas = _datas_do_ano_base(2063, 52)
    assert len(datas) == 52
    assert datas[-1] == date(2067, 4, 1)
    assert len(set(datas)) == 52


def test_sem_print_no_modulo():
    """Diagnóstico sai por logging, nunca print (previsao R12)."""
    from fluxocaixa.services import modelos_economicos_service as modelos

    fonte = inspect.getsource(modelos)
    assert "print(" not in fonte, "diagnóstico por print voltou ao módulo"


def test_sem_filterwarnings_global_no_import():
    """A supressão de warnings fica confinada aos fit() — o import do módulo
    não pode alterar os filtros do processo inteiro (A8)."""
    from fluxocaixa.services import modelos_economicos_service as modelos

    fonte = inspect.getsource(modelos)
    corpo_do_modulo = [
        linha for linha in fonte.splitlines()
        if linha.startswith("warnings.filterwarnings")
    ]
    assert corpo_do_modulo == [], (
        "filterwarnings global no nível de módulo: suprime warnings do "
        "processo inteiro como efeito colateral do import")


def test_validar_formula_nao_avalia():
    """L14: fórmula com divisão por variável valida (parse ok); o erro de
    avaliação é de runtime, com mensagem própria."""
    from fluxocaixa.services.formula_engine import avaliar_formula, validar_formula

    ok, mensagem = validar_formula("base / (x - 1)")
    assert ok is True, mensagem

    try:
        avaliar_formula("base / (x - 1)", {"base": 10.0, "x": 1.0})
        raiz_ok = True
    except ValueError as exc:
        raiz_ok = False
        assert "avaliar" in str(exc) or "Erro" in str(exc)
    assert raiz_ok is False, "divisão por zero em runtime deveria falhar"


# --- change corrigir-motores-de-previsao (R18/R19) ---------------------------

def _serie_ate(ultimo_mes: str, n: int):
    import pandas as pd

    datas = pd.date_range(end=ultimo_mes, periods=n, freq="MS")
    return pd.DataFrame({"data": datas, "valor": [1.0] * n})


def test_horizonte_historico_ate_dezembro_nao_descarta():
    from fluxocaixa.services.modelos_economicos_service import _horizonte

    passos, descarte, datas = _horizonte(_serie_ate("2084-12-01", 24), 2085, 12)
    assert (passos, descarte) == (12, 0)
    assert (datas[0].year, datas[0].month) == (2085, 1)
    assert (datas[-1].year, datas[-1].month) == (2085, 12)


def test_horizonte_historico_ate_setembro_descarta_out_a_dez():
    from fluxocaixa.services.modelos_economicos_service import _horizonte

    passos, descarte, datas = _horizonte(_serie_ate("2084-09-01", 24), 2085, 12)
    assert (passos, descarte) == (15, 3)
    assert (datas[0].year, datas[0].month) == (2085, 1)


def test_horizonte_sem_ano_base_segue_o_ultimo_mes():
    from fluxocaixa.services.modelos_economicos_service import _horizonte

    passos, descarte, datas = _horizonte(_serie_ate("2084-09-01", 24), None, 3)
    assert (passos, descarte) == (3, 0)
    assert (datas[0].year, datas[0].month) == (2084, 10)


def test_minimo_de_meses_tem_origem_unica():
    """O mesmo mínimo nos quatro pontos de despacho (R19): a rota avulsa, o
    cenário por perna e o backtest leem MINIMO_DE_MESES direto; o método por
    qualificador declara o seu e tem de coincidir."""
    import inspect

    from fluxocaixa.services import backtest_service, simulador_cenario_service
    from fluxocaixa.services import modelos_economicos_service as modelos
    from fluxocaixa.services.metodo_qualificador_service import MODELOS_DE_SERIE

    assert modelos.MINIMO_DE_MESES["XGBOOST"] == 14
    assert modelos.MINIMO_DE_MESES["LIGHTGBM"] == 14
    for modelo, minimo in modelos.MINIMO_DE_MESES.items():
        assert MODELOS_DE_SERIE[modelo][1] == minimo, modelo
    assert "MINIMO_DE_MESES" in inspect.getsource(modelos.calcular_projecao)
    assert "MINIMO_DE_MESES" in inspect.getsource(backtest_service._executar_modelo)
    assert "MINIMO_DE_MESES" in inspect.getsource(simulador_cenario_service._projetar_perna)
