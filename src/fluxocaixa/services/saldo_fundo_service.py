"""Gravação de saldo por (conta, fundo, dia) — spec saldo-por-fundo R3/R4.

Invariantes:
- versionamento por inativação: a linha ativa da chave é inativada e uma nova
  é inserida — NUNCA UPDATE de valores nem DELETE físico;
- coerência tipo × sistema de origem (RegraNegocioError);
- `Decimal` de ponta a ponta.

Este serviço é o bloco que o `importar_lote` (F2.3) consome.
"""
from datetime import date
from decimal import Decimal

from ..auth.contexto import cod_pessoa_atual
from ..models import ContaBancaria, Fundo, SaldoContaFundo
from ..models.base import db
from .origem_saldo import resolver_sistema as _resolver_sistema
from .origem_saldo import resolver_tipo as _resolver_tipo
from .validacao import RegraNegocioError


def gravar_saldo(
    seq_conta: int,
    seq_fundo: int,
    dat_saldo: date,
    val_saldo: Decimal,
    val_aplicacoes: Decimal = Decimal("0"),
    val_resgates: Decimal = Decimal("0"),
    sigla_tipo_origem: str = 'MANUAL',
    sigla_sistema_origem: str | None = None,
) -> SaldoContaFundo:
    """Grava o saldo da chave, preservando o histórico por inativação."""
    tipo = _resolver_tipo(sigla_tipo_origem)
    sistema = _resolver_sistema(sigla_tipo_origem, sigla_sistema_origem)

    if ContaBancaria.query.get(seq_conta) is None:
        raise RegraNegocioError("Conta bancária inexistente")
    if Fundo.query.get(seq_fundo) is None:
        raise RegraNegocioError("Fundo inexistente")

    ativa = SaldoContaFundo.query.filter_by(
        seq_conta=seq_conta, seq_fundo=seq_fundo, dat_saldo=dat_saldo, ind_status='A'
    ).first()
    if ativa is not None:
        ativa.ind_status = 'I'
        ativa.dat_alteracao = date.today()
        ativa.cod_pessoa_alteracao = cod_pessoa_atual()

    novo = SaldoContaFundo(
        seq_conta=seq_conta,
        seq_fundo=seq_fundo,
        dat_saldo=dat_saldo,
        val_saldo=Decimal(val_saldo),
        val_aplicacoes=Decimal(val_aplicacoes),
        val_resgates=Decimal(val_resgates),
        seq_tipo_origem=tipo.seq_tipo_origem_saldo,
        seq_sistema_origem=sistema.seq_sistema_origem if sistema else None,
        ind_status='A',
        cod_pessoa_inclusao=cod_pessoa_atual(),
    )
    db.session.add(novo)
    db.session.commit()
    return novo


def inativar_saldo(seq_conta: int, seq_fundo: int, dat_saldo: date) -> bool:
    """Inativa a linha ativa da chave sem inserir substituta (spec R19).

    O "excluir" da tela — preserva o histórico. Retorna True se inativou algo.
    """
    ativa = SaldoContaFundo.query.filter_by(
        seq_conta=seq_conta, seq_fundo=seq_fundo, dat_saldo=dat_saldo, ind_status='A'
    ).first()
    if ativa is None:
        return False
    ativa.ind_status = 'I'
    ativa.dat_alteracao = date.today()
    ativa.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return True
