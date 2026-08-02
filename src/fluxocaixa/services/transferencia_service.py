"""Transferências internas (spec desembolso R13) — registro de controle."""
from datetime import date
from decimal import Decimal

from ..auth.contexto import cod_pessoa_atual
from ..models import ContaBancaria, Transferencia
from ..models.base import db
from .validacao import RegraNegocioError


def criar_transferencia(dat_transferencia: date, seq_conta_origem: int,
                        seq_conta_destino: int, val_transferencia: Decimal,
                        dsc_transferencia: str | None = None) -> Transferencia:
    if seq_conta_origem == seq_conta_destino:
        raise RegraNegocioError("Origem e destino da transferência devem ser diferentes")
    if val_transferencia is None or Decimal(val_transferencia) <= 0:
        raise RegraNegocioError("Valor da transferência deve ser positivo")
    for seq in (seq_conta_origem, seq_conta_destino):
        conta = ContaBancaria.query.get(seq)
        if conta is None or conta.ind_status != 'A':
            raise RegraNegocioError("Conta bancária inexistente ou inativa")

    transferencia = Transferencia(
        dat_transferencia=dat_transferencia,
        seq_conta_origem=seq_conta_origem,
        seq_conta_destino=seq_conta_destino,
        val_transferencia=Decimal(val_transferencia).quantize(Decimal("0.01")),
        dsc_transferencia=(dsc_transferencia or "").strip() or None,
        ind_status='A',
        cod_pessoa_inclusao=cod_pessoa_atual(),
    )
    db.session.add(transferencia)
    db.session.commit()
    return transferencia


def inativar_transferencia(seq_transferencia: int) -> Transferencia:
    transferencia = Transferencia.query.get(seq_transferencia)
    if transferencia is None or transferencia.ind_status != 'A':
        raise RegraNegocioError("Transferência inexistente")
    transferencia.ind_status = 'I'
    transferencia.dat_alteracao = date.today()
    transferencia.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return transferencia


def listar_transferencias(data_inicio: date | None = None,
                          data_fim: date | None = None) -> list[Transferencia]:
    q = Transferencia.query.filter_by(ind_status='A')
    if data_inicio and data_fim:
        q = q.filter(Transferencia.dat_transferencia.between(data_inicio, data_fim))
    return q.order_by(Transferencia.dat_transferencia.desc()).all()


def total_do_dia(dia: date) -> Decimal:
    """Consumido pela conciliação (F7.1c): saída do dia coberta por
    transferência interna é NEUTRA, não divergência."""
    total = Decimal("0.00")
    for transferencia in Transferencia.query.filter_by(
            dat_transferencia=dia, ind_status='A').all():
        total += Decimal(transferencia.val_transferencia)
    return total.quantize(Decimal("0.01"))
