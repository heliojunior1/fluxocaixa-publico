import os

import pytest
from fastapi.testclient import TestClient

# Senha do admin após a troca obrigatória feita uma única vez na sessão de testes
ADMIN_SENHA_TESTES = "Senha-Testes-123"


@pytest.fixture(scope="session")
def app():
    """Create the real FastAPI application using a file-based test DB."""
    # Começa do zero: um test.db antigo (pré-Alembic, sem alembic_version)
    # dispararia a detecção de instalação legada no boot.
    if os.path.exists("test.db"):
        os.remove("test.db")
    os.environ["DATABASE_URL"] = "sqlite:///./test.db"
    from fluxocaixa import create_app

    application = create_app()
    return application


@pytest.fixture(scope="session")
def _admin_pronto(app):
    """Conclui a troca de senha obrigatória do admin (uma vez por sessão)."""
    tc = TestClient(app, follow_redirects=False)
    resp = tc.post("/login", data={"usuario": "admin", "senha": "admin"})
    if resp.status_code in (302, 303):
        tc.post(
            "/trocar-senha",
            data={
                "senha_atual": "admin",
                "nova_senha": ADMIN_SENHA_TESTES,
                "confirmacao": ADMIN_SENHA_TESTES,
            },
        )
    return ADMIN_SENHA_TESTES


@pytest.fixture()
def client(app, _admin_pronto) -> TestClient:
    """Cliente autenticado como admin (uso padrão dos testes)."""
    tc = TestClient(app)
    resp = tc.post(
        "/login",
        data={"usuario": "admin", "senha": _admin_pronto},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), "login do admin de testes falhou"
    return tc


@pytest.fixture()
def client_anonimo(app) -> TestClient:
    """Cliente sem sessão (testes de controle de acesso)."""
    return TestClient(app)
