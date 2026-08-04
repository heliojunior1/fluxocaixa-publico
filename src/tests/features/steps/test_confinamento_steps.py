"""Steps BDD — confinamento de destino dos conectores (spec R23).

Change: confinar-conectores-extracao.
"""
import os

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import garantir_sistema_origem

scenarios("../extracao-configuravel/confinamento.feature")

PADRAO_NOME = "{:%Y%m%d}_0001_EXTRATO.csv"

# Formatos válidos — o cenário afere o CONFINAMENTO, não a validação de layout.
LAYOUT_ARQUIVO = {
    "separador": ";",
    "encoding": "utf-8-sig",
    "tem_header": False,
    "formato_data": "%d/%m/%Y",
    "formato_decimal": "PT_BR",
    "colunas": [
        {"origem": 0, "destino": "num_agencia"},
        {"origem": 1, "destino": "num_conta"},
        {"origem": 2, "destino": "dat_saldo", "transformacao": "data"},
        {"origem": 3, "destino": "val_saldo", "transformacao": "decimal"},
    ],
}
LAYOUT_MAPA = {"campos": [{"caminho": "saldo", "destino": "val_saldo"}]}


@pytest.fixture()
def contexto():
    return {}


# --------------------------------------------------------------------- Dado


@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente
    from fluxocaixa.extracao.conectores import registrar_conectores_disponiveis

    definir_usuario_corrente(777)
    registrar_conectores_disponiveis()


@given(parsers.parse('um sistema de origem "{sigla}" cadastrado'))
def sistema_cadastrado(app, sigla):
    garantir_sistema_origem(sigla)


@given("uma raiz de extração configurada")
def raiz_configurada(tmp_path, monkeypatch, contexto):
    from fluxocaixa.extracao import confinamento

    raiz = tmp_path / "raiz_extracao"
    raiz.mkdir()
    monkeypatch.setenv(confinamento.VAR_RAIZ, str(raiz))
    monkeypatch.delenv(confinamento.VAR_HOSTS_PERMITIDOS, raising=False)
    contexto["raiz"] = raiz
    contexto["fora"] = tmp_path / "fora_da_raiz"
    contexto["fora"].mkdir()


@given("um link simbólico dentro da raiz apontando para fora dela")
def symlink_para_fora(contexto):
    atalho = contexto["raiz"] / "atalho"
    os.symlink(contexto["fora"], atalho)
    contexto["atalho"] = atalho


@given(parsers.parse('que o host "{host}" está declarado como permitido'))
def host_permitido(host, monkeypatch):
    from fluxocaixa.extracao import confinamento

    monkeypatch.setenv(confinamento.VAR_HOSTS_PERMITIDOS, host)


# -------------------------------------------------------------------- Quando


def _criar_fonte_local(contexto, nome, diretorio):
    from fluxocaixa.services.extracao_service import criar_fonte
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        criar_fonte(
            nom_fonte=nome,
            cod_tipo_conector="FTP_ARQUIVO",
            sigla_sistema="SIS_C",
            json_config={
                "protocolo": "PASTA_LOCAL",
                "diretorio": str(diretorio),
                "padrao_nome": PADRAO_NOME,
            },
            json_layout=LAYOUT_ARQUIVO,
        )
        contexto["erro"] = None
    except (RegraNegocioError, Exception) as exc:
        # Pydantic embrulha o RegraNegocioError do validador em ValidationError;
        # o que importa ao cenário é a MENSAGEM chegar ao usuário.
        contexto["erro"] = str(exc)


@when(parsers.parse('cadastro a fonte local "{nome}" com diretório dentro da raiz'))
def cadastra_dentro(contexto, nome):
    dentro = contexto["raiz"] / "banco_a"
    dentro.mkdir(exist_ok=True)
    _criar_fonte_local(contexto, nome, dentro)


@when(parsers.parse('cadastro a fonte local "{nome}" com o diretório "{diretorio}"'))
def cadastra_diretorio(contexto, nome, diretorio):
    _criar_fonte_local(contexto, nome, diretorio)


@when(parsers.parse('cadastro a fonte local "{nome}" com o diretório do link'))
def cadastra_link(contexto, nome):
    _criar_fonte_local(contexto, nome, contexto["atalho"])


@when(parsers.parse('cadastro a fonte de API "{nome}" apontando para "{url}"'))
def cadastra_api(contexto, nome, url):
    from fluxocaixa.services.extracao_service import criar_fonte

    try:
        criar_fonte(
            nom_fonte=nome,
            cod_tipo_conector="API_REST",
            sigla_sistema="SIS_C",
            json_config={
                "url_base": url,
                "path_template": "/v1/saldo/agencia/{agencia}/conta/{conta}",
                "cod_banco": "001",
                "autenticacao": "BEARER",
                "token": "${TOKEN_FICTICIO}",
                "contas": [{"agencia": "0001", "conta": "12345-6"}],
            },
            json_layout=LAYOUT_MAPA,
        )
        contexto["erro"] = None
    except Exception as exc:
        contexto["erro"] = str(exc)


@when(parsers.parse('cadastro a fonte SQL "{nome}" apontando para um arquivo fora da raiz'))
def cadastra_sql_fora(contexto, nome):
    from fluxocaixa.services.extracao_service import criar_fonte

    try:
        criar_fonte(
            nom_fonte=nome,
            cod_tipo_conector="BANCO_SQL",
            sigla_sistema="SIS_C",
            json_config={
                "url_conexao": f"sqlite:///{contexto['fora']}/externo.db",
                "query": "SELECT 1 AS x WHERE :data_inicio <= :data_fim",
                "cod_banco": "001",
            },
            json_layout={"campos": [{"caminho": "x", "destino": "val_saldo"}]},
        )
        contexto["erro"] = None
    except Exception as exc:
        contexto["erro"] = str(exc)


# --------------------------------------------------------------------- Então


@then("o cadastro é recusado citando a raiz de extração")
def recusado_raiz(contexto):
    assert contexto["erro"], "o cadastro foi aceito"
    assert "raiz de extração" in contexto["erro"], contexto["erro"]


@then("o cadastro é recusado citando destino interno")
def recusado_interno(contexto):
    assert contexto["erro"], "o cadastro foi aceito"
    assert "destino interno" in contexto["erro"], contexto["erro"]


@then(parsers.parse('a fonte "{nome}" existe'))
def fonte_existe(app, contexto, nome):
    from ..conftest_extracao import fonte_por_nome

    assert contexto.get("erro") is None, contexto["erro"]
    assert fonte_por_nome(nome) is not None


@then(parsers.parse('a fonte "{nome}" não existe'))
def fonte_nao_existe(app, nome):
    from ..conftest_extracao import fonte_por_nome

    assert fonte_por_nome(nome) is None
