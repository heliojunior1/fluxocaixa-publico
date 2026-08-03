"""Unitários de `_destino_seguro` (spec controle-acesso R2).

Change: corrigir-open-redirect-destino. Função pura, então a bateria de formas
maliciosas cabe aqui — mais barata e mais exaustiva que no BDD.

Import de `fluxocaixa` é TARDIO (convenção do projeto: import no topo de um
unitário quebra o isolamento de banco da suíte inteira).
"""
import pytest

# Formas que o navegador resolve como host externo, ainda que "comecem com /".
DESTINOS_EXTERNOS = [
    "//exemplo-externo.test",
    "//exemplo-externo.test/painel",
    "/\\exemplo-externo.test",
    "/\\\\exemplo-externo.test",
    "https://exemplo-externo.test",
    "http://exemplo-externo.test/painel",
    "//exemplo-externo.test:8080/x",
    "javascript:alert(1)",
    "JaVaScRiPt:alert(1)",
    "  //exemplo-externo.test",
    "\t//exemplo-externo.test",
    "\n/\\exemplo-externo.test",
    "",
    None,
]

DESTINOS_INTERNOS = [
    "/",
    "/saldos",
    "/relatorios/dfc",
    "/saldos?page=2&tipo=C",
    "/mapeamentos/1/editar",
    "/relatorios/dfc#ancora",
]


@pytest.mark.parametrize("destino", DESTINOS_EXTERNOS)
def test_destino_externo_cai_para_raiz(destino):
    from fluxocaixa.auth.routes import _destino_seguro

    assert _destino_seguro(destino) == "/", (
        f"{destino!r} escapou da guarda de open redirect")


@pytest.mark.parametrize("destino", DESTINOS_INTERNOS)
def test_destino_interno_e_preservado(destino):
    from fluxocaixa.auth.routes import _destino_seguro

    assert _destino_seguro(destino) == destino


def test_caminho_relativo_sem_barra_cai_para_raiz():
    """`saldos` (sem barra) resolveria relativo à página corrente — ambíguo."""
    from fluxocaixa.auth.routes import _destino_seguro

    assert _destino_seguro("saldos") == "/"
