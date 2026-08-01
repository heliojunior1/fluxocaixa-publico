"""Steps BDD — agendador embutido de extração (spec extracao-configuravel R5)."""
import os

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import (
    criar_fonte_fake,
    fonte_por_nome,
    garantir_conector_fake,
    garantir_fonte_ativa,
    garantir_sistema_origem,
)

scenarios("../extracao-configuravel/agendador.feature")


@pytest.fixture(autouse=True)
def _agendador_limpo(app):
    """Cada cenário parte de agendador parado e flag no default."""
    os.environ.pop("EXTRACAO_SCHEDULER", None)
    yield
    from fluxocaixa.extracao import scheduler

    scheduler.encerrar()
    os.environ.pop("EXTRACAO_SCHEDULER", None)


def _job_da_fonte(nome):
    from fluxocaixa.extracao import scheduler

    fonte = fonte_por_nome(nome)
    assert fonte is not None, f"fonte {nome!r} não cadastrada"
    return scheduler.job_da_fonte(fonte.seq_fonte_extracao)


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(777)


@given(parsers.parse('um sistema de origem "{sigla}" cadastrado'))
def sistema_cadastrado(app, sigla):
    garantir_sistema_origem(sigla)


@given('o conector de teste "FAKE" registrado', target_fixture="conector_fake")
def conector_fake_registrado(app):
    return garantir_conector_fake()


@given(parsers.parse('uma fonte "{nome}" do tipo "{tipo:w}"'))
def fonte_sem_cron(app, nome, tipo):
    garantir_fonte_ativa(nome, tipo=tipo)


@given(parsers.parse('uma fonte "{nome}" do tipo "{tipo:w}" com cron "{cron}"'))
def fonte_com_cron(app, nome, tipo, cron):
    garantir_fonte_ativa(nome, tipo=tipo, cron=cron)


@given("a flag do agendador desabilitada")
def flag_desabilitada():
    os.environ["EXTRACAO_SCHEDULER"] = "false"


@given("o agendador iniciado")
def agendador_iniciado(app):
    from fluxocaixa.extracao import scheduler

    scheduler.iniciar()


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when("o agendador inicia")
def agendador_inicia(app):
    from fluxocaixa.extracao import scheduler

    scheduler.iniciar()


@when(parsers.parse('inativo a fonte "{nome}"'))
def inativa_fonte(app, nome):
    from fluxocaixa.services.extracao_service import inativar_fonte

    inativar_fonte(fonte_por_nome(nome).seq_fonte_extracao)


@when(parsers.parse('crio a fonte "{nome}" do tipo "{tipo:w}" com cron "{cron}"'))
def cria_fonte(app, nome, tipo, cron):
    criar_fonte_fake(nome, tipo=tipo, cron=cron)


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('existe job agendado para a fonte "{nome}"'))
def job_existe(nome):
    assert _job_da_fonte(nome) is not None


@then(parsers.parse('não existe job agendado para a fonte "{nome}"'))
def job_nao_existe(nome):
    assert _job_da_fonte(nome) is None
