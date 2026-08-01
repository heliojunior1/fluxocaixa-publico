"""Coerência tipo × sistema de origem (spec saldo-por-fundo R4).

Implementação única compartilhada por `saldo_fundo_service` (gravação de
saldo) e `fundo_service` (cadastro/aprovação/upsert de fundo).
"""
from ..models import SistemaOrigem, TipoOrigemSaldo
from .validacao import RegraNegocioError


def resolver_tipo(sigla: str) -> TipoOrigemSaldo:
    tipo = TipoOrigemSaldo.query.filter_by(txt_sigla=sigla, ind_status='A').first()
    if tipo is None:
        raise RegraNegocioError(f"Tipo de origem de saldo '{sigla}' não encontrado")
    return tipo


def resolver_sistema(sigla_tipo: str, sigla_sistema: str | None) -> SistemaOrigem | None:
    """Aplica a coerência tipo×sistema e devolve o sistema (ou None).

    AUTOMATIZADO ⇒ sistema obrigatório e ativo; MANUAL/IMPORTADO ⇒ sem sistema.
    """
    if sigla_tipo == 'AUTOMATIZADO':
        if not sigla_sistema:
            raise RegraNegocioError("Origem automatizada exige o sistema de origem")
        sistema = SistemaOrigem.query.filter_by(txt_sigla=sigla_sistema, ind_status='A').first()
        if sistema is None:
            raise RegraNegocioError(
                f"Sistema de origem '{sigla_sistema}' não encontrado ou inativo"
            )
        return sistema
    if sigla_sistema:
        raise RegraNegocioError("Origem manual/importada não deve informar sistema de origem")
    return None
