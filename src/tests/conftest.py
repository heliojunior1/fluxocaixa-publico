import os

import pytest
from fastapi.testclient import TestClient

# Senha do admin após a troca obrigatória feita uma única vez na sessão de testes
ADMIN_SENHA_TESTES = "Senha-Testes-123"


@pytest.fixture(scope="session", autouse=True)
def _raiz_extracao(tmp_path_factory):
    """Declara a raiz de confinamento da extração para a suíte inteira.

    O confinamento (extracao-configuravel R23) exige que todo caminho local de
    fonte esteja sob `EXTRACAO_PASTA_RAIZ`. Os testes montam suas fontes em
    `tmp_path`, que vive sob a base temporária do pytest — apontar a raiz para
    lá é o ambiente de teste declarando a sua raiz, como qualquer instalação
    faz, e NÃO um relaxamento da guarda: caminho fora dessa base continua
    recusado (é o que o unitário de `/etc` afere).
    """
    base = str(tmp_path_factory.getbasetemp())
    os.environ["EXTRACAO_PASTA_RAIZ"] = base
    yield base


@pytest.fixture(scope="session")
def app(_raiz_extracao):
    """Create the real FastAPI application using a file-based test DB."""
    # Começa do zero: um test.db antigo (pré-Alembic, sem alembic_version)
    # dispararia a detecção de instalação legada no boot.
    if os.path.exists("test.db"):
        os.remove("test.db")
    os.environ["DATABASE_URL"] = "sqlite:///./test.db"
    # A senha inicial do admin passou a ser ALEATÓRIA quando a variável não
    # está definida (controle-acesso R4) — o ambiente de teste declara a sua,
    # como qualquer instalação faz. Sem isto a suíte não conseguiria logar.
    os.environ["ADMIN_INITIAL_PASSWORD"] = "admin"
    # `https_only` passou a ser o DEFAULT (controle-acesso R3), desligado só
    # em dev. O TestClient fala HTTP, então sem declarar o ambiente o cookie
    # `Secure` não voltaria e nenhuma sessão se sustentaria. O ambiente de
    # teste É de desenvolvimento — declará-lo é o correto, não um contorno.
    os.environ.setdefault("APP_ENV", "dev")
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


@pytest.fixture(scope="session", autouse=True)
def _testclient_envia_csrf():
    """Faz TODO `TestClient` da suíte enviar o token CSRF, como o navegador.

    Centralizado aqui porque a suíte cria `TestClient` em 19 pontos (fixtures de
    permissão, `navegador` de cada módulo BDD, clientes ad hoc). Editar os 19
    deixaria o vigésimo de fora — e o vigésimo falharia com 403 numa mensagem
    que não explica nada.

    ⚠️ Isto NÃO afrouxa a verificação: o token continua sendo exigido e
    validado pelo middleware. O que o wrapper faz é o que o `seguranca.js` faz
    no navegador — buscar o token numa página e anexá-lo. Cenário que precise
    testar a AUSÊNCIA do token limpa o cabeçalho explicitamente
    (`features/controle-acesso/csrf.feature`).
    """
    # ⚠️ Import TARDIO, dentro do wrapper. Esta fixture é autouse de sessão e
    # pode rodar ANTES da fixture `app` — importar `fluxocaixa` aqui criaria o
    # engine com o DATABASE_URL default (instance/fluxo.db) e a suíte inteira
    # rodaria contra o banco errado. É a armadilha registrada no CLAUDE.md.
    CABECALHO = "X-CSRF-Token"
    METODOS_SEGUROS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

    # Duas formas de o token chegar à página: a meta tag do `base.html` e o
    # campo oculto das telas standalone (`trocar_senha.html`), que não estendem
    # o base — o navegador lê as duas.
    marcadores = ('name="csrf-token" content="', 'name="csrf_token" value="')
    original = TestClient.request

    cache: dict = {}

    def request(self, method, url, *args, **kwargs):
        if str(method).upper() in METODOS_SEGUROS:
            return original(self, method, url, *args, **kwargs)
        if CABECALHO in self.headers or CABECALHO in (kwargs.get("headers") or {}):
            return original(self, method, url, *args, **kwargs)

        # O token é POR SESSÃO, e a sessão muda a cada login. Cachear no cliente
        # entregaria o token do usuário anterior depois de trocar de login —
        # 403 com mensagem que não explica nada. A chave do cache é o cookie.
        cookie = self.cookies.get("session")
        token = cache.get(cookie) if cookie else None
        if token is None:
            for caminho in ("/", "/saldos", "/trocar-senha"):
                corpo = original(self, "GET", caminho, follow_redirects=True).text
                for marcador in marcadores:
                    if marcador in corpo:
                        token = corpo.split(marcador, 1)[1].split('"', 1)[0]
                        break
                if token:
                    if cookie:
                        cache[cookie] = token
                    break
        if token:
            cabecalhos = dict(kwargs.get("headers") or {})
            cabecalhos[CABECALHO] = token
            kwargs["headers"] = cabecalhos
        return original(self, method, url, *args, **kwargs)

    TestClient.request = request
    yield
    TestClient.request = original


def aparelhar_csrf(tc: TestClient) -> TestClient:
    """Faz o cliente enviar o token CSRF em toda requisição, como o navegador.

    A alternativa seria isentar o ambiente de teste da verificação — e isso
    anularia a proteção exatamente onde ela deveria ser exercitada. Assim a
    suíte continua provando o caminho feliz ATRAVÉS da proteção, e o cenário
    que queira testar a ausência do token o faz explicitamente
    (`features/controle-acesso/csrf.feature`).
    """
    from fluxocaixa.auth.csrf import CABECALHO

    # O token vive na sessão assinada e a página o expõe na meta tag — o
    # cliente o lê do mesmo lugar que o `seguranca.js` lê no navegador.
    marcador = 'name="csrf-token" content="'
    for caminho in ("/", "/saldos", "/login"):
        corpo = tc.get(caminho).text
        if marcador in corpo:
            tc.headers.update({CABECALHO: corpo.split(marcador, 1)[1].split('"', 1)[0]})
            break
    return tc


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
    return aparelhar_csrf(tc)


@pytest.fixture()
def client_anonimo(app) -> TestClient:
    """Cliente sem sessão (testes de controle de acesso)."""
    return TestClient(app)
