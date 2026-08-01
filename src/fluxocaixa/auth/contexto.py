"""Contexto do usuário corrente (auditoria — spec controle-acesso R9)."""
from contextvars import ContextVar

_usuario_corrente: ContextVar[int | None] = ContextVar("usuario_corrente", default=None)


def definir_usuario_corrente(seq_usuario: int | None) -> None:
    _usuario_corrente.set(seq_usuario)


def cod_pessoa_atual() -> int:
    """Usuário da sessão corrente; fallback 1 fora de request (seeds/scripts)."""
    return _usuario_corrente.get() or 1
