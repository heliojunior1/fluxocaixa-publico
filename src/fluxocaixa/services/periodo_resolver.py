"""Origem única de (ano, período) por periodicidade (spec previsao R7/R8, F6.3).

Porta o `PeriodoResolver` da referência. Antes desta feature o Python não tinha
NADA disso: `formula_engine` fazia `if periodicidade == 'ANUAL': ... else:
<mensal>`, e QUINZENAL/SEMANAL — oferecidas na tela — caíam no ramo mensal.
Quem pedia "Semanal, 52 semanas" recebia 52 MESES.

⚠️ Python puro, não SQL (design D3). A referência usa `TO_CHAR(data,'IYYY')` e
`'IW'`, que são Oracle; **SQLite não tem semana ISO** (`%W` conta semanas
começando no domingo, e difere da ISO), e o projeto exige SQL portável
SQLite/PostgreSQL. `date.isocalendar()` dá ano e semana ISO corretos de graça.

Dois detalhes que só se descobrem lendo a referência, e que a intuição erra:

1. **O ano do SEMANAL é o ano ISO**, não o civil: 29/12/2025 pertence à semana 1
   de 2026, e 01/01/2021 à semana 53 de 2020.
2. **O mês de uma semana ISO é o da sua QUINTA-FEIRA** — a semana que atravessa
   a virada pertence ao mês/ano que contém a quinta.

E a **semana 53 existe** (anos ISO longos, como 2020). Recusá-la é o erro
clássico de quem assume 52.
"""
from datetime import date, timedelta
from typing import NamedTuple

from .validacao import RegraNegocioError

ANUAL = 'ANUAL'
MENSAL = 'MENSAL'
QUINZENAL = 'QUINZENAL'
SEMANAL = 'SEMANAL'

PERIODICIDADES = (ANUAL, MENSAL, QUINZENAL, SEMANAL)

#: Máximo de períodos por periodicidade. SEMANAL é 53, não 52.
MAXIMO_POR_PERIODICIDADE = {ANUAL: 1, MENSAL: 12, QUINZENAL: 24, SEMANAL: 53}

#: Passo em dias das periodicidades de granularidade fina (R9).
DIAS_POR_PERIODO = {SEMANAL: 7}


class Periodo(NamedTuple):
    ano: int
    periodo: int


def normalizar(periodicidade: str | None) -> str:
    """Valida e normaliza; periodicidade desconhecida é erro de negócio."""
    valor = (periodicidade or '').strip().upper()
    if valor not in PERIODICIDADES:
        raise RegraNegocioError(
            f"Periodicidade inválida: '{periodicidade}' — "
            f"use {', '.join(PERIODICIDADES)}"
        )
    return valor


def resolver(data: date, periodicidade: str) -> Periodo:
    """(ano, período) de uma data. Para SEMANAL o ano é o ANO ISO."""
    p = normalizar(periodicidade)
    if p == ANUAL:
        return Periodo(data.year, 1)
    if p == MENSAL:
        return Periodo(data.year, data.month)
    if p == QUINZENAL:
        return Periodo(data.year, quinzena(data))
    ano_iso, semana_iso, _dia = data.isocalendar()
    return Periodo(ano_iso, semana_iso)


def quinzena(data: date) -> int:
    """1ª quinzena até o dia 15; 2ª a partir do 16."""
    return (data.month - 1) * 2 + (1 if data.day <= 15 else 2)


def mes_do_periodo(periodicidade: str, ano: int, periodo: int) -> int | None:
    """Mês do período — a granularidade dos relatórios (DFC, KPIs).

    ANUAL não tem mês único (devolve `None`): o total do ano é distribuído na
    leitura pelo perfil histórico, como a F5.2 já faz.
    """
    p = normalizar(periodicidade)
    if p == ANUAL:
        return None
    if p == MENSAL:
        return periodo
    if p == QUINZENAL:
        return (periodo + 1) // 2
    return _quinta_da_semana_iso(ano, periodo).month


def validar_periodo(periodicidade: str, periodo: int) -> None:
    """Faixa do período (R8). Fora dela é erro de negócio."""
    p = normalizar(periodicidade)
    maximo = MAXIMO_POR_PERIODICIDADE[p]
    if not isinstance(periodo, int) or periodo < 1 or periodo > maximo:
        raise RegraNegocioError(
            f"Período {periodo} fora da faixa de {p}: esperado entre 1 e {maximo}"
        )


def primeiro_dia_da_semana_iso(ano_iso: int, semana: int) -> date:
    """Segunda-feira da semana ISO."""
    return date.fromisocalendar(ano_iso, semana, 1)


def _quinta_da_semana_iso(ano_iso: int, semana: int) -> date:
    """Quinta-feira da semana ISO — é ela que define o mês e o ano da semana."""
    return date.fromisocalendar(ano_iso, semana, 4)


def data_inicial_do_periodo(periodicidade: str, ano: int, periodo: int) -> date:
    """Primeira data do período — usada para gerar a série da projeção (R9)."""
    p = normalizar(periodicidade)
    validar_periodo(p, periodo)
    if p == ANUAL:
        return date(ano, 1, 1)
    if p == MENSAL:
        return date(ano, periodo, 1)
    if p == QUINZENAL:
        mes = (periodo + 1) // 2
        return date(ano, mes, 1 if periodo % 2 == 1 else 16)
    try:
        return primeiro_dia_da_semana_iso(ano, periodo)
    except ValueError:
        # A semana 53 existe — mas só em ano ISO longo. `validar_periodo` não
        # tem como saber (a faixa é 1..53 para toda semana); só aqui, com o
        # ano em mãos, dá para dizer. Sem isto o `ValueError` do
        # `fromisocalendar` subiria cru e viraria 500.
        raise RegraNegocioError(
            f"O ano {ano} não tem semana {periodo}: são 52 semanas ISO."
        )


def rotulo_periodo(periodicidade: str, ano: int, periodo: int) -> str | None:
    """Rótulo curto do período para a tela — `None` no MENSAL.

    MENSAL devolve `None` de propósito: o nome do mês já é a linguagem das
    telas de projeção (`meses_nomes` nos templates) e trocá-lo por "M3" seria
    uma regressão de leitura. `Q1…Q24` e `S1…S53` são o vocabulário que a tela
    do simulador já usava — só agora correspondem ao que o backend gera.
    """
    p = normalizar(periodicidade)
    if p == MENSAL:
        return None
    if p == ANUAL:
        return str(ano)
    return f"{'Q' if p == QUINZENAL else 'S'}{periodo}"


def serie_de_datas(periodicidade: str, ano_base: int, quantidade: int) -> list[date]:
    """`quantidade` datas consecutivas na granularidade da periodicidade.

    É o que consertou QUINZENAL/SEMANAL: antes toda periodicidade caía no passo
    mensal, então 52 "semanas" viravam 52 meses.
    """
    from dateutil.relativedelta import relativedelta

    p = normalizar(periodicidade)
    datas: list[date] = []
    if p == SEMANAL:
        # começa na 1ª semana ISO cujo ano ISO é o ano-base
        atual = primeiro_dia_da_semana_iso(ano_base, 1)
        for _ in range(quantidade):
            datas.append(atual)
            atual += timedelta(days=7)
        return datas
    if p == QUINZENAL:
        for i in range(quantidade):
            ano = ano_base + i // 24
            periodo = i % 24 + 1
            datas.append(data_inicial_do_periodo(QUINZENAL, ano, periodo))
        return datas
    if p == MENSAL:
        inicio = date(ano_base, 1, 1)
        return [inicio + relativedelta(months=i) for i in range(quantidade)]
    return [date(ano_base + i, 1, 1) for i in range(quantidade)]


__all__ = [
    'ANUAL',
    'MAXIMO_POR_PERIODICIDADE',
    'MENSAL',
    'PERIODICIDADES',
    'QUINZENAL',
    'SEMANAL',
    'Periodo',
    'data_inicial_do_periodo',
    'mes_do_periodo',
    'normalizar',
    'primeiro_dia_da_semana_iso',
    'quinzena',
    'resolver',
    'rotulo_periodo',
    'serie_de_datas',
    'validar_periodo',
]
