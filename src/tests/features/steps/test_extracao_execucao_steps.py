"""Steps BDD — execução de fontes de extração (spec extracao-configuravel R3/R4/R6–R9)."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import (
    execucoes_da_fonte,
    fonte_por_nome,
    garantir_conector_fake,
    garantir_conta,
    garantir_fonte_ativa,
    garantir_fundo,
    garantir_sistema_origem,
    linha_extraida,
)
from ..conftest_permissoes import criar_usuario_com_perfil

scenarios("../extracao-configuravel/execucao.feature")

D2 = lambda v: Decimal(str(v)).quantize(Decimal("0.01"))


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


def _executar(contexto, nome):
    from fluxocaixa.services.extracao_service import executar_fonte
    from fluxocaixa.services.validacao import RegraNegocioError

    contexto["fonte_nome"] = nome
    fonte = fonte_por_nome(nome)
    try:
        contexto["execucao"] = executar_fonte(fonte.seq_fonte_extracao)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


def _ultima_execucao(contexto):
    execucoes = execucoes_da_fonte(contexto["fonte_nome"])
    assert execucoes, f"nenhuma execução registrada para {contexto['fonte_nome']!r}"
    return execucoes[-1]


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(777)


@given(parsers.parse('um sistema de origem "{sigla}" cadastrado'))
def sistema_cadastrado(app, sigla):
    garantir_sistema_origem(sigla)


@given('o conector de teste "FAKE" registrado', target_fixture="conector_fake")
def conector_fake_registrado(app):
    return garantir_conector_fake()


@given(parsers.parse('uma conta extraível "{ident}"'))
def conta_extraivel(app, ident):
    garantir_conta(ident)


@given(parsers.parse('um fundo extraível "{cod}"'))
def fundo_extraivel(app, cod):
    garantir_fundo(cod)


@given(parsers.parse('uma fonte "{nome}" do tipo "{tipo:w}"'))
def fonte_existente(app, nome, tipo):
    garantir_fonte_ativa(nome, tipo=tipo)


@given(parsers.parse('uma fonte "{nome}" do tipo "{tipo}" com token "{token}"'))
def fonte_com_token(app, nome, tipo, token):
    garantir_fonte_ativa(nome, tipo=tipo, token=token)


@given(parsers.parse('a variável de ambiente "{var}" definida como "{valor}"'))
def variavel_ambiente(monkeypatch, var, valor):
    monkeypatch.setenv(var, valor)


@given(parsers.parse('que o conector devolve saldos válidos de "{valor}" para {dias:d} dias na conta "{ident}" e fundo "{cod}"'))
def conector_devolve_dias(app, conector_fake, valor, dias, ident, cod):
    hoje = date.today()
    for i in range(dias):
        conector_fake.linhas.append(
            linha_extraida(ident, cod, valor, dat_saldo=hoje - timedelta(days=i))
        )


@given(parsers.parse('que o conector devolve um saldo de "{valor}" para a conta "{ident}" e fundo "{cod}"'))
def conector_devolve_um(app, conector_fake, valor, ident, cod):
    conector_fake.linhas.append(linha_extraida(ident, cod, valor))


@given(parsers.parse('que o conector devolve também um saldo para a conta inexistente "{ident}"'))
def conector_devolve_conta_inexistente(app, conector_fake, ident):
    conector_fake.linhas.append(linha_extraida(ident, "9999", "50.00"))


@given(parsers.parse('que o conector está configurado para falhar com "{mensagem}"'))
def conector_falha(app, conector_fake, mensagem):
    conector_fake.excecao = RuntimeError(mensagem)


@given(parsers.parse('que executei a fonte "{nome}"'))
def ja_executei(app, contexto, conector_fake, nome):
    _executar(contexto, nome)
    assert contexto["erro"] is None
    conector_fake.linhas = []


@given(parsers.parse('que a fonte "{nome}" foi inativada'))
def fonte_inativada(app, nome):
    from fluxocaixa.services.extracao_service import inativar_fonte

    inativar_fonte(fonte_por_nome(nome).seq_fonte_extracao)


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

@when(parsers.parse('executo a fonte "{nome}"'))
def executa_fonte(app, contexto, nome):
    _executar(contexto, nome)


@when(parsers.parse('testo a conexão da fonte "{nome}"'))
def quando_testo_conexao(app, contexto, nome):
    from fluxocaixa.services.extracao_service import testar_conexao_fonte

    contexto["fonte_nome"] = nome
    contexto["teste"] = testar_conexao_fonte(fonte_por_nome(nome).seq_fonte_extracao)


def _chamar_endpoint(cliente_http, contexto, nome, payload):
    contexto["fonte_nome"] = nome
    fonte = fonte_por_nome(nome)
    contexto["resp"] = cliente_http.post(
        f"/api/extracao/fontes/{fonte.seq_fonte_extracao}/executar", json=payload
    )


@when(parsers.parse('o cliente chama o endpoint de execução da fonte "{nome}" sem janela'))
def endpoint_sem_janela(cliente_http, contexto, nome):
    _chamar_endpoint(cliente_http, contexto, nome, {})


@when(parsers.parse('o cliente chama o endpoint de execução da fonte "{nome}" com janela de "{inicio}" a "{fim}"'))
def endpoint_com_janela(cliente_http, contexto, nome, inicio, fim):
    _chamar_endpoint(cliente_http, contexto, nome,
                     {"data_inicio": inicio, "data_fim": fim})


@when(parsers.parse('o cliente chama o endpoint de execução da fonte "{nome}" com apenas data_inicio "{inicio}"'))
def endpoint_janela_incompleta(cliente_http, contexto, nome, inicio):
    _chamar_endpoint(cliente_http, contexto, nome, {"data_inicio": inicio})


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('a execução registra status "{status}" com {ok:d} inseridas e {erro:d} com erro'))
def execucao_status(contexto, status, ok, erro):
    execucao = _ultima_execucao(contexto)
    assert execucao.cod_status == status, (
        f"esperava {status}, veio {execucao.cod_status} "
        f"(detalhe: {execucao.txt_detalhe_erros!r})"
    )
    assert (execucao.qtd_linhas_inseridas, execucao.qtd_linhas_erro) == (ok, erro)


@then(parsers.parse('o detalhe de erros da execução menciona "{trecho}"'))
def detalhe_menciona(contexto, trecho):
    execucao = _ultima_execucao(contexto)
    assert execucao.txt_detalhe_erros and trecho in execucao.txt_detalhe_erros


@then(parsers.parse('o saldo ativo da conta "{ident}" e fundo "{cod}" vale "{valor}" com tipo "{tipo}" e sistema "{sigla}"'))
def saldo_ativo_com_origem(ident, cod, valor, tipo, sigla):
    from fluxocaixa.models import SaldoContaFundo, SistemaOrigem, TipoOrigemSaldo

    _db().session.expire_all()
    ativos = SaldoContaFundo.query.filter_by(
        seq_conta=_conta(ident).seq_conta, seq_fundo=_fundo(cod).seq_fundo,
        dat_saldo=date.today(), ind_status="A",
    ).all()
    assert len(ativos) == 1
    saldo = ativos[0]
    assert D2(saldo.val_saldo) == D2(valor)
    assert TipoOrigemSaldo.query.get(saldo.seq_tipo_origem).txt_sigla == tipo
    assert SistemaOrigem.query.get(saldo.seq_sistema_origem).txt_sigla == sigla


@then(parsers.parse('o saldo ativo da conta "{ident}" e fundo "{cod}" passa a valer "{valor}"'))
def saldo_ativo(ident, cod, valor):
    from fluxocaixa.models import SaldoContaFundo

    _db().session.expire_all()
    ativos = SaldoContaFundo.query.filter_by(
        seq_conta=_conta(ident).seq_conta, seq_fundo=_fundo(cod).seq_fundo,
        dat_saldo=date.today(), ind_status="A",
    ).all()
    assert len(ativos) == 1
    assert D2(ativos[0].val_saldo) == D2(valor)


@then(parsers.parse('existe saldo inativo de "{valor}" para a conta "{ident}" e fundo "{cod}"'))
def saldo_inativo(valor, ident, cod):
    from fluxocaixa.models import SaldoContaFundo

    _db().session.expire_all()
    inativos = [
        s for s in SaldoContaFundo.query.filter_by(
            seq_conta=_conta(ident).seq_conta, seq_fundo=_fundo(cod).seq_fundo,
            dat_saldo=date.today(), ind_status="I",
        )
        if D2(s.val_saldo) == D2(valor)
    ]
    assert inativos, f"nenhum saldo inativo de {valor}"


@then(parsers.parse('a resposta HTTP é {status:d} com status "{cod_status}"'))
def resposta_com_status(contexto, status, cod_status):
    resp = contexto["resp"]
    assert resp.status_code == status, resp.text
    assert resp.json()["codStatus"] == cod_status


@then(parsers.parse('a resposta HTTP é {status:d} com mensagem contendo "{trecho}"'))
def resposta_com_mensagem(contexto, status, trecho):
    resp = contexto["resp"]
    assert resp.status_code == status, resp.text
    assert trecho.lower() in resp.json()["detail"].lower()


@then(parsers.parse("a resposta HTTP é {status:d} em JSON"))
def resposta_json(contexto, status):
    resp = contexto["resp"]
    assert resp.status_code == status, resp.text
    assert "application/json" in resp.headers.get("content-type", "")


@then(parsers.parse('a última execução da fonte "{nome}" tem disparo "{disparo}" e janela do dia corrente'))
def execucao_manual_dia_corrente(nome, disparo):
    execucoes = execucoes_da_fonte(nome)
    assert execucoes, f"nenhuma execução registrada para {nome!r}"
    execucao = execucoes[-1]
    assert execucao.cod_disparo == disparo
    assert execucao.dat_janela_inicio == date.today()
    assert execucao.dat_janela_fim == date.today()


@then(parsers.parse('nenhuma execução foi registrada para a fonte "{nome}"'))
def nenhuma_execucao(nome):
    assert execucoes_da_fonte(nome) == []


@then(parsers.parse('o conector recebeu o token "{valor}"'))
def conector_recebeu_token(conector_fake, valor):
    assert conector_fake.ultimo_config is not None
    assert conector_fake.ultimo_config.get("token") == valor


@then(parsers.parse('o config persistido da fonte "{nome}" contém "{placeholder}" e não contém "{valor}"'))
def config_persistido_sem_segredo(nome, placeholder, valor):
    import json

    fonte = fonte_por_nome(nome)
    persistido = json.dumps(fonte.json_config)
    assert placeholder in persistido
    assert valor not in persistido


@then("o teste de conexão retorna sucesso")
def entao_teste_conexao_ok(contexto):
    assert contexto["teste"].ok is True
