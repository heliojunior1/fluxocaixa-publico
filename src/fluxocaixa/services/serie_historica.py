"""Origem única da costura da série histórica entre exercícios (F10.2).

Com o qualificador por exercício (F10.1), "a mesma rubrica ao longo do tempo"
deixou de ser o mesmo `seq_qualificador`: é o conjunto de linhas que
compartilham a mesma `cod_rubrica_raiz` (spec previsao R17, concepção D-B).
Toda consulta de série histórica filtra `seq_qualificador IN
seqs_da_rubrica(seq)` — nunca igualdade crua; a guarda estrutural
(`src/tests/unit/test_serie_por_raiz.py`) reprova a igualdade nos serviços
de série.

⚠️ O `ind_status` do QUALIFICADOR não entra no filtro: rubrica extinta (C7)
tem o passado consultável — o filtro de ativos da spec R11 é sobre o
LANÇAMENTO, e sempre foi.
"""
from __future__ import annotations


def seqs_da_rubrica(seq_qualificador: int) -> list[int]:
    """Todos os `seq_qualificador` que compartilham a raiz do informado.

    Enquanto nenhum exercício foi aberto, raiz == seq e o retorno é `[seq]` —
    a conversão dos consumidores é comportamentalmente inerte (golden de
    previsão é o critério). Raiz nula (linha fora do backfill da 0035, não
    deveria existir) degrada para `[seq]`, nunca para lista vazia.
    """
    from ..models import Qualificador

    qualificador = Qualificador.query.get(seq_qualificador)
    if qualificador is None or qualificador.cod_rubrica_raiz is None:
        return [seq_qualificador]
    linhas = Qualificador.query.filter(
        Qualificador.cod_rubrica_raiz == qualificador.cod_rubrica_raiz
    ).all()
    return [linha.seq_qualificador for linha in linhas]


def seqs_das_rubricas(seq_qualificadores: list[int]) -> list[int]:
    """Versão para consultas agregadas (vários qualificadores de uma vez)."""
    vistos: set[int] = set()
    for seq in seq_qualificadores:
        vistos.update(seqs_da_rubrica(seq))
    return sorted(vistos)
