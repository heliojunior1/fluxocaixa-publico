"""Steps BDD — perfis e permissões por verbo+recurso (spec controle-acesso R6–R10)."""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_permissoes import criar_usuario_com_perfil

scenarios("../controle-acesso/permissoes.feature")


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _form_lancamento_valido():
    """Monta um POST válido de lançamento usando os dados de demonstração."""
    from fluxocaixa.models import Qualificador, TipoLancamento, OrigemLancamento

    folha = next(q for q in Qualificador.query.filter_by(ind_status='A') if q.is_folha())
    tipo = TipoLancamento.query.filter_by(dsc_tipo_lancamento='Entrada').first()
    origem = OrigemLancamento.query.filter_by(dsc_origem_lancamento='Manual').first()
    return {
        "dat_lancamento": date.today().isoformat(),
        "seq_qualificador": str(folha.seq_qualificador),
        "val_lancamento": "1234.56",
        "cod_tipo_lancamento": str(tipo.cod_tipo_lancamento),
        "cod_origem_lancamento": str(origem.cod_origem_lancamento),
    }


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given(parsers.parse('um usuário autenticado com o perfil "{perfil}"'), target_fixture="navegador")
def navegador_com_perfil(app, contexto, perfil):
    login, senha, seq_usuario = criar_usuario_com_perfil(perfil)
    contexto["seq_usuario"] = seq_usuario
    tc = TestClient(app, follow_redirects=False, headers={"Accept": "text/html"})
    resp = tc.post("/login", data={"usuario": login, "senha": senha})
    assert resp.status_code in (302, 303), f"login do perfil {perfil} falhou"
    return tc


@given("que estou autenticado como admin de testes", target_fixture="navegador")
def navegador_admin(app, contexto, _admin_pronto):
    tc = TestClient(app, follow_redirects=False, headers={"Accept": "text/html"})
    resp = tc.post("/login", data={"usuario": "admin", "senha": _admin_pronto})
    assert resp.status_code in (302, 303)
    return tc


@given(parsers.parse('que a instalação removeu a permissão "{cod}" do perfil "{perfil}"'))
def remove_permissao_do_perfil(app, cod, perfil):
    from fluxocaixa.models import Perfil, Permissao, PerfilPermissao

    db = _db()
    p = Perfil.query.filter_by(cod_perfil=perfil).first()
    perm = Permissao.query.filter_by(cod_permissao=cod).first()
    assert p is not None and perm is not None
    PerfilPermissao.query.filter_by(
        seq_perfil=p.seq_perfil, seq_permissao=perm.seq_permissao
    ).delete()
    db.session.commit()


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when("tenta criar um lançamento válido")
def tenta_criar_lancamento(navegador, contexto):
    from fluxocaixa.models import Lancamento

    contexto["qtd_antes"] = Lancamento.query.count()
    contexto["resp"] = navegador.post("/saldos/add", data=_form_lancamento_valido())


@when(parsers.parse('acessa a tela "{caminho}"'))
def acessa_tela(navegador, contexto, caminho):
    contexto["resp"] = navegador.get(caminho)


@when("o seed de domínio executa novamente")
def executa_seed_dominio(app):
    from fluxocaixa.services.seed_dominio import seed_dominio

    seed_dominio()


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('os perfis "{lista}" existem'))
def perfis_existem(app, lista):
    from fluxocaixa.models import Perfil

    existentes = {p.cod_perfil for p in Perfil.query.filter_by(ind_status='A')}
    faltantes = set(lista.split(",")) - existentes
    assert not faltantes, f"Perfis não seedados: {faltantes}"


@then(parsers.parse('o usuário "{login}" possui todos os perfis'))
def usuario_possui_todos_os_perfis(app, login):
    from fluxocaixa.models import Perfil, Usuario, UsuarioPerfil

    usuario = Usuario.query.filter_by(nom_usuario=login).first()
    vinculados = {
        up.seq_perfil for up in UsuarioPerfil.query.filter_by(seq_usuario=usuario.seq_usuario)
    }
    todos = {p.seq_perfil for p in Perfil.query.filter_by(ind_status='A')}
    assert todos <= vinculados, "Admin deveria estar vinculado a todos os perfis"


@then(parsers.parse("recebe status {status:d}"))
def recebe_status(contexto, status):
    assert contexto["resp"].status_code == status, contexto["resp"].status_code


@then(parsers.parse("o recurso é servido com status {status:d}"))
def recurso_com_status(contexto, status):
    assert contexto["resp"].status_code == status, contexto["resp"].status_code


@then("nenhum lançamento novo foi criado")
def nenhum_lancamento_criado(contexto):
    from fluxocaixa.models import Lancamento

    assert Lancamento.query.count() == contexto["qtd_antes"]


@then("o lançamento é criado com sucesso")
def lancamento_criado(contexto):
    from fluxocaixa.models import Lancamento

    assert contexto["resp"].status_code in (302, 303), contexto["resp"].status_code
    assert Lancamento.query.count() == contexto["qtd_antes"] + 1


@then("o lançamento criado registra esse usuário como autor")
def lancamento_auditado(contexto):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.base import db

    db.session.expire_all()
    ultimo = Lancamento.query.order_by(Lancamento.seq_lancamento.desc()).first()
    assert ultimo.cod_pessoa_inclusao == contexto["seq_usuario"], (
        f"Auditoria: esperado {contexto['seq_usuario']}, veio {ultimo.cod_pessoa_inclusao}"
    )


@then(parsers.parse('recebe a página 403 informando a permissão "{cod}"'))
def pagina_403_com_permissao(contexto, cod):
    resp = contexto["resp"]
    assert resp.status_code == 403, resp.status_code
    assert cod in resp.text, f"Página 403 deveria citar {cod}"


@then(parsers.parse('a página não exibe o elemento "{testid}"'))
def pagina_nao_exibe(contexto, testid):
    resp = contexto["resp"]
    assert resp.status_code == 200, resp.status_code
    assert f'data-testid="{testid}"' not in resp.text


@then(parsers.parse('a página exibe o elemento "{testid}"'))
def pagina_exibe(contexto, testid):
    resp = contexto["resp"]
    assert resp.status_code == 200, resp.status_code
    assert f'data-testid="{testid}"' in resp.text


@then(parsers.parse('o perfil "{perfil}" continua sem a permissão "{cod}"'))
def perfil_sem_permissao(app, perfil, cod):
    from fluxocaixa.models import Perfil, Permissao, PerfilPermissao

    p = Perfil.query.filter_by(cod_perfil=perfil).first()
    perm = Permissao.query.filter_by(cod_permissao=cod).first()
    vinculo = PerfilPermissao.query.filter_by(
        seq_perfil=p.seq_perfil, seq_permissao=perm.seq_permissao
    ).first()
    assert vinculo is None, "Seed recriou vínculo removido pela instalação"
