"""Steps BDD — sessão revalidada e revogável (spec controle-acesso R13/R3).

Change: sessao-revalidada-e-revogavel.
"""
import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../controle-acesso/sessao_revogavel.feature")


@pytest.fixture()
def contexto():
    return {}


def _criar_usuario(login, senha):
    from fluxocaixa.auth.service import gerar_hash
    from fluxocaixa.models import Perfil, UsuarioPerfil
    from fluxocaixa.models.base import db
    from fluxocaixa.models.usuario import Usuario

    db.session.rollback()
    existente = Usuario.query.filter_by(nom_usuario=login).first()
    if existente:
        UsuarioPerfil.query.filter_by(seq_usuario=existente.seq_usuario).delete()
        db.session.delete(existente)
        db.session.commit()
    usuario = Usuario(
        nom_usuario=login, nom_completo=f"Usuário {login}",
        txt_hash_senha=gerar_hash(senha), ind_troca_senha='N', ind_status='A',
    )
    db.session.add(usuario)
    db.session.commit()
    perfil = Perfil.query.filter_by(cod_perfil='CONSULTA').first()
    db.session.add(UsuarioPerfil(seq_usuario=usuario.seq_usuario,
                                 seq_perfil=perfil.seq_perfil))
    db.session.commit()
    return usuario


def _logar(app, login, senha):
    tc = TestClient(app, follow_redirects=False, headers={"Accept": "text/html"})
    resp = tc.post("/login", data={"usuario": login, "senha": senha})
    assert resp.status_code in (302, 303), f"login falhou: {resp.status_code}"
    return tc


@given(parsers.parse('um usuário ativo "{login}" com senha "{senha}"'))
def usuario_ativo(app, contexto, login, senha):
    _criar_usuario(login, senha)
    contexto["senha"] = senha


@given(parsers.parse('estou autenticado como "{login}"'))
def autenticado(app, contexto, login):
    contexto["cliente"] = _logar(app, login, contexto["senha"])
    contexto["login"] = login


@given(parsers.parse('tenho uma segunda sessão aberta de "{login}"'))
def segunda_sessao(app, contexto, login):
    contexto["cliente2"] = _logar(app, login, contexto["senha"])


@when(parsers.parse('o usuário "{login}" é desativado'))
def desativa_usuario(app, login):
    from fluxocaixa.models.base import db
    from fluxocaixa.models.usuario import Usuario

    usuario = Usuario.query.filter_by(nom_usuario=login).first()
    usuario.ind_status = 'I'
    db.session.commit()


@when(parsers.parse('"{login}" troca a senha para "{nova}"'))
def troca_senha(contexto, login, nova):
    resp = contexto["cliente"].post("/trocar-senha", data={
        "senha_atual": contexto["senha"],
        "nova_senha": nova,
        "confirmacao": nova,
    })
    assert resp.status_code in (200, 302, 303), resp.text[:200]


@when("passa mais tempo que o limite de inatividade")
def passa_muito_tempo(monkeypatch):
    """Relógio injetado — nada de `sleep` de uma hora na suíte."""
    from fluxocaixa.auth import dependencies

    limite = dependencies.INATIVIDADE_MAX_SEGUNDOS
    original = dependencies.time.time
    monkeypatch.setattr(dependencies.time, "time",
                        lambda: original() + limite + 60)


@when("passa menos tempo que o limite de inatividade")
def passa_pouco_tempo(monkeypatch):
    from fluxocaixa.auth import dependencies

    original = dependencies.time.time
    monkeypatch.setattr(dependencies.time, "time", lambda: original() + 5)


@when("a segunda sessão acessa outra tela")
def segunda_acessa(contexto):
    contexto["resp"] = contexto["cliente2"].get("/saldos")


@when("acesso outra tela")
def acesso_outra_tela(contexto):
    contexto["resp"] = contexto["cliente"].get("/saldos")


@then("o acesso é recusado")
def acesso_recusado(contexto):
    resp = contexto["resp"]
    assert resp.status_code in (302, 401, 403), (
        f"a sessão continuou válida: {resp.status_code}")
    if resp.status_code == 302:
        assert "/login" in resp.headers.get("location", "")


@then("o acesso é permitido")
def acesso_permitido(contexto):
    assert contexto["resp"].status_code == 200, contexto["resp"].status_code
