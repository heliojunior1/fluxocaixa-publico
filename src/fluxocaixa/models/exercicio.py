"""Exercício aberto/fechado (cadastros-nucleo R31).

`flc_exercicio` guarda a situação ATUAL de um ano (cache, gravado na mesma
transação do evento); `flc_exercicio_evento` é o registro imutável — abertura,
fechamento e reabertura, com autor, data e motivo. Ano sem linha é ABERTO:
instalação que nunca fechou nada se comporta como sempre.
"""
from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, Integer, String

from .base import Base

SITUACAO_ABERTO = 'A'
SITUACAO_FECHADO = 'F'

EVENTO_ABERTURA = 'A'
EVENTO_FECHAMENTO = 'F'
EVENTO_REABERTURA = 'R'
ROTULO_EVENTO = {EVENTO_ABERTURA: 'ABERTURA', EVENTO_FECHAMENTO: 'FECHAMENTO',
                 EVENTO_REABERTURA: 'REABERTURA'}


class Exercicio(Base):
    __tablename__ = 'flc_exercicio'

    num_ano_exercicio = Column(Integer, primary_key=True, autoincrement=False)
    cod_situacao = Column(String(1), nullable=False, default=SITUACAO_ABERTO)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)


class ExercicioEvento(Base):
    """Linha IMUTÁVEL do livro de eventos do exercício."""

    __tablename__ = 'flc_exercicio_evento'

    seq_exercicio_evento = Column(Integer, primary_key=True)
    num_ano_exercicio = Column(Integer, nullable=False)
    cod_tipo_evento = Column(String(1), nullable=False)
    dsc_motivo = Column(String(1000))
    dat_evento = Column(DateTime, default=datetime.now, nullable=False)
    cod_pessoa_evento = Column(Integer)

    @property
    def rotulo(self) -> str:
        return ROTULO_EVENTO.get(self.cod_tipo_evento, self.cod_tipo_evento)
