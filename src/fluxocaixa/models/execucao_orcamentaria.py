"""Execução orçamentária E/L/P (spec execucao-orcamentaria R4–R7).

Documentos encadeados por `seq_documento_pai` (L consome E, P consome L —
vínculo N:1 com valor próprio; cobre liquidação/pagamento PARCIAL) e
movimentos como eventos imutáveis (I/R/A). ⚠️ O valor corrente do documento
é SEMPRE derivado dos eventos (`execucao_orcamentaria_service`), nunca
coluna — e "liquidado não pago", o número que a F8.4 consome, é derivado da
cadeia. Estágio `P` aqui é o pagamento ORÇAMENTÁRIO — não se funde com
`flc_pagamento` (desembolso financeiro): são conciliados na F8.3.
"""
from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from .base import Base

ESTAGIO_EMPENHO = 'E'
ESTAGIO_LIQUIDACAO = 'L'
ESTAGIO_PAGAMENTO = 'P'
#: cadeia estrita: estágio → estágio do pai obrigatório (E não tem pai)
PAI_DO_ESTAGIO = {ESTAGIO_LIQUIDACAO: ESTAGIO_EMPENHO,
                  ESTAGIO_PAGAMENTO: ESTAGIO_LIQUIDACAO}

EVENTO_INSCRICAO = 'I'
EVENTO_REFORCO = 'R'
EVENTO_ANULACAO = 'A'


class ExecucaoOrcamentaria(Base):
    __tablename__ = 'flc_execucao_orcamentaria'

    seq_execucao = Column(Integer, primary_key=True)
    cod_estagio = Column(String(1), nullable=False)
    num_documento = Column(String(30), nullable=False)
    num_ano = Column(Integer, nullable=False)
    cod_orgao = Column(Integer, ForeignKey('flc_orgao.cod_orgao'), nullable=False)
    seq_qualificador = Column(
        Integer, ForeignKey('flc_qualificador.seq_qualificador'), nullable=False)
    seq_fonte_recurso = Column(
        Integer, ForeignKey('flc_fonte_recurso.seq_fonte_recurso'), nullable=True)
    seq_documento_pai = Column(
        Integer, ForeignKey('flc_execucao_orcamentaria.seq_execucao'), nullable=True)
    dat_documento = Column(Date, nullable=False)
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)

    qualificador = relationship('Qualificador')
    fonte_recurso = relationship('FonteRecurso')
    pai = relationship('ExecucaoOrcamentaria', remote_side=[seq_execucao])
    eventos = relationship('ExecucaoEvento', back_populates='documento')


class ExecucaoEvento(Base):
    __tablename__ = 'flc_execucao_evento'

    seq_evento = Column(Integer, primary_key=True)
    seq_execucao = Column(
        Integer, ForeignKey('flc_execucao_orcamentaria.seq_execucao'), nullable=False)
    cod_tipo_evento = Column(String(1), nullable=False)
    val_evento = Column(Numeric(18, 2), nullable=False)
    dat_evento = Column(Date, nullable=False)
    dsc_referencia = Column(String(120))
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)

    documento = relationship('ExecucaoOrcamentaria', back_populates='eventos')
