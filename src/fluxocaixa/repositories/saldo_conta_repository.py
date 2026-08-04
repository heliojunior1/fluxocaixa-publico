"""Leitura de compatibilidade do saldo agregado por conta (spec R18).

Após o corte do legado (F2.4), o saldo por conta/dia deixou de ser uma tabela
própria (`flc_saldo_conta`) e passou a ser derivado da soma dos fundos, exposto
por `vw_flc_saldo_conta_agregado`. Este repositório preserva a interface de
leitura que DFC, resumo e saldos diários já usavam — os relatórios não mudam.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models.base import SessionLocal


@dataclass
class SaldoAgregado:
    """Objeto leve compatível com o que os relatórios liam (atributo val_saldo)."""
    seq_conta: int
    dat_saldo: date
    val_saldo: Decimal


class SaldoContaRepository:
    def __init__(self, session: Session | None = None):
        self.session = session or SessionLocal()

    def get_saldo_by_conta_and_date(self, seq_conta: int, data: date) -> "SaldoAgregado | None":
        row = self.session.execute(
            text("SELECT seq_conta, dat_saldo, val_saldo FROM vw_flc_saldo_conta_agregado "
                 "WHERE seq_conta = :c AND dat_saldo = :d"),
            {"c": seq_conta, "d": data},
        ).mappings().first()
        return self._para_obj(row)

    def get_saldo_total_by_date(self, data: date) -> float | None:
        """`None` = NÃO há registro na data; `0.0` = há registro e soma zero.

        O COALESCE antigo colapsava os dois em `0`, e o fallback de carry dos
        relatórios trocava um zero VERDADEIRO pelo último saldo não-zero
        (relatorios R22 — achado L9). SUM sem linhas devolve NULL.
        """
        row = self.session.execute(
            text("SELECT SUM(a.val_saldo) AS total "
                 "FROM vw_flc_saldo_conta_agregado a "
                 "JOIN flc_conta_bancaria c ON c.seq_conta = a.seq_conta "
                 "WHERE a.dat_saldo = :d AND c.ind_status = 'A'"),
            {"d": data},
        ).scalar()
        return float(row) if row is not None else None

    def get_latest_saldo_before_date(self, seq_conta: int, data: date) -> "SaldoAgregado | None":
        row = self.session.execute(
            text("SELECT seq_conta, dat_saldo, val_saldo FROM vw_flc_saldo_conta_agregado "
                 "WHERE seq_conta = :c AND dat_saldo < :d "
                 "ORDER BY dat_saldo DESC LIMIT 1"),
            {"c": seq_conta, "d": data},
        ).mappings().first()
        return self._para_obj(row)

    def get_latest_saldo_total_before_date(self, data: date) -> float:
        contas = self.session.execute(
            text("SELECT seq_conta FROM flc_conta_bancaria WHERE ind_status = 'A'")
        ).scalars().all()
        total = 0.0
        for seq in contas:
            saldo = self.get_latest_saldo_before_date(seq, data)
            if saldo:
                total += float(saldo.val_saldo)
        return total

    @staticmethod
    def _para_obj(row) -> "SaldoAgregado | None":
        if row is None:
            return None
        dat = row["dat_saldo"]
        if isinstance(dat, str):
            dat = date.fromisoformat(dat)
        return SaldoAgregado(
            seq_conta=row["seq_conta"], dat_saldo=dat,
            val_saldo=Decimal(str(row["val_saldo"] or 0)),
        )
