"""Steps BDD — ciclo de vida da conta bancária (spec cadastros-nucleo R19–R23).

Feature majoritariamente de service: os steps chamam o conta_bancaria_service
direto. O cenário de permissão (403) usa a rota via TestClient com perfil.
Todos os identificadores são fictícios (repositório público).
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_permissoes import criar_usuario_com_perfil

scenarios("../cadastros-nucleo/crud_conta_bancaria.feature")

USUARIO_SESSAO = 12345  # cod_pessoa fixo no contexto de teste (sem request real)


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _partes(ident):
    # Sem strip: o cenário de trim afere que a normalização é do serviço
    return ident.split("/")


def _conta(ident):
    from fluxocaixa.models import ContaBancaria

    banco, agencia, num = (p.strip() for p in _partes(ident))
    return ContaBancaria.query.filter_by(
        cod_banco=banco, num_agencia=agencia, num_conta=num
    ).first()


def _executar(contexto, fn):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        contexto["resultado"] = fn()
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    # Fixa o usuário corrente para checar auditoria (contextvar da F1.3)
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(USUARIO_SESSAO)


@given(parsers.parse('uma conta bancária cadastrada "{ident}"'))
def conta_cadastrada(app, ident):
    from fluxocaixa.services.conta_bancaria_service import criar_conta

    _db().session.rollback()
    if _conta(ident) is None:
        banco, agencia, num = _partes(ident)
        criar_conta(banco, agencia, num, f"Conta {ident}")


@given(parsers.parse('um lançamento vinculado à conta "{ident}"'))
def lancamento_vinculado(app, ident):
    from fluxocaixa.models import (
        Lancamento,
        OrigemLancamento,
        Qualificador,
        TipoLancamento,
    )

    db = _db()
    db.session.rollback()
    q = Qualificador.query.filter_by(num_qualificador="9.77").first()
    if q is None:
        q = Qualificador(num_qualificador="9.77", dsc_qualificador="Folha CRUD conta",
                         ind_status='A')
        db.session.add(q)
        db.session.commit()
    tipo = TipoLancamento.query.filter_by(dsc_tipo_lancamento='Entrada').first()
    origem = OrigemLancamento.query.filter_by(dsc_origem_lancamento='Manual').first()
    db.session.add(Lancamento(
        dat_lancamento=date(2026, 7, 1),
        seq_qualificador=q.seq_qualificador,
        val_lancamento=Decimal("1234.56"),
        cod_tipo_lancamento=tipo.cod_tipo_lancamento,
        cod_origem_lancamento=origem.cod_origem_lancamento,
        cod_pessoa_inclusao=USUARIO_SESSAO,
        ind_status='A',
        seq_conta=_conta(ident).seq_conta,
    ))
    db.session.commit()


@given(parsers.parse('um saldo ativo na conta "{ident}" em "{dat}"'))
def saldo_ativo(app, ident, dat):
    from fluxocaixa.services.fundo_service import garantir_fundo_geral
    from fluxocaixa.services.saldo_fundo_service import gravar_saldo

    fundo = garantir_fundo_geral()
    gravar_saldo(
        seq_conta=_conta(ident).seq_conta,
        seq_fundo=fundo.seq_fundo,
        dat_saldo=date.fromisoformat(dat),
        val_saldo=Decimal("1234.56"),
    )


@given(parsers.parse('a conta "{ident}" foi inativada'))
def conta_ja_inativada(app, ident):
    from fluxocaixa.services.conta_bancaria_service import inativar_conta

    _db().session.rollback()
    conta = _conta(ident)
    if conta.ind_status == 'A':
        inativar_conta(conta.seq_conta)


@given(parsers.parse('um usuário autenticado com o perfil "{perfil}"'), target_fixture="navegador")
def navegador_com_perfil(app, contexto, perfil):
    login, senha, seq = criar_usuario_com_perfil(perfil)
    tc = TestClient(app, follow_redirects=False, headers={"Accept": "text/html"})
    resp = tc.post("/login", data={"usuario": login, "senha": senha})
    assert resp.status_code in (302, 303)
    return tc


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when(parsers.parse('cadastro a conta bancária "{ident}" com descrição "{dsc}"'))
def cadastra_conta(app, contexto, ident, dsc):
    from fluxocaixa.services.conta_bancaria_service import criar_conta

    banco, agencia, num = _partes(ident)
    _executar(contexto, lambda: criar_conta(banco, agencia, num, dsc))


@when(parsers.parse('altero a descrição da conta "{ident}" para "{dsc}"'))
def altera_descricao(app, contexto, ident, dsc):
    from fluxocaixa.services.conta_bancaria_service import alterar_conta

    conta = _conta(ident)
    _executar(contexto, lambda: alterar_conta(
        conta.seq_conta, conta.cod_banco, conta.num_agencia, conta.num_conta, dsc))


@when(parsers.parse('altero a tripla da conta "{ident}" para "{nova}"'))
def altera_tripla(app, contexto, ident, nova):
    from fluxocaixa.services.conta_bancaria_service import alterar_conta

    conta = _conta(ident)
    banco, agencia, num = _partes(nova)
    _executar(contexto, lambda: alterar_conta(
        conta.seq_conta, banco, agencia, num, conta.dsc_conta))


@when(parsers.parse('inativo a conta "{ident}"'))
def inativa_conta(app, contexto, ident):
    from fluxocaixa.services.conta_bancaria_service import inativar_conta

    _executar(contexto, lambda: inativar_conta(_conta(ident).seq_conta))


@when(parsers.parse('reativo a conta "{ident}"'))
def reativa_conta(app, contexto, ident):
    from fluxocaixa.services.conta_bancaria_service import reativar_conta

    _executar(contexto, lambda: reativar_conta(_conta(ident).seq_conta))


@when(parsers.parse('listo as contas bancárias com status "{status}"'))
def lista_por_status(app, contexto, status):
    from fluxocaixa.services.conta_bancaria_service import listar_contas

    mapa = {"ativas": "ativo", "inativas": "inativo", "todas": "todas"}
    contexto["lista"] = listar_contas(status=mapa[status])


@when(parsers.parse('listo as contas bancárias filtrando pelo número "{num}"'))
def lista_por_numero(app, contexto, num):
    from fluxocaixa.services.conta_bancaria_service import listar_contas

    contexto["lista"] = listar_contas(num_conta=num, status="todas")


@when("o operador tenta cadastrar uma conta bancária pela rota")
def operador_cadastra(navegador, contexto):
    contexto["resp"] = navegador.post(
        "/contas-bancarias/adicionar",
        data={"cod_banco": "001", "num_agencia": "0001",
              "num_conta": "12345-6", "dsc_conta": "Tentativa operador"},
    )


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('a conta "{ident}" existe ativa com descrição "{dsc}"'))
def conta_ativa_com_descricao(ident, dsc):
    _db().session.expire_all()
    conta = _conta(ident)
    assert conta is not None and conta.ind_status == 'A'
    assert conta.dsc_conta == dsc


@then(parsers.parse('a auditoria da conta "{ident}" registra o usuário da sessão'))
def auditoria_inclusao(ident):
    _db().session.expire_all()
    conta = _conta(ident)
    assert conta.cod_pessoa_inclusao == USUARIO_SESSAO
    assert conta.dat_inclusao is not None


@then(parsers.parse('a auditoria de alteração da conta "{ident}" registra o usuário da sessão'))
def auditoria_alteracao(ident):
    _db().session.expire_all()
    conta = _conta(ident)
    assert conta.cod_pessoa_alteracao == USUARIO_SESSAO
    assert conta.dat_alteracao is not None


@then(parsers.parse('a operação de conta é rejeitada com a mensagem "{mensagem}"'))
def operacao_rejeitada(contexto, mensagem):
    assert contexto["erro"] == mensagem, f"esperava {mensagem!r}, veio {contexto['erro']!r}"


@then(parsers.parse('existe exatamente 1 conta "{ident}"'))
def uma_conta(ident):
    from fluxocaixa.models import ContaBancaria

    _db().session.expire_all()
    banco, agencia, num = (p.strip() for p in _partes(ident))
    assert ContaBancaria.query.filter_by(
        cod_banco=banco, num_agencia=agencia, num_conta=num
    ).count() == 1


@then(parsers.parse('a conta "{ident}" continua existindo'))
def conta_continua(ident):
    _db().session.expire_all()
    assert _conta(ident) is not None


@then(parsers.parse('a conta "{ident}" permanece ativa'))
def conta_permanece_ativa(ident):
    _db().session.expire_all()
    assert _conta(ident).ind_status == 'A'


@then(parsers.parse('a conta "{ident}" está inativa'))
def conta_inativa(ident):
    _db().session.expire_all()
    assert _conta(ident).ind_status == 'I'


@then(parsers.parse('o lançamento da conta "{ident}" permanece ativo'))
def lancamento_permanece(ident):
    from fluxocaixa.models import Lancamento

    _db().session.expire_all()
    lanc = Lancamento.query.filter_by(seq_conta=_conta(ident).seq_conta).first()
    assert lanc is not None and lanc.ind_status == 'A'


@then(parsers.parse('a conta "{ident}" não aparece entre as contas ativas'))
def fora_das_ativas(ident):
    from fluxocaixa.repositories.conta_bancaria_repository import (
        ContaBancariaRepository,
    )

    _db().session.expire_all()
    seq = _conta(ident).seq_conta
    assert all(c.seq_conta != seq for c in ContaBancariaRepository().list_active())


@then(parsers.parse('a conta "{ident}" aparece entre as contas ativas'))
def entre_as_ativas(ident):
    from fluxocaixa.repositories.conta_bancaria_repository import (
        ContaBancariaRepository,
    )

    _db().session.expire_all()
    seq = _conta(ident).seq_conta
    assert any(c.seq_conta == seq for c in ContaBancariaRepository().list_active())


@then(parsers.parse('a lista de contas contém "{ident}"'))
def lista_contem(contexto, ident):
    banco, agencia, num = (p.strip() for p in _partes(ident))
    assert any(
        (c.cod_banco, c.num_agencia, c.num_conta) == (banco, agencia, num)
        for c in contexto["lista"]
    )


@then(parsers.parse('a lista de contas não contém "{ident}"'))
def lista_nao_contem(contexto, ident):
    banco, agencia, num = (p.strip() for p in _partes(ident))
    assert all(
        (c.cod_banco, c.num_agencia, c.num_conta) != (banco, agencia, num)
        for c in contexto["lista"]
    )


@then(parsers.parse('o operador recebe status {status:d}'))
def operador_status(contexto, status):
    assert contexto["resp"].status_code == status
