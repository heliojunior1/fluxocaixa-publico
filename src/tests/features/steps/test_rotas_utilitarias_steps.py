"""Steps BDD — rotas utilitárias de banco (spec controle-acesso R6 / infra R8).

Change: blindar-rotas-administrativas-banco.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../controle-acesso/rotas_utilitarias.feature")


@pytest.fixture()
def navegador(app):
    return TestClient(app, follow_redirects=False, headers={"Accept": "text/html"})


@pytest.fixture()
def contexto():
    return {}


# --------------------------------------------------------------------- Dado


@given(parsers.parse('um usuário ativo "{login}" com senha "{senha}"'))
def usuario_ativo(app, login, senha):
    from fluxocaixa.auth.service import gerar_hash
    from fluxocaixa.models.base import db
    from fluxocaixa.models.usuario import Usuario

    db.session.rollback()
    existente = Usuario.query.filter_by(nom_usuario=login).first()
    if existente is None:
        db.session.add(Usuario(
            nom_usuario=login,
            nom_completo=f"Usuário {login}",
            txt_hash_senha=gerar_hash(senha),
            ind_troca_senha='N',
            ind_status='A',
        ))
        db.session.commit()


@given(parsers.parse('que "{login}" tem a permissão de administrar o banco'))
def usuario_admin_banco(app, login):
    from fluxocaixa.models import Perfil, UsuarioPerfil
    from fluxocaixa.models.base import db
    from fluxocaixa.models.usuario import Usuario

    usuario = Usuario.query.filter_by(nom_usuario=login).first()
    perfil = Perfil.query.filter_by(cod_perfil='ADMINISTRADOR').first()
    ja_tem = UsuarioPerfil.query.filter_by(
        seq_usuario=usuario.seq_usuario, seq_perfil=perfil.seq_perfil).first()
    if ja_tem is None:
        db.session.add(UsuarioPerfil(seq_usuario=usuario.seq_usuario,
                                     seq_perfil=perfil.seq_perfil))
        db.session.commit()


@given(parsers.parse('estou autenticado como "{login}" com senha "{senha}"'))
def autenticado(navegador, login, senha):
    resp = navegador.post("/login", data={"usuario": login, "senha": senha})
    assert resp.status_code in (302, 303), f"login falhou: {resp.status_code}"


@given(parsers.parse("existe um lançamento fictício de {valor:f}"))
def lancamento_ficticio(app, contexto, valor):
    from fluxocaixa.models import Lancamento, Qualificador
    from fluxocaixa.models.base import db
    from fluxocaixa.services.dominio_lancamento import resolver_origem, resolver_tipo

    qualificador = Qualificador.query.filter_by(ind_status='A').first()
    lancamento = Lancamento(
        dat_lancamento=date(2061, 3, 1),
        seq_qualificador=qualificador.seq_qualificador,
        val_lancamento=Decimal(str(valor)),
        cod_tipo_lancamento=resolver_tipo("Entrada").cod_tipo_lancamento,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        cod_pessoa_inclusao=1,
        ind_status='A',
    )
    db.session.add(lancamento)
    db.session.commit()
    contexto["seq_lancamento"] = lancamento.seq_lancamento


@given("que o ambiente é de desenvolvimento")
def ambiente_dev(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")


@given("que o ambiente não é de desenvolvimento")
def ambiente_nao_dev(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)


@given(parsers.parse('que a inicialização do banco vai falhar com "{mensagem}"'))
def inicializacao_vai_falhar(monkeypatch, mensagem):
    """A mensagem imita o que o SQLAlchemy vaza: nome de tabela e coluna."""
    from fluxocaixa import bootstrap_db

    def explode():
        raise RuntimeError(mensagem)

    monkeypatch.setattr(bootstrap_db, "preparar_banco", explode)


# -------------------------------------------------------------------- Quando


@when(parsers.parse('acesso "{caminho}" por GET'))
def acessa_get(navegador, contexto, caminho):
    contexto["resp"] = navegador.get(caminho)


@when(parsers.parse('aciono "{caminho}" por POST confirmado'))
def aciona_post_confirmado(navegador, contexto, caminho):
    contexto["resp"] = navegador.post(caminho, data={"confirmado": "true"})


@when(parsers.parse('aciono "{caminho}" por POST sem confirmação'))
def aciona_post_sem_confirmacao(navegador, contexto, caminho):
    contexto["resp"] = navegador.post(caminho, data={})


@when(parsers.parse('aciono "{caminho}" por POST sem confirmação vindo de "{referer}"'))
def aciona_post_com_referer(navegador, contexto, caminho, referer):
    contexto["resp"] = navegador.post(
        caminho, data={}, headers={"Referer": referer})


# --------------------------------------------------------------------- Então


@then(parsers.parse("recebo status {status:d}"))
def recebo_status(contexto, status):
    assert contexto["resp"].status_code == status, (
        f"esperado {status}, veio {contexto['resp'].status_code}: "
        f"{contexto['resp'].text[:200]}")


@then("a operação é recusada")
def operacao_recusada(contexto):
    """`RegraNegocioError` vira flash + redirect em HTML (convenção do projeto).

    O que se afirma aqui é a ausência de sucesso; que o dado sobreviveu é o
    passo seguinte, e é ele que prova a recusa de fato.
    """
    resp = contexto["resp"]
    assert resp.status_code != 200 or "successfully" not in resp.text, (
        f"a operação não foi recusada: {resp.status_code} {resp.text[:200]}")


@then("o lançamento fictício continua no banco")
def lancamento_continua(app, contexto):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.base import db

    db.session.expire_all()
    assert Lancamento.query.get(contexto["seq_lancamento"]) is not None, \
        "o seed destrutivo rodou e apagou o lançamento"


@then("o redirecionamento aponta para a própria aplicação")
def redirect_interno(contexto):
    """Duas camadas cobrem isto, e a asserção aceita as duas.

    A verificação de origem do CSRF (R12) passou a recusar a requisição ANTES
    de o erro de negócio existir — 403, sem `Location`. Antes dela, quem
    protegia era `_destino_seguro` sobre o `Referer` (R2), devolvendo redirect
    interno. O que o cenário afere é o invariante comum: **em nenhum caminho o
    navegador é mandado para fora do domínio**.
    """
    resp = contexto["resp"]
    if resp.status_code == 403:
        return
    destino = resp.headers.get("location", "")
    assert destino.startswith("/") and not destino.startswith("//"), (
        f"o redirect saiu do domínio: {destino!r}")


@then(parsers.parse('a resposta não contém "{trecho}"'))
def resposta_sem_trecho(contexto, trecho):
    assert trecho not in contexto["resp"].text, (
        f"detalhe interno vazou na resposta: {contexto['resp'].text[:300]}")
