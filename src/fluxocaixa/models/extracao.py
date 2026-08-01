"""Fontes e execuções de extração embutida (spec extracao-configuravel).

`flc_fonte_extracao` é o cadastro parametrizável (design D4): o tipo de
conector é a chave do registry (`extracao/registry.py`), não uma tabela de
domínio — tipos vêm de código/plugin. `json_config` guarda apenas
parâmetros e placeholders `${VAR}`; credenciais resolvidas NUNCA são
persistidas.

`flc_execucao_extracao` é log imutável (sem `ind_status`): cada execução —
agendada ou manual — vira uma linha com status, contadores e janela.
"""
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)

from .base import Base

# Domínios de aplicação (semântica do sistema, não cadastro do usuário)
DESTINO_SALDO_FUNDO = 'SALDO_FUNDO'
DESTINO_LANCAMENTO = 'LANCAMENTO'  # reservado — habilita na automação (F4)

DISPARO_AGENDADO = 'AGENDADO'
DISPARO_MANUAL = 'MANUAL'

STATUS_SUCESSO = 'SUCESSO'
STATUS_PARCIAL = 'PARCIAL'
STATUS_ERRO = 'ERRO'
STATUS_SEM_DADOS = 'SEM_DADOS'


class FonteExtracao(Base):
    """Fonte de extração parametrizável por cadastro."""

    __tablename__ = 'flc_fonte_extracao'

    seq_fonte_extracao = Column(Integer, primary_key=True)
    # Unicidade entre fontes ATIVAS é regra de serviço (inativas mantêm o nome)
    nom_fonte = Column(String(120), nullable=False)
    cod_tipo_conector = Column(String(30), nullable=False)
    cod_destino = Column(String(20), nullable=False, default=DESTINO_SALDO_FUNDO)
    seq_sistema_origem = Column(
        Integer, ForeignKey('flc_sistema_origem.seq_sistema_origem'), nullable=False
    )
    txt_cron = Column(String(60))  # crontab 5 campos; None = só execução manual
    json_config = Column(JSON, nullable=False, default=dict)
    json_layout = Column(JSON)  # parser/mapeamento — usado a partir da F3.2
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)


class ExecucaoExtracao(Base):
    """Log imutável de execuções de fonte (alimenta o KPI de defasagem)."""

    __tablename__ = 'flc_execucao_extracao'

    seq_execucao_extracao = Column(Integer, primary_key=True)
    seq_fonte_extracao = Column(
        Integer, ForeignKey('flc_fonte_extracao.seq_fonte_extracao'), nullable=False
    )
    dat_inicio_execucao = Column(DateTime, default=datetime.now, nullable=False)
    num_duracao_segundos = Column(Numeric(12, 3))
    cod_disparo = Column(String(10), nullable=False)
    cod_status = Column(String(10), nullable=False)
    dat_janela_inicio = Column(Date, nullable=False)
    dat_janela_fim = Column(Date, nullable=False)
    qtd_linhas_inseridas = Column(Integer, nullable=False, default=0)
    qtd_linhas_erro = Column(Integer, nullable=False, default=0)
    qtd_fundos_auto_cadastrados = Column(Integer, nullable=False, default=0)
    txt_detalhe_erros = Column(Text)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)
