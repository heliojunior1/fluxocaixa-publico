"""Unitários + guarda estrutural — série por raiz (previsao R17, F10.2).

A guarda varre os serviços de série e reprova a igualdade crua de
`seq_qualificador` — a costura por raiz tem origem única
(`services/serie_historica.py`) e voltar à igualdade truncaria a série entre
exercícios EM SILÊNCIO (o dano do documento de concepção: 1 ponto em vez de 3,
números plausíveis e errados).
"""
import re
from pathlib import Path

import pytest

RAIZ_SRC = Path(__file__).resolve().parents[2] / "fluxocaixa" / "services"

# Serviços de SÉRIE: têm de consultar via seqs_da_rubrica/seqs_das_rubricas.
ARQUIVOS_DE_SERIE = [
    "formula_engine.py",
    "modelos_economicos_service.py",
    "backtest_service.py",
]

# As duas formas da lição F6.1b: o predicado de classe e o filter_by.
PADRAO_IGUALDADE = re.compile(
    r"Lancamento\.seq_qualificador\s*==|filter_by\(\s*seq_qualificador\s*="
)


def test_guarda_igualdade_crua_nos_servicos_de_serie():
    violacoes = []
    for nome in ARQUIVOS_DE_SERIE:
        texto = (RAIZ_SRC / nome).read_text(encoding="utf-8")
        for n, linha in enumerate(texto.splitlines(), start=1):
            if PADRAO_IGUALDADE.search(linha):
                violacoes.append(f"{nome}:{n}: {linha.strip()}")
    assert not violacoes, (
        "Consulta de série por igualdade crua de seq_qualificador — use "
        "serie_historica.seqs_da_rubrica:\n" + "\n".join(violacoes)
    )


RAMO = "8.3"
ANO_A, ANO_B = 2075, 2076


@pytest.fixture(autouse=True)
def _ilha(client):
    _limpar()
    yield
    _limpar()


def _limpar():
    from fluxocaixa.models import Qualificador
    from fluxocaixa.models.base import db

    db.session.rollback()
    for q in Qualificador.query.filter(
            Qualificador.num_qualificador.like(f"{RAMO}%")).all():
        db.session.delete(q)
    db.session.commit()


def _criar(num, dsc, ano, raiz=None):
    from fluxocaixa.services import qualificador_service

    return qualificador_service.create_qualificador(
        num, dsc, num_ano_exercicio=ano, cod_rubrica_raiz=raiz)


def test_rubrica_solitaria_devolve_o_proprio_seq():
    from fluxocaixa.services.serie_historica import seqs_da_rubrica

    q = _criar(RAMO, "Rubrica Solitaria", ANO_A)
    assert seqs_da_rubrica(q.seq_qualificador) == [q.seq_qualificador]


def test_raiz_compartilhada_devolve_todos_os_seqs():
    from fluxocaixa.services.serie_historica import (
        seqs_da_rubrica,
        seqs_das_rubricas,
    )

    a = _criar(RAMO, "Rubrica Ano A", ANO_A)
    b = _criar(RAMO, "Rubrica Ano B", ANO_B, raiz=a.cod_rubrica_raiz)
    esperado = sorted([a.seq_qualificador, b.seq_qualificador])
    assert sorted(seqs_da_rubrica(b.seq_qualificador)) == esperado
    assert sorted(seqs_da_rubrica(a.seq_qualificador)) == esperado
    assert seqs_das_rubricas([a.seq_qualificador, b.seq_qualificador]) == esperado


def test_raiz_nula_degrada_para_o_proprio_seq():
    from fluxocaixa.models import Qualificador
    from fluxocaixa.models.base import db
    from fluxocaixa.services.serie_historica import seqs_da_rubrica

    q = _criar(RAMO, "Rubrica Sem Raiz", ANO_A)
    db.session.execute(
        Qualificador.__table__.update()
        .where(Qualificador.__table__.c.seq_qualificador == q.seq_qualificador)
        .values(cod_rubrica_raiz=None)
    )
    db.session.commit()
    db.session.expire_all()
    assert seqs_da_rubrica(q.seq_qualificador) == [q.seq_qualificador]


def test_seq_inexistente_degrada_para_o_proprio_seq():
    from fluxocaixa.services.serie_historica import seqs_da_rubrica

    assert seqs_da_rubrica(99999999) == [99999999]
