"""Steps BDD — tela de saldos por fundo e import de transição (R19/R20)."""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../saldo-por-fundo/telas_migracao.feature")

D2 = lambda v: Decimal(str(v)).quantize(Decimal("0.01"))  # noqa: E731


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _conta(ident):
    from fluxocaixa.models import ContaBancaria

    banco, ag, num = ident.split("/")
    c = ContaBancaria.query.filter_by(cod_banco=banco, num_agencia=ag, num_conta=num).first()
    if c is None:
        c = ContaBancaria(cod_banco=banco, num_agencia=ag, num_conta=num, dsc_conta=f"Tela {ident}")
        _db().session.add(c)
        _db().session.commit()
    return c


def _fundo(cod):
    from fluxocaixa.models import Fundo

    return Fundo.query.filter_by(cod_fundo=cod).first()


@given("que estou autenticado como administrador")
def admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(999)


@given(parsers.parse('um sistema de origem "{sigla}" cadastrado'))
def sistema(app, sigla):
    from fluxocaixa.models import SistemaOrigem

    _db().session.rollback()
    if not SistemaOrigem.query.filter_by(txt_sigla=sigla).first():
        _db().session.add(SistemaOrigem(txt_sigla=sigla, dsc_sistema_origem=sigla))
        _db().session.commit()


@given(parsers.parse('uma conta de tela "{ident}"'))
def conta(app, ident):
    _conta(ident)


@given(parsers.parse('um fundo de tela "{cod}"'))
def fundo(app, cod):
    from fluxocaixa.services.fundo_service import criar_fundo

    if _fundo(cod) is None:
        criar_fundo(cod, f"Fundo Tela {cod}")


@given(parsers.parse('um saldo de tela "{valor}" na conta "{ident}" fundo "{cod}" em "{dat}"'))
def saldo_tela(app, valor, ident, cod, dat):
    from fluxocaixa.services.saldo_fundo_service import gravar_saldo

    gravar_saldo(seq_conta=_conta(ident).seq_conta, seq_fundo=_fundo(cod).seq_fundo,
                 dat_saldo=date.fromisoformat(dat), val_saldo=Decimal(valor))


@when(parsers.parse('listo os saldos na visão "{visao}"'))
def lista_visao(app, contexto, visao):
    from fluxocaixa.services.saldo_conta_service import listar_saldos_tela

    contexto["lista"] = listar_saldos_tela(visao=visao)


@when(parsers.parse('edito o saldo da conta "{ident}" fundo "{cod}" em "{dat}" para "{valor}"'))
def edita_saldo(app, ident, cod, dat, valor):
    from fluxocaixa.services.saldo_fundo_service import gravar_saldo

    gravar_saldo(seq_conta=_conta(ident).seq_conta, seq_fundo=_fundo(cod).seq_fundo,
                 dat_saldo=date.fromisoformat(dat), val_saldo=Decimal(valor))


@when(parsers.parse('inativo o saldo da conta "{ident}" fundo "{cod}" em "{dat}"'))
def inativa_saldo(app, ident, cod, dat):
    from fluxocaixa.services.saldo_fundo_service import inativar_saldo

    inativar_saldo(_conta(ident).seq_conta, _fundo(cod).seq_fundo, date.fromisoformat(dat))


@when(parsers.parse('importo pela tela um CSV com o saldo "{valor}" para a conta "{ident}" em "{dat}"'))
def importa_csv_tela(app, contexto, valor, ident, dat):
    # Fluxo com pré-processamento (F2.5): preview → confirmar
    from fluxocaixa.services.preprocessamento import confirmar, criar_preview

    banco, ag, num = ident.split("/")
    _conta(ident)
    conteudo = f"Data;Conta;Valor\n{dat};{banco}/{ag}/{num};{valor}\n".encode("utf-8")
    sessao = {}
    token, _ = criar_preview("saldos", conteudo, "saldos.csv", sessao)
    contexto["resultado"] = confirmar(token, sessao)


def _saldos(ident, cod, dat, status):
    from fluxocaixa.models import SaldoContaFundo

    _db().session.expire_all()
    return SaldoContaFundo.query.filter_by(
        seq_conta=_conta(ident).seq_conta, seq_fundo=_fundo(cod).seq_fundo,
        dat_saldo=date.fromisoformat(dat), ind_status=status,
    ).all()


@then(parsers.parse('a conta "{ident}" em "{dat}" aparece com saldo agregado "{valor}"'))
def agregado_na_lista(contexto, ident, dat, valor):
    seq = _conta(ident).seq_conta
    alvo = next((r for r in contexto["lista"]
                 if r["seq_conta"] == seq and str(r["dat_saldo"]) == dat), None)
    assert alvo is not None, f"conta não encontrada na visão agregada: {contexto['lista']}"
    assert D2(alvo["val_saldo"]) == D2(valor)


@then(parsers.parse('a chave conta "{ident}" fundo "{cod}" em "{dat}" tem {qtd:d} ativo com "{valor}"'))
def chave_ativo(ident, cod, dat, qtd, valor):
    ativos = _saldos(ident, cod, dat, 'A')
    assert len(ativos) == qtd
    assert D2(ativos[0].val_saldo) == D2(valor)


@then(parsers.parse('a chave conta "{ident}" fundo "{cod}" em "{dat}" tem {qtd:d} ativo'))
def chave_ativo_qtd(ident, cod, dat, qtd):
    assert len(_saldos(ident, cod, dat, 'A')) == qtd


@then(parsers.parse('a chave conta "{ident}" fundo "{cod}" em "{dat}" tem {qtd:d} inativo com "{valor}"'))
def chave_inativo(ident, cod, dat, qtd, valor):
    inativos = [s for s in _saldos(ident, cod, dat, 'I') if D2(s.val_saldo) == D2(valor)]
    assert len(inativos) == qtd


@then(parsers.parse("o resultado da tela informa {ok:d} inserida e {erro:d} com erro"))
def resultado_tela(contexto, ok, erro):
    r = contexto["resultado"]
    assert (r.linhas_inseridas, r.linhas_com_erro) == (ok, erro)


@then(parsers.parse('a conta "{ident}" tem no fundo "{cod}" em "{dat}" o saldo ativo "{valor}" com origem "{tipo}"'))
def saldo_geral_importado(ident, cod, dat, valor, tipo):
    from fluxocaixa.models import TipoOrigemSaldo

    ativos = _saldos(ident, cod, dat, 'A')
    assert len(ativos) == 1
    assert D2(ativos[0].val_saldo) == D2(valor)
    assert TipoOrigemSaldo.query.get(ativos[0].seq_tipo_origem).txt_sigla == tipo
