"""Steps BDD — Decimal/soft-delete/auditoria (infraestrutura-banco R14).

Ilha 2072. Import tardio de `fluxocaixa`.
"""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../infraestrutura-banco/repositorio_decimal.feature")

ANO = 2072
QUAL = "1.72.1"


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from fluxocaixa.models import Lancamento, Pagamento, Qualificador

    db = _db()
    db.session.rollback()
    q = Qualificador.query.filter_by(num_qualificador=QUAL).first()
    if q is not None:
        Lancamento.query.filter_by(seq_qualificador=q.seq_qualificador).delete()
        Pagamento.query.filter_by(seq_qualificador=q.seq_qualificador).delete()
        db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


@given(parsers.parse('um qualificador folha do repositório "{num}"'),
       target_fixture="qualificador")
def qualificador(app, num):
    from fluxocaixa.models import Qualificador

    db = _db()
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    if q is None:
        q = Qualificador(num_qualificador=num,
                         dsc_qualificador="Rubrica Repositório Q12",
                         ind_status='A')
        db.session.add(q)
        db.session.commit()
    return q


def _criar_lancamento(qualificador, valor, origem="Manual"):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.services.dominio_lancamento import resolver_origem, resolver_tipo

    db = _db()
    lanc = Lancamento(
        dat_lancamento=date(ANO, 6, 15),
        seq_qualificador=qualificador.seq_qualificador,
        val_lancamento=Decimal(valor),
        cod_tipo_lancamento=resolver_tipo("Entrada").cod_tipo_lancamento,
        cod_origem_lancamento=resolver_origem(origem).cod_origem_lancamento,
        cod_pessoa_inclusao=1, ind_status='A',
    )
    db.session.add(lanc)
    db.session.commit()
    return lanc


@given(parsers.parse("um lançamento ativo de {valor} em {ano:d}"))
def lancamento_ativo(app, qualificador, valor, ano):
    _criar_lancamento(qualificador, valor)


@given(parsers.parse("um lançamento manual de {valor} em {ano:d}"),
       target_fixture="lancamento")
def lancamento_manual(app, qualificador, valor, ano):
    return _criar_lancamento(qualificador, valor)


@given(parsers.parse("um pagamento ativo de {v1} e um excluído de {v2} em "
                     "junho de {ano:d}"))
def pagamentos(app, qualificador, v1, v2, ano):
    from fluxocaixa.models import Orgao, Pagamento

    db = _db()
    orgao = Orgao.query.filter_by(cod_orgao=70072).first()
    if orgao is None:
        orgao = Orgao(cod_orgao=70072, nom_orgao="Órgão Q12", ind_status='A',
                      cod_pessoa_inclusao=1)
        db.session.add(orgao)
        db.session.commit()
    for valor, status in ((v1, 'A'), (v2, 'I')):
        db.session.add(Pagamento(
            dat_pagamento=date(ano, 6, 10), cod_orgao=orgao.cod_orgao,
            seq_qualificador=qualificador.seq_qualificador,
            val_pagamento=Decimal(valor), ind_status=status,
            cod_pessoa_inclusao=1))
    db.session.commit()


@when(parsers.parse("consulto o total de créditos de {ano:d} no repositório"))
def consulta_total(app, contexto, ano):
    from fluxocaixa.models.lancamento import TIPO_CREDITO
    from fluxocaixa.repositories.lancamento_repository import LancamentoRepository

    contexto["total"] = LancamentoRepository().get_total_by_tipo_and_period(
        TIPO_CREDITO, ano)


@when(parsers.parse("consulto o comparativo de pagamentos por qualificador de "
                    "{ano:d}"))
def consulta_comparativo(app, contexto, qualificador, ano):
    from fluxocaixa.repositories.pagamento_repository import PagamentoRepository

    linhas = PagamentoRepository().get_comparative_by_qualificador(
        anos=[ano], meses=[6])
    contexto["soma"] = sum(
        float(total) for (dsc, _a, _m, total) in linhas
        if dsc == qualificador.dsc_qualificador)


@when(parsers.parse("edito o valor do lançamento para {valor}"))
def edita_lancamento(app, lancamento, valor):
    from fluxocaixa.domain import LancamentoCreate
    from fluxocaixa.services.lancamento_service import update_lancamento

    update_lancamento(lancamento.seq_lancamento, LancamentoCreate(
        dat_lancamento=lancamento.dat_lancamento,
        seq_qualificador=lancamento.seq_qualificador,
        val_lancamento=Decimal(valor),
        cod_tipo_lancamento=lancamento.cod_tipo_lancamento,
        cod_origem_lancamento=lancamento.cod_origem_lancamento,
        seq_conta=None))


@when("inspeciono os imports dos repositórios")
def inspeciona_imports(app, contexto):
    raiz = Path(__file__).resolve().parents[3] / "fluxocaixa" / "repositories"
    ofensores = []
    for arquivo in raiz.glob("*.py"):
        conteudo = arquivo.read_text(encoding="utf-8")
        if "from ..auth" in conteudo or "auth.contexto" in conteudo:
            ofensores.append(arquivo.name)
    contexto["ofensores"] = ofensores


@then(parsers.parse("o total é Decimal de valor {valor}"))
def total_decimal(contexto, valor):
    total = contexto["total"]
    assert isinstance(total, Decimal), (
        f"{type(total).__name__} — dinheiro degradado para float na leitura")
    assert total == Decimal(valor)


@then(parsers.parse("o comparativo soma {valor}"))
def comparativo_soma(contexto, valor):
    assert contexto["soma"] == pytest.approx(float(valor)), (
        f"{contexto['soma']} — pagamento excluído entrou no comparativo")


@then("o lançamento tem data e autor de alteração preenchidos")
def auditoria_preenchida(app, lancamento):
    _db().session.expire_all()
    from fluxocaixa.models import Lancamento

    atual = _db().session.get(Lancamento, lancamento.seq_lancamento)
    assert atual.dat_alteracao is not None, "edição sem rastro de quando"
    assert atual.cod_pessoa_alteracao is not None, "edição sem rastro de quem"


@then("nenhum repositório importa da camada de autenticação")
def sem_import_auth(contexto):
    assert contexto["ofensores"] == [], contexto["ofensores"]
