"""Origem única da série histórica da previsão entre exercícios.

Duas camadas de identidade:

1. **Raiz** (F10.2, spec previsao R17): "a mesma rubrica ao longo do tempo"
   é o conjunto de linhas de `flc_qualificador` com a mesma
   `cod_rubrica_raiz` — continuidade 1:1 (renome, renumeração, reativação).
   `seqs_da_rubrica` continua servindo os relatórios de REALIZADO, que não
   usam correspondência.
2. **Correspondência** (De/Para, previsao R30/R31): fusão e desdobramento.
   `serie_mensal` é a ÚNICA leitura da série de PREVISÃO — modelos, métodos
   por qualificador, crescimento, fórmulas e backtest passam por ela. Ela
   expande cada identidade pelas correspondências de que é destino, com corte
   em 1º de janeiro da vigência:
   - fusão → soma integral das origens;
   - desdobramento com regra que RECONCILIA → lançamentos automáticos da
     origem cujos atributos (staging) satisfazem a regra do destino;
   - desdobramento com rateio → origem × percentual, meses ESTIMADOS;
   - desdobramento sem nada disso → PENDENTE: a rubrica sozinha não recebe a
     origem; um conjunto com TODOS os destinos a recebe uma única vez.

⚠️ Os lançamentos nunca mudam — a série reconstruída é visão derivada. A
guarda estrutural (`src/tests/unit/test_serie_por_raiz.py`) reprova filtro
de `Lancamento.seq_qualificador` nos serviços de série: a consulta mora aqui.
⚠️ O `ind_status` do QUALIFICADOR não entra no filtro: rubrica extinta tem o
passado consultável — o filtro de ativos (R11) é sobre o LANÇAMENTO.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import date, timedelta

#: versão do De/Para fixada por uma execução (R33) — todas as séries da
#: execução leem a MESMA versão, e é ela que vai para o resultado.
_VERSAO_FIXADA: ContextVar[int | None] = ContextVar('versao_de_para', default=None)

INICIO_DOS_TEMPOS = date(1900, 1, 1)
TOLERANCIA_RECONCILIACAO = 0.01

MODO_RECONSTRUCAO = 'RECONSTRUCAO'
MODO_RATEIO = 'RATEIO'
MODO_PENDENTE = 'PENDENTE'


# ------------------------------------------------------------------ raiz

def raiz_de(seq_qualificador: int) -> int:
    from ..models import Qualificador
    from ..models.base import db

    qualificador = db.session.get(Qualificador, seq_qualificador)
    if qualificador is None or qualificador.cod_rubrica_raiz is None:
        return seq_qualificador
    return qualificador.cod_rubrica_raiz


def seqs_por_raiz(raiz: int) -> list[int]:
    """Linhas da identidade; raiz sem linha (dado legado) degrada para [raiz]."""
    from ..models import Qualificador

    linhas = Qualificador.query.filter(Qualificador.cod_rubrica_raiz == raiz).all()
    return [linha.seq_qualificador for linha in linhas] or [raiz]


def seqs_da_rubrica(seq_qualificador: int) -> list[int]:
    """Todos os `seq_qualificador` que compartilham a raiz do informado —
    continuidade 1:1, SEM correspondência (uso: relatórios de realizado)."""
    return seqs_por_raiz(raiz_de(seq_qualificador))


def seqs_das_rubricas(seq_qualificadores: list[int]) -> list[int]:
    vistos: set[int] = set()
    for seq in seq_qualificadores:
        vistos.update(seqs_da_rubrica(seq))
    return sorted(vistos)


# ------------------------------------------------------------- consultas

def _mensal(raiz: int, inicio: date, fim: date, ate: date | None,
            regra: str | None = None) -> dict[tuple[int, int], float]:
    """Soma COM SINAL por (ano, mês) dos lançamentos ATIVOS da identidade,
    na faixa [inicio, fim] e antes de `ate` (corte da vigência). Com `regra`,
    só os automáticos cuja linha de staging satisfaz a regra."""
    from sqlalchemy import extract, func

    from ..models import EtlStaging, Lancamento
    from ..models.base import db

    limite = fim if ate is None else min(fim, ate - timedelta(days=1))
    if limite < inicio:
        return {}
    ano = extract('year', Lancamento.dat_lancamento)
    mes = extract('month', Lancamento.dat_lancamento)
    consulta = (
        db.session.query(ano.label('ano'), mes.label('mes'),
                         func.sum(Lancamento.valor_com_sinal).label('total'))
        .filter(
            Lancamento.seq_qualificador.in_(seqs_por_raiz(raiz)),
            Lancamento.dat_lancamento >= inicio,
            Lancamento.dat_lancamento <= limite,
            Lancamento.ind_status == 'A',
        )
    )
    if regra is not None:
        from .regra import traduzir_regra

        consulta = (consulta
                    .join(EtlStaging,
                          EtlStaging.seq_etl_staging == Lancamento.seq_etl_staging)
                    .filter(traduzir_regra(regra)))
    # erro de banco SOBE (R11): nunca projeção zero com cara de dado apurado
    return {(int(r.ano), int(r.mes)): float(r.total or 0)
            for r in consulta.group_by(ano, mes).all()}


def realizado_proprio(raiz: int, desde: date) -> float:
    """Soma com sinal dos lançamentos da própria identidade desde `desde`."""
    return sum(_mensal(raiz, desde, date(2999, 12, 31), None).values())


# ------------------------------------------------------------- expansão

@dataclass(frozen=True)
class _Componente:
    raiz: int
    fator: float
    ate: date | None
    estimado: bool
    regra: str | None = None


@dataclass
class SerieRubricas:
    """Série de previsão de um conjunto de rubricas."""

    #: (ano, mês) → soma com sinal (meses sem movimento podem faltar)
    valores: dict = field(default_factory=dict)
    #: (ano, mês) com contribuição de rateio estimado
    estimados: set = field(default_factory=set)
    #: desdobramentos pendentes que tocam o conjunto sem ter todos os destinos
    #: [{'correspondencia': seq, 'faltam': [raiz, ...]}]
    pendencias: list = field(default_factory=list)
    versao: int = 0


def _min_data(a: date | None, b: date) -> date:
    return b if a is None else min(a, b)


class _Expansao:
    """Expansão de um conjunto de identidades pelas correspondências."""

    def __init__(self, estados: list, modos: dict | None = None):
        self.por_destino: dict[int, list] = {}
        for estado in estados:
            for destino in estado.destinos:
                self.por_destino.setdefault(destino, []).append(estado)
        self.modos = modos if modos is not None else {}
        self.componentes: list[_Componente] = []
        self.pendentes: dict[int, dict] = {}

    def executar(self, raizes, ate: date | None = None) -> _Expansao:
        for raiz in sorted(raizes):
            self._expandir(raiz, 1.0, ate, False, frozenset())
        self._resolver_pendentes()
        return self

    def _expandir(self, raiz, fator, ate, estimado, caminho):
        if raiz in caminho:  # defesa em profundidade: o cadastro já recusa ciclo
            return
        caminho = caminho | {raiz}
        self.componentes.append(_Componente(raiz, fator, ate, estimado))
        for estado in self.por_destino.get(raiz, []):
            corte = _min_data(ate, estado.inicio_vigencia)
            if estado.tipo == 'F':
                for origem in estado.origens:
                    self._expandir(origem, fator, corte, estimado, caminho)
                continue
            modo = modo_da_divisao(estado, self.modos)
            origem = estado.origens[0]
            if modo == MODO_RECONSTRUCAO:
                base = _Expansao(self._estados(), self.modos).executar({origem}, corte)
                for comp in base.componentes:
                    self.componentes.append(_Componente(
                        comp.raiz, fator, comp.ate, estimado,
                        regra=estado.destinos[raiz]))
            elif modo == MODO_RATEIO:
                pct = float(estado.rateio[raiz]) / 100.0
                self._expandir(origem, fator * pct, corte, True, caminho)
            else:
                info = self.pendentes.setdefault(
                    estado.seq, {'estado': estado, 'alcancados': {}})
                info['alcancados'][raiz] = (fator, corte, estimado, caminho)

    def _estados(self):
        vistos, estados = set(), []
        for lista in self.por_destino.values():
            for estado in lista:
                if estado.seq not in vistos:
                    vistos.add(estado.seq)
                    estados.append(estado)
        return estados

    def _resolver_pendentes(self):
        resolvidos: set[int] = set()
        while True:
            prontos = [
                info for seq, info in self.pendentes.items()
                if seq not in resolvidos
                and set(info['alcancados']) == set(info['estado'].destinos)
                and len({(f, c) for f, c, _e, _cam in info['alcancados'].values()}) == 1
            ]
            if not prontos:
                break
            for info in prontos:
                resolvidos.add(info['estado'].seq)
                fator, corte, estimado, caminho = next(iter(info['alcancados'].values()))
                self._expandir(info['estado'].origens[0], fator, corte, estimado, caminho)
        self.nao_resolvidos = [
            {'correspondencia': seq,
             'faltam': sorted(set(info['estado'].destinos) - set(info['alcancados']))}
            for seq, info in self.pendentes.items() if seq not in resolvidos]

    @property
    def simples(self) -> bool:
        """Toda contribuição é lançamento integral (sem fator, regra,
        estimativa nem pendência) — pré-condição da reconstrução."""
        return (not self.nao_resolvidos and all(
            c.fator == 1.0 and not c.estimado and c.regra is None
            for c in self.componentes))


def _somar(componentes, inicio, fim, valores, estimados=None):
    for comp in componentes:
        for chave, valor in _mensal(comp.raiz, inicio, fim, comp.ate, comp.regra).items():
            valores[chave] = valores.get(chave, 0.0) + valor * comp.fator
            if estimados is not None and comp.estimado and valor:
                estimados.add(chave)


def modo_da_divisao(estado, modos: dict | None = None) -> str | None:
    """RECONSTRUCAO (regras que reconciliam), RATEIO ou PENDENTE.

    A reconstrução só vale se, em TODO mês anterior à vigência, a soma
    reconstruída dos destinos igualar o total da origem (± 0,01): lançamento
    manual/importado (sem staging) ou linha que casa com duas regras impede a
    reconciliação daquele mês — e aí o caso cai para o rateio ou a pendência.
    """
    if estado.tipo != 'D':
        return None
    modos = modos if modos is not None else {}
    if estado.seq in modos:
        return modos[estado.seq]
    modos[estado.seq] = MODO_PENDENTE  # guarda de reentrada
    modo = MODO_RATEIO if estado.rateio else MODO_PENDENTE
    if all(estado.destinos.values()):
        from .correspondencia_rubrica_service import correspondencias

        base = _Expansao(correspondencias(_versao_vigente()), modos).executar(
            {estado.origens[0]}, estado.inicio_vigencia)
        if base.simples:
            total: dict = {}
            _somar(base.componentes, INICIO_DOS_TEMPOS, estado.inicio_vigencia, total)
            reconstruido: dict = {}
            for regra in estado.destinos.values():
                _somar([_Componente(c.raiz, 1.0, c.ate, False, regra)
                        for c in base.componentes],
                       INICIO_DOS_TEMPOS, estado.inicio_vigencia, reconstruido)
            meses = set(total) | set(reconstruido)
            if all(abs(total.get(m, 0.0) - reconstruido.get(m, 0.0))
                   <= TOLERANCIA_RECONCILIACAO for m in meses):
                modo = MODO_RECONSTRUCAO
    modos[estado.seq] = modo
    return modo


# ------------------------------------------------------------------ API

def _versao_vigente() -> int:
    fixada = _VERSAO_FIXADA.get()
    if fixada is not None:
        return fixada
    from .correspondencia_rubrica_service import versao_atual

    return versao_atual()


@contextmanager
def versao_fixada(versao: int | None = None):
    """Fixa a versão do De/Para durante uma execução (R33). Devolve a versão."""
    if versao is None:
        from .correspondencia_rubrica_service import versao_atual

        versao = versao_atual()
    token = _VERSAO_FIXADA.set(versao)
    try:
        yield versao
    finally:
        _VERSAO_FIXADA.reset(token)


def serie_mensal(seq_qualificadores, inicio: date, fim: date,
                 versao: int | None = None) -> SerieRubricas:
    """Série de PREVISÃO de um conjunto de rubricas (soma COM SINAL por mês),
    expandida pela raiz e pelas correspondências da versão (default: a fixada
    pela execução ou a atual)."""
    from .correspondencia_rubrica_service import correspondencias

    if versao is None:
        versao = _versao_vigente()
    serie = SerieRubricas(versao=versao)
    raizes = {raiz_de(int(seq)) for seq in seq_qualificadores}
    if not raizes:
        return serie
    estados = correspondencias(versao) if versao else []
    expansao = _Expansao(estados).executar(raizes)
    _somar(expansao.componentes, inicio, fim, serie.valores, serie.estimados)
    serie.pendencias = expansao.nao_resolvidos
    return serie


def anos_com_movimento(seq_qualificadores) -> list[int]:
    """Anos com lançamento na série de previsão, mais recente primeiro."""
    serie = serie_mensal(seq_qualificadores, INICIO_DOS_TEMPOS, date(2999, 12, 31))
    return sorted({ano for ano, _mes in serie.valores}, reverse=True)


def pendencias_do_conjunto(seq_qualificadores, versao: int | None = None) -> list[dict]:
    """Desdobramentos pendentes que o conjunto toca sem conter todos os
    destinos (sem consultar lançamentos)."""
    from .correspondencia_rubrica_service import correspondencias

    if versao is None:
        versao = _versao_vigente()
    if not versao:
        return []
    raizes = {raiz_de(int(seq)) for seq in seq_qualificadores}
    return _Expansao(correspondencias(versao)).executar(raizes).nao_resolvidos


def grupo_pendente_da(seq_qualificador: int, versao: int | None = None):
    """Estado do desdobramento PENDENTE de que a rubrica é destino (direto),
    ou None."""
    from .correspondencia_rubrica_service import correspondencias

    if versao is None:
        versao = _versao_vigente()
    if not versao:
        return None
    raiz = raiz_de(seq_qualificador)
    modos: dict = {}
    for estado in correspondencias(versao):
        if raiz in estado.destinos and modo_da_divisao(estado, modos) == MODO_PENDENTE:
            return estado
    return None
