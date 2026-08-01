"""Steps BDD — importação de saldos em lote (spec saldo-por-fundo R12/R14–R16)."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_permissoes import criar_usuario_com_perfil

scenarios("../saldo-por-fundo/importacao_lote.feature")

DATA_LOTE = date(2026, 7, 10)
D2 = lambda v: Decimal(str(v)).quantize(Decimal("0.01"))  # noqa: E731


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _conta(ident):
    from fluxocaixa.models import ContaBancaria

    banco, agencia, num = ident.split("/")
    return ContaBancaria.query.filter_by(
        cod_banco=banco, num_agencia=agencia, num_conta=num
    ).first()


def _fundo(cod):
    from fluxocaixa.models import Fundo

    return Fundo.query.filter_by(cod_fundo=cod).first()


def _linha(ident, cod_fundo, valor):
    from fluxocaixa.services.importacao_lote_service import LinhaLote

    banco, agencia, num = ident.split("/")
    return LinhaLote(
        cod_banco=banco, num_agencia=agencia, num_conta=num,
        cod_fundo=cod_fundo, dsc_fundo=f"Fundo {cod_fundo}",
        val_saldo=Decimal(valor),
    )


def _importar(contexto, linhas, sigla_sistema=None):
    from fluxocaixa.services.importacao_lote_service import importar_lote
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        contexto["resultado"] = importar_lote(
            linhas, dat_saldo_lote=DATA_LOTE, sigla_sistema=sigla_sistema,
            arquivo_origem="lote-bdd.json",
        )
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(777)


@given(parsers.parse('uma conta de lote "{ident}"'))
def conta_de_lote(app, ident):
    from fluxocaixa.models import ContaBancaria

    db = _db()
    db.session.rollback()
    if _conta(ident) is None:
        banco, agencia, num = ident.split("/")
        db.session.add(ContaBancaria(cod_banco=banco, num_agencia=agencia,
                                     num_conta=num, dsc_conta=f"Conta {ident}"))
        db.session.commit()


@given(parsers.parse('um fundo importável "{cod}"'))
def fundo_importavel(app, cod):
    from fluxocaixa.services.fundo_service import criar_fundo

    _db().session.rollback()
    if _fundo(cod) is None:
        criar_fundo(cod, f"Fundo Importável {cod}")


@given(parsers.parse('um sistema de origem "{sigla}" cadastrado'))
def sistema_cadastrado(app, sigla):
    from fluxocaixa.models import SistemaOrigem

    db = _db()
    if not SistemaOrigem.query.filter_by(txt_sigla=sigla).first():
        db.session.add(SistemaOrigem(txt_sigla=sigla, dsc_sistema_origem=f"Sistema {sigla}"))
        db.session.commit()


@given(parsers.parse('um lote já importado com "{valor}" para a conta "{ident}" e fundo "{cod}"'))
def lote_ja_importado(app, contexto, valor, ident, cod):
    _importar(contexto, [_linha(ident, cod, valor)])
    assert contexto["erro"] is None


@given(parsers.parse('um cliente HTTP autenticado com o perfil "{perfil}"'), target_fixture="cliente_http")
def cliente_http(app, perfil):
    login, senha, _ = criar_usuario_com_perfil(perfil)
    tc = TestClient(app)
    resp = tc.post("/login", data={"usuario": login, "senha": senha}, follow_redirects=False)
    assert resp.status_code in (302, 303)
    return tc


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when("importo um lote com as linhas:")
def importa_lote_tabela(app, contexto, datatable):
    # datatable: lista de listas, primeira linha é o cabeçalho
    linhas = [_linha(conta, fundo, valor) for conta, fundo, valor in datatable[1:]]
    _importar(contexto, linhas)


@when(parsers.parse('importo um lote com "{valor}" para a conta "{ident}" e fundo "{cod}"'))
def importa_lote_simples(app, contexto, valor, ident, cod):
    _importar(contexto, [_linha(ident, cod, valor)])


@when(parsers.parse('importo um lote da origem "{sigla}" com o fundo inexistente "{cod}" para a conta "{ident}"'))
def importa_com_origem(app, contexto, sigla, cod, ident):
    _importar(contexto, [_linha(ident, cod, "500.00")], sigla_sistema=sigla)


@when(parsers.parse('importo um lote sem origem com o fundo inexistente "{cod}" para a conta "{ident}"'))
def importa_sem_origem(app, contexto, cod, ident):
    _importar(contexto, [_linha(ident, cod, "500.00")])


@when(parsers.parse('o upsert de fundo é chamado para "{cod}" sem sistema de origem'))
def upsert_sem_sistema(app, contexto, cod):
    from fluxocaixa.services.fundo_service import upsert_fundo_pendente

    upsert_fundo_pendente(cod, f"Fundo {cod}", None)


@when("importo um lote sem linhas")
def importa_lote_vazio(app, contexto):
    _importar(contexto, [])


@when(parsers.parse('o cliente envia ao endpoint um lote com valSaldo "{valor}" para a conta "{ident}" e fundo "{cod}"'))
def cliente_envia_lote(cliente_http, contexto, valor, ident, cod):
    banco, agencia, num = ident.split("/")
    contexto["resp"] = cliente_http.post(
        "/api/saldo/importacao-lote",
        json={
            "origem": None,
            "dataSaldo": DATA_LOTE.isoformat(),
            "arquivoOrigem": "lote-endpoint.json",
            "linhas": [{
                "codBanco": banco, "numAgencia": agencia, "numConta": num,
                "codFundo": cod, "dscFundo": f"Fundo {cod}", "valSaldo": valor,
            }],
        },
    )


@when("o cliente envia ao endpoint um lote qualquer")
def cliente_envia_qualquer(cliente_http, contexto):
    contexto["resp"] = cliente_http.post(
        "/api/saldo/importacao-lote",
        json={"dataSaldo": DATA_LOTE.isoformat(), "linhas": []},
    )


@when("um cliente anônimo envia ao endpoint um lote qualquer")
def anonimo_envia(app, contexto):
    tc = TestClient(app)
    contexto["resp"] = tc.post(
        "/api/saldo/importacao-lote",
        json={"dataSaldo": DATA_LOTE.isoformat(), "linhas": []},
    )


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse("o resultado informa {ok:d} inseridas e {erro:d} com erro"))
def resultado_contadores(contexto, ok, erro):
    r = contexto["resultado"]
    assert (r.linhas_inseridas, r.linhas_com_erro) == (ok, erro), (
        f"esperava ({ok},{erro}), veio ({r.linhas_inseridas},{r.linhas_com_erro}): {r.detalhe_erros}"
    )


@then(parsers.parse("o detalhe de erros aponta a linha {n:d}"))
def detalhe_linha(contexto, n):
    assert any(e["linha"] == n for e in contexto["resultado"].detalhe_erros)


@then(parsers.parse('a chave da conta "{ident}" e fundo "{cod}" tem {qtd:d} linha ativa com "{valor}"'))
def chave_ativa(ident, cod, qtd, valor):
    from fluxocaixa.models import SaldoContaFundo

    _db().session.expire_all()
    ativas = SaldoContaFundo.query.filter_by(
        seq_conta=_conta(ident).seq_conta, seq_fundo=_fundo(cod).seq_fundo,
        dat_saldo=DATA_LOTE, ind_status='A',
    ).all()
    assert len(ativas) == qtd
    assert D2(ativas[0].val_saldo) == D2(valor)


@then(parsers.parse('a chave da conta "{ident}" e fundo "{cod}" tem {qtd:d} linha inativa com "{valor}"'))
def chave_inativa(ident, cod, qtd, valor):
    from fluxocaixa.models import SaldoContaFundo

    _db().session.expire_all()
    inativas = [
        s for s in SaldoContaFundo.query.filter_by(
            seq_conta=_conta(ident).seq_conta, seq_fundo=_fundo(cod).seq_fundo,
            dat_saldo=DATA_LOTE, ind_status='I',
        )
        if D2(s.val_saldo) == D2(valor)
    ]
    assert len(inativas) == qtd


@then(parsers.parse('o fundo "{cod}" existe pendente, com origem "{tipo}", sistema "{sigla}" e data de auto-cadastro'))
def fundo_pendente_com_sistema(cod, tipo, sigla):
    from fluxocaixa.models import SistemaOrigem, TipoOrigemSaldo

    _db().session.expire_all()
    f = _fundo(cod)
    assert f is not None and f.ind_pendente_revisao == 'S'
    assert TipoOrigemSaldo.query.get(f.seq_tipo_origem).txt_sigla == tipo
    assert SistemaOrigem.query.get(f.seq_sistema_origem).txt_sigla == sigla
    assert f.dat_auto_cadastro is not None


@then(parsers.parse('o fundo "{cod}" existe pendente, com origem "{tipo}" e sem sistema'))
def fundo_pendente_sem_sistema(cod, tipo):
    from fluxocaixa.models import TipoOrigemSaldo

    _db().session.expire_all()
    f = _fundo(cod)
    assert f is not None and f.ind_pendente_revisao == 'S'
    assert TipoOrigemSaldo.query.get(f.seq_tipo_origem).txt_sigla == tipo
    assert f.seq_sistema_origem is None
    assert f.dat_auto_cadastro is not None


@then(parsers.parse('o resultado lista "{cod}" nos fundos auto-cadastrados'))
def resultado_auto_cadastrados(contexto, cod):
    assert cod in contexto["resultado"].fundos_auto_cadastrados


@then(parsers.parse('a importação é rejeitada com a mensagem "{mensagem}"'))
def importacao_rejeitada(contexto, mensagem):
    assert contexto["erro"] == mensagem, f"esperava {mensagem!r}, veio {contexto['erro']!r}"


@then(parsers.parse('o fundo "{cod}" não existe'))
def fundo_nao_existe(cod):
    _db().session.expire_all()
    assert _fundo(cod) is None


@then("o resultado indica falha sistêmica")
def falha_sistemica(contexto):
    r = contexto["resultado"]
    assert r.falha_sistemica is True
    assert r.linhas_inseridas == 0 and r.linhas_com_erro > 0


@then(parsers.parse("a resposta HTTP é {status:d} com linhasInseridas {n:d}"))
def resposta_com_inseridas(contexto, status, n):
    resp = contexto["resp"]
    assert resp.status_code == status, resp.text
    assert resp.json()["linhasInseridas"] == n


@then(parsers.parse("a resposta HTTP é {status:d} em JSON"))
def resposta_json(contexto, status):
    resp = contexto["resp"]
    assert resp.status_code == status, resp.text
    assert "application/json" in resp.headers.get("content-type", "")
