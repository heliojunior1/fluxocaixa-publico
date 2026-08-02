"""Reservas financeiras e bloqueios judiciais (spec desembolso R19–R20).

As duas lentes da seção 4.4 do módulo: vinculação é atributo da FONTE
(permanente); reserva/bloqueio é EVENTO sobre o valor (temporário, atinge
qualquer fonte). A subtração é ÚNICA, na leitura da disponibilidade
operacional (F7.2) — nunca embutida no saldo bruto.

Cabeçalho + LIVRO DE EVENTOS (v2.1 item 7): o valor corrente é sempre
derivado (`constituição + reforços − reduções − liberações`) — corrigir é
lançar o evento contrário, coluna de valor atualizada não existe.

⚠️ Sequestro judicial NÃO é reserva — é saída efetiva, tratada na
conciliação (F7.1c).
"""
from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from .base import Base

#: Tipos de reserva.
TIPO_ADMINISTRATIVA = 'A'
TIPO_JUDICIAL = 'J'

#: Tipos de evento do livro.
EVENTO_CONSTITUICAO = 'CONSTITUICAO'
EVENTO_REFORCO = 'REFORCO'
EVENTO_REDUCAO = 'REDUCAO'
EVENTO_LIBERACAO = 'LIBERACAO'


class ReservaFinanceira(Base):
    __tablename__ = 'flc_reserva_financeira'

    seq_reserva = Column(Integer, primary_key=True)
    #: 'A' administrativa (decisão de gestão) | 'J' bloqueio judicial (ordem)
    cod_tipo_reserva = Column(String(1), nullable=False)
    #: a fonte que o valor atinge (declara o GRUPO abatido)
    seq_fonte_recurso = Column(
        Integer, ForeignKey('flc_fonte_recurso.seq_fonte_recurso'), nullable=False)
    #: a ordem judicial tipicamente bloqueia uma CONTA — referência p/ regularização
    seq_conta = Column(Integer, ForeignKey('flc_conta_bancaria.seq_conta'))
    dsc_motivo = Column(String(255), nullable=False)
    #: obrigatória no tipo 'J' (nº do processo/ofício)
    dsc_referencia_processo = Column(String(120))
    dat_inicio_vigencia = Column(Date, nullable=False)
    #: nulo = vigência aberta (o judicial não tem prazo conhecido)
    dat_fim_vigencia = Column(Date)
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)

    fonte_recurso = relationship('FonteRecurso')
    eventos = relationship('ReservaEvento', back_populates='reserva')


class ReservaEvento(Base):
    """Linha IMUTÁVEL — valor corrente = Σ(constituição+reforços−reduções−liberações)."""

    __tablename__ = 'flc_reserva_evento'

    seq_reserva_evento = Column(Integer, primary_key=True)
    seq_reserva = Column(
        Integer, ForeignKey('flc_reserva_financeira.seq_reserva'), nullable=False)
    cod_tipo_evento = Column(String(15), nullable=False)
    val_evento = Column(Numeric(18, 2), nullable=False)
    #: obrigatória nos eventos de bloqueio judicial (ordem/ofício)
    dsc_referencia_documental = Column(String(120))
    dat_evento = Column(Date, default=date.today, nullable=False)
    cod_pessoa_evento = Column(Integer)

    reserva = relationship('ReservaFinanceira', back_populates='eventos')
