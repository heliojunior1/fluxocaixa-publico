"""Dicionário de termos de regra — cadastrável (spec R5).

Liga um termo de negócio em pt-BR ("Unidade Gestora") a um campo da staging.
Cada órgão define os seus: é comum esse dicionário viver hardcoded no código
do ETL; aqui é cadastro.

Duas origens de campo:
- `COLUNA`   → coluna de negócio de `flc_etl_staging`, restrita à whitelist
               `COLUNAS_PERMITIDAS`. Sem ela um termo alcançaria colunas de
               controle (`ind_status_processamento`, `dsc_erro`, FKs) ou um
               atributo qualquer do model.
- `ATRIBUTO` → chave livre de `json_atributos` (vocabulário da origem;
               consultada de forma parametrizada).

`cod_tipo` permite validar operador↔tipo no parse (rejeita, por exemplo,
`Valor começa com '1112'`).
"""
from datetime import date

from sqlalchemy import Column, Date, Index, Integer, String

from .base import Base

ORIGEM_COLUNA = 'COLUNA'
ORIGEM_ATRIBUTO = 'ATRIBUTO'
ORIGENS_VALIDAS = (ORIGEM_COLUNA, ORIGEM_ATRIBUTO)

TIPO_TEXTO = 'TEXTO'
TIPO_NUMERO = 'NUMERO'
TIPO_DATA = 'DATA'
TIPOS_VALIDOS = (TIPO_TEXTO, TIPO_NUMERO, TIPO_DATA)

# Whitelist do lado COLUNA: só colunas de NEGÓCIO da staging.
# Deliberadamente fora: ind_status_processamento, dsc_erro, seq_* (controle).
COLUNAS_PERMITIDAS = {
    'dat_referencia': TIPO_DATA,
    'val_referencia': TIPO_NUMERO,
    'num_ano_exercicio': TIPO_NUMERO,
}


class TermoRegra(Base):
    __tablename__ = 'flc_termo_regra'
    __table_args__ = (
        Index('ix_flc_termo_regra_nom', 'nom_termo'),
    )

    seq_termo_regra = Column(Integer, primary_key=True)
    nom_termo = Column(String(100), nullable=False)
    cod_origem_campo = Column(String(8), nullable=False)   # COLUNA | ATRIBUTO
    nom_campo = Column(String(100), nullable=False)
    cod_tipo = Column(String(7), nullable=False)           # TEXTO | NUMERO | DATA
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)
