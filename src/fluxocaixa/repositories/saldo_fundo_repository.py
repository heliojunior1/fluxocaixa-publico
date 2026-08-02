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


def saldo_bruto_por_grupo(data_referencia: date | None = None) -> dict:
    """Saldo BRUTO por grupo de disponibilidade (spec fonte-recurso R5).

    'L' livre / 'V' vinculado / 'P' pendente (fundo sem fonte — fora do
    livre, conservador), derivado da vw_flc_saldo_fundo_fonte. Sem data,
    usa a linha mais recente de cada (conta, fundo); com data, o saldo do dia.

    ⚠️ Entrega o BRUTO: reservas/bloqueios (F7.4) não são subtraídos aqui —
    a subtração acontece uma única vez, na leitura da disponibilidade
    operacional (doc do módulo, seção 4.4).
    """
    if data_referencia is None:
        sql = (
            "SELECT cod_grupo, SUM(val_saldo) AS val_saldo "
            "FROM vw_flc_saldo_fundo_fonte "
            "WHERE num_ordem_recente = 1 GROUP BY cod_grupo"
        )
        params: dict = {}
    else:
        sql = (
            "SELECT cod_grupo, SUM(val_saldo) AS val_saldo "
            "FROM vw_flc_saldo_fundo_fonte "
            "WHERE dat_saldo = :referencia GROUP BY cod_grupo"
        )
        params = {"referencia": data_referencia}

    linhas = db.session.execute(text(sql), params).mappings().all()
    grupos = {"L": _dec(0), "V": _dec(0), "P": _dec(0)}
    for linha in linhas:
        grupos[linha["cod_grupo"]] = _dec(linha["val_saldo"])
    grupos["total"] = _dec(grupos["L"] + grupos["V"] + grupos["P"])
    return grupos


def saldo_bruto_por_fonte() -> dict:
    """Saldo BRUTO por fonte (spec fonte-recurso R11) — mesma view do grupo,
    grão `seq_fonte_recurso`, linha mais recente por (conta, fundo). Fundos
    sem fonte (pendentes) ficam FORA: não há fonte para conciliar. Entrega o
    BRUTO — reservas são subtraídas na leitura da operacional (uma vez só).
    """
    sql = (
        "SELECT seq_fonte_recurso, SUM(val_saldo) AS val_saldo "
        "FROM vw_flc_saldo_fundo_fonte "
        "WHERE num_ordem_recente = 1 AND seq_fonte_recurso IS NOT NULL "
        "GROUP BY seq_fonte_recurso"
    )
    return {linha["seq_fonte_recurso"]: _dec(linha["val_saldo"])
            for linha in db.session.execute(text(sql)).mappings().all()}


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
