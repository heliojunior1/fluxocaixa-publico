"""Unitários do confinamento de conectores (spec extracao-configuravel R23).

Change: confinar-conectores-extracao. As duas guardas são funções puras sobre
caminho e host, então a bateria de formas maliciosas cabe aqui — mais barata e
mais exaustiva que no BDD.

Import de `fluxocaixa` é TARDIO (convenção: import no topo de um unitário quebra
o isolamento de banco da suíte).
"""
import os

import pytest

# Formas de alcançar o próprio host / rede interna.
HOSTS_INTERNOS = [
    "127.0.0.1",
    "127.1",                      # forma curta do loopback
    "0.0.0.0",
    "::1",
    "::ffff:127.0.0.1",           # loopback mapeado em IPv6
    "10.0.0.5",
    "172.16.0.9",
    "192.168.1.10",
    "169.254.169.254",            # metadados de nuvem (link-local)
    "metadata.google.internal",
    "METADATA.GOOGLE.INTERNAL",   # o cadastro não normaliza caixa
    "224.0.0.1",                  # multicast
]

HOSTS_EXTERNOS = [
    "api.exemplo.test",
    "8.8.8.8",
    "banco-externo.exemplo.test",
]


@pytest.fixture()
def raiz(tmp_path, monkeypatch):
    from fluxocaixa.extracao import confinamento

    destino = tmp_path / "extracao"
    destino.mkdir()
    monkeypatch.setenv(confinamento.VAR_RAIZ, str(destino))
    return destino


@pytest.mark.parametrize("host", HOSTS_INTERNOS)
def test_host_interno_e_recusado(host, monkeypatch):
    from fluxocaixa.extracao.confinamento import (
        VAR_HOSTS_PERMITIDOS,
        validar_host_externo,
    )
    from fluxocaixa.services.validacao import RegraNegocioError

    monkeypatch.delenv(VAR_HOSTS_PERMITIDOS, raising=False)
    with pytest.raises(RegraNegocioError):
        validar_host_externo(host)


@pytest.mark.parametrize("host", HOSTS_EXTERNOS)
def test_host_externo_passa(host, monkeypatch):
    from fluxocaixa.extracao.confinamento import (
        VAR_HOSTS_PERMITIDOS,
        validar_host_externo,
    )

    monkeypatch.delenv(VAR_HOSTS_PERMITIDOS, raising=False)
    assert validar_host_externo(host) == host


def test_host_interno_declarado_passa(monkeypatch):
    """Extrair de host interno é o caso de uso principal — a exceção é declarada."""
    from fluxocaixa.extracao.confinamento import (
        VAR_HOSTS_PERMITIDOS,
        validar_host_externo,
    )

    monkeypatch.setenv(VAR_HOSTS_PERMITIDOS, "10.0.0.5, erp.interno.test")
    assert validar_host_externo("10.0.0.5") == "10.0.0.5"
    assert validar_host_externo("erp.interno.test") == "erp.interno.test"


def test_diretorio_dentro_da_raiz_passa(raiz):
    from fluxocaixa.extracao.confinamento import validar_diretorio_local

    dentro = raiz / "banco_a"
    dentro.mkdir()
    assert validar_diretorio_local(str(dentro)) == os.path.realpath(str(dentro))


def test_diretorio_absoluto_fora_da_raiz_e_recusado(raiz):
    from fluxocaixa.extracao.confinamento import validar_diretorio_local
    from fluxocaixa.services.validacao import RegraNegocioError

    with pytest.raises(RegraNegocioError):
        validar_diretorio_local("/etc")


def test_traversal_relativo_e_recusado(raiz):
    from fluxocaixa.extracao.confinamento import validar_diretorio_local
    from fluxocaixa.services.validacao import RegraNegocioError

    with pytest.raises(RegraNegocioError):
        validar_diretorio_local(str(raiz / ".." / ".." / "etc"))


def test_symlink_para_fora_da_raiz_e_recusado(raiz, tmp_path):
    """Não contém `..` e é absoluto sob a raiz — só `realpath` pega."""
    from fluxocaixa.extracao.confinamento import validar_diretorio_local
    from fluxocaixa.services.validacao import RegraNegocioError

    fora = tmp_path / "segredos"
    fora.mkdir()
    atalho = raiz / "atalho"
    os.symlink(fora, atalho)

    with pytest.raises(RegraNegocioError):
        validar_diretorio_local(str(atalho))


def test_url_conexao_sqlite_fora_da_raiz_e_recusada(raiz, tmp_path):
    from fluxocaixa.extracao.confinamento import validar_url_conexao
    from fluxocaixa.services.validacao import RegraNegocioError

    with pytest.raises(RegraNegocioError):
        validar_url_conexao(f"sqlite:///{tmp_path}/externo.db")


def test_url_conexao_sqlite_dentro_da_raiz_passa(raiz):
    from fluxocaixa.extracao.confinamento import validar_url_conexao

    url = f"sqlite:///{raiz}/externo.db"
    assert validar_url_conexao(url) == url


def test_url_conexao_para_host_interno_e_recusada(raiz, monkeypatch):
    from fluxocaixa.extracao.confinamento import (
        VAR_HOSTS_PERMITIDOS,
        validar_url_conexao,
    )
    from fluxocaixa.services.validacao import RegraNegocioError

    monkeypatch.delenv(VAR_HOSTS_PERMITIDOS, raising=False)
    with pytest.raises(RegraNegocioError):
        validar_url_conexao("postgresql://u:p@127.0.0.1:5432/base")


def test_url_externa_valida_o_host(monkeypatch):
    from fluxocaixa.extracao.confinamento import (
        VAR_HOSTS_PERMITIDOS,
        validar_url_externa,
    )
    from fluxocaixa.services.validacao import RegraNegocioError

    monkeypatch.delenv(VAR_HOSTS_PERMITIDOS, raising=False)
    with pytest.raises(RegraNegocioError):
        validar_url_externa("http://169.254.169.254/latest/meta-data/")
    assert validar_url_externa("https://api.exemplo.test/v1") == \
        "https://api.exemplo.test/v1"
