"""Steps BDD — limite e validação de upload (spec importacao-arquivos R6).

Change: limites-e-validacao-de-upload.
"""
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../importacao-arquivos/limites_upload.feature")

CSV_VALIDO = (
    "conta;fundo;data;valor\n"
    "12345-6;9999;01/07/2026;1234,56\n"
)


@pytest.fixture()
def contexto():
    return {}


@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(777)


def _enviar(client, contexto, conteudo: bytes, nome: str):
    from fluxocaixa.models import EtlStaging  # noqa: F401  (força o app pronto)

    contexto["resp"] = client.post(
        "/saldos/import",
        files={"file": (nome, conteudo, "text/csv")},
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )


@when("envio para importação um arquivo maior que o limite")
def envia_grande(client, contexto):
    from fluxocaixa.services.preprocessamento import MAX_UPLOAD_BYTES

    # +1 byte além do teto: o helper lê `limite + 1` justamente para decidir
    # sem materializar o arquivo.
    _enviar(client, contexto, b"a" * (MAX_UPLOAD_BYTES + 1), "grande.csv")


@when("envio para importação um arquivo válido dentro do limite")
def envia_valido(client, contexto):
    _enviar(client, contexto, CSV_VALIDO.encode("utf-8"), "saldos.csv")


@when(parsers.parse('envio para importação um arquivo com extensão "{ext}"'))
def envia_extensao(client, contexto, ext):
    _enviar(client, contexto, b"conteudo qualquer", f"planilha.{ext}")


def _mensagem(contexto) -> str:
    """A recusa é `RegraNegocioError` → flash na sessão + redirect."""
    resp = contexto["resp"]
    if resp.status_code in (302, 303):
        return resp.headers.get("location", "") + " " + resp.text
    return resp.text


@then("a importação é recusada citando o limite")
def recusada_limite(client, contexto):
    assert contexto["resp"].status_code in (302, 303, 400), contexto["resp"].status_code
    corpo = client.get("/saldos").text
    assert "limite" in corpo.lower(), corpo[:300]


@then("a importação é recusada citando os formatos aceitos")
def recusada_formato(client, contexto):
    assert contexto["resp"].status_code in (302, 303, 400)
    corpo = client.get("/saldos").text
    assert ".csv" in corpo.lower() or "não suportado" in corpo.lower(), corpo[:300]


@then("nenhuma pré-visualização é criada")
def sem_preview(contexto):
    destino = contexto["resp"].headers.get("location", "")
    assert "/importacoes/" not in destino, destino


@then("a pré-visualização é criada")
def com_preview(contexto):
    resp = contexto["resp"]
    destino = resp.headers.get("location", "")
    assert resp.status_code in (200, 302, 303), resp.status_code
    assert "/importacoes/" in destino or "preview" in resp.text.lower(), (
        f"{resp.status_code} {destino} {resp.text[:200]}")
