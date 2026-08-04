"""Guarda da série histórica única da previsão (previsao R11).

Estrutural, no espírito de `costura.py`: a régua que impede o dialeto
(`strftime`, só SQLite) e o vazamento de inativos de voltarem aos leitores
de série histórica. Import tardio de `fluxocaixa` dentro dos testes.
"""
import inspect


def _fonte(modulo):
    return inspect.getsource(modulo)


def test_sem_strftime_nos_leitores_de_serie():
    """`strftime` é exclusivo do SQLite — o projeto declara PostgreSQL via
    DATABASE_URL. `extract` é a forma portável (previsao R11)."""
    from fluxocaixa.services import formula_engine, modelos_economicos_service

    for modulo in (formula_engine, modelos_economicos_service):
        assert "strftime('%Y'" not in _fonte(modulo), (
            f"{modulo.__name__} voltou a usar strftime — quebra em PostgreSQL")
        assert "strftime('%m'" not in _fonte(modulo), (
            f"{modulo.__name__} voltou a usar strftime — quebra em PostgreSQL")


def test_leitores_de_serie_filtram_ativos():
    """Toda leitura de série histórica considera só lançamentos ativos —
    a mesma série do backtest (previsao R11)."""
    from fluxocaixa.services import formula_engine
    from fluxocaixa.services import modelos_economicos_service as modelos

    leitores = [
        formula_engine.listar_anos_disponiveis,
        formula_engine.listar_todos_anos_disponiveis,
        formula_engine._buscar_valores_historicos_mes,
        formula_engine._buscar_valores_historicos_anual,
        formula_engine._soma_acumulada,
        formula_engine._perfil_sazonal,
        modelos.obter_dados_historicos,
        modelos.obter_dados_historicos_agregados,
    ]
    for leitor in leitores:
        fonte = inspect.getsource(leitor)
        assert "ind_status == 'A'" in fonte, (
            f"{leitor.__name__} lê a série sem filtrar ind_status='A' — "
            "lançamento excluído voltaria a inflar a previsão")


def test_leitores_nao_engolem_excecao_de_banco():
    """`except Exception → {}/[]/0.0` transformava erro de banco em projeção
    zero com cara de dado apurado. O erro deve SUBIR (previsao R11)."""
    from fluxocaixa.services import formula_engine

    for leitor in (
        formula_engine.listar_anos_disponiveis,
        formula_engine.listar_todos_anos_disponiveis,
        formula_engine._buscar_valores_historicos_mes,
        formula_engine._buscar_valores_historicos_anual,
        formula_engine._soma_acumulada,
        formula_engine._perfil_sazonal,
    ):
        fonte = inspect.getsource(leitor)
        assert "except Exception" not in fonte, (
            f"{leitor.__name__} voltou a engolir exceção de banco")
