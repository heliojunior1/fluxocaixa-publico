"""Liberação financeira — a cota que o Tesouro solta para o órgão pagar
(spec desembolso R1–R3, change liberacoes-desembolso).

Três decisões estruturais, todas da revisão v2.1 do módulo:

- **Livro de eventos** (`flc_liberacao_evento`): criação, confirmação e
  cancelamento são linhas imutáveis e datadas; `cod_situacao` na liberação é
  só o estado corrente (consistente com o último evento, gravados na MESMA
  transação pelo serviço). Quem responde "quem confirmou, quando, com que
  números" são os eventos.
- **Apropriação nasce junto e como evento** (`flc_pagamento_liberacao`,
  `cod_tipo_evento` 'A'/'E'): o consumo de uma liberação é `Σ(A) − Σ(E)`,
  nunca uma coluna atualizada — a UI chega na F7.1b, o modelo nasce aqui para
  não forçar migração.
- **Pendente é derivado**: NÃO existe coluna `val_utilizado` — o saldo
  liberado pendente é função das confirmadas e das apropriações
  (`liberacao_service.saldo_liberado_pendente`, origem única).

A fonte é **obrigatória e sem default** (pré-marcar a livre seria
classificação silenciosa) e a **natureza da obrigação** separa o
discricionário do obrigatório — é ela que a simulação (F7.2) consome para
decidir o que entra na curva-base e o que passa pelo veredicto.
"""
from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from .base import Base

#: Situações da liberação.
SITUACAO_RASCUNHO = 'R'
SITUACAO_CONFIRMADA = 'C'
SITUACAO_CANCELADA = 'X'

#: Natureza da obrigação (seção 4.5 do módulo — v2.1).
NATUREZA_DISCRICIONARIA = 'D'
NATUREZA_CONSTITUCIONAL = 'O'  #: obrigação constitucional/legal (duodécimos, pisos)
NATUREZA_JUDICIAL = 'J'
NATUREZA_FOLHA = 'F'
NATUREZA_DIVIDA = 'V'
NATUREZAS = (NATUREZA_DISCRICIONARIA, NATUREZA_CONSTITUCIONAL,
             NATUREZA_JUDICIAL, NATUREZA_FOLHA, NATUREZA_DIVIDA)

#: Eventos do ciclo de vida.
EVENTO_CRIACAO = 'CRIACAO'
EVENTO_CONFIRMACAO = 'CONFIRMACAO'
EVENTO_CANCELAMENTO = 'CANCELAMENTO'

#: Eventos de apropriação (F7.1b consome; o modelo nasce aqui).
APROPRIACAO = 'A'
ESTORNO = 'E'


class Liberacao(Base):
    __tablename__ = 'flc_liberacao'

    seq_liberacao = Column(Integer, primary_key=True)
    #: data da DECISÃO
    dat_liberacao = Column(Date, nullable=False)
    #: posiciona o desconto na curva da F7.2 (default: a data da liberação)
    dat_prevista_desembolso = Column(Date, nullable=False)
    cod_orgao = Column(Integer, ForeignKey('flc_orgao.cod_orgao'), nullable=False)
    seq_qualificador = Column(
        Integer, ForeignKey('flc_qualificador.seq_qualificador'), nullable=False)
    #: obrigatória e SEM default — seleção sempre explícita (v2.1)
    seq_fonte_recurso = Column(
        Integer, ForeignKey('flc_fonte_recurso.seq_fonte_recurso'), nullable=False)
    val_liberacao = Column(Numeric(18, 2), nullable=False)
    dsc_liberacao = Column(String(255))
    #: obrigatória quando a simulação apontar abaixo do colchão (F7.2)
    dsc_justificativa = Column(String(500))
    cod_natureza_obrigacao = Column(String(1), nullable=False,
                                    default=NATUREZA_DISCRICIONARIA)
    dsc_base_legal = Column(String(200))
    cod_situacao = Column(String(1), nullable=False, default=SITUACAO_RASCUNHO)
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)

    orgao = relationship('Orgao')
    qualificador = relationship('Qualificador')
    fonte_recurso = relationship('FonteRecurso')
    eventos = relationship('LiberacaoEvento', back_populates='liberacao')

    @property
    def nao_gerenciavel(self) -> bool:
        """Obrigatória (curva-base da F7.2) := natureza ≠ discricionária."""
        return self.cod_natureza_obrigacao != NATUREZA_DISCRICIONARIA


class LiberacaoEvento(Base):
    """Linha IMUTÁVEL do livro de eventos — corrigir é lançar o contrário."""

    __tablename__ = 'flc_liberacao_evento'

    seq_liberacao_evento = Column(Integer, primary_key=True)
    seq_liberacao = Column(
        Integer, ForeignKey('flc_liberacao.seq_liberacao'), nullable=False)
    cod_tipo_evento = Column(String(15), nullable=False)
    dsc_justificativa = Column(String(500))
    #: rastro da decisão da F7.2 (nasce agora; preenchida pela simulação)
    dsc_referencia_snapshot = Column(String(120))
    dat_evento = Column(Date, default=date.today, nullable=False)
    cod_pessoa_evento = Column(Integer)

    liberacao = relationship('Liberacao', back_populates='eventos')


class PagamentoLiberacao(Base):
    """Apropriação pagamento ↔ liberação como LINHAS-EVENTO (A/E).

    Nasce na F7.1a (modelo) e ganha fluxo/UI na F7.1b: um pagamento pode
    consumir várias liberações e uma liberação pode ser consumida por vários
    pagamentos; estorno devolve saldo, edição não existe.
    """

    __tablename__ = 'flc_pagamento_liberacao'

    seq_pagamento_liberacao = Column(Integer, primary_key=True)
    seq_pagamento = Column(
        Integer, ForeignKey('flc_pagamento.seq_pagamento'), nullable=False)
    seq_liberacao = Column(
        Integer, ForeignKey('flc_liberacao.seq_liberacao'), nullable=False)
    #: 'A' apropriação | 'E' estorno — consumo = Σ(A) − Σ(E)
    cod_tipo_evento = Column(String(1), nullable=False, default=APROPRIACAO)
    val_apropriado = Column(Numeric(18, 2), nullable=False)
    dat_evento = Column(Date, default=date.today, nullable=False)
    cod_pessoa_evento = Column(Integer)
