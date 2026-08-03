"""Steps BDD — escape de texto de cadastro (spec relatorios R21).

Change: escapar-html-dinamico-relatorios.

⚠️ O escape do RELATÓRIO é do lado do cliente (`escHtml`); quem o afere é o E2E
Playwright. Aqui fica a metade que É do servidor: as telas renderizadas por
Jinja escapam a descrição, e o `tojson` do DFC entrega a descrição como DADO.
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../relatorios/escape_html.feature")


@pytest.fixture()
def contexto():
    return {}


# --------------------------------------------------------------------- Dado


@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(777)


@given(parsers.parse('um qualificador "{num}" com descrição "{descricao}"'))
def qualificador_com_descricao(app, contexto, num, descricao):
    from fluxocaixa.models import Qualificador
    from fluxocaixa.models.base import db

    existente = Qualificador.query.filter_by(num_qualificador=num).first()
    if existente is None:
        existente = Qualificador(
            num_qualificador=num,
            dsc_qualificador=descricao,
            ind_status='A',
        )
        db.session.add(existente)
        db.session.commit()
    contexto["qualificador"] = existente
    contexto["descricao"] = descricao


@given(parsers.parse("um lançamento fictício de {valor:f} nesse qualificador"))
def lancamento_no_qualificador(app, contexto, valor):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.base import db
    from fluxocaixa.services.dominio_lancamento import resolver_origem, resolver_tipo

    db.session.add(Lancamento(
        dat_lancamento=date(2026, 7, 1),
        seq_qualificador=contexto["qualificador"].seq_qualificador,
        val_lancamento=Decimal(str(valor)),
        cod_tipo_lancamento=resolver_tipo("Entrada").cod_tipo_lancamento,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        cod_pessoa_inclusao=777,
        ind_status='A',
    ))
    db.session.commit()


# -------------------------------------------------------------------- Quando


@when("abro a tela de qualificadores")
def abre_qualificadores(client, contexto):
    contexto["resp"] = client.get("/qualificadores")


@when("consulto os dados do relatório DFC")
def consulta_dfc(client, contexto):
    contexto["resp"] = client.get("/relatorios/dfc?ano=2026")


# --------------------------------------------------------------------- Então


@then("a marcação aparece escapada no HTML")
def marcacao_escapada(contexto):
    corpo = contexto["resp"].text
    assert "&lt;img" in corpo or "&lt;b&gt;" in corpo, (
        "a descrição não aparece escapada — o autoescape do Jinja foi desligado?")


@then("a marcação não aparece crua no HTML")
def marcacao_nao_crua(contexto):
    corpo = contexto["resp"].text
    bruta = contexto["descricao"]
    assert bruta not in corpo, (
        "a descrição foi renderizada CRUA — alguém aplicou `|safe` sobre texto "
        "de cadastro (spec relatorios R21)")


@then("a descrição chega íntegra como valor de dado")
def descricao_como_dado(contexto):
    """`tojson` do Jinja escapa `<`, `>`, `&` e `'` — o dado chega inteiro e inerte."""
    corpo = contexto["resp"].text
    assert contexto["descricao"] not in corpo, (
        "a descrição apareceu crua no HTML da página")
    assert "\\u003c" in corpo or "&lt;" in corpo, (
        "o dado não foi serializado de forma inerte")
