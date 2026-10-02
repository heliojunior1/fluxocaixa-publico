"""Exercício aberto/fechado e linha por exercício — unitários puros
(cadastros-nucleo R31, extracao R24). Import tardio de `fluxocaixa`."""
from datetime import date, datetime
from types import SimpleNamespace

import pytest


def _linha(dat_saldo=None, ano=None, registro=None):
    return SimpleNamespace(dat_saldo=dat_saldo, num_ano_exercicio=ano, dat_registro=registro)


@pytest.mark.parametrize("valor,esperado", [
    (date(2141, 12, 31), date(2141, 12, 31)),
    (datetime(2141, 12, 31, 10, 30), date(2141, 12, 31)),
    ("2141-12-31", date(2141, 12, 31)),
    ("31/12/2141", date(2141, 12, 31)),
    (None, None),
    ("", None),
])
def test_como_data_aceita_iso_e_dia_mes_ano(valor, esperado):
    from fluxocaixa.services.staging_service import _como_data

    assert _como_data(valor) == esperado


def test_como_data_recusa_lixo():
    from fluxocaixa.services.staging_service import _como_data
    from fluxocaixa.services.validacao import RegraNegocioError

    with pytest.raises(RegraNegocioError):
        _como_data("31-31-2141")


def test_exercicio_da_linha_informado_vence_a_data():
    from fluxocaixa.services.staging_service import ano_da_linha

    # ajuste de 2141 lançado com data de janeiro de 2142: vale o informado
    assert ano_da_linha(_linha(date(2142, 1, 5), ano="2141"), 2142) == 2141


def test_exercicio_da_linha_cai_para_o_ano_do_movimento():
    from fluxocaixa.services.staging_service import ano_da_linha

    assert ano_da_linha(_linha("31/12/2141"), 2142) == 2141


def test_exercicio_da_linha_sem_nada_usa_o_padrao():
    from fluxocaixa.services.staging_service import ano_da_linha

    assert ano_da_linha(_linha(), 2142) == 2142


def test_janela_padrao_usa_os_dias_retroativos():
    from fluxocaixa.services.extracao_service import montar_janela

    janela = montar_janela(None, None, dias_retroativos=7)
    assert (janela.data_fim - janela.data_inicio).days == 7
    assert janela.data_fim == date.today()


def test_exercicios_alvo_entre_o_ano_anterior_e_o_fim(monkeypatch):
    from fluxocaixa.services import exercicio_service

    monkeypatch.setattr(exercicio_service, "anos_conhecidos",
                        lambda: [2143, 2142, 2141, 2140, 2139])
    monkeypatch.setattr(exercicio_service, "anos_fechados", lambda: {2141})
    # janela em janeiro de 2142: alcança 2141 (fechado, fora) e 2142
    assert exercicio_service.exercicios_alvo(date(2142, 1, 1), date(2142, 1, 31)) == [2142]
    # janela atravessando a virada: 2140 (ano anterior ao início) a 2142
    assert exercicio_service.exercicios_alvo(date(2141, 12, 20),
                                             date(2142, 1, 3)) == [2140, 2142]


def test_exercicios_alvo_sem_plano_usa_o_ano_do_fim(monkeypatch):
    from fluxocaixa.services import exercicio_service

    monkeypatch.setattr(exercicio_service, "anos_conhecidos", lambda: [])
    monkeypatch.setattr(exercicio_service, "anos_fechados", lambda: set())
    assert exercicio_service.exercicios_alvo(date(2142, 1, 1), date(2142, 1, 2)) == [2142]


def test_rotulo_do_evento():
    from fluxocaixa.models.exercicio import ExercicioEvento

    assert ExercicioEvento(cod_tipo_evento='F').rotulo == 'FECHAMENTO'
