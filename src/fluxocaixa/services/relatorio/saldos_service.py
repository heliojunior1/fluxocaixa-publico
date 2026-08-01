"""Saldos diários — modo agregado por conta e modo por fundo (F5.3).

Spec relatorios R14–R16: fonte única nas views da F2.1
(`vw_flc_saldo_conta_agregado` / `vw_flc_saldo_conta_fundo_calc`).
- Saldo inicial = DERIVADO: último dia anterior COM saldo (LAG histórico,
  mesma semântica do D-1 dos KPIs) — nulo quando a conta não tem histórico.
- Rendimento do dia (agregado) = soma do rendimento calculado dos fundos da
  conta; nunca persistido (consistência por construção, regra da F2.1).
- Saldo final CALCULADO = inicial + entradas − |saídas| (lançamentos da
  conta); a divergência compara com o saldo REGISTRADO do dia seguinte.
- Série de 30 dias preservada (mesma view, via strangler SaldoContaRepository,
  com carry-forward do último dia com saldo).

Cálculo em Decimal (2 casas); conversão para o template na borda.
"""
from datetime import date, timedelta
from decimal import Decimal

from ...models import ContaBancaria, Fundo, SistemaOrigem, TipoOrigemSaldo
from ...repositories import saldo_fundo_repository
from ...repositories.lancamento_repository import LancamentoRepository
from ...repositories.saldo_conta_repository import SaldoContaRepository

_ZERO = Decimal("0.00")


def _dec(valor) -> Decimal:
    return Decimal(str(valor if valor is not None else 0)).quantize(Decimal("0.01"))


def _data(valor) -> date | None:
    if valor is None or isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor))


def get_saldos_diarios_data(
    data_ref: date,
    visao: str = "agregado",
    seq_conta: int | None = None,
) -> dict:
    """Relatório de saldos diários nos modos agregado (default) e por fundo."""
    visao = "fundo" if (visao or "").lower() == "fundo" else "agregado"

    if visao == "fundo":
        rows_fundo, totais_fundo = _modo_fundo(data_ref, seq_conta)
        rows, totais = [], _totais_vazios()
    else:
        rows, totais = _modo_agregado(data_ref, seq_conta)
        rows_fundo, totais_fundo = [], _totais_fundo_vazios()

    labels, serie = _evolucao_30_dias(data_ref)
    return {
        "visao": visao,
        "rows": rows,
        "totais": totais,
        "rows_fundo": rows_fundo,
        "totais_fundo": totais_fundo,
        "evolucao_labels": labels,
        "evolucao_saldos": serie,
    }


# --------------------------------------------------------------------------
# Modo agregado (R14)
# --------------------------------------------------------------------------

def _totais_vazios() -> dict:
    return {
        "saldo_anterior": _ZERO, "entradas": _ZERO, "saidas": _ZERO,
        "saldo_final": _ZERO, "rendimento": _ZERO, "saldo_registrado": _ZERO,
    }


def _modo_agregado(data_ref: date, seq_conta: int | None) -> tuple[list, dict]:
    lancamento_repo = LancamentoRepository()

    registrados = {
        linha["seq_conta"]: linha
        for linha in saldo_fundo_repository.agregado_por_conta(
            data_ref, data_ref, seq_conta=seq_conta
        )
    }
    anteriores = {
        linha["seq_conta"]: linha
        for linha in saldo_fundo_repository.ultimo_agregado_anterior(
            data_ref, seq_conta=seq_conta
        )
    }
    proximos = {
        linha["seq_conta"]: linha
        for linha in saldo_fundo_repository.agregado_por_conta(
            data_ref + timedelta(days=1), data_ref + timedelta(days=1),
            seq_conta=seq_conta,
        )
    }
    rendimento_conta: dict[int, Decimal] = {}
    for linha in saldo_fundo_repository.calc_por_periodo(
        data_ref, data_ref, seq_conta=seq_conta
    ):
        rendimento_conta[linha["seq_conta"]] = (
            rendimento_conta.get(linha["seq_conta"], _ZERO)
            + linha["val_rendimento_calculado"]
        )

    query_contas = ContaBancaria.query.filter_by(ind_status="A")
    if seq_conta is not None:
        query_contas = query_contas.filter_by(seq_conta=seq_conta)
    contas = query_contas.order_by(
        ContaBancaria.cod_banco, ContaBancaria.num_agencia, ContaBancaria.num_conta
    ).all()

    rows = []
    totais = _totais_vazios()
    for conta in contas:
        registrado = registrados.get(conta.seq_conta)
        anterior = anteriores.get(conta.seq_conta)
        entradas = _dec(lancamento_repo.get_sum_by_account_on_date_positive(
            seq_conta=conta.seq_conta, on_date=data_ref
        ))
        saidas = _dec(lancamento_repo.get_sum_by_account_on_date_negative(
            seq_conta=conta.seq_conta, on_date=data_ref
        ))
        # Linha só para conta com saldo (na data ou carregado) ou movimento
        if registrado is None and anterior is None and not entradas and not saidas:
            continue

        saldo_inicial = anterior["val_saldo"] if anterior else None
        saldo_final = (saldo_inicial or _ZERO) + entradas - saidas
        proximo = proximos.get(conta.seq_conta)
        divergencia = (
            proximo["val_saldo"] - saldo_final if proximo is not None else None
        )
        rows.append({
            "conta": conta,
            "saldo_inicial": saldo_inicial,
            # inicial vindo exatamente da véspera = "exato"; mais antigo = carregado
            "saldo_exato": (
                anterior is not None
                and _data(anterior["dat_saldo"]) == data_ref - timedelta(days=1)
            ),
            "entradas_dia": entradas,
            "saidas_dia": saidas,
            "saldo_final": saldo_final,
            "rendimento_dia": rendimento_conta.get(conta.seq_conta, _ZERO),
            "saldo_registrado": registrado["val_saldo"] if registrado else None,
            "origem_consolidada": (
                registrado["dsc_origem_consolidada"] if registrado else None
            ),
            "divergencia": divergencia,
        })

        totais["saldo_anterior"] += saldo_inicial or _ZERO
        totais["entradas"] += entradas
        totais["saidas"] += saidas
        totais["saldo_final"] += saldo_final
        totais["rendimento"] += rendimento_conta.get(conta.seq_conta, _ZERO)
        totais["saldo_registrado"] += registrado["val_saldo"] if registrado else _ZERO

    return rows, totais


# --------------------------------------------------------------------------
# Modo por fundo (R15)
# --------------------------------------------------------------------------

def _totais_fundo_vazios() -> dict:
    return {"saldo": _ZERO, "aplicacoes": _ZERO, "resgates": _ZERO,
            "rendimento": _ZERO}


def _descrever_origem(seq_tipo, seq_sistema, tipos: dict, sistemas: dict) -> str:
    sigla = tipos.get(seq_tipo, "")
    if sigla == "MANUAL":
        return "Manual"
    if sigla == "IMPORTADO":
        return "Importado"
    return f"Automatizado - {sistemas.get(seq_sistema, '')}"


def _modo_fundo(data_ref: date, seq_conta: int | None) -> tuple[list, dict]:
    linhas = saldo_fundo_repository.calc_por_periodo(
        data_ref, data_ref, seq_conta=seq_conta
    )
    contas = {c.seq_conta: c for c in ContaBancaria.query.all()}
    fundos = {f.seq_fundo: f for f in Fundo.query.all()}
    tipos = {t.seq_tipo_origem_saldo: t.txt_sigla for t in TipoOrigemSaldo.query.all()}
    sistemas = {s.seq_sistema_origem: s.txt_sigla for s in SistemaOrigem.query.all()}

    rows = []
    totais = _totais_fundo_vazios()
    for linha in linhas:
        rows.append({
            "conta": contas[linha["seq_conta"]],
            "fundo": fundos[linha["seq_fundo"]],
            "saldo_inicial": linha["val_saldo_inicial_derivado"],
            "aplicacoes": linha["val_aplicacoes"],
            "resgates": linha["val_resgates"],
            "rendimento": linha["val_rendimento_calculado"],
            "saldo": linha["val_saldo"],
            "origem": _descrever_origem(
                linha["seq_tipo_origem"], linha["seq_sistema_origem"],
                tipos, sistemas,
            ),
        })
        totais["saldo"] += linha["val_saldo"]
        totais["aplicacoes"] += linha["val_aplicacoes"]
        totais["resgates"] += linha["val_resgates"]
        totais["rendimento"] += linha["val_rendimento_calculado"]

    return rows, totais


# --------------------------------------------------------------------------
# Evolução 30 dias (R16) — comportamento preservado
# --------------------------------------------------------------------------

def _evolucao_30_dias(data_ref: date) -> tuple[list[str], list[float]]:
    saldo_repo = SaldoContaRepository()
    labels: list[str] = []
    serie: list[float] = []
    dia = data_ref - timedelta(days=29)
    while dia <= data_ref:
        total_dia = saldo_repo.get_saldo_total_by_date(dia)
        if total_dia == 0:
            total_dia = saldo_repo.get_latest_saldo_total_before_date(dia)
        labels.append(dia.strftime("%Y-%m-%d"))
        serie.append(float(total_dia))
        dia += timedelta(days=1)
    return labels, serie
