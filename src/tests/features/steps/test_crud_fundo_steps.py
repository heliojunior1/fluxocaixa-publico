"""Steps BDD — ciclo de vida do fundo (spec saldo-por-fundo R7–R13).

Feature majoritariamente de service: os steps chamam o fundo_service direto.
Os cenários de permissão (403) usam a rota via TestClient com perfil.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_permissoes import criar_usuario_com_perfil

scenarios("../saldo-por-fundo/crud_fundo.feature")

USUARIO_SESSAO = 12345  # cod_pessoa fixo no contexto de teste (sem request real)


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _fundo(cod):
    from fluxocaixa.models import Fundo

    return Fundo.query.filter_by(cod_fundo=cod).first()


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    # Fixa o usuário corrente para checar auditoria (contextvar da F1.3)
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(USUARIO_SESSAO)


@given(parsers.parse('um sistema de origem "{sigla}" cadastrado'))
def sistema_cadastrado(app, sigla):
    from fluxocaixa.models import SistemaOrigem

    db = _db()
    db.session.rollback()
    if not SistemaOrigem.query.filter_by(txt_sigla=sigla).first():
        db.session.add(SistemaOrigem(txt_sigla=sigla, dsc_sistema_origem=f"Sistema {sigla}"))
        db.session.commit()


@given(parsers.parse('um fundo manual "{cod}" chamado "{dsc}"'))
def fundo_manual(app, cod, dsc):
    from fluxocaixa.services.fundo_service import criar_fundo

    _db().session.rollback()
    if _fundo(cod) is None:
        criar_fundo(cod, dsc)


@given(parsers.parse('um fundo pendente "{cod}" auto-cadastrado pelo sistema "{sigla}"'))
def fundo_pendente(app, cod, sigla):
    from fluxocaixa.services.fundo_service import upsert_fundo_pendente

    _db().session.rollback()
    if _fundo(cod) is None:
        upsert_fundo_pendente(cod, f"Fundo {cod}", sigla)


@given(parsers.parse('o upsert de fundo já criou "{cod}" pelo sistema "{sigla}"'))
def upsert_ja_criou(app, cod, sigla):
    from fluxocaixa.services.fundo_service import upsert_fundo_pendente

    upsert_fundo_pendente(cod, f"Fundo {cod}", sigla)


@given(parsers.parse('uma conta de fundo "{ident}"'), target_fixture="conta")
def conta_de_fundo(app, ident):
    from fluxocaixa.models import ContaBancaria

    db = _db()
    db.session.rollback()
    banco, agencia, num = ident.split("/")
    existente = ContaBancaria.query.filter_by(
        cod_banco=banco, num_agencia=agencia, num_conta=num
    ).first()
    if existente:
        return existente
    conta = ContaBancaria(cod_banco=banco, num_agencia=agencia, num_conta=num,
                          dsc_conta=f"Conta {ident}")
    db.session.add(conta)
    db.session.commit()
    return conta


@given(parsers.parse('um saldo ativo do fundo "{cod}" nessa conta em "{dat}"'))
def saldo_ativo(app, conta, cod, dat):
    from fluxocaixa.services.saldo_fundo_service import gravar_saldo

    gravar_saldo(
        seq_conta=conta.seq_conta,
        seq_fundo=_fundo(cod).seq_fundo,
        dat_saldo=date.fromisoformat(dat),
        val_saldo=Decimal("1000.00"),
    )


@given(parsers.parse('um usuário autenticado com o perfil "{perfil}"'), target_fixture="navegador")
def navegador_com_perfil(app, contexto, perfil):
    login, senha, seq = criar_usuario_com_perfil(perfil)
    tc = TestClient(app, follow_redirects=False, headers={"Accept": "text/html"})
    resp = tc.post("/login", data={"usuario": login, "senha": senha})
    assert resp.status_code in (302, 303)
    return tc


# --------------------------------------------------------------------------
# Quando (operações de service capturam RegraNegocioError no contexto)
# --------------------------------------------------------------------------

def _executar(contexto, fn):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        contexto["resultado"] = fn()
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@when(parsers.re(r'cadastro o fundo "(?P<cod>[^"]*)" com descrição "(?P<dsc>[^"]*)"'))
def cadastra_fundo(app, contexto, cod, dsc):
    from fluxocaixa.services.fundo_service import criar_fundo

    _executar(contexto, lambda: criar_fundo(cod, dsc))


@when(parsers.parse('altero a descrição do fundo "{cod}" para "{dsc}"'))
def altera_descricao(app, contexto, cod, dsc):
    from fluxocaixa.services.fundo_service import alterar_fundo

    _executar(contexto, lambda: alterar_fundo(_fundo(cod).seq_fundo, dsc))


@when(parsers.parse('tento alterar o código do fundo "{cod}" para "{novo}"'))
def altera_codigo(app, contexto, cod, novo):
    from fluxocaixa.services.fundo_service import alterar_fundo

    _executar(contexto, lambda: alterar_fundo(_fundo(cod).seq_fundo, "x", novo_cod=novo))


@when(parsers.parse('aprovo o fundo "{cod}" sem alterar a descrição'))
def aprova_fundo(app, contexto, cod):
    from fluxocaixa.services.fundo_service import aprovar_fundo

    _executar(contexto, lambda: aprovar_fundo(_fundo(cod).seq_fundo))


@when(parsers.parse('aprovo o fundo "{cod}" com a descrição "{dsc}"'))
def aprova_fundo_dsc(app, contexto, cod, dsc):
    from fluxocaixa.services.fundo_service import aprovar_fundo

    _executar(contexto, lambda: aprovar_fundo(_fundo(cod).seq_fundo, dsc=dsc))


@when(parsers.parse('inativo o fundo "{cod}"'))
def inativa_fundo(app, contexto, cod):
    from fluxocaixa.services.fundo_service import inativar_fundo

    _executar(contexto, lambda: inativar_fundo(_fundo(cod).seq_fundo))


@when("listo os fundos filtrando por pendentes")
def lista_pendentes(app, contexto):
    from fluxocaixa.services.fundo_service import listar_fundos

    contexto["lista"] = listar_fundos(pendente=True)


@when(parsers.parse('o upsert de fundo é chamado para "{cod}" com sistema "{sigla}"'))
def upsert_chamado(app, contexto, cod, sigla):
    from fluxocaixa.services.fundo_service import upsert_fundo_pendente

    _executar(contexto, lambda: upsert_fundo_pendente(cod, f"Fundo {cod}", sigla))


@when(parsers.parse('o upsert de fundo é chamado para "{cod}" com sistema "{sigla}" e outra descrição'))
def upsert_reentrada(app, contexto, cod, sigla):
    from fluxocaixa.services.fundo_service import upsert_fundo_pendente

    _executar(contexto, lambda: upsert_fundo_pendente(cod, "DESCRICAO DIFERENTE", sigla))


@when("o operador tenta cadastrar um fundo pela rota")
def operador_cadastra(navegador, contexto):
    contexto["resp"] = navegador.post(
        "/fundos/adicionar", data={"cod_fundo": "8888", "dsc_fundo": "Tentativa operador"}
    )


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('o fundo "{cod}" existe ativo, aprovado, com origem "{tipo}" e sem sistema'))
def fundo_ativo_aprovado(cod, tipo):
    from fluxocaixa.models import TipoOrigemSaldo

    _db().session.expire_all()
    f = _fundo(cod)
    assert f is not None and f.ind_status == 'A' and f.ind_pendente_revisao == 'N'
    assert f.seq_sistema_origem is None
    assert TipoOrigemSaldo.query.get(f.seq_tipo_origem).txt_sigla == tipo


@then(parsers.parse('a auditoria do fundo "{cod}" registra o usuário da sessão'))
def auditoria_fundo(cod):
    assert _fundo(cod).cod_pessoa_inclusao == USUARIO_SESSAO


@then(parsers.parse('a operação de fundo é rejeitada com a mensagem "{mensagem}"'))
def operacao_rejeitada(contexto, mensagem):
    assert contexto["erro"] == mensagem, f"esperava {mensagem!r}, veio {contexto['erro']!r}"


@then(parsers.parse('o fundo "{cod}" tem descrição "{dsc}"'))
def fundo_com_descricao(cod, dsc):
    _db().session.expire_all()
    assert _fundo(cod).dsc_fundo == dsc


@then(parsers.parse('o fundo "{cod}" não está mais pendente'))
def fundo_nao_pendente(cod):
    _db().session.expire_all()
    assert _fundo(cod).ind_pendente_revisao == 'N'


@then(parsers.parse('o fundo "{cod}" mantém origem "{tipo}", sistema "{sigla}" e a data de auto-cadastro'))
def fundo_mantem_origem(cod, tipo, sigla):
    from fluxocaixa.models import SistemaOrigem, TipoOrigemSaldo

    _db().session.expire_all()
    f = _fundo(cod)
    assert TipoOrigemSaldo.query.get(f.seq_tipo_origem).txt_sigla == tipo
    assert SistemaOrigem.query.get(f.seq_sistema_origem).txt_sigla == sigla
    assert f.dat_auto_cadastro is not None


@then(parsers.parse('o fundo "{cod}" permanece ativo'))
def fundo_permanece_ativo(cod):
    _db().session.expire_all()
    assert _fundo(cod).ind_status == 'A'


@then(parsers.parse('o fundo "{cod}" está inativo'))
def fundo_inativo(cod):
    _db().session.expire_all()
    assert _fundo(cod).ind_status == 'I'


@then(parsers.parse('a lista de fundos contém "{cod}"'))
def lista_contem(contexto, cod):
    assert any(f.cod_fundo == cod for f in contexto["lista"])


@then(parsers.parse('a lista de fundos não contém "{cod}"'))
def lista_nao_contem(contexto, cod):
    assert all(f.cod_fundo != cod for f in contexto["lista"])


@then(parsers.parse('o fundo "{cod}" existe pendente, com origem "{tipo}", sistema "{sigla}" e data de auto-cadastro'))
def fundo_pendente_completo(cod, tipo, sigla):
    from fluxocaixa.models import SistemaOrigem, TipoOrigemSaldo

    _db().session.expire_all()
    f = _fundo(cod)
    assert f is not None and f.ind_pendente_revisao == 'S'
    assert TipoOrigemSaldo.query.get(f.seq_tipo_origem).txt_sigla == tipo
    assert SistemaOrigem.query.get(f.seq_sistema_origem).txt_sigla == sigla
    assert f.dat_auto_cadastro is not None


@then(parsers.parse('existe exatamente 1 fundo com código "{cod}"'))
def um_fundo(cod):
    from fluxocaixa.models import Fundo

    _db().session.expire_all()
    assert Fundo.query.filter_by(cod_fundo=cod).count() == 1


@then(parsers.parse('o fundo "{cod}" continua pendente'))
def fundo_continua_pendente(cod):
    _db().session.expire_all()
    assert _fundo(cod).ind_pendente_revisao == 'S'


@then(parsers.parse('o fundo "{cod}" continua aprovado, com origem "{tipo}" e sem sistema'))
def fundo_continua_aprovado(cod, tipo):
    from fluxocaixa.models import TipoOrigemSaldo

    _db().session.expire_all()
    f = _fundo(cod)
    assert f.ind_pendente_revisao == 'N' and f.seq_sistema_origem is None
    assert TipoOrigemSaldo.query.get(f.seq_tipo_origem).txt_sigla == tipo


@then(parsers.parse('o operador recebe status {status:d}'))
def operador_status(contexto, status):
    assert contexto["resp"].status_code == status
