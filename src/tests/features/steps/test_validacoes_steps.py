"""Steps BDD — validações dos cadastros do núcleo (spec cadastros-nucleo R1–R4, R6)."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../cadastros-nucleo/validacoes.feature")


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar_qualificador(num):
    from fluxocaixa.models import Lancamento, Qualificador

    db = _db()
    db.session.rollback()
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    if q:
        Lancamento.query.filter_by(seq_qualificador=q.seq_qualificador).delete()
        db.session.delete(q)
        db.session.commit()


def _criar_qualificador(num, dsc, pai_seq=None, ativo=True):
    from fluxocaixa.models import Qualificador

    db = _db()
    _limpar_qualificador(num)
    q = Qualificador(
        num_qualificador=num,
        dsc_qualificador=dsc,
        cod_qualificador_pai=pai_seq,
        ind_status='A' if ativo else 'I',
    )
    db.session.add(q)
    db.session.commit()
    return q


def _codigos_aux():
    from fluxocaixa.models import OrigemLancamento, TipoLancamento

    tipo = TipoLancamento.query.filter_by(dsc_tipo_lancamento='Entrada').first()
    manual = OrigemLancamento.query.filter_by(dsc_origem_lancamento='Manual').first()
    return tipo.cod_tipo_lancamento, manual.cod_origem_lancamento


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given("que estou autenticado como administrador", target_fixture="navegador")
def navegador_admin(app, _admin_pronto):
    tc = TestClient(app, headers={"Accept": "text/html"})
    resp = tc.post(
        "/login", data={"usuario": "admin", "senha": _admin_pronto}, follow_redirects=False
    )
    assert resp.status_code in (302, 303)
    return tc


@given(parsers.parse('um qualificador folha ativo "{num}" chamado "{dsc}"'), target_fixture="qualificador")
def qualificador_folha(app, num, dsc):
    return _criar_qualificador(num, dsc)


@given(parsers.parse('um qualificador folha inativo "{num}" chamado "{dsc}"'), target_fixture="qualificador")
def qualificador_folha_inativo(app, num, dsc):
    return _criar_qualificador(num, dsc, ativo=False)


@given(
    parsers.parse('um qualificador "{num_pai}" chamado "{dsc_pai}" com o filho ativo "{num_filho}" chamado "{dsc_filho}"'),
    target_fixture="qualificador",
)
def qualificador_com_filho(app, num_pai, dsc_pai, num_filho, dsc_filho):
    _limpar_qualificador(num_filho)
    pai = _criar_qualificador(num_pai, dsc_pai)
    _criar_qualificador(num_filho, dsc_filho, pai_seq=pai.seq_qualificador)
    return pai


@given(
    parsers.parse('um lançamento Manual de valor "{valor}" em "{dat}" no qualificador "{num}"'),
    target_fixture="lancamento",
)
def lancamento_manual(app, valor, dat, num):
    from fluxocaixa.models import Lancamento, Qualificador

    db = _db()
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    tipo, origem_manual = _codigos_aux()
    lanc = Lancamento(
        dat_lancamento=date.fromisoformat(dat),
        seq_qualificador=q.seq_qualificador,
        val_lancamento=Decimal(valor),
        cod_tipo_lancamento=tipo,
        cod_origem_lancamento=origem_manual,
        cod_pessoa_inclusao=1,
        ind_status='A',
    )
    db.session.add(lanc)
    db.session.commit()
    return lanc


@given(
    parsers.parse('um lançamento de origem "{origem}" de valor "{valor}" no qualificador "{num}"'),
    target_fixture="lancamento",
)
def lancamento_com_origem(app, origem, valor, num):
    from fluxocaixa.models import Lancamento, OrigemLancamento, Qualificador

    db = _db()
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    tipo, _ = _codigos_aux()
    o = OrigemLancamento.query.filter_by(dsc_origem_lancamento=origem).first()
    lanc = Lancamento(
        dat_lancamento=date(2026, 7, 1),
        seq_qualificador=q.seq_qualificador,
        val_lancamento=Decimal(valor),
        cod_tipo_lancamento=tipo,
        cod_origem_lancamento=o.cod_origem_lancamento,
        cod_pessoa_inclusao=1,
        ind_status='A',
    )
    db.session.add(lanc)
    db.session.commit()
    return lanc


@given(parsers.parse('uma conta bancária de teste "{ident}"'), target_fixture="conta")
def conta_de_teste(app, ident):
    from fluxocaixa.models import ContaBancaria, SaldoConta

    banco, agencia, num = ident.split("/")
    db = _db()
    existente = ContaBancaria.query.filter_by(
        cod_banco=banco, num_agencia=agencia, num_conta=num
    ).first()
    if existente:
        SaldoConta.query.filter_by(seq_conta=existente.seq_conta).delete()
        db.session.delete(existente)
        db.session.commit()
    conta = ContaBancaria(
        cod_banco=banco, num_agencia=agencia, num_conta=num, dsc_conta=f"Teste {ident}"
    )
    db.session.add(conta)
    db.session.commit()
    return conta


@given(parsers.parse('um saldo de "{valor}" para essa conta em "{dat}"'))
def saldo_existente(navegador, conta, valor, dat):
    resp = navegador.post(
        "/saldos-bancarios/adicionar",
        data={"seq_conta": str(conta.seq_conta), "dat_saldo": dat, "val_saldo": valor},
    )
    assert resp.status_code == 200


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when(parsers.parse('crio um lançamento de valor "{valor}" no qualificador "{num}"'))
def cria_lancamento(navegador, contexto, valor, num):
    from fluxocaixa.models import Lancamento, Qualificador

    q = Qualificador.query.filter_by(num_qualificador=num).first()
    tipo, origem_manual = _codigos_aux()
    contexto["qtd_antes"] = Lancamento.query.filter_by(seq_qualificador=q.seq_qualificador).count()
    contexto["resp"] = navegador.post(
        "/saldos/add",
        data={
            "dat_lancamento": "2026-07-10",
            "seq_qualificador": str(q.seq_qualificador),
            "val_lancamento": valor,
            "cod_tipo_lancamento": str(tipo),
            "cod_origem_lancamento": str(origem_manual),
        },
    )


@when(parsers.parse('edito esse lançamento alterando a data para "{nova_data}"'))
def edita_data(navegador, contexto, lancamento, nova_data):
    contexto["resp"] = navegador.post(
        f"/saldos/edit/{lancamento.seq_lancamento}",
        data={
            "dat_lancamento": nova_data,
            "seq_qualificador": str(lancamento.seq_qualificador),
            "val_lancamento": str(lancamento.val_lancamento),
            "cod_tipo_lancamento": str(lancamento.cod_tipo_lancamento),
            "cod_origem_lancamento": str(lancamento.cod_origem_lancamento),
        },
    )


@when(parsers.parse('edito esse lançamento alterando o valor para "{novo_valor}"'))
def edita_valor(navegador, contexto, lancamento, novo_valor):
    contexto["resp"] = navegador.post(
        f"/saldos/edit/{lancamento.seq_lancamento}",
        data={
            "dat_lancamento": lancamento.dat_lancamento.isoformat(),
            "seq_qualificador": str(lancamento.seq_qualificador),
            "val_lancamento": novo_valor,
            "cod_tipo_lancamento": str(lancamento.cod_tipo_lancamento),
            "cod_origem_lancamento": str(lancamento.cod_origem_lancamento),
        },
    )


@when("excluo esse lançamento")
def exclui_lancamento(navegador, contexto, lancamento):
    contexto["resp"] = navegador.post(f"/saldos/delete/{lancamento.seq_lancamento}")


@when(parsers.parse('cadastro um qualificador com código "{codigo}", descrição "{descricao}" e pai "{pai}"'))
def cadastra_qualificador(navegador, contexto, codigo, descricao, pai):
    from fluxocaixa.models import Qualificador

    dados = {"num_qualificador": codigo, "dsc_qualificador": descricao}
    if pai != "-":
        p = Qualificador.query.filter_by(num_qualificador=pai).first()
        dados["cod_qualificador_pai"] = str(p.seq_qualificador)
    contexto["resp"] = navegador.post("/qualificadores/add", data=dados)


@when(parsers.parse('excluo o qualificador "{num}"'))
def exclui_qualificador(navegador, contexto, num):
    from fluxocaixa.models import Qualificador

    q = Qualificador.query.filter_by(num_qualificador=num).first()
    contexto["resp"] = navegador.post(f"/qualificadores/delete/{q.seq_qualificador}")


@when(parsers.parse('excluo o qualificador "{num}" com confirmação'))
def exclui_qualificador_confirmado(navegador, contexto, num):
    from fluxocaixa.models import Qualificador

    q = Qualificador.query.filter_by(num_qualificador=num).first()
    contexto["resp"] = navegador.post(
        f"/qualificadores/delete/{q.seq_qualificador}", data={"confirmado": "true"}
    )


@when(parsers.parse('adiciono um saldo de "{valor}" para essa conta em "{dat}"'))
def adiciona_saldo(navegador, contexto, conta, valor, dat):
    contexto["resp"] = navegador.post(
        "/saldos-bancarios/adicionar",
        data={"seq_conta": str(conta.seq_conta), "dat_saldo": dat, "val_saldo": valor},
    )


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('vejo a mensagem "{mensagem}"'))
def vejo_mensagem(contexto, mensagem):
    resp = contexto["resp"]
    assert resp.status_code == 200, f"esperava 200 pós-redirect, veio {resp.status_code}"
    assert mensagem in resp.text, f"mensagem '{mensagem}' não encontrada na página"


@then(parsers.parse('nenhum lançamento novo existe no qualificador "{num}"'))
def nenhum_lancamento_novo(contexto, num):
    from fluxocaixa.models import Lancamento, Qualificador

    q = Qualificador.query.filter_by(num_qualificador=num).first()
    assert (
        Lancamento.query.filter_by(seq_qualificador=q.seq_qualificador).count()
        == contexto["qtd_antes"]
    )


@then(parsers.parse('o lançamento permanece com a data "{dat}"'))
def lancamento_data_intacta(lancamento, dat):
    db = _db()
    db.session.expire_all()
    from fluxocaixa.models import Lancamento

    atual = Lancamento.query.get(lancamento.seq_lancamento)
    assert atual.dat_lancamento == date.fromisoformat(dat)


@then(parsers.parse('o lançamento permanece ativo com valor "{valor}"'))
def lancamento_intacto(lancamento, valor):
    db = _db()
    db.session.expire_all()
    from fluxocaixa.models import Lancamento

    atual = Lancamento.query.get(lancamento.seq_lancamento)
    assert atual.ind_status == 'A'
    assert atual.val_lancamento == Decimal(valor)


@then(parsers.parse('o qualificador "{num}" permanece ativo'))
def qualificador_ativo(num):
    from fluxocaixa.models import Qualificador

    _db().session.expire_all()
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    assert q.ind_status == 'A'


@then(parsers.parse('o qualificador "{num}" está inativo'))
def qualificador_inativo(num):
    from fluxocaixa.models import Qualificador

    _db().session.expire_all()
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    assert q.ind_status == 'I'


@then(parsers.parse('o saldo dessa conta em "{dat}" permanece "{valor}"'))
def saldo_intacto(conta, dat, valor):
    from fluxocaixa.models import SaldoConta

    _db().session.expire_all()
    saldos = SaldoConta.query.filter_by(
        seq_conta=conta.seq_conta, dat_saldo=date.fromisoformat(dat)
    ).all()
    assert len(saldos) == 1
    assert saldos[0].val_saldo == Decimal(valor)
