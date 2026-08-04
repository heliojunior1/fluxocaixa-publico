"""Steps BDD — importação exige folha ativa (spec automacao-lancamentos R18).

Ilha 2070. Import tardio de `fluxocaixa`.
"""
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../automacao-lancamentos/importacao_folha_ativa.feature")

ANO = 2070
CODIGOS = ("1.71", "1.71.1", "1.71.2", "1.71.3", "1.71.4", "1.71.9")


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
    quals = Qualificador.query.filter(
        Qualificador.num_qualificador.in_(CODIGOS)).all()
    for q in quals:
        Lancamento.query.filter_by(seq_qualificador=q.seq_qualificador).delete()
    # filhos antes dos pais (FK de hierarquia)
    for q in sorted(quals, key=lambda x: -len(x.num_qualificador)):
        db.session.delete(q)
    db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


def _criar_qualificador(num, dsc, ind_status='A', pai=None):
    from fluxocaixa.models import Qualificador

    db = _db()
    q = Qualificador(num_qualificador=num, dsc_qualificador=dsc,
                     ind_status=ind_status,
                     cod_qualificador_pai=pai.seq_qualificador if pai else None)
    db.session.add(q)
    db.session.commit()
    return q


@given(parsers.parse('um qualificador folha inativo "{num}" descrito como '
                     '"{dsc}"'))
def folha_inativa(app, num, dsc):
    _criar_qualificador(num, dsc, ind_status='I')


@given(parsers.parse('um qualificador pai "{num_pai}" descrito como "{dsc}" '
                     'com filho ativo "{num_filho}"'))
def pai_com_filho(app, num_pai, dsc, num_filho):
    pai = _criar_qualificador(num_pai, dsc)
    _criar_qualificador(num_filho, f"Filho {num_filho}", pai=pai)


@given(parsers.parse('duas rubricas ativas "{n1}" e "{n2}" descritas como '
                     '"{dsc}"'))
def rubricas_ambiguas(app, n1, n2, dsc):
    _criar_qualificador(n1, dsc)
    _criar_qualificador(n2, dsc)


@given(parsers.parse('um qualificador folha ativo "{num}" descrito como '
                     '"{dsc}"'))
def folha_ativa(app, num, dsc):
    _criar_qualificador(num, dsc)


@when(parsers.parse('importo uma planilha com uma linha para "{dsc}"'))
def importa(app, contexto, dsc):
    from fluxocaixa.services.lancamento_service import import_lancamentos_service

    csv = (f"Data;Qualificador;Tipo;Valor (R$)\n"
           f"{ANO}-06-15;{dsc};Entrada;1234.56\n").encode()
    contexto["resultado"] = import_lancamentos_service(csv, "planilha.csv")


@then(parsers.parse('a importação recusa a linha citando "{trecho}"'))
def recusa_citando(contexto, trecho):
    erros = contexto["resultado"].get("erros", [])
    assert erros, f"nenhum erro reportado: {contexto['resultado']}"
    assert any(trecho.lower() in e.lower() for e in erros), erros


@then(parsers.parse('a importação recusa a linha como ambígua citando "{t1}" e "{t2}"'))
def recusa_citando_dois(contexto, t1, t2):
    erros = contexto["resultado"].get("erros", [])
    assert erros, f"nenhum erro reportado: {contexto['resultado']}"
    assert any(t1 in e and t2 in e for e in erros), (
        f"a ambiguidade não citou os dois códigos: {erros}")


@then(parsers.parse("nenhum lançamento de {ano:d} foi gravado"))
def nenhum_lancamento(app, ano):
    from datetime import date

    from fluxocaixa.models import Lancamento

    _db().session.expire_all()
    lancs = Lancamento.query.filter(
        Lancamento.dat_lancamento.between(date(ano, 1, 1), date(ano, 12, 31)),
        Lancamento.ind_status == 'A').all()
    assert lancs == [], (
        f"{len(lancs)} lançamentos gravados — a planilha furou a regra de "
        "folha ativa / ambiguidade")


@then(parsers.parse('um lançamento de {ano:d} foi gravado com origem '
                    '"{origem}"'))
def lancamento_gravado(app, ano, origem):
    from datetime import date

    from fluxocaixa.models import Lancamento
    from fluxocaixa.services.dominio_lancamento import resolver_origem

    _db().session.expire_all()
    lancs = Lancamento.query.filter(
        Lancamento.dat_lancamento.between(date(ano, 1, 1), date(ano, 12, 31)),
        Lancamento.ind_status == 'A').all()
    assert len(lancs) == 1, len(lancs)
    assert lancs[0].cod_origem_lancamento == \
        resolver_origem(origem).cod_origem_lancamento
