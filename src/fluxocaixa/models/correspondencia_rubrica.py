"""Correspondência de rubricas entre exercícios — o "De/Para" (previsao R30).

A identidade estável (`flc_qualificador.cod_rubrica_raiz`) cobre a
continuidade 1:1. Fusão (N origens → 1 destino) e desdobramento (1 origem →
N destinos) vivem AQUI, referenciando rubricas pela raiz — nunca pelo `seq` de
um exercício.

⚠️ Livro de eventos: estrutura e rateio são IMUTÁVEIS. Corrigir é inativar e
criar outra (estrutura) ou definir um rateio novo (rateio); todo gesto grava
uma linha em `flc_correspondencia_evento`, e o número do último evento é a
VERSÃO do De/Para — a projeção publicada guarda essa versão, e o De/Para como
estava nela continua reconstruível (`correspondencia_rubrica_service.
correspondencias(versao=...)`). O `ind_status` da correspondência é só o
estado corrente, gravado na mesma transação do evento (padrão da liberação).
"""
from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from .base import Base

TIPO_FUSAO = 'F'
TIPO_DESDOBRAMENTO = 'D'

EVENTO_CRIACAO = 'C'
EVENTO_INATIVACAO = 'I'
EVENTO_RATEIO = 'R'
EVENTO_RATEIO_REMOVIDO = 'X'


class CorrespondenciaRubrica(Base):
    __tablename__ = 'flc_correspondencia_rubrica'

    seq_correspondencia_rubrica = Column(Integer, primary_key=True)
    cod_tipo = Column(String(1), nullable=False)
    #: exercício a partir do qual o destino substitui as origens
    num_ano_vigencia = Column(Integer, nullable=False)
    #: fundamento normativo da mudança de classificação (portaria, ementário…)
    dsc_referencia_ato = Column(String(255), nullable=False)
    dsc_fundamento = Column(String(500), nullable=False)
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer, nullable=True)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)

    origens = relationship('CorrespondenciaOrigem', back_populates='correspondencia',
                           order_by='CorrespondenciaOrigem.seq_correspondencia_origem')
    destinos = relationship('CorrespondenciaDestino', back_populates='correspondencia',
                            order_by='CorrespondenciaDestino.seq_correspondencia_destino')
    eventos = relationship('CorrespondenciaEvento', back_populates='correspondencia',
                           order_by='CorrespondenciaEvento.seq_correspondencia_evento')


class CorrespondenciaOrigem(Base):
    __tablename__ = 'flc_correspondencia_origem'

    seq_correspondencia_origem = Column(Integer, primary_key=True)
    seq_correspondencia_rubrica = Column(
        Integer, ForeignKey('flc_correspondencia_rubrica.seq_correspondencia_rubrica'),
        nullable=False)
    cod_rubrica_raiz = Column(Integer, nullable=False)

    correspondencia = relationship('CorrespondenciaRubrica', back_populates='origens')


class CorrespondenciaDestino(Base):
    __tablename__ = 'flc_correspondencia_destino'

    seq_correspondencia_destino = Column(Integer, primary_key=True)
    seq_correspondencia_rubrica = Column(
        Integer, ForeignKey('flc_correspondencia_rubrica.seq_correspondencia_rubrica'),
        nullable=False)
    cod_rubrica_raiz = Column(Integer, nullable=False)
    #: regra em pt-BR (motor de regras da automação) que identifica, nos
    #: atributos dos lançamentos automáticos da origem, o que é deste destino
    txt_regra_reconstrucao = Column(String(1000))

    correspondencia = relationship('CorrespondenciaRubrica', back_populates='destinos')


class CorrespondenciaEvento(Base):
    """Linha IMUTÁVEL — o seq é a versão do De/Para."""

    __tablename__ = 'flc_correspondencia_evento'

    seq_correspondencia_evento = Column(Integer, primary_key=True)
    seq_correspondencia_rubrica = Column(
        Integer, ForeignKey('flc_correspondencia_rubrica.seq_correspondencia_rubrica'),
        nullable=False)
    cod_tipo_evento = Column(String(1), nullable=False)
    dsc_justificativa = Column(String(500))
    dat_evento = Column(DateTime, default=datetime.now, nullable=False)
    cod_pessoa_evento = Column(Integer)

    correspondencia = relationship('CorrespondenciaRubrica', back_populates='eventos')
    rateio = relationship('CorrespondenciaRateio', back_populates='evento')


class CorrespondenciaRateio(Base):
    """Percentual de um destino no rateio definido pelo evento 'R' — o
    conjunto do evento soma 100%. Imutável: rateio novo = evento novo."""

    __tablename__ = 'flc_correspondencia_rateio'

    seq_correspondencia_rateio = Column(Integer, primary_key=True)
    seq_correspondencia_evento = Column(
        Integer, ForeignKey('flc_correspondencia_evento.seq_correspondencia_evento'),
        nullable=False)
    cod_rubrica_raiz = Column(Integer, nullable=False)
    val_percentual = Column(Numeric(7, 4), nullable=False)

    evento = relationship('CorrespondenciaEvento', back_populates='rateio')
