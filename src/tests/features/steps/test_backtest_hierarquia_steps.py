"""Steps BDD — backtest: métrica zero e hierarquia profunda (previsao R16).

Treino 2062 / teste 2063 — o recorte por `qualificadores_ids` isola das
outras ilhas. Import tardio de `fluxocaixa`.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../previsao/backtest_hierarquia.feature")

CODIGOS = ("1.75", "1.75.1", "1.75.1.1")


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
    for q in sorted(quals, key=lambda x: -len(x.num_qualificador)):
        db.session.delete(q)
    db.session.execute(text(
        "DELETE FROM flc_backtest_recomendacao WHERE cod_modelo = 'Q16_TESTE'"))
    db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


@given("uma recomendação de backtest gravada com viés zero")
def recomendacao_vies_zero(app):
    from fluxocaixa.models import Qualificador

    db = _db()
    q = Qualificador.query.filter_by(ind_status='A').first()
    db.session.execute(text(
        """INSERT INTO flc_backtest_recomendacao
           (seq_qualificador, cod_modelo, val_mape, val_wmape, val_bias,
            anos_teste, dat_execucao)
           VALUES (:q, 'Q16_TESTE', 5.0, 4.0, 0.0, '[]', '2069-01-01')"""),
        {"q": q.seq_qualificador})
    db.session.commit()


@given(parsers.parse('uma árvore "{raiz}" com bloco "{bloco}" e folha '
                     '"{folha}" com histórico'), target_fixture="arvore")
def arvore_profunda(app, raiz, bloco, folha):
    from fluxocaixa.models import Lancamento, Qualificador
    from fluxocaixa.services.dominio_lancamento import resolver_origem, resolver_tipo

    db = _db()
    pai = None
    nos = {}
    for codigo in (raiz, bloco, folha):
        q = Qualificador(
            num_qualificador=codigo, dsc_qualificador=f"Nó {codigo}",
            cod_qualificador_pai=pai.seq_qualificador if pai else None,
            ind_status='A')
        db.session.add(q)
        db.session.commit()
        nos[codigo] = q
        pai = q

    folha_q = nos[folha]
    for ano in (2062, 2063):
        for mes in range(1, 13):
            db.session.add(Lancamento(
                dat_lancamento=date(ano, mes, 15),
                seq_qualificador=folha_q.seq_qualificador,
                val_lancamento=Decimal("100.00"),
                cod_tipo_lancamento=resolver_tipo("Entrada").cod_tipo_lancamento,
                cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
                cod_pessoa_inclusao=1, ind_status='A'))
    db.session.commit()
    return nos


@when("leio as recomendações do backtest")
def le_recomendacoes(app, contexto):
    from fluxocaixa.services.backtest_service import obter_recomendacoes

    contexto["recomendacoes"] = obter_recomendacoes()


@when("executo o backtest da folha com média histórica")
def executa_backtest(app, contexto, arvore):
    from fluxocaixa.services.backtest_service import executar_backtest

    folha = arvore["1.75.1.1"]
    contexto["resultado"] = executar_backtest(
        anos_treino=[2062], anos_teste=[2063], modelos=["MEDIA_HISTORICA"],
        qualificadores_ids=[folha.seq_qualificador])


@then("o viés da recomendação é 0.0, não ausência")
def vies_zero(contexto):
    linhas = [r for r in contexto["recomendacoes"].values()
              if r["modelo"] == "Q16_TESTE"]
    assert linhas, "recomendação de teste não encontrada"
    assert linhas[0]["bias"] == 0.0, (
        f"{linhas[0]['bias']!r} — viés 0.0 virou 'sem dado' (sentinela falsy)")


def _agregado(contexto, arvore, codigo):
    seq = arvore[codigo].seq_qualificador
    pais = contexto["resultado"].get("resultados_pai", [])
    return next((p for p in pais if p["seq_qualificador"] == seq), None)


@then(parsers.parse('o agregado do bloco "{codigo}" contém métricas'))
def agregado_bloco(contexto, arvore, codigo):
    agregado = _agregado(contexto, arvore, codigo)
    assert agregado is not None and agregado.get("modelos"), (
        f"o agregado de {codigo} ficou vazio — a agregação não alcançou a "
        "folha de nível 3")


@then(parsers.parse('o agregado da raiz "{codigo}" também contém métricas'))
def agregado_raiz(contexto, arvore, codigo):
    agregado = _agregado(contexto, arvore, codigo)
    assert agregado is not None and agregado.get("modelos"), (
        f"o agregado de {codigo} ficou vazio — o nível 1 só enxergava os "
        "filhos diretos de nível 2")
