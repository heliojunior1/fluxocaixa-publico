"""Relatório de KPIs (spec relatorios R1–R8, feature F5.1).

Monta os seis blocos sobre `repositories/kpis_repository.py`. Valores
monetários trafegam como `Decimal` e saem serializados como string com 2
casas (o template/Chart.js converte); percentuais com 2 casas HALF_UP.

Defasagem (R7, design D2): o semáforo mede horas — truncadas para inteiro,
como a referência — desde a última execução elegível por destino, usando o
único timestamp real do modelo (`dat_inicio_execucao`). O relógio (`agora`)
é injetável para os testes de borda 24h/48h.
"""
import calendar
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from ...models import Qualificador
from ...repositories import kpis_repository
from ..dominio_lancamento import TIPO_ENTRADA, TIPO_SAIDA, resolver_tipo
from ..validacao import RegraNegocioError

LIMITE_TOP_QUALIFICADOR = 5
HORAS_LIMITE_OK = 24
HORAS_LIMITE_AMARELO = 48

ESTADO_OK = 'OK'
ESTADO_AMARELO = 'AMARELO'
ESTADO_VERMELHO = 'VERMELHO'
ESTADO_SEM_FONTE = 'SEM_FONTE'

_CEM = Decimal(100)


def _fmt(valor: Decimal | None) -> str | None:
    if valor is None:
        return None
    return str(valor.quantize(Decimal("0.01")))


def _percentual(parte: Decimal, total: Decimal) -> Decimal | None:
    """Percentual com 2 casas HALF_UP; total não positivo ⇒ None (o chamador
    decide entre nulo e 0.00 conforme o requisito)."""
    if total <= 0:
        return None
    return (parte * _CEM / total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _mes_anterior(ano: int, mes: int) -> tuple[int, int]:
    return (ano - 1, 12) if mes == 1 else (ano, mes - 1)


def _meses_da_evolucao(referencia: date) -> list[tuple[int, int]]:
    """Os 12 (ano, mês) terminando no mês da referência, em ordem."""
    meses: list[tuple[int, int]] = []
    ano, mes = referencia.year, referencia.month
    for _ in range(12):
        meses.append((ano, mes))
        ano, mes = _mes_anterior(ano, mes)
    return list(reversed(meses))


def get_kpis_data(
    data_referencia: date | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    seq_conta: int | None = None,
    cod_banco: str | None = None,
    agora: datetime | None = None,
) -> dict:
    referencia = data_referencia or date.today()
    inicio = data_inicio or referencia.replace(day=1)
    fim = data_fim or referencia
    if inicio > fim:
        raise RegraNegocioError(
            "Período inválido: data inicial posterior à data final."
        )
    agora = agora or datetime.now()

    cod_entrada = resolver_tipo(TIPO_ENTRADA).cod_tipo_lancamento
    cod_saida = resolver_tipo(TIPO_SAIDA).cod_tipo_lancamento

    linhas_saldo = kpis_repository.linhas_saldo_na_referencia(
        referencia, seq_conta=seq_conta, cod_banco=cod_banco
    )
    totais = kpis_repository.totais_por_tipo(
        inicio, fim, seq_conta=seq_conta, cod_banco=cod_banco
    )
    receita = totais.get(cod_entrada, Decimal("0.00"))
    despesa = abs(totais.get(cod_saida, Decimal("0.00")))

    return {
        "filtros": {
            "data_referencia": referencia.isoformat(),
            "data_inicio": inicio.isoformat(),
            "data_fim": fim.isoformat(),
            "seq_conta": seq_conta,
            "cod_banco": cod_banco,
            # R8: qualquer recorte por conta/banco deixa de cobrir os
            # lançamentos sem conta vinculada — a UI avisa.
            "recorte_sem_conta": seq_conta is not None or cod_banco is not None,
        },
        "saldos": _bloco_saldos(linhas_saldo, inicio, fim, seq_conta, cod_banco),
        "receita_despesa": _bloco_receita_despesa(receita, despesa),
        "evolucao": _bloco_evolucao(
            referencia, cod_entrada, cod_saida, seq_conta, cod_banco
        ),
        "saldo_por_conta": _bloco_saldo_por_conta(linhas_saldo),
        "composicao": _bloco_composicao(
            inicio, fim, cod_entrada, cod_saida, receita, despesa,
            seq_conta, cod_banco,
        ),
        "defasagem": _bloco_defasagem(agora),
    }


# --------------------------------------------------------------------------
# Blocos
# --------------------------------------------------------------------------

def _bloco_saldos(linhas_saldo, inicio, fim, seq_conta, cod_banco) -> dict:
    consolidado = sum((l["val_saldo"] for l in linhas_saldo), Decimal("0.00"))
    com_d1 = [l for l in linhas_saldo if l["val_saldo_d1"] is not None]
    consolidado_d1 = sum((l["val_saldo_d1"] for l in com_d1), Decimal("0.00"))
    variacao = consolidado - consolidado_d1 if com_d1 else None

    por_banco: dict[str, Decimal] = {}
    for linha in linhas_saldo:
        por_banco[linha["cod_banco"]] = (
            por_banco.get(linha["cod_banco"], Decimal("0.00")) + linha["val_saldo"]
        )

    rendimento = kpis_repository.rendimento_no_periodo(
        inicio, fim, seq_conta=seq_conta, cod_banco=cod_banco
    )
    return {
        "consolidado": _fmt(consolidado),
        "por_banco": [
            {"cod_banco": banco, "valor": _fmt(valor)}
            for banco, valor in sorted(por_banco.items())
        ],
        "rendimento": _fmt(rendimento),
        "consolidado_d1": _fmt(consolidado_d1) if com_d1 else None,
        "variacao_d1": _fmt(variacao),
    }


def _bloco_receita_despesa(receita: Decimal, despesa: Decimal) -> dict:
    return {
        "receita": _fmt(receita),
        "despesa": _fmt(despesa),
        "resultado": _fmt(receita - despesa),
        "percentual": _fmt(_percentual(despesa, receita)),
    }


def _bloco_evolucao(referencia, cod_entrada, cod_saida, seq_conta, cod_banco) -> list[dict]:
    meses = _meses_da_evolucao(referencia)
    primeiro_ano, primeiro_mes = meses[0]
    inicio = date(primeiro_ano, primeiro_mes, 1)
    fim = date(
        referencia.year, referencia.month,
        calendar.monthrange(referencia.year, referencia.month)[1],
    )
    agregados = kpis_repository.agregados_mensais(
        inicio, fim, seq_conta=seq_conta, cod_banco=cod_banco
    )
    receita_mes: dict[tuple[int, int], Decimal] = {}
    despesa_mes: dict[tuple[int, int], Decimal] = {}
    for ano, mes, cod_tipo, soma in agregados:
        if cod_tipo == cod_entrada:
            receita_mes[(ano, mes)] = receita_mes.get((ano, mes), Decimal("0.00")) + soma
        elif cod_tipo == cod_saida:
            despesa_mes[(ano, mes)] = despesa_mes.get((ano, mes), Decimal("0.00")) + soma

    return [
        {
            "ano": ano,
            "mes": mes,
            "receita": _fmt(receita_mes.get((ano, mes), Decimal("0.00"))),
            "despesa": _fmt(abs(despesa_mes.get((ano, mes), Decimal("0.00")))),
            "parcial": (ano, mes) == (referencia.year, referencia.month),
        }
        for ano, mes in meses
    ]


def _bloco_saldo_por_conta(linhas_saldo) -> list[dict]:
    consolidado = sum((l["val_saldo"] for l in linhas_saldo), Decimal("0.00"))
    resultado = []
    for linha in linhas_saldo:
        saldo_d1 = linha["val_saldo_d1"]
        delta = linha["val_saldo"] - saldo_d1 if saldo_d1 is not None else None
        # Consolidado não positivo ⇒ 0.00 (R5), diferente do percentual nulo do R3
        percentual = _percentual(linha["val_saldo"], consolidado) or Decimal("0.00")
        resultado.append({
            "seq_conta": linha["seq_conta"],
            "cod_banco": linha["cod_banco"],
            "num_agencia": linha["num_agencia"],
            "num_conta": linha["num_conta"],
            "dsc_conta": linha["dsc_conta"],
            "saldo": _fmt(linha["val_saldo"]),
            "saldo_d1": _fmt(saldo_d1),
            "delta": _fmt(delta),
            "aplicacoes": _fmt(linha["val_aplicacoes"]),
            "resgates": _fmt(linha["val_resgates"]),
            "percentual": _fmt(percentual),
        })
    return resultado


def _bloco_composicao(inicio, fim, cod_entrada, cod_saida, receita, despesa,
                      seq_conta, cod_banco) -> dict:
    top_receitas = _itens_composicao(
        inicio, fim, cod_entrada, receita, seq_conta, cod_banco
    )
    top_despesas = _itens_composicao(
        inicio, fim, cod_saida, despesa, seq_conta, cod_banco
    )
    soma_top_receitas = sum(
        (Decimal(item["valor"]) for item in top_receitas), Decimal("0.00")
    )
    soma_top_despesas = sum(
        (Decimal(item["valor"]) for item in top_despesas), Decimal("0.00")
    )
    return {
        "top_receitas": top_receitas,
        "top_despesas": top_despesas,
        "outras_receitas": _fmt(receita - soma_top_receitas),
        "outras_despesas": _fmt(despesa - soma_top_despesas),
    }


def _itens_composicao(inicio, fim, cod_tipo, total_do_tipo,
                      seq_conta, cod_banco) -> list[dict]:
    itens = []
    top = kpis_repository.top_por_tipo(
        inicio, fim, cod_tipo, LIMITE_TOP_QUALIFICADOR,
        seq_conta=seq_conta, cod_banco=cod_banco,
    )
    for seq_qualificador, soma in top:
        qualificador = Qualificador.query.get(seq_qualificador)
        pai = qualificador.pai if qualificador else None
        valor = abs(soma)
        itens.append({
            "seq_qualificador": seq_qualificador,
            "num_qualificador": qualificador.num_qualificador if qualificador else None,
            "dsc_qualificador": qualificador.dsc_qualificador if qualificador else None,
            "num_qualificador_pai": pai.num_qualificador if pai else None,
            "dsc_qualificador_pai": pai.dsc_qualificador if pai else None,
            "valor": _fmt(valor),
            "percentual": _fmt(_percentual(valor, total_do_tipo) or Decimal("0.00")),
        })
    return itens


def _bloco_defasagem(agora: datetime) -> dict:
    destinos_ativos = kpis_repository.destinos_com_fonte_ativa()
    ultimas = kpis_repository.ultima_execucao_por_destino()
    return {
        "saldo": _defasagem_destino(
            'SALDO_FUNDO', destinos_ativos, ultimas, agora,
            kpis_repository.max_dat_inclusao_saldo(),
        ),
        "lancamento": _defasagem_destino(
            'LANCAMENTO', destinos_ativos, ultimas, agora,
            kpis_repository.max_dat_inclusao_lancamento(),
        ),
    }


def _defasagem_destino(destino: str, destinos_ativos: set[str],
                       ultimas: dict[str, datetime], agora: datetime,
                       ultima_inclusao: date | None) -> dict:
    resultado = {
        "estado": ESTADO_SEM_FONTE,
        "horas": None,
        "ultima_execucao": None,
        "ultima_inclusao": ultima_inclusao.isoformat() if ultima_inclusao else None,
    }
    if destino not in destinos_ativos:
        return resultado
    ultima = ultimas.get(destino)
    if ultima is None:
        resultado["estado"] = ESTADO_VERMELHO
        return resultado
    # Horas truncadas (piso), como a referência — 24h em ponto ainda é OK
    horas = max(0, int((agora - ultima).total_seconds() // 3600))
    resultado["horas"] = horas
    resultado["ultima_execucao"] = ultima.isoformat(sep=' ', timespec='seconds')
    if horas <= HORAS_LIMITE_OK:
        resultado["estado"] = ESTADO_OK
    elif horas <= HORAS_LIMITE_AMARELO:
        resultado["estado"] = ESTADO_AMARELO
    else:
        resultado["estado"] = ESTADO_VERMELHO
    return resultado
