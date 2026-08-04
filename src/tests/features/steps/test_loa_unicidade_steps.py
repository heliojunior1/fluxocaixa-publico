"""Steps BDD — unicidade da LOA e serviço próprio (spec cadastros-nucleo R24).

Ilha 2065. Import tardio de `fluxocaixa`.
"""
from decimal import Decimal
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../cadastros-nucleo/loa_unicidade.feature")

ANO = 2065
QUAL = "1.67.1"


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from fluxocaixa.models import Loa, Qualificador

    db = _db()
    db.session.rollback()
    q = Qualificador.query.filter_by(num_qualificador=QUAL).first()
    if q is not None:
        Loa.query.filter_by(seq_qualificador=q.seq_qualificador).delete()
        db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


@given("um qualificador folha da LOA", target_fixture="qualificador")
def qualificador(app):
    from fluxocaixa.models import Qualificador

    db = _db()
    q = Qualificador.query.filter_by(num_qualificador=QUAL).first()
    if q is None:
        q = Qualificador(num_qualificador=QUAL,
                         dsc_qualificador=f"Rubrica LOA {QUAL}", ind_status='A')
        db.session.add(q)
        db.session.commit()
    return q


@given(parsers.parse("um registro ativo de LOA de {valor} para o ano {ano:d}"))
def registro_ativo(app, qualificador, valor, ano):
    from fluxocaixa.services import loa_service

    loa_service.upsert_loa(ano, qualificador.seq_qualificador, Decimal(valor))
    _db().session.commit()


@when(parsers.parse("gravo a LOA de {valor} para o ano {ano:d}"))
def grava(app, qualificador, valor, ano):
    from fluxocaixa.services import loa_service

    loa_service.upsert_loa(ano, qualificador.seq_qualificador, Decimal(valor))
    _db().session.commit()


@when(parsers.parse("submeto o formulário da LOA com {valor} para o ano "
                    "{ano:d} duas vezes"))
def duplo_submit(client, qualificador, valor, ano):
    dados = {"num_ano": str(ano),
             "seq_qualificador": str(qualificador.seq_qualificador),
             "val_loa": valor.replace(".", ",")}
    for _ in range(2):
        resp = client.post("/loa/add", data=dados, follow_redirects=False)
        assert resp.status_code in (302, 303), resp.status_code


@when("insiro por fora do serviço uma segunda linha ativa para a mesma chave")
def insere_por_fora(app, qualificador, contexto):
    from sqlalchemy.exc import IntegrityError

    from fluxocaixa.models import Loa

    db = _db()
    db.session.add(Loa(num_ano=ANO,
                       seq_qualificador=qualificador.seq_qualificador,
                       val_loa=Decimal("999.00"), ind_status='A'))
    try:
        db.session.commit()
        contexto["erro_integridade"] = None
    except IntegrityError as exc:
        db.session.rollback()
        contexto["erro_integridade"] = exc


@when("inspeciono os imports dos módulos de serviço")
def inspeciona_imports(app, contexto):
    raiz = Path(__file__).resolve().parents[3] / "fluxocaixa" / "services"
    ofensores = []
    for arquivo in raiz.rglob("*.py"):
        conteudo = arquivo.read_text(encoding="utf-8")
        if "from ..web" in conteudo or "from fluxocaixa.web" in conteudo:
            ofensores.append(arquivo.name)
    contexto["ofensores"] = ofensores


@then(parsers.parse("existe um único registro ativo de {ano:d} com valor "
                    "{valor}"))
def um_registro(app, qualificador, ano, valor):
    from fluxocaixa.models import Loa

    _db().session.expire_all()
    registros = Loa.query.filter_by(
        num_ano=ano, seq_qualificador=qualificador.seq_qualificador,
        ind_status='A').all()
    assert len(registros) == 1, (
        f"{len(registros)} registros ativos — a chave duplicou e toda soma "
        "da LOA dobraria")
    assert registros[0].val_loa == Decimal(valor)


@then("o banco recusa com violação de unicidade")
def banco_recusa(contexto):
    assert contexto["erro_integridade"] is not None, (
        "o banco aceitou a segunda linha ativa — sem constraint, a corrida "
        "que escapar ao check-then-insert duplica a LOA")


@then("nenhum módulo de serviço importa da camada web")
def sem_import_da_web(contexto):
    assert contexto["ofensores"] == [], (
        f"serviço importando da web: {contexto['ofensores']}")
