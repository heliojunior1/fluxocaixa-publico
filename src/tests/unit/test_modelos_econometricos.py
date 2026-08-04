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
