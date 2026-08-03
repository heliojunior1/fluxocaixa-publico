"""Contexto do usuário corrente (auditoria — spec controle-acesso R9/R13)."""
from contextvars import ContextVar

_usuario_corrente: ContextVar[int | None] = ContextVar("usuario_corrente", default=None)
_em_requisicao: ContextVar[bool] = ContextVar("em_requisicao", default=False)


class UsuarioCorrenteAusenteError(Exception):
    """Gravação auditada dentro de request sem usuário definido."""


def definir_usuario_corrente(seq_usuario: int | None) -> None:
    _usuario_corrente.set(seq_usuario)


def marcar_em_requisicao() -> None:
    """Sinaliza que há requisição em curso (chamado por `exigir_login`)."""
    _em_requisicao.set(True)


def cod_pessoa_atual() -> int:
    """Usuário da sessão corrente; fallback 1 apenas FORA de request.

    Dentro de um request sem usuário definido, falhar é melhor que atribuir:
    gravar com `cod_pessoa=1` produz dado errado com APARÊNCIA de correto, e a
    trilha de auditoria passa a mentir sem que nada acuse (R9). Fora de request
    — seeds e scripts — o fallback é intencional e documentado.
    """
    seq = _usuario_corrente.get()
    if seq:
        return seq
    if _em_requisicao.get():
        raise UsuarioCorrenteAusenteError(
            "Gravação auditada sem usuário corrente definido na requisição."
        )
    return 1
