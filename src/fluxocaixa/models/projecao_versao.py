"""Histórico de projeções (versões salvas de cenários do simulador).

Modelo normalizado em duas tabelas:
- flc_projecao_versao: cabeçalho de cada versão (snapshot publicável).
- flc_projecao_valor:  uma linha por (qualificador, ano, mes, tipo) com valor projetado.

Permite que relatórios comparativos (RF-21, RF-25 do documento de requisitos)
sejam montados em SQL puro sem desserializar o JSON do snapshot.
"""
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .base import Base


class ProjecaoVersao(Base):
    """Cabeçalho de uma versão salva da projeção."""

    __tablename__ = 'flc_projecao_versao'

    seq_projecao_versao = Column(Integer, primary_key=True)
    seq_simulador_cenario = Column(
        Integer,
        ForeignKey('flc_simulador_cenario.seq_simulador_cenario'),
        nullable=False,
    )
    nom_versao = Column(String(80), nullable=False)
    dsc_motivo = Column(String(255))
    dat_versao = Column(DateTime, default=datetime.now, nullable=False)
    cod_pessoa = Column(Integer)
    # 'S' publicada (imutável), 'N' rascunho
    ind_publicado = Column(String(1), default='N', nullable=False)
    # Inputs (config + ajustes serializados) — auditoria, não consultado em queries
    json_inputs = Column(Text)
    # Resumo agregado para listagem rápida (total_receita, total_despesa, saldo_final)
    json_resumo = Column(Text)

    valores = relationship(
        'ProjecaoValor',
        backref='versao',
        cascade='all, delete-orphan',
        lazy='dynamic',
    )


class ProjecaoValor(Base):
    """Valor projetado para um (qualificador, ano, mes, tipo) dentro de uma versão."""

    __tablename__ = 'flc_projecao_valor'
    __table_args__ = (
        Index(
            'ix_projecao_valor_versao_qual_periodo',
            'seq_projecao_versao',
            'seq_qualificador',
            'ano',
            'num_periodo',
        ),
        Index('ix_projecao_valor_tipo', 'cod_tipo'),
    )

    seq_projecao_valor = Column(Integer, primary_key=True)
    seq_projecao_versao = Column(
        Integer,
        ForeignKey('flc_projecao_versao.seq_projecao_versao', ondelete='CASCADE'),
        nullable=False,
    )
    seq_qualificador = Column(
        Integer,
        ForeignKey('flc_qualificador.seq_qualificador'),
        nullable=True,
    )
    cod_tipo = Column(String(1), nullable=False)  # 'C' crédito/receita, 'D' débito/despesa (convergiu de 'R' na F6.1b)
    ano = Column(Integer, nullable=False)
    # Granularidade REAL do cenário (F6.3): mês, quinzena ou semana ISO,
    # conforme a periodicidade. ⚠️ `mes` saiu: é função pura de
    # (periodicidade, ano, período) e vem de `periodo_resolver.mes_do_periodo`
    # na leitura — mesmo princípio da F2.1, onde o agregado nunca é persistido.
    num_periodo = Column(Integer, nullable=False)
    val_projetado = Column(Numeric(18, 2), nullable=False, default=0)
    # Realizado é preenchido posteriormente (job/rotina) para meses já fechados.
    val_realizado = Column(Numeric(18, 2))

    qualificador = relationship('Qualificador')
