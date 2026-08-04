"""Ciclo de vida da sessão SQLAlchemy por requisição (infraestrutura-banco R13).

Change: sessao-sqlalchemy-por-request (achado P1 — o único crítico da revisão
de 2026-08-03). `SessionLocal` é `scoped_session` (thread-local) e TODOS os
endpoints são `async def` executando na thread do event loop: sem remoção por
request, o processo inteiro compartilhava UMA `Session` nunca fechada — o
identity map devolvia estado carregado por requests anteriores (leitura
obsoleta com cara de dado atual), o rollback do `SafeAPIRouter` desfazia o
pending de quem estivesse na mesma sessão, e objetos acumulavam para sempre.

ASGI puro, e NÃO `BaseHTTPMiddleware`: o projeto já documentou (CSRF) que o
BaseHTTP entrega um `Request` DIFERENTE ao endpoint. Aqui não lemos o corpo,
mas o padrão fica alinhado e sem o overhead do wrapper.

Limitação conhecida que PERMANECE: o I/O de banco síncrono continua rodando
dentro de `async def` (bloqueia o event loop). A solução real — endpoints
`def` + injeção de sessão — é mudança estrutural própria.
"""
from .models.base import SessionLocal


class SessaoPorRequestMiddleware:
    """`try/finally: SessionLocal.remove()` em toda requisição HTTP.

    O `remove()` faz rollback de pendências não commitadas e fecha a sessão
    da thread corrente — o próximo request começa limpo.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        finally:
            SessionLocal.remove()
