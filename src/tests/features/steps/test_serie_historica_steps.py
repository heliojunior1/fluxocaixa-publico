"""Steps BDD — série histórica única da previsão (spec previsao R11).

Ilha 2063. Import tardio de `fluxocaixa` em todos os steps.
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../previsao/serie_historica.feature")

ANO = 2063
QUAL = "1.63.1"


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from fluxocaixa.models import Lancamento, Qualificador

    db = _db()
    db.session.rollback()
    q = Qualificador.query.filter_by(num_qualificador=QUAL).first()
    if q is not None:
        Lancamento.query.filter_by(seq_qualificador=q.seq_qualificador).delete()
        db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


@given("um qualificador folha de série histórica", target_fixture="qualificador")
def qualificador(app):
    from fluxocaixa.models import Qualificador

    db = _db()
    q = Qualificador.query.filter_by(num_qualificador=QUAL).first()
    if q is None:
        q = Qualificador(num_qualificador=QUAL,
                         dsc_qualificador=f"Rubrica série {QUAL}",
                         ind_status='A')
        db.session.add(q)
        db.session.commit()
    return q


def _criar_lancamento(qualificador, valor, mes, ind_status):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.services.dominio_lancamento import resolver_origem, resolver_tipo

    db = _db()
    db.session.add(Lancamento(
        dat_lancamento=date(ANO, mes, 15),
        seq_qualificador=qualificador.seq_qualificador,
        val_lancamento=Decimal(valor),
        cod_tipo_lancamento=resolver_tipo("Entrada").cod_tipo_lancamento,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        cod_pessoa_inclusao=1,
        ind_status=ind_status,
    ))
    db.session.commit()


@given(parsers.parse("lançamentos ativos de {v1} e {v2} em março de 2063"))
def lancamentos_ativos(app, qualificador, v1, v2):
    _criar_lancamento(qualificador, v1, 3, 'A')
    _criar_lancamento(qualificador, v2, 3, 'A')


@given(parsers.parse("um lançamento inativo de {valor} em março de 2063"))
def lancamento_inativo(app, qualificador, valor):
    _criar_lancamento(qualificador, valor, 3, 'I')


@given("que a consulta de valores históricos falhará com erro de banco")
def consulta_falha(app, monkeypatch):
    from sqlalchemy.exc import OperationalError

    from fluxocaixa.models.base import db

    def _explode(*args, **kwargs):
        raise OperationalError("SELECT ...", {}, Exception("banco fora"))

    monkeypatch.setattr(db.session, "query", _explode)


@when("calculo a base de março por média simples do ano 2063")
def calcula_base(app, qualificador, contexto):
    from fluxocaixa.services import formula_engine

    try:
        contexto["base"] = formula_engine.calcular_base(
            qualificador.seq_qualificador, 3, "MEDIA_SIMPLES", {"anos": [ANO]})
        contexto["erro"] = None
    except Exception as exc:
        contexto["erro"] = exc


@when("obtenho os dados históricos do qualificador em 2063")
def obtem_dados(app, qualificador, contexto):
    from fluxocaixa.services import modelos_economicos_service as modelos

    df = modelos.obter_dados_historicos(
        qualificador.seq_qualificador, date(ANO, 1, 1), date(ANO, 12, 31))
    contexto["soma_serie"] = float(df["valor"].sum()) if len(df) else 0.0


@when("calculo a soma acumulada de janeiro a dezembro de 2063")
def calcula_acumulado(app, qualificador, contexto):
    from fluxocaixa.services import formula_engine

    contexto["acumulado"] = formula_engine._soma_acumulada(
        [qualificador.seq_qualificador], ANO, 1, 12)


@then(parsers.parse("a base é {valor}"))
def base_e(app, contexto, valor):
    assert contexto["erro"] is None, contexto["erro"]
    assert contexto["base"] == pytest.approx(float(valor)), contexto["base"]


@then(parsers.parse("a série soma {valor}"))
def serie_soma(app, contexto, valor):
    assert contexto["soma_serie"] == pytest.approx(float(valor)), \
        contexto["soma_serie"]


@then(parsers.parse("o acumulado é {valor}"))
def acumulado_e(app, contexto, valor):
    assert contexto["acumulado"] == pytest.approx(float(valor)), \
        contexto["acumulado"]


@then("a chamada levanta erro explícito")
def erro_explicito(app, contexto):
    assert contexto["erro"] is not None, (
        f"a base devolveu {contexto.get('base')} em vez de levantar erro — "
        "erro de banco virou projeção zero")
