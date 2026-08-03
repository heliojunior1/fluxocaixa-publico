"""Unitários do limite e da extensão de upload (spec importacao-arquivos R6).

Change: limites-e-validacao-de-upload. Import de `fluxocaixa` TARDIO.
"""
import asyncio

import pytest


class _UploadFalso:
    """Imita `UploadFile.read(n)` e registra quantos bytes foram pedidos.

    O registro é o ponto: o helper precisa ler `limite + 1`, e NÃO o arquivo
    inteiro — se lesse tudo para depois medir, o teto não protegeria de nada.
    """

    def __init__(self, conteudo: bytes, filename: str = "a.csv"):
        self._conteudo = conteudo
        self.filename = filename
        self.pedidos = []

    async def read(self, n: int = -1) -> bytes:
        self.pedidos.append(n)
        return self._conteudo[:n] if n >= 0 else self._conteudo


def _ler(upload, **kwargs):
    from fluxocaixa.services.preprocessamento import ler_upload_limitado

    return asyncio.get_event_loop().run_until_complete(
        ler_upload_limitado(upload, **kwargs))


def test_arquivo_dentro_do_limite_passa():
    upload = _UploadFalso(b"a" * 100)
    assert _ler(upload, max_bytes=1000) == b"a" * 100


def test_arquivo_acima_do_limite_e_recusado():
    from fluxocaixa.services.validacao import RegraNegocioError

    upload = _UploadFalso(b"a" * 2000)
    with pytest.raises(RegraNegocioError) as exc:
        _ler(upload, max_bytes=1000)
    assert "limite" in str(exc.value).lower()


def test_le_apenas_limite_mais_um_byte():
    """Se lesse o arquivo inteiro para depois medir, o teto não protegeria."""
    upload = _UploadFalso(b"a" * 10_000)
    try:
        _ler(upload, max_bytes=1000)
    except Exception:
        pass
    assert upload.pedidos == [1001], upload.pedidos


def test_arquivo_exatamente_no_limite_passa():
    upload = _UploadFalso(b"a" * 1000)
    assert len(_ler(upload, max_bytes=1000)) == 1000


@pytest.mark.parametrize("nome", ["dados.csv", "DADOS.CSV", "x.txt", "p.xlsx"])
def test_extensoes_suportadas_passam(nome):
    from fluxocaixa.services.preprocessamento import validar_extensao

    validar_extensao(nome)


@pytest.mark.parametrize("nome", ["a.pdf", "a.exe", "a", "", None, "a.csv.exe"])
def test_extensoes_nao_suportadas_sao_recusadas(nome):
    from fluxocaixa.services.preprocessamento import validar_extensao
    from fluxocaixa.services.validacao import RegraNegocioError

    with pytest.raises(RegraNegocioError) as exc:
        validar_extensao(nome)
    assert ".csv" in str(exc.value)
