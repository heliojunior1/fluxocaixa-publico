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
from sqlalchemy.orm import relationship

from .base import Base


class Loa(Base):
    """Lei Orçamentária Anual – previsão de receita/despesa por qualificador e ano."""
    __tablename__ = 'flc_loa'
    __table_args__ = (
        # No máximo UMA linha ativa por (ano, qualificador) — cadastros-nucleo
        # R24, migração 0033 (com dedupe). Duplicata dobraria o teto do
        # autorizado, as metas fiscais e o previsto do desembolso.
        Index(
            'ux_flc_loa_ano_qualificador_ativo',
            'num_ano',
            'seq_qualificador',
            unique=True,
            sqlite_where=text("ind_status = 'A'"),
            postgresql_where=text("ind_status = 'A'"),
        ),
    )

    seq_loa = Column(Integer, primary_key=True)
    num_ano = Column(Integer, nullable=False)
    seq_qualificador = Column(Integer, ForeignKey('flc_qualificador.seq_qualificador'), nullable=False)
    val_loa = Column(Numeric(18, 2), nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    # Auditoria (R24): nullable — linha anterior à migração 0033 não ganha
    # autor fabricado.
    cod_pessoa_inclusao = Column(Integer, nullable=True)
    dat_alteracao = Column(Date, nullable=True)
    cod_pessoa_alteracao = Column(Integer, nullable=True)
    ind_status = Column(String(1), default='A', nullable=False)

    qualificador = relationship('Qualificador')
