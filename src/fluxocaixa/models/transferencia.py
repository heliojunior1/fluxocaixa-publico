"""Transferência interna entre contas (spec desembolso R13).

Registro de CONTROLE para a conciliação (F7.1c) — a saída-sem-pagamento mais
frequente num Tesouro é transferência interna, e sem o par registrado a
categoria "possível ordem judicial" nasceria poluída de falsos positivos.

⚠️ NÃO gera lançamento nem altera saldo (os efeitos bancários chegam pelos
extratos/conectores) e NÃO carrega fonte: transferência não muda a fonte do
recurso (LRF art. 8º, parágrafo único) — "transferir entre fontes" não
existe como operação.
"""
from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from .base import Base


class Transferencia(Base):
    __tablename__ = 'flc_transferencia'

    seq_transferencia = Column(Integer, primary_key=True)
    dat_transferencia = Column(Date, nullable=False)
    seq_conta_origem = Column(
        Integer, ForeignKey('flc_conta_bancaria.seq_conta'), nullable=False)
    seq_conta_destino = Column(
        Integer, ForeignKey('flc_conta_bancaria.seq_conta'), nullable=False)
    val_transferencia = Column(Numeric(18, 2), nullable=False)
    dsc_transferencia = Column(String(255))
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)

    conta_origem = relationship('ContaBancaria', foreign_keys=[seq_conta_origem])
    conta_destino = relationship('ContaBancaria', foreign_keys=[seq_conta_destino])
