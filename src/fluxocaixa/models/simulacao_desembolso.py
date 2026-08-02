"""Simulação de disponibilidade do desembolso (spec desembolso R9–R12).

- `flc_parametro_desembolso`: parâmetros OPERACIONAIS do módulo (hoje, o
  colchão mínimo) — por grupo de fonte, com default global (grupo nulo).
  ⚠️ Não é `flc_parametro_global`: aquele par pertence ao motor de fórmulas
  (macro, permissões de fórmula) — decisão da revisão v2 do módulo.
- `flc_simulacao_desembolso`: snapshot IMUTÁVEL da simulação no momento da
  confirmação do lote — com que números a decisão foi tomada (espírito dos
  snapshots do simulador de cenários). Os eventos de confirmação das
  liberações referenciam `SIM-{seq}`.
"""
from datetime import date

from sqlalchemy import JSON, Column, Date, Integer, Numeric, String

from .base import Base

#: Parâmetros conhecidos.
PARAM_COLCHAO_MINIMO = 'COLCHAO_MINIMO'


class ParametroDesembolso(Base):
    __tablename__ = 'flc_parametro_desembolso'

    seq_parametro_desembolso = Column(Integer, primary_key=True)
    cod_parametro = Column(String(30), nullable=False)
    #: 'L'/'V' — nulo = default global (o override por grupo vence)
    cod_grupo = Column(String(1))
    val_parametro = Column(Numeric(18, 2), nullable=False)
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)


class SimulacaoDesembolso(Base):
    """Snapshot imutável — nunca é editado nem apagado (rastro da decisão)."""

    __tablename__ = 'flc_simulacao_desembolso'

    seq_simulacao_desembolso = Column(Integer, primary_key=True)
    dat_simulacao = Column(Date, default=date.today, nullable=False)
    cod_grupo = Column(String(1), nullable=False)
    cod_veredicto = Column(String(10), nullable=False)
    json_snapshot = Column(JSON, nullable=False)
    cod_pessoa_inclusao = Column(Integer)

    @property
    def referencia(self) -> str:
        return f"SIM-{self.seq_simulacao_desembolso}"
