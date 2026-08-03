"""Steps BDD — proteção CSRF (spec controle-acesso R12).

Change: protecao-csrf-global.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../controle-acesso/csrf.feature")

CABECALHO = "X-CSRF-Token"


@pytest.fixture()
def contexto():
    return {}


@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto, contexto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(777)
    tc = TestClient(app)
    resp = tc.post("/login", data={"usuario": "admin", "senha": _admin_pronto},
                   follow_redirects=False)
    assert resp.status_code in (302, 303)
    contexto["cliente"] = tc
    marcador = 'name="csrf-token" content="'
    corpo = tc.get("/").text
    contexto["token"] = corpo.split(marcador, 1)[1].split('"', 1)[0]


@given(parsers.parse("existe um lançamento fictício de {valor:f}"))
def lancamento_ficticio(app, contexto, valor):
    from fluxocaixa.models import Lancamento, Qualificador
    from fluxocaixa.models.base import db
    from fluxocaixa.services.dominio_lancamento import resolver_origem, resolver_tipo

    qualificador = Qualificador.query.filter_by(ind_status='A').first()
    lancamento = Lancamento(
        dat_lancamento=date(2026, 7, 1),
        seq_qualificador=qualificador.seq_qualificador,
        val_lancamento=Decimal(str(valor)),
        cod_tipo_lancamento=resolver_tipo("Entrada").cod_tipo_lancamento,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        cod_pessoa_inclusao=777, ind_status='A',
    )
    db.session.add(lancamento)
    db.session.commit()
    contexto["seq"] = lancamento.seq_lancamento


def _excluir(contexto, *, headers=None):
    # `headers=` explícito impede o wrapper da suíte de anexar o token: estes
    # cenários testam justamente a AUSÊNCIA ou a invalidez dele.
    cabecalhos = {CABECALHO: ""} if headers is None else dict(headers)
    contexto["resp"] = contexto["cliente"].post(
        f"/saldos/delete/{contexto['seq']}", headers=cabecalhos,
        follow_redirects=False)


@when("envio a exclusão do lançamento sem o token")
def exclui_sem_token(contexto):
    _excluir(contexto)


@when("envio a exclusão do lançamento com o token de outra sessão")
def exclui_token_alheio(contexto):
    _excluir(contexto, headers={CABECALHO: "token-de-outra-sessao-qualquer"})


@when("envio a exclusão do lançamento com o token no cabeçalho")
def exclui_token_valido(contexto):
    _excluir(contexto, headers={CABECALHO: contexto["token"]})


@when("envio a exclusão do lançamento com token válido e origem externa")
def exclui_origem_externa(contexto):
    _excluir(contexto, headers={
        CABECALHO: contexto["token"],
        "Origin": "https://exemplo-externo.test",
    })


@when("a sessão perde o token e envio a exclusão do lançamento")
def sessao_sem_token(app, contexto):
    """Sessão autenticada sem token deve falhar FECHADO.

    Deixar passar seria a brecha exata que o token cobre: bastaria a sessão
    nunca ter renderizado uma página para a validação ser pulada.
    """
    from fluxocaixa.auth import csrf

    original = csrf.CHAVE_SESSAO
    csrf.CHAVE_SESSAO = "csrf_token_inexistente"
    try:
        _excluir(contexto, headers={CABECALHO: contexto["token"]})
    finally:
        csrf.CHAVE_SESSAO = original


@then(parsers.parse("recebo status {status:d}"))
def recebo_status(contexto, status):
    assert contexto["resp"].status_code == status, (
        f"veio {contexto['resp'].status_code}: {contexto['resp'].text[:200]}")


@then("o lançamento continua ativo")
def lancamento_ativo(app, contexto):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.base import db

    db.session.expire_all()
    assert Lancamento.query.get(contexto["seq"]).ind_status == 'A'


@then("a exclusão é aplicada")
def exclusao_aplicada(app, contexto):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.base import db

    assert contexto["resp"].status_code in (200, 302, 303), contexto["resp"].text[:200]
    db.session.expire_all()
    assert Lancamento.query.get(contexto["seq"]).ind_status == 'I'
