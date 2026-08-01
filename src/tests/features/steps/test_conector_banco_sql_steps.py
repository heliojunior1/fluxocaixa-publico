"""Steps BDD — conector de banco SQL externo (spec R21)."""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import (
    execucoes_da_fonte,
    fonte_por_nome,
    garantir_conta,
    garantir_sistema_origem,
)

scenarios("../extracao-configuravel/conector_banco_sql.feature")

QUERY = ("SELECT agencia, conta, cod_fundo, nome_fundo, data, valor "
         "FROM saldos_ext WHERE data BETWEEN :data_inicio AND :data_fim")

LAYOUT_SQL = {
    "campos": [
        {"caminho": "agencia", "destino": "num_agencia"},
        {"caminho": "conta", "destino": "num_conta"},
        {"caminho": "cod_fundo", "destino": "cod_fundo"},
        {"caminho": "nome_fundo", "destino": "dsc_fundo"},
        {"caminho": "data", "destino": "dat_saldo"},
        {"caminho": "valor", "destino": "val_saldo"},
    ],
}


@pytest.fixture()
def contexto():
    return {}


@pytest.fixture()
def banco_ext(tmp_path):
    """SQLite externo com a tabela de saldos (simula o banco do órgão)."""
    import sqlalchemy as sa

    caminho = tmp_path / "externo.db"
    url = f"sqlite:///{caminho}"
    eng = sa.create_engine(url)
    with eng.begin() as conn:
        conn.execute(sa.text(
            "CREATE TABLE saldos_ext (agencia TEXT, conta TEXT, cod_fundo TEXT, "
            "nome_fundo TEXT, data TEXT, valor TEXT)"
        ))
    eng.dispose()
    return {"url": url, "path": caminho}


def _inserir(banco_ext, linhas):
    import sqlalchemy as sa

    eng = sa.create_engine(banco_ext["url"])
    with eng.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO saldos_ext VALUES (:ag, :cc, :cf, :nf, :dt, :vl)"),
            linhas,
        )
    eng.dispose()


def _linha(conta, fundo, data, valor, agencia="0001"):
    return {"ag": agencia, "cc": conta, "cf": fundo, "nf": f"FUNDO {fundo}",
            "dt": data, "vl": valor}


def _criar_fonte_sql(nome, banco_ext, *, query=QUERY, destino="SALDO_FUNDO",
                     batch_size=5000, layout=None):
    from fluxocaixa.services.extracao_service import criar_fonte

    return criar_fonte(
        nom_fonte=nome, cod_tipo_conector="BANCO_SQL", sigla_sistema="SIS_X",
        json_config={"url_conexao": banco_ext["url"], "query": query,
                     "cod_banco": "001", "batch_size": batch_size},
        json_layout=layout if layout is not None else LAYOUT_SQL,
        cod_destino=destino,
    )


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


@given('o conector "BANCO_SQL" registrado')
def conector_sql_registrado(app):
    from fluxocaixa.extracao import registry
    from fluxocaixa.extracao.conectores.banco_sql import ConectorBancoSql

    if "BANCO_SQL" not in registry.tipos_disponiveis():
        registry.registrar(ConectorBancoSql())


@given("as contas de SQL cadastradas")
def contas_sql(app):
    garantir_conta("001/0001/12345")
    garantir_conta("001/0001/2020")


@given("um banco externo com saldos em 10/07/2026")
def banco_com_saldos(banco_ext):
    _inserir(banco_ext, [
        _linha("12345", "9101", "2026-07-10", "1850432.10"),
        _linha("2020", "9102", "2026-07-10", "925100.55"),
    ])


@given("um banco externo com saldos em 10/07/2026 e em 20/07/2026")
def banco_dois_periodos(banco_ext):
    _inserir(banco_ext, [
        _linha("12345", "9101", "2026-07-10", "100.00"),
        _linha("2020", "9102", "2026-07-10", "200.00"),
        _linha("12345", "9101", "2026-07-20", "999.00"),
    ])


@given("um banco externo com 60 saldos em 10/07/2026")
def banco_60(banco_ext):
    linhas = [_linha("12345", str(1000 + i), "2026-07-10", f"{i + 1}.00") for i in range(60)]
    _inserir(banco_ext, linhas)


@given("um banco externo com um saldo válido e um saldo com valor inválido em 10/07/2026")
def banco_um_invalido(banco_ext):
    _inserir(banco_ext, [
        _linha("12345", "9101", "2026-07-10", "500.00"),
        _linha("2020", "9102", "2026-07-10", "NAO_NUMERO"),
    ])


@given(parsers.parse('uma fonte "{nome}" que consulta esse banco por período'))
def fonte_sql(app, banco_ext, nome):
    _criar_fonte_sql(nome, banco_ext)


@given(parsers.parse('uma fonte "{nome}" que consulta esse banco por período com batch {n:d}'))
def fonte_sql_batch(app, banco_ext, nome, n):
    _criar_fonte_sql(nome, banco_ext, batch_size=n)


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when(parsers.parse('executo a fonte "{nome}" de "{ini}" a "{fim}"'))
def executa_janela(app, contexto, nome, ini, fim):
    from fluxocaixa.extracao.conector import Janela
    from fluxocaixa.services.extracao_service import executar_fonte

    contexto["fonte_nome"] = nome
    executar_fonte(fonte_por_nome(nome).seq_fonte_extracao,
                   janela=Janela(date.fromisoformat(ini), date.fromisoformat(fim)))


@when(parsers.parse('cadastro pela API uma fonte SQL com a query "{query}"'))
def cadastra_query_ruim(app, banco_ext, contexto, query):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        _criar_fonte_sql("SQL Perigosa", banco_ext, query=query)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@when(parsers.parse('cadastro pela API uma fonte SQL "{nome}" com comentário antes do SELECT'))
def cadastra_comentario(app, banco_ext, contexto, nome):
    from fluxocaixa.services.validacao import RegraNegocioError

    q = "-- carga diária\n/* bloco */\n" + QUERY
    try:
        _criar_fonte_sql(nome, banco_ext, query=q)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@when(parsers.parse('cadastro pela API uma fonte SQL com destino "{destino}"'))
def cadastra_destino(app, banco_ext, contexto, destino):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        _criar_fonte_sql("SQL Destino", banco_ext, destino=destino)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@when(parsers.parse('testo a conexão da fonte "{alvo}"'))
def quando_testar_conexao(app, contexto, alvo):
    from fluxocaixa.services.extracao_service import testar_conexao_fonte

    contexto["fonte_nome"] = alvo
    contexto["teste"] = testar_conexao_fonte(fonte_por_nome(alvo).seq_fonte_extracao)


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('a execução de SQL registra status "{status}" com {ok:d} inseridas e {erro:d} com erro'))
def execucao_sql_status(contexto, status, ok, erro):
    execucoes = execucoes_da_fonte(contexto["fonte_nome"])
    assert execucoes, f"nenhuma execução para {contexto['fonte_nome']!r}"
    e = execucoes[-1]
    assert e.cod_status == status, (
        f"esperava {status}, veio {e.cod_status} (detalhe: {e.txt_detalhe_erros!r})"
    )
    assert (e.qtd_linhas_inseridas, e.qtd_linhas_erro) == (ok, erro)


@then(parsers.parse('o saldo gravado da conta "{ident}" e fundo "{cod}" vale "{valor}"'))
def saldo_gravado(ident, cod, valor):
    from fluxocaixa.models import ContaBancaria, Fundo, SaldoContaFundo
    from fluxocaixa.models.base import db

    db.session.expire_all()
    banco, ag, num = ident.split("/")
    conta = ContaBancaria.query.filter_by(cod_banco=banco, num_agencia=ag, num_conta=num).first()
    fundo = Fundo.query.filter_by(cod_fundo=cod).first()
    saldo = SaldoContaFundo.query.filter_by(
        seq_conta=conta.seq_conta, seq_fundo=fundo.seq_fundo, ind_status="A"
    ).first()
    assert saldo is not None
    assert saldo.val_saldo == Decimal(valor).quantize(Decimal("0.01"))


@then("o cadastro de SQL é rejeitado")
def cadastro_rejeitado(contexto):
    assert contexto["erro"] is not None


@then(parsers.parse('a fonte "{nome}" não existe'))
def fonte_nao_existe(nome):
    assert fonte_por_nome(nome) is None


@then(parsers.parse('a fonte "{nome}" existe'))
def fonte_existe(contexto, nome):
    assert contexto["erro"] is None, f"cadastro rejeitado: {contexto['erro']!r}"
    assert fonte_por_nome(nome) is not None


@then("o teste de conexão de SQL retorna sucesso")
def entao_teste_conexao_ok(contexto):
    assert contexto["teste"].ok is True, contexto["teste"].mensagem


@then(parsers.parse('nenhuma execução foi registrada para a fonte de SQL "{nome}"'))
def nenhuma_execucao(nome):
    assert execucoes_da_fonte(nome) == []
