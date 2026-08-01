from datetime import date
from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    Numeric,
    ForeignKey,
    UniqueConstraint,
    Text,
)
from sqlalchemy.orm import relationship, backref

from .base import Base
from .lancamento import TIPO_CREDITO, TIPO_DEBITO


def _cod_pessoa_default():
    # Import tardio: evita ciclo models -> auth -> routes -> models
    from ..auth.contexto import cod_pessoa_atual
    return cod_pessoa_atual()


class SimuladorCenario(Base):
    """Cenário principal do simulador que combina receita e despesa."""
    
    __tablename__ = 'flc_simulador_cenario'
    
    seq_simulador_cenario = Column(Integer, primary_key=True)
    nom_cenario = Column(String(100), nullable=False)
    dsc_cenario = Column(String(255))
    ano_base = Column(Integer, nullable=False)
    # Quantidade de PERÍODOS na periodicidade do cenário — semanas, quinzenas
    # ou meses. Chamava-se `num_periodos` e a tela já gravava semanas nele.
    num_periodos = Column(Integer, nullable=False, default=12)
    # 'ANUAL', 'MENSAL', 'QUINZENAL', 'SEMANAL'
    cod_periodicidade = Column(String(15), nullable=False, default='MENSAL')
    # Método de cálculo da base histórica: 'MEDIA_SIMPLES', 'MEDIA_PONDERADA', 'VALOR_FIXO'
    cod_metodo_base = Column(String(20), nullable=False, default='MEDIA_SIMPLES')
    # JSON com config da base: {"anos": [2024,2025], "pesos": {"2024":1,"2025":3}}
    json_config_base = Column(Text)
    dat_criacao = Column(Date, default=date.today, nullable=False)
    ind_status = Column(String(1), default='A', nullable=False)  # 'A' Ativo, 'I' Inativo
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer, nullable=False, default=_cod_pessoa_default)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)


# ---------------------------------------------------------------------------
# Catálogo de modelos (F6.2, spec previsao R2)
# ---------------------------------------------------------------------------
# Fica em código, não em tabela: o tipo decide QUAL MOTOR roda, então é
# semântica de aplicação — mesmo critério do `cod_tipo_conector` da extração.
#
# ⚠️ A perna aplicável precisa ser validada. As tabelas separadas davam essa
# garantia por construção (LOA só existia na de despesa); unificar sem validar
# seria perder isso em silêncio.
MODELOS_AMBAS = ('MANUAL', 'FORMULA', 'CRESCIMENTO_ANO', 'MEDIA_CRESCIMENTO')
MODELOS_CREDITO = ('HOLT_WINTERS', 'ARIMA', 'SARIMA', 'REGRESSAO', 'XGBOOST', 'LIGHTGBM')
MODELOS_DEBITO = ('LOA', 'MEDIA_HISTORICA')

CATALOGO_MODELOS = {
    **{m: (TIPO_CREDITO, TIPO_DEBITO) for m in MODELOS_AMBAS},
    **{m: (TIPO_CREDITO,) for m in MODELOS_CREDITO},
    **{m: (TIPO_DEBITO,) for m in MODELOS_DEBITO},
}


def pernas_do_modelo(cod_tipo_modelo: str) -> tuple:
    """Pernas que o modelo aceita; tupla vazia se o modelo não existe."""
    return CATALOGO_MODELOS.get(cod_tipo_modelo, ())


class CenarioConfig(Base):
    """Configuração do cenário por PERNA (F6.2).

    Substitui `flc_cenario_receita` e `flc_cenario_despesa`, que eram
    espelhadas. A perna é o `cod_tipo_lancamento` — 'C'/'D', o MESMO código do
    lançamento —, com FK para o domínio: é o que a referência faz ("reusando o
    código já existente em FLC_LANCAMENTO") e só ficou possível após a F6.1b.
    """

    __tablename__ = 'flc_cenario_config'
    __table_args__ = (
        UniqueConstraint('seq_simulador_cenario', 'cod_tipo_lancamento',
                         name='uix_cenario_config_perna'),
    )

    seq_cenario_config = Column(Integer, primary_key=True)
    seq_simulador_cenario = Column(
        Integer, ForeignKey('flc_simulador_cenario.seq_simulador_cenario'),
        nullable=False,
    )
    cod_tipo_lancamento = Column(
        String(1), ForeignKey('flc_tipo_lancamento.cod_tipo_lancamento'),
        nullable=False,
    )
    cod_tipo_modelo = Column(String(20), nullable=False)
    json_configuracao = Column(Text)
    dat_inclusao = Column(Date, default=date.today, nullable=False)

    simulador_cenario = relationship(
        'SimuladorCenario',
        backref=backref('configs', cascade='all, delete-orphan'),
    )


class CenarioAjuste(Base):
    """Ajuste manual por (config, qualificador, ano, mês) — F6.2."""

    __tablename__ = 'flc_cenario_ajuste'
    __table_args__ = (
        UniqueConstraint('seq_cenario_config', 'seq_qualificador', 'ano', 'mes',
                         name='uix_cenario_ajuste'),
    )

    seq_cenario_ajuste = Column(Integer, primary_key=True)
    seq_cenario_config = Column(
        Integer, ForeignKey('flc_cenario_config.seq_cenario_config'), nullable=False,
    )
    seq_qualificador = Column(
        Integer, ForeignKey('flc_qualificador.seq_qualificador'), nullable=False,
    )
    ano = Column(Integer, nullable=False)
    mes = Column(Integer, nullable=False)
    cod_tipo_ajuste = Column(String(1), nullable=False)  # 'P' percentual, 'V' valor
    val_ajuste = Column(Numeric(18, 2), nullable=False)
    dsc_ajuste = Column(String(100))
    dat_inclusao = Column(Date, default=date.today, nullable=False)

    config = relationship(
        'CenarioConfig', backref=backref('ajustes', cascade='all, delete-orphan'))
    qualificador = relationship('Qualificador')


class ModeloEconomicoParametro(Base):
    """Parâmetros para modelos de regressão linear múltipla."""
    
    __tablename__ = 'flc_modelo_economico_parametro'
    
    seq_parametro = Column(Integer, primary_key=True)
    # D8 (achado no apply): apontava para `flc_cenario_receita`, que a migração
    # 0012 dropa. Reponta para a config unificada — o parâmetro pertence ao
    # modelo daquela perna (REGRESSÃO só existe em crédito).
    seq_cenario_config = Column(
        Integer,
        ForeignKey('flc_cenario_config.seq_cenario_config'),
        nullable=False,
    )
    nom_variavel = Column(String(50), nullable=False)  # Ex: "PIB", "Inflacao", "Selic"
    val_coeficiente = Column(Numeric(18, 6), nullable=False)  # Valor do β para a variável
    # JSON com série temporal da variável: [{"mes": 1, "ano": 2025, "valor": 1.5}, ...]
    json_valores_historicos = Column(Text)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    
    cenario_receita = relationship(
        'CenarioConfig',
        backref=backref('parametros_economicos', cascade="all, delete-orphan")
    )
