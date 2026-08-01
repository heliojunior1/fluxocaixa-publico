"""Saldo por conta × fundo × dia (spec saldo-por-fundo).

Paridade com o modelo Java (FLC_FUNDO, FLC_SALDO_CONTA_FUNDO,
FLC_TIPO_ORIGEM_SALDO, FLC_SISTEMA_ORIGEM). As views de cálculo
(vw_flc_saldo_conta_fundo_calc, vw_flc_saldo_conta_agregado) vivem nas
migrações — NUNCA mapeá-las aqui (quebraria o teste anti-deriva).
"""
from datetime import date

from sqlalchemy import (
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)

from .base import Base


class TipoOrigemSaldo(Base):
    """Domínio fixo: MANUAL, AUTOMATIZADO, IMPORTADO (seedado)."""

    __tablename__ = 'flc_tipo_origem_saldo'

    seq_tipo_origem_saldo = Column(Integer, primary_key=True)
    txt_sigla = Column(String(20), nullable=False, unique=True)
    dsc_tipo_origem = Column(String(120))
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)


class SistemaOrigem(Base):
    """Sistemas de origem de extração — cadastráveis pela instalação (sem seed)."""

    __tablename__ = 'flc_sistema_origem'

    seq_sistema_origem = Column(Integer, primary_key=True)
    txt_sigla = Column(String(30), nullable=False, unique=True)
    dsc_sistema_origem = Column(String(120))
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)


class Fundo(Base):
    """Fundo de investimento (cod_fundo imutável — regra aplicada na F2.2)."""

    __tablename__ = 'flc_fundo'

    seq_fundo = Column(Integer, primary_key=True)
    cod_fundo = Column(String(10), nullable=False, unique=True)
    dsc_fundo = Column(String(120))
    seq_tipo_origem = Column(
        Integer, ForeignKey('flc_tipo_origem_saldo.seq_tipo_origem_saldo'), nullable=False
    )
    seq_sistema_origem = Column(
        Integer, ForeignKey('flc_sistema_origem.seq_sistema_origem'), nullable=True
    )
    # 'S' = auto-cadastrado por importação, aguardando aprovação (F2.2/F2.3)
    ind_pendente_revisao = Column(String(1), default='N', nullable=False)
    dat_auto_cadastro = Column(Date)
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)


class SaldoContaFundo(Base):
    """Fato: saldo diário por (conta, fundo). Histórico por inativação."""

    __tablename__ = 'flc_saldo_conta_fundo'
    __table_args__ = (
        # No máximo UMA linha ativa por chave; inativas convivem (histórico)
        Index(
            'ux_flc_saldo_conta_fundo_ativo',
            'seq_conta',
            'seq_fundo',
            'dat_saldo',
            unique=True,
            sqlite_where=text("ind_status = 'A'"),
            postgresql_where=text("ind_status = 'A'"),
        ),
    )

    seq_saldo_conta_fundo = Column(Integer, primary_key=True)
    seq_conta = Column(Integer, ForeignKey('flc_conta_bancaria.seq_conta'), nullable=False)
    seq_fundo = Column(Integer, ForeignKey('flc_fundo.seq_fundo'), nullable=False)
    dat_saldo = Column(Date, nullable=False)
    val_saldo = Column(Numeric(18, 2), nullable=False)
    val_aplicacoes = Column(Numeric(18, 2), nullable=False, default=0)
    val_resgates = Column(Numeric(18, 2), nullable=False, default=0)
    seq_tipo_origem = Column(
        Integer, ForeignKey('flc_tipo_origem_saldo.seq_tipo_origem_saldo'), nullable=False
    )
    seq_sistema_origem = Column(
        Integer, ForeignKey('flc_sistema_origem.seq_sistema_origem'), nullable=True
    )
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)
