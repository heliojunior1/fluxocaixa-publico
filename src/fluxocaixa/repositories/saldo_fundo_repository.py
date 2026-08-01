"""Leitura das views de saldo por fundo (spec saldo-por-fundo R5/R6).

As views vivem nas migrações (fora do Base.metadata — anti-deriva);
aqui só consultas com bind params, valores convertidos para Decimal.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import text

from ..models.base import db


def _dec(valor) -> Decimal:
    return Decimal(str(valor if valor is not None else 0)).quantize(Decimal("0.01"))


def calc_por_periodo(
    data_inicio: date,
    data_fim: date,
    seq_conta: int | None = None,
    seq_fundo: int | None = None,
) -> list[dict]:
    """Linhas da vw_flc_saldo_conta_fundo_calc no período (com rendimento)."""
    sql = (
        "SELECT * FROM vw_flc_saldo_conta_fundo_calc "
        "WHERE dat_saldo BETWEEN :inicio AND :fim"
    )
    params = {"inicio": data_inicio, "fim": data_fim}
    if seq_conta is not None:
        sql += " AND seq_conta = :conta"
        params["conta"] = seq_conta
    if seq_fundo is not None:
        sql += " AND seq_fundo = :fundo"
        params["fundo"] = seq_fundo
    sql += " ORDER BY seq_conta, seq_fundo, dat_saldo"

    linhas = db.session.execute(text(sql), params).mappings().all()
    return [
        {
            **dict(linha),
            "val_saldo": _dec(linha["val_saldo"]),
            "val_aplicacoes": _dec(linha["val_aplicacoes"]),
            "val_resgates": _dec(linha["val_resgates"]),
            "val_saldo_inicial_derivado": _dec(linha["val_saldo_inicial_derivado"]),
            "val_rendimento_calculado": _dec(linha["val_rendimento_calculado"]),
        }
        for linha in linhas
    ]


def ultimo_agregado_anterior(
    data_referencia: date,
    seq_conta: int | None = None,
) -> list[dict]:
    """Última linha do agregado ANTERIOR à data, por conta (LAG histórico).

    É o "saldo inicial derivado" do relatório de saldos diários (spec
    relatorios R14): o último dia anterior COM saldo, não o dia-calendário.
    """
    sql = (
        "SELECT a.* FROM vw_flc_saldo_conta_agregado a "
        "JOIN ("
        "  SELECT seq_conta, MAX(dat_saldo) AS dat_ultimo "
        "  FROM vw_flc_saldo_conta_agregado "
        "  WHERE dat_saldo < :referencia "
        "  GROUP BY seq_conta"
        ") u ON u.seq_conta = a.seq_conta AND u.dat_ultimo = a.dat_saldo"
    )
    params: dict = {"referencia": data_referencia}
    if seq_conta is not None:
        sql += " WHERE a.seq_conta = :conta"
        params["conta"] = seq_conta

    linhas = db.session.execute(text(sql), params).mappings().all()
    return [
        {
            **dict(linha),
            "val_saldo": _dec(linha["val_saldo"]),
            "val_aplicacoes": _dec(linha["val_aplicacoes"]),
            "val_resgates": _dec(linha["val_resgates"]),
        }
        for linha in linhas
    ]


def agregado_por_conta(
    data_inicio: date,
    data_fim: date,
    seq_conta: int | None = None,
) -> list[dict]:
    """Linhas da vw_flc_saldo_conta_agregado no período (nunca persistido)."""
    sql = (
        "SELECT * FROM vw_flc_saldo_conta_agregado "
        "WHERE dat_saldo BETWEEN :inicio AND :fim"
    )
    params = {"inicio": data_inicio, "fim": data_fim}
    if seq_conta is not None:
        sql += " AND seq_conta = :conta"
        params["conta"] = seq_conta
    sql += " ORDER BY seq_conta, dat_saldo"

    linhas = db.session.execute(text(sql), params).mappings().all()
    return [
        {
            **dict(linha),
            "val_saldo": _dec(linha["val_saldo"]),
            "val_aplicacoes": _dec(linha["val_aplicacoes"]),
            "val_resgates": _dec(linha["val_resgates"]),
        }
        for linha in linhas
    ]
