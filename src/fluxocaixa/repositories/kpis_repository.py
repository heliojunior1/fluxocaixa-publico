"""Queries do relatório de KPIs (spec relatorios R2–R8).

Sem view nova (design D1): as agregações rodam aqui, sobre as views da F2.1
(`vw_flc_saldo_conta_agregado`, `vw_flc_saldo_conta_fundo_calc`) e as tabelas
de lançamento/extração. O D-1 é `LAG` sobre TODA a história da conta — o
último dia anterior COM saldo, não o dia-calendário anterior (paridade com a
referência). Window functions exigem SQLite ≥ 3.25 (Python 3.10 embute 3.31+).

Filtros de conta/banco: no lado de lançamento, filtrar por banco/conta usa o
JOIN com `flc_conta_bancaria` e portanto EXCLUI lançamentos sem conta
vinculada (design D3); sem filtro, o join não é aplicado e todo lançamento
ativo conta. A defasagem (R7) nunca é filtrada.
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import extract, func, text

from ..models import ContaBancaria, Lancamento
from ..models.base import db
from ..models.extracao import (
    STATUS_PARCIAL,
    STATUS_SEM_DADOS,
    STATUS_SUCESSO,
    ExecucaoExtracao,
    FonteExtracao,
)


def _dec(valor) -> Decimal:
    return Decimal(str(valor if valor is not None else 0)).quantize(Decimal("0.01"))


# --------------------------------------------------------------------------
# Saldos (R2/R5)
# --------------------------------------------------------------------------

def linhas_saldo_na_referencia(
    data_referencia: date,
    seq_conta: int | None = None,
    cod_banco: str | None = None,
) -> list[dict]:
    """Uma linha por conta com saldo ativo na data, com D-1 via LAG."""
    sql = (
        "SELECT s.seq_conta, s.val_saldo, s.val_aplicacoes, s.val_resgates, "
        "       s.val_saldo_d1, c.cod_banco, c.num_agencia, c.num_conta, c.dsc_conta "
        "FROM ("
        "  SELECT a.seq_conta, a.dat_saldo, a.val_saldo, a.val_aplicacoes, a.val_resgates, "
        "         LAG(a.val_saldo) OVER ("
        "             PARTITION BY a.seq_conta ORDER BY a.dat_saldo"
        "         ) AS val_saldo_d1 "
        "  FROM vw_flc_saldo_conta_agregado a"
        ") s "
        "JOIN flc_conta_bancaria c ON c.seq_conta = s.seq_conta "
        "WHERE s.dat_saldo = :referencia"
    )
    params: dict = {"referencia": data_referencia}
    if seq_conta is not None:
        sql += " AND s.seq_conta = :conta"
        params["conta"] = seq_conta
    if cod_banco is not None:
        sql += " AND c.cod_banco = :banco"
        params["banco"] = cod_banco
    sql += " ORDER BY c.cod_banco, c.num_agencia, c.num_conta"

    linhas = db.session.execute(text(sql), params).mappings().all()
    return [
        {
            **dict(linha),
            "val_saldo": _dec(linha["val_saldo"]),
            "val_aplicacoes": _dec(linha["val_aplicacoes"]),
            "val_resgates": _dec(linha["val_resgates"]),
            "val_saldo_d1": (
                _dec(linha["val_saldo_d1"]) if linha["val_saldo_d1"] is not None else None
            ),
        }
        for linha in linhas
    ]


def rendimento_no_periodo(
    data_inicio: date,
    data_fim: date,
    seq_conta: int | None = None,
    cod_banco: str | None = None,
) -> Decimal:
    """Soma do rendimento calculado por fundo no período (view calc da F2.1)."""
    sql = (
        "SELECT COALESCE(SUM(v.val_rendimento_calculado), 0) AS total "
        "FROM vw_flc_saldo_conta_fundo_calc v "
        "JOIN flc_conta_bancaria c ON c.seq_conta = v.seq_conta "
        "WHERE v.dat_saldo BETWEEN :inicio AND :fim"
    )
    params: dict = {"inicio": data_inicio, "fim": data_fim}
    if seq_conta is not None:
        sql += " AND v.seq_conta = :conta"
        params["conta"] = seq_conta
    if cod_banco is not None:
        sql += " AND c.cod_banco = :banco"
        params["banco"] = cod_banco
    return _dec(db.session.execute(text(sql), params).scalar())


def max_dat_inclusao_saldo() -> date | None:
    """Última data (dia) de inclusão de saldo ativo — info secundária do R7."""
    sql = "SELECT MAX(dat_inclusao) FROM flc_saldo_conta_fundo WHERE ind_status = 'A'"
    valor = db.session.execute(text(sql)).scalar()
    return date.fromisoformat(valor) if isinstance(valor, str) else valor


# --------------------------------------------------------------------------
# Lançamentos (R3/R4/R6/R8)
# --------------------------------------------------------------------------

def _query_lancamentos(seq_conta: int | None, cod_banco: str | None, *colunas):
    """Base das agregações de lançamento ativo, aplicando o recorte de conta.

    Sem filtro não há join com conta — lançamento sem conta vinculada entra
    (design D3). Com filtro, o join o exclui por definição.
    """
    query = db.session.query(*colunas).filter(Lancamento.ind_status == 'A')
    if seq_conta is not None:
        query = query.filter(Lancamento.seq_conta == seq_conta)
    if cod_banco is not None:
        query = query.join(
            ContaBancaria, ContaBancaria.seq_conta == Lancamento.seq_conta
        ).filter(ContaBancaria.cod_banco == cod_banco)
    return query


def totais_por_tipo(
    data_inicio: date,
    data_fim: date,
    seq_conta: int | None = None,
    cod_banco: str | None = None,
) -> dict[int, Decimal]:
    """Soma do valor com sinal no período por `cod_tipo_lancamento`."""
    linhas = (
        _query_lancamentos(
            seq_conta, cod_banco,
            Lancamento.cod_tipo_lancamento,
            func.sum(Lancamento.valor_com_sinal),
        )
        .filter(Lancamento.dat_lancamento.between(data_inicio, data_fim))
        .group_by(Lancamento.cod_tipo_lancamento)
        .all()
    )
    return {cod: _dec(total) for cod, total in linhas}


def agregados_mensais(
    data_inicio: date,
    data_fim: date,
    seq_conta: int | None = None,
    cod_banco: str | None = None,
) -> list[tuple[int, int, int, Decimal]]:
    """(ano, mês, cod_tipo_lancamento, soma) por mês do intervalo."""
    ano = extract("year", Lancamento.dat_lancamento)
    mes = extract("month", Lancamento.dat_lancamento)
    linhas = (
        _query_lancamentos(
            seq_conta, cod_banco,
            ano.label("ano"), mes.label("mes"),
            Lancamento.cod_tipo_lancamento,
            func.sum(Lancamento.valor_com_sinal),
        )
        .filter(Lancamento.dat_lancamento.between(data_inicio, data_fim))
        .group_by("ano", "mes", Lancamento.cod_tipo_lancamento)
        .all()
    )
    return [
        (int(linha[0]), int(linha[1]), linha[2], _dec(linha[3]))
        for linha in linhas
    ]


def top_por_tipo(
    data_inicio: date,
    data_fim: date,
    cod_tipo_lancamento: int,
    limite: int,
    seq_conta: int | None = None,
    cod_banco: str | None = None,
) -> list[tuple[int, Decimal]]:
    """Top-N (seq_qualificador, soma) do tipo no período, por valor absoluto."""
    soma = func.sum(Lancamento.valor_com_sinal)
    linhas = (
        _query_lancamentos(seq_conta, cod_banco, Lancamento.seq_qualificador, soma)
        .filter(
            Lancamento.dat_lancamento.between(data_inicio, data_fim),
            Lancamento.cod_tipo_lancamento == cod_tipo_lancamento,
        )
        .group_by(Lancamento.seq_qualificador)
        .order_by(func.abs(soma).desc())
        .limit(limite)
        .all()
    )
    return [(seq_qualificador, _dec(total)) for seq_qualificador, total in linhas]


def max_dat_inclusao_lancamento() -> date | None:
    """Última data (dia) de inclusão de lançamento ativo — info do R7."""
    valor = (
        db.session.query(func.max(Lancamento.dat_inclusao))
        .filter(Lancamento.ind_status == 'A')
        .scalar()
    )
    return valor


# --------------------------------------------------------------------------
# Defasagem da extração (R7)
# --------------------------------------------------------------------------

STATUS_ELEGIVEIS_DEFASAGEM = (STATUS_SUCESSO, STATUS_PARCIAL, STATUS_SEM_DADOS)


def destinos_com_fonte_ativa() -> set[str]:
    linhas = (
        db.session.query(FonteExtracao.cod_destino)
        .filter(FonteExtracao.ind_status == 'A')
        .distinct()
        .all()
    )
    return {destino for (destino,) in linhas}


def ultima_execucao_por_destino() -> dict[str, datetime]:
    """MAX(dat_inicio_execucao) das execuções elegíveis de fontes ativas.

    ERRO fica de fora (design D2): pipeline quebrado não renova o semáforo.
    """
    linhas = (
        db.session.query(
            FonteExtracao.cod_destino,
            func.max(ExecucaoExtracao.dat_inicio_execucao),
        )
        .join(
            FonteExtracao,
            FonteExtracao.seq_fonte_extracao == ExecucaoExtracao.seq_fonte_extracao,
        )
        .filter(
            FonteExtracao.ind_status == 'A',
            ExecucaoExtracao.cod_status.in_(STATUS_ELEGIVEIS_DEFASAGEM),
        )
        .group_by(FonteExtracao.cod_destino)
        .all()
    )
    resultado: dict[str, datetime] = {}
    for destino, ultima in linhas:
        if isinstance(ultima, str):
            ultima = datetime.fromisoformat(ultima)
        resultado[destino] = ultima
    return resultado
