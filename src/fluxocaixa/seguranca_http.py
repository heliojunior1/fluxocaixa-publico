"""Cabeçalhos de segurança HTTP (spec controle-acesso R11).

Change: headers-seguranca-http.
"""
import os

from starlette.middleware.base import BaseHTTPMiddleware

# ⚠️ `script-src` admite `'unsafe-inline'` DELIBERADAMENTE e em caráter
# TRANSITÓRIO. O projeto tem 51 templates com `<script>` inline e dezenas de
# handlers `onclick=`; uma política sem `unsafe-inline` quebraria praticamente
# toda a aplicação de uma vez. Apertar isso exige extrair o JS para /static —
# trabalho próprio, e não algo a embutir num change de cabeçalhos.
#
# O que JÁ vale integralmente, sem depender do inline: `frame-ancestors`
# (clickjacking, relevante porque há ações destrutivas de um clique),
# `object-src` e `base-uri` (dois vetores de injeção), além de `nosniff` e
# `Referrer-Policy`.
_CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    # data: cobre os ícones embutidos; blob: é usado pelo Chart.js ao exportar
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    "connect-src 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "object-src 'none'",
    "base-uri 'self'",
])

_CABECALHOS = {
    "Content-Security-Policy": _CSP,
    "X-Content-Type-Options": "nosniff",
    # `same-origin` não vaza a URL interna para terceiros — reduz por outro
    # ângulo o problema de `Referer` tratado no change do open redirect.
    "Referrer-Policy": "same-origin",
    "X-Frame-Options": "DENY",
}

HSTS = "max-age=31536000; includeSubDomains"


class CabecalhosSegurancaMiddleware(BaseHTTPMiddleware):
    """Aplica os cabeçalhos a toda resposta.

    O ambiente é lido POR REQUISIÇÃO (e não no `__init__`) para que testes
    alternem `APP_ENV` sem recriar a aplicação — mesmo motivo pelo qual
    `modo_demo()` é lida a cada chamada.
    """

    async def dispatch(self, request, call_next):
        resposta = await call_next(request)
        for nome, valor in _CABECALHOS.items():
            resposta.headers.setdefault(nome, valor)
        # HSTS só em produção: em dev fixaria HTTPS no navegador do
        # desenvolvedor para o host inteiro, incluindo localhost.
        if os.getenv("APP_ENV") == "prod":
            resposta.headers.setdefault("Strict-Transport-Security", HSTS)
        return resposta


__all__ = ["CabecalhosSegurancaMiddleware", "HSTS"]
