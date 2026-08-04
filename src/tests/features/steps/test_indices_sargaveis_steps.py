"""Steps BDD — índices e filtros sargáveis (spec infraestrutura-banco R12).

Ilha 2064 (ano bissexto — 29/02 existe). Import tardio de `fluxocaixa`.
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../infraestrutura-banco/indices_sargaveis.feature")

ANO = 2064
QUAL = "1.64.1"

INDICES_ESPERADOS = {
    "ix_flc_lancamento_status_data",
    "ix_flc_lancamento_qualificador_data",
    "ix_flc_lancamento_conta_data",
    "ix_flc_lancamento_etl_staging",
}


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


@given("um qualificador folha de índice", target_fixture="qualificador")
def qualificador(app):
    from fluxocaixa.models import Qualificador

    db = _db()
    q = Qualificador.query.filter_by(num_qualificador=QUAL).first()
    if q is None:
        q = Qualificador(num_qualificador=QUAL,
                         dsc_qualificador=f"Rubrica índice {QUAL}",
                         ind_status='A')
        db.session.add(q)
        db.session.commit()
    return q


def _criar(qualificador, valor, dia):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.services.dominio_lancamento import resolver_origem, resolver_tipo

    db = _db()
    db.session.add(Lancamento(
        dat_lancamento=dia,
        seq_qualificador=qualificador.seq_qualificador,
        val_lancamento=Decimal(valor),
        cod_tipo_lancamento=resolver_tipo("Entrada").cod_tipo_lancamento,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        cod_pessoa_inclusao=1, ind_status='A',
    ))
    db.session.commit()


@given(parsers.parse("lançamentos ativos de {valor} em 01/01, 15/06 e 31/12 de "
                     "{ano:d}"))
def lancamentos_bordas(app, qualificador, valor, ano):
    for dia in (date(ano, 1, 1), date(ano, 6, 15), date(ano, 12, 31)):
        _criar(qualificador, valor, dia)


@given(parsers.parse("um lançamento ativo de {valor} em 31/12 de {ano:d}"))
def lancamento_ano_anterior(app, qualificador, valor, ano):
    _criar(qualificador, valor, date(ano, 12, 31))


@given(parsers.parse("um lançamento ativo de {valor} em 29/02 de {ano:d}"))
def lancamento_bissexto(app, qualificador, valor, ano):
    _criar(qualificador, valor, date(ano, 2, 29))


@when("inspeciono os índices de flc_lancamento")
def inspeciona_indices(app, contexto):
    from sqlalchemy import inspect

    from fluxocaixa.models.base import engine

    contexto["indices"] = {
        i["name"] for i in inspect(engine).get_indexes("flc_lancamento")}


@when(parsers.parse("consulto o total de créditos do ano {ano:d}"))
def total_do_ano(app, contexto, ano):
    from fluxocaixa.models.lancamento import TIPO_CREDITO
    from fluxocaixa.repositories.lancamento_repository import LancamentoRepository

    contexto["total"] = LancamentoRepository().get_total_by_tipo_and_period(
        TIPO_CREDITO, ano)


@when(parsers.parse("consulto o total de créditos de fevereiro de {ano:d}"))
def total_de_fevereiro(app, contexto, ano):
    from fluxocaixa.models.lancamento import TIPO_CREDITO
    from fluxocaixa.repositories.lancamento_repository import LancamentoRepository

    contexto["total"] = LancamentoRepository().get_total_by_tipo_and_period(
        TIPO_CREDITO, ano, meses=[2])


@when("compilo a consulta de total por tipo e ano")
def compila_consulta(app, contexto, monkeypatch):
    from fluxocaixa.models.lancamento import TIPO_CREDITO
    from fluxocaixa.repositories.lancamento_repository import LancamentoRepository

    repo = LancamentoRepository()
    capturado = {}
    original = repo.session.query

    class _Sonda:
        def __init__(self, query):
            self._query = query

        def filter(self, *args, **kwargs):
            return _Sonda(self._query.filter(*args, **kwargs))

        def scalar(self):
            capturado["sql"] = str(self._query.statement.compile(
                compile_kwargs={"literal_binds": False}))
            return None

    monkeypatch.setattr(
        repo.session, "query", lambda *a, **k: _Sonda(original(*a, **k)))
    repo.get_total_by_tipo_and_period(TIPO_CREDITO, ANO)
    contexto["sql"] = capturado["sql"]


@then("os quatro índices declarados existem")
def indices_existem(app, contexto):
    faltando = INDICES_ESPERADOS - contexto["indices"]
    assert not faltando, f"índices ausentes: {sorted(faltando)}"


@then(parsers.parse("o total é {valor}"))
def total_e(app, contexto, valor):
    assert contexto["total"] == pytest.approx(float(valor)), contexto["total"]


@then("o SQL filtra por faixa de datas e não contém extract no WHERE")
def sql_sargavel(app, contexto):
    sql = contexto["sql"].lower()
    assert "between" in sql, sql
    assert "extract" not in sql, (
        f"filtro de período com extract — não sargável:\n{contexto['sql']}")
