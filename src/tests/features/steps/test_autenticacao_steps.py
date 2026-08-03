"""Steps BDD — autenticação e proteção de rotas (spec controle-acesso R1–R6)."""
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../controle-acesso/autenticacao.feature")


# --------------------------------------------------------------------------
# Fixtures locais
# --------------------------------------------------------------------------

@pytest.fixture()
def navegador(app):
    """Cliente HTTP por cenário, sem seguir redirects (para inspecioná-los).

    Envia Accept de navegador — o handler decide entre redirect (HTML) e 401 (API).
    """
    return TestClient(app, follow_redirects=False, headers={"Accept": "text/html"})


@pytest.fixture()
def contexto():
    return {}


def _criar_usuario(login, senha, ativo=True, troca_pendente=False):
    from fluxocaixa.auth.service import gerar_hash
    from fluxocaixa.models import Perfil, UsuarioPerfil
    from fluxocaixa.models.base import db
    from fluxocaixa.models.usuario import Usuario

    db.session.rollback()  # limpa qualquer estado envenenado de cenário anterior
    existente = Usuario.query.filter_by(nom_usuario=login).first()
    if existente:
        UsuarioPerfil.query.filter_by(seq_usuario=existente.seq_usuario).delete()
        db.session.delete(existente)
        db.session.commit()  # INSERT do mesmo login não pode ir no mesmo flush
    usuario = Usuario(
        nom_usuario=login,
        nom_completo=f"Usuário {login}",
        txt_hash_senha=gerar_hash(senha),
        ind_troca_senha='S' if troca_pendente else 'N',
        ind_status='A' if ativo else 'I',
    )
    db.session.add(usuario)
    db.session.commit()

    # Estes cenários testam SESSÃO, não permissões: perfil CONSULTA basta
    # para navegar nas rotas usadas (/ e /saldos).
    consulta = Perfil.query.filter_by(cod_perfil='CONSULTA').first()
    db.session.add(UsuarioPerfil(seq_usuario=usuario.seq_usuario, seq_perfil=consulta.seq_perfil))
    db.session.commit()


def _hash_de(login):
    from fluxocaixa.models.usuario import Usuario

    return Usuario.query.filter_by(nom_usuario=login).first().txt_hash_senha


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given(parsers.parse('um usuário ativo "{login}" com senha "{senha}"'))
def usuario_ativo(app, login, senha):
    _criar_usuario(login, senha, ativo=True)


@given(parsers.parse('um usuário inativo "{login}" com senha "{senha}"'))
def usuario_inativo(app, login, senha):
    _criar_usuario(login, senha, ativo=False)


@given(parsers.parse('um usuário "{login}" com senha inicial "{senha}" e troca de senha pendente'))
def usuario_troca_pendente(app, login, senha):
    _criar_usuario(login, senha, ativo=True, troca_pendente=True)


@given(parsers.parse('estou autenticado como "{login}" com senha "{senha}"'))
def autenticado(navegador, login, senha):
    resp = navegador.post("/login", data={"usuario": login, "senha": senha})
    assert resp.status_code in (302, 303), f"login falhou: {resp.status_code}"


@given("o hash de senha atual do admin registrado")
def hash_admin_registrado(app, contexto):
    contexto["hash_admin"] = _hash_de("admin")


@given("o ambiente não é de desenvolvimento")
def ambiente_nao_dev(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when(parsers.parse('envio login "{login}" com senha "{senha}"'))
def envia_login(navegador, contexto, login, senha):
    contexto["resp"] = navegador.post("/login", data={"usuario": login, "senha": senha})


@when(parsers.parse('envio login "{login}" com senha "{senha}" com destino "{destino}"'))
def envia_login_com_destino(navegador, contexto, login, senha, destino):
    contexto["resp"] = navegador.post(
        f"/login?next={quote(destino, safe='/')}",
        data={"usuario": login, "senha": senha},
    )


@when(parsers.parse('acesso "{caminho}" sem estar autenticado'))
def acessa_anonimo(app, contexto, caminho):
    cliente = TestClient(app, follow_redirects=False, headers={"Accept": "text/html"})
    contexto["resp"] = cliente.get(caminho)


@when(parsers.parse('acesso "{caminho}" com um cookie de sessão adulterado'))
def acessa_cookie_adulterado(app, contexto, caminho):
    cliente = TestClient(app, follow_redirects=False, headers={"Accept": "text/html"})
    cliente.cookies.set("session", "adulterado.assinatura-invalida")
    contexto["resp"] = cliente.get(caminho)


@when(parsers.parse('acesso "{caminho}" na mesma sessão'))
def acessa_na_sessao(navegador, contexto, caminho):
    contexto["resp"] = navegador.get(caminho)


@when(parsers.parse('aciono "{caminho}" por POST na mesma sessão'))
def aciona_post_na_sessao(navegador, contexto, caminho):
    """As rotas destrutivas de banco só existem em POST (controle-acesso R6)."""
    contexto["resp"] = navegador.post(caminho, data={"confirmado": "true"})


@when("aciono o logout")
def aciona_logout(navegador, contexto):
    contexto["resp"] = navegador.post("/logout")


@when(parsers.parse('troco a senha de "{atual}" para "{nova}"'))
def troca_senha(navegador, contexto, atual, nova):
    contexto["resp"] = navegador.post(
        "/trocar-senha",
        data={"senha_atual": atual, "nova_senha": nova, "confirmacao": nova},
    )


@when("o seed de domínio executa novamente")
def executa_seed_dominio(app):
    from fluxocaixa.services.seed_dominio import seed_dominio

    seed_dominio()


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('sou redirecionado para "{destino}"'))
@then(parsers.parse('recebo redirect para "{destino}"'))
def verifica_redirect(contexto, destino):
    resp = contexto["resp"]
    assert resp.status_code in (302, 303), f"esperava redirect, veio {resp.status_code}"
    assert resp.headers["location"] == destino, resp.headers["location"]


@then("a sessão está estabelecida")
def sessao_estabelecida(navegador):
    resp = navegador.get("/")
    assert resp.status_code == 200


@then(parsers.parse('permaneço na tela de login com a mensagem "{mensagem}"'))
def tela_login_com_mensagem(contexto, mensagem):
    resp = contexto["resp"]
    assert resp.status_code == 200
    assert mensagem in resp.text


@then("o recurso é servido com sucesso")
def recurso_servido(contexto):
    assert contexto["resp"].status_code == 200


@then(parsers.parse('a troca é rejeitada com a mensagem "{mensagem}"'))
def troca_rejeitada(contexto, mensagem):
    resp = contexto["resp"]
    assert resp.status_code == 200, f"esperava re-render 200, veio {resp.status_code}"
    assert mensagem in resp.text


@then("o hash da senha do admin permanece o mesmo")
def hash_admin_intacto(contexto):
    assert _hash_de("admin") == contexto["hash_admin"]


@then(parsers.parse('o hash da senha de "{login}" começa com "{prefixo}"'))
def hash_comeca_com(login, prefixo):
    assert _hash_de(login).startswith(prefixo)


@then(parsers.parse('o hash da senha de "{login}" é diferente de "{senha}"'))
def hash_diferente_da_senha(login, senha):
    assert _hash_de(login) != senha


@then(parsers.parse("recebo status {status:d}"))
def verifica_status(contexto, status):
    assert contexto["resp"].status_code == status


# --------------------------------------------------------------------------
# Modo de demonstração pública (DEMO_MODE)
# --------------------------------------------------------------------------

@given("que o modo demonstração está ligado")
def modo_demo_ligado(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")


@given("que o modo demonstração está desligado")
def modo_demo_desligado(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)


@when("acesso a tela de login")
def acessa_tela_login(navegador, contexto):
    contexto["resp"] = navegador.get("/login")


@then("a tela de login traz o aviso de demonstração")
def login_com_aviso_demo(contexto):
    assert 'data-testid="login-aviso-demo"' in contexto["resp"].text


@then("a tela de login não traz o aviso de demonstração")
def login_sem_aviso_demo(contexto):
    assert 'data-testid="login-aviso-demo"' not in contexto["resp"].text


@then(parsers.parse('a senha de "{login}" continua valendo "{senha}"'))
def senha_inalterada(login, senha):
    from fluxocaixa.auth.service import autenticar

    assert autenticar(login, senha) is not None
