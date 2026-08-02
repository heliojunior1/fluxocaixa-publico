"""Programação de desembolso — as cotas do decreto (spec desembolso R21–R22).

A LRF (art. 8º) exige o decreto de programação financeira/cronograma mensal;
esta tabela é a IMPORTAÇÃO dele. ⚠️ Revisão NÃO sobrescreve: nova cota para
a mesma chave (ano, mês, órgão, qualificador) inativa a anterior e insere —
histórico preservado (padrão do saldo por fundo). A cota é PREVISTO, não
trava (o teto duro é a LOA/dotação).
"""
from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from .base import Base


class ProgramacaoDesembolso(Base):
    __tablename__ = 'flc_programacao_desembolso'

    seq_programacao = Column(Integer, primary_key=True)
    num_ano = Column(Integer, nullable=False)
    num_mes = Column(Integer, nullable=False)
    cod_orgao = Column(Integer, ForeignKey('flc_orgao.cod_orgao'), nullable=False)
    seq_qualificador = Column(
        Integer, ForeignKey('flc_qualificador.seq_qualificador'), nullable=True)
    seq_fonte_recurso = Column(
        Integer, ForeignKey('flc_fonte_recurso.seq_fonte_recurso'), nullable=True)
    val_cota = Column(Numeric(18, 2), nullable=False)
    #: decreto/portaria que fixou a cota (a referência do ato é o rastro legal)
    dsc_referencia_ato = Column(String(120), nullable=False)
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)

    orgao = relationship('Orgao')
