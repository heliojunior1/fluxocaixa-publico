import os
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .auth import (
    exigir_login,
    obter_secret_key,
    registrar_handlers,
    router_publico,
    router_sessao,
)
from .bootstrap_db import env_flag, preparar_banco
from .config import Config
from .config_guarda import validar_configuracao
from .auth.csrf import obter_token, verificar_csrf
from .seguranca_http import CabecalhosSegurancaMiddleware
from .services.seed import seed_data
from .services.seed_dominio import seed_dominio
from .utils.formatters import format_currency
from .web import router, templates

SESSAO_MAX_AGE_SEGUNDOS = 8 * 3600  # expediente


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Agendador de extração vive no ciclo do servidor (spec extracao R5).

    Precisa do event loop ativo — por isso lifespan, não create_app. Em
    testes (TestClient sem context manager) o lifespan não roda; os testes
    iniciam/encerram o agendador explicitamente."""
    from .extracao import scheduler as scheduler_extracao

    scheduler_extracao.iniciar()
    yield
    scheduler_extracao.encerrar()


def create_app(config_class: type[Config] = Config) -> FastAPI:
    """Create and configure the FastAPI application."""
    static_folder = os.path.join(os.path.dirname(__file__), "static")

    # OpenAPI desabilitada nas URLs default — servida atrás de login (R2)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=_lifespan)

    # Schema via Alembic (AUTO_MIGRATE), domínio sempre, demo opcional
    preparar_banco()
    validar_configuracao(dict(os.environ))

    seed_dominio()
    if env_flag("SEED_DEMO_DATA", True):
        seed_data()

    # Cabeçalhos de segurança (controle-acesso R11). Registrado ANTES do
    # SessionMiddleware: no Starlette o último adicionado é o mais externo,
    # então assim os cabeçalhos envolvem também as respostas de sessão.
    app.add_middleware(CabecalhosSegurancaMiddleware)

    # Sessão em cookie assinado (HttpOnly por padrão; Secure em produção)
    app.add_middleware(
        SessionMiddleware,
        secret_key=obter_secret_key(),
        max_age=SESSAO_MAX_AGE_SEGUNDOS,
        same_site="lax",
        # Seguro por DEFAULT: desligado apenas em dev. Antes exigia
        # APP_ENV=prod, então quem não definisse a variável rodava sem
        # `Secure` — a configuração segura não pode depender de alguém
        # lembrar de setar algo.
        https_only=os.getenv("APP_ENV") != "dev",
    )
    registrar_handlers(app)

    # Register Jinja2 filters
    templates.env.filters["format_currency"] = format_currency

    # Token CSRF disponível a todo template (controle-acesso R12).
    templates.env.globals["csrf_token"] = lambda request: obter_token(request.session)

    # Rotas de autenticação (login público; logout/troca exigem sessão)
    app.include_router(router_publico)
    app.include_router(router_sessao, dependencies=[Depends(verificar_csrf)])

    # Todas as rotas de negócio exigem login (proteção default — R2)
    app.include_router(
        router, dependencies=[Depends(exigir_login), Depends(verificar_csrf)]
    )

    # Documentação OpenAPI atrás de login
    docs_router = APIRouter(dependencies=[Depends(exigir_login)])

    @docs_router.get("/docs", include_in_schema=False)
    async def _docs():
        return get_swagger_ui_html(openapi_url="/openapi.json", title="FluxoDeCaixa — Docs")

    @docs_router.get("/openapi.json", include_in_schema=False)
    async def _openapi():
        return JSONResponse(app.openapi())

    app.include_router(docs_router)

    # Mount static files (público)
    app.mount("/static", StaticFiles(directory=static_folder), name="static")

    # Fecha as conexões abertas pelo boot (migrações/seeds). Essencial com
    # gunicorn --preload: sem isso os workers herdariam do master, via fork,
    # conexões SQLite abertas — cada worker deve criar as suas sob demanda.
    from .models.base import SessionLocal, engine

    SessionLocal.remove()
    engine.dispose()

    return app
