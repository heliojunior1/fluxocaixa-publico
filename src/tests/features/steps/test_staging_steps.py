"""Steps BDD — staging genérica da automação de lançamentos (spec R1–R4)."""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import (
    execucoes_da_fonte,
    fonte_por_nome,
    garantir_sistema_origem,
)

scenarios("../automacao-lancamentos/staging.feature")

QUERY = ("SELECT data, valor, natureza, ug FROM lancamentos_ext "
         "WHERE data BETWEEN :data_inicio AND :data_fim")

LAYOUT_LANC = {
    "capturar_atributos": True,
    "campos": [
        {"caminho": "data", "destino": "dat_saldo"},
        {"caminho": "valor", "destino": "val_saldo"},
    ],
}
LAYOUT_SEM_VALOR = {
    "capturar_atributos": True,
    "campos": [{"caminho": "data", "destino": "dat_saldo"}],
}


@pytest.fixture()
def contexto():
    return {}


@pytest.fixture()
def banco_ext(tmp_path):
    import sqlalchemy as sa

    url = f"sqlite:///{tmp_path / 'lanc.db'}"
    eng = sa.create_engine(url)
    with eng.begin() as conn:
        conn.execute(sa.text(
            "CREATE TABLE lancamentos_ext (data TEXT, valor TEXT, natureza TEXT, ug TEXT)"
        ))
    eng.dispose()
    return {"url": url}


def _inserir(banco_ext, linhas):
    import sqlalchemy as sa

    eng = sa.create_engine(banco_ext["url"])
    with eng.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO lancamentos_ext VALUES (:d, :v, :n, :u)"), linhas
        )
    eng.dispose()


def _lanc(valor, natureza="11120000", ug="510001", data="2026-07-10"):
    return {"d": data, "v": valor, "n": natureza, "u": ug}


def _criar_fonte_lanc(nome, banco_ext, *, layout=None):
    from fluxocaixa.services.extracao_service import criar_fonte

    return criar_fonte(
        nom_fonte=nome, cod_tipo_conector="BANCO_SQL", sigla_sistema="SIS_X",
        json_config={"url_conexao": banco_ext["url"], "query": QUERY,
                     "cod_banco": "001", "batch_size": 5000},
        json_layout=layout if layout is not None else LAYOUT_LANC,
        cod_destino="LANCAMENTO",
    )


def _staging_da_fonte(nome):
    from fluxocaixa.models import EtlStaging
    from fluxocaixa.models.base import db

    db.session.expire_all()
    fonte = fonte_por_nome(nome)
    return (EtlStaging.query.filter_by(seq_fonte_extracao=fonte.seq_fonte_extracao)
            .order_by(EtlStaging.seq_etl_staging).all())


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


@given("um banco externo com 3 lançamentos em 10/07/2026")
def banco_3(banco_ext):
    _inserir(banco_ext, [_lanc("100.00"), _lanc("200.00"), _lanc("300.00")])


@given("um banco externo com 2 lançamentos válidos e 1 com valor inválido em 10/07/2026")
def banco_parcial(banco_ext):
    _inserir(banco_ext, [_lanc("100.00"), _lanc("200.00"), _lanc("NAO_NUMERO")])


@given("um banco externo sem lançamentos")
def banco_vazio(banco_ext):
    pass  # tabela criada vazia


@given(parsers.parse('uma fonte de lançamento "{nome}" apontando para esse banco'))
def fonte_lanc(app, banco_ext, nome):
    _criar_fonte_lanc(nome, banco_ext)


@given(parsers.parse('que executei a fonte de lançamento "{nome}" para o dia "{dia}"'))
def ja_executei(app, contexto, nome, dia):
    from fluxocaixa.extracao.conector import Janela
    from fluxocaixa.services.extracao_service import executar_fonte

    d = date.fromisoformat(dia)
    executar_fonte(fonte_por_nome(nome).seq_fonte_extracao, janela=Janela(d, d))


@given(parsers.parse('que as linhas dessa execução estão com status "{s1}" e "{s2}"'))
def linhas_com_status(app, s1, s2):
    from fluxocaixa.models import EtlStaging
    from fluxocaixa.models.base import db

    linhas = EtlStaging.query.order_by(EtlStaging.seq_etl_staging).all()
    for i, ln in enumerate(linhas):
        ln.ind_status_processamento = s1 if i % 2 == 0 else s2
        ln.dsc_erro = "algo" if ln.ind_status_processamento == "2" else None
    db.session.commit()


@given("uma linha pendente na staging")
def linha_pendente(app, banco_ext, contexto):
    _inserir(banco_ext, [_lanc("100.00")])
    _criar_fonte_lanc("Uma Linha", banco_ext)
    from fluxocaixa.extracao.conector import Janela
    from fluxocaixa.services.extracao_service import executar_fonte

    executar_fonte(fonte_por_nome("Uma Linha").seq_fonte_extracao,
                   janela=Janela(date(2026, 7, 10), date(2026, 7, 10)))
    contexto["seq_linha"] = _staging_da_fonte("Uma Linha")[0].seq_etl_staging


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when(parsers.parse('cadastro a fonte de lançamento "{nome}" com layout de staging válido'))
def cadastra_valido(app, banco_ext, contexto, nome):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        _criar_fonte_lanc(nome, banco_ext)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@when(parsers.parse('cadastro a fonte de lançamento "{nome}" com layout sem val_saldo'))
def cadastra_invalido(app, banco_ext, contexto, nome):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        _criar_fonte_lanc(nome, banco_ext, layout=LAYOUT_SEM_VALOR)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@when(parsers.parse('executo a fonte de lançamento "{nome}" de "{ini}" a "{fim}"'))
def executa(app, contexto, nome, ini, fim):
    from fluxocaixa.extracao.conector import Janela
    from fluxocaixa.services.extracao_service import executar_fonte

    contexto["fonte_nome"] = nome
    executar_fonte(fonte_por_nome(nome).seq_fonte_extracao,
                   janela=Janela(date.fromisoformat(ini), date.fromisoformat(fim)))


@when(parsers.parse('marco a linha da staging como erro com uma mensagem de {n:d} caracteres'))
def marca_erro(app, contexto, n):
    from fluxocaixa.services.staging_service import marcar_erro

    marcar_erro(contexto["seq_linha"], "X" * n)


@when(parsers.parse('reprocesso a execução da fonte "{nome}"'))
def reprocessa(app, contexto, nome):
    from fluxocaixa.services.staging_service import reprocessar_execucao

    contexto["fonte_nome"] = nome
    seq_exec = execucoes_da_fonte(nome)[-1].seq_execucao_extracao
    reprocessar_execucao(seq_exec)


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('a fonte "{nome}" existe com destino "{destino}"'))
def fonte_existe_destino(contexto, nome, destino):
    assert contexto.get("erro") is None, f"rejeitado: {contexto.get('erro')!r}"
    fonte = fonte_por_nome(nome)
    assert fonte is not None and fonte.cod_destino == destino


@then("o cadastro de lançamento é rejeitado")
def cadastro_rejeitado(contexto):
    assert contexto["erro"] is not None


@then(parsers.parse('a fonte "{nome}" não existe'))
def fonte_nao_existe(nome):
    assert fonte_por_nome(nome) is None


@then(parsers.parse('a execução de lançamento registra status "{status}" com {ok:d} gravadas e {erro:d} com erro'))
def execucao_status(contexto, status, ok, erro):
    e = execucoes_da_fonte(contexto["fonte_nome"])[-1]
    assert e.cod_status == status, (
        f"esperava {status}, veio {e.cod_status} (detalhe: {e.txt_detalhe_erros!r})"
    )
    assert (e.qtd_linhas_inseridas, e.qtd_linhas_erro) == (ok, erro)


@then(parsers.parse('a staging tem {n:d} linhas pendentes da fonte "{nome}"'))
def staging_pendentes(n, nome):
    linhas = _staging_da_fonte(nome)
    assert len(linhas) == n
    assert all(ln.ind_status_processamento == "0" for ln in linhas)


@then("cada linha da staging guarda a linha crua em json_atributos")
def staging_atributos(contexto):
    linhas = _staging_da_fonte(contexto["fonte_nome"])
    for ln in linhas:
        assert ln.json_atributos and "natureza" in ln.json_atributos


@then(parsers.parse('o detalhe da execução de lançamento menciona "{trecho}"'))
def detalhe_menciona(contexto, trecho):
    e = execucoes_da_fonte(contexto["fonte_nome"])[-1]
    assert e.txt_detalhe_erros and trecho in e.txt_detalhe_erros


@then(parsers.parse('a linha da staging fica com status "{status}" e dsc_erro com no máximo {n:d} caracteres'))
def linha_status_trunc(app, contexto, status, n):
    from fluxocaixa.models import EtlStaging

    from fluxocaixa.models.base import db
    db.session.expire_all()
    ln = EtlStaging.query.get(contexto["seq_linha"])
    assert ln.ind_status_processamento == status
    assert ln.dsc_erro is not None and len(ln.dsc_erro) <= n


@then(parsers.parse('todas as linhas da execução voltam ao status "{status}" com dsc_erro vazio'))
def linhas_resetadas(app, contexto, status):
    linhas = _staging_da_fonte(contexto["fonte_nome"])
    assert linhas
    assert all(ln.ind_status_processamento == status and not ln.dsc_erro for ln in linhas)
