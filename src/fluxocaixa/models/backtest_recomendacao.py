"""Recomendação de modelo por qualificador, gravada pelo backtest.

Change transacao-unica-cenario-e-backtest (previsao R13): a tabela era usada
por SQL cru em `backtest_service` SEM model nem migração — não existia em
banco novo (o "salvar recomendações" quebrava com `no such table` em qualquer
instalação limpa; só funcionava sobre bancos legados). Entrou no schema
oficial (migração 0034) e no radar do anti-deriva.

Sem `ind_status`: é dado de MÁQUINA, integralmente reproduzível ao rodar o
backtest de novo — a regravação limpa e insere (mesma lógica do resync da
F4.3); soft-delete acumularia gerações de lixo que toda leitura filtraria.
"""
from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String, Text

from .base import Base


class BacktestRecomendacao(Base):
    __tablename__ = 'flc_backtest_recomendacao'

    seq_backtest_recomendacao = Column(Integer, primary_key=True)
    seq_qualificador = Column(
        Integer, ForeignKey('flc_qualificador.seq_qualificador'), nullable=False)
    cod_modelo = Column(String(30), nullable=False)
    val_mape = Column(Numeric(18, 6))
    val_wmape = Column(Numeric(18, 6))
    val_bias = Column(Numeric(18, 6))
    anos_teste = Column(Text)  # JSON com a lista de anos
    dat_execucao = Column(Date, nullable=False)
