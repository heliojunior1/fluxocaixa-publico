"""Steps BDD — credenciais e força bruta (spec controle-acesso R14).

Change: endurecer-credenciais-e-antibruteforce.
"""
from datetime import datetime, timedelta

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../controle-acesso/credenciais.feature")


@pytest.fixture()
def contexto():
    return {}


def _criar_usuario(login, senha):
    from fluxocaixa.auth.service import gerar_hash
    from fluxocaixa.models.base import db
    from fluxocaixa.models.usuario import Usuario

    db.session.rollback()
    existente = Usuario.query.filter_by(nom_usuario=login).first()
    if existente:
        db.session.delete(existente)
        db.session.commit()
    usuario = Usuario(
        nom_usuario=login, nom_completo=f"Usuário {login}",
        txt_hash_senha=gerar_hash(senha), ind_troca_senha='N', ind_status='A',
    )
    db.session.add(usuario)
    db.session.commit()
    return usuario


@given(parsers.parse('um usuário ativo "{login}" com senha "{senha}"'))
def usuario_ativo(app, contexto, login, senha):
    _criar_usuario(login, senha)
    contexto["senha"] = senha
    contexto["login"] = login


@given("que o modo demonstração está ligado")
def modo_demo_ligado(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")


@when(parsers.parse('envio {n:d} tentativas de login de "{login}" com senha incorreta'))
def tentativas_erradas(app, contexto, n, login):
    from fluxocaixa.auth.service import autenticar

    for _ in range(n):
        assert autenticar(login, "senha-errada") is None


@when(parsers.parse('envio uma tentativa de "{login}" com a senha CORRETA'))
def tentativa_correta(app, contexto, login):
    from fluxocaixa.auth.service import autenticar

    contexto["resultado"] = autenticar(
        login, contexto["senha"], agora=contexto.get("agora"))


@when("passa mais tempo que o período de bloqueio")
def passa_o_bloqueio(contexto):
    """Relógio injetado — nada de esperar 15 minutos na suíte."""
    from fluxocaixa.auth.service import BLOQUEIO_LOGIN_SEGUNDOS

    contexto["agora"] = datetime.now() + timedelta(
        seconds=BLOQUEIO_LOGIN_SEGUNDOS + 60)


@when(parsers.parse('tento autenticar o login inexistente "{login}"'))
def login_inexistente(app, contexto, login, monkeypatch):
    """Afere que bcrypt É exercido — é o custo que fecha a enumeração por tempo."""
    from fluxocaixa.auth import service

    chamadas = []
    original = service.verificar_senha

    def espiao(senha, hash_armazenado):
        chamadas.append(hash_armazenado)
        return original(senha, hash_armazenado)

    monkeypatch.setattr(service, "verificar_senha", espiao)
    contexto["resultado"] = service.autenticar(login, "qualquer-coisa")
    contexto["chamadas_hash"] = chamadas


@then("o acesso é recusado com a mensagem genérica")
def acesso_recusado(contexto):
    assert contexto["resultado"] is None


@then("nenhuma sessão é criada")
def sem_sessao(contexto):
    assert contexto["resultado"] is None


@then("o acesso é permitido")
def acesso_permitido(contexto):
    assert contexto["resultado"] is not None, "a autenticação falhou"


@then(parsers.parse('o contador de falhas de "{login}" está zerado'))
def contador_zerado(app, login):
    from fluxocaixa.models.base import db
    from fluxocaixa.models.usuario import Usuario

    db.session.expire_all()
    assert Usuario.query.filter_by(nom_usuario=login).first().qtd_falhas_login == 0


@then("a verificação de senha foi exercida")
def verificacao_exercida(contexto):
    assert contexto["chamadas_hash"], (
        "bcrypt não foi executado para login inexistente — a resposta rápida "
        "revela que a conta não existe (enumeração por tempo)")
