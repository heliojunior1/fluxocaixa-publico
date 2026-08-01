"""Guarda estrutural da costura `valor_com_sinal` (spec cadastros-nucleo R6).

Derruba a suíte se um módulo de agregação ler `val_lancamento` cru — é o único
mecanismo capaz de pegar isso na F6.1a, onde a costura é a identidade e um site
esquecido não muda número nenhum (só quebraria na F6.1b).
"""
from .. import costura


def test_agregacoes_passam_pela_costura():
    violacoes = costura.violacoes()
    assert not violacoes, (
        "leitura crua de val_lancamento em módulo de agregação — use "
        "Lancamento.valor_com_sinal (ou libere explicitamente em "
        "src/tests/costura.py::LIBERADOS, com motivo):\n  "
        + "\n  ".join(violacoes)
    )


def test_allow_list_esta_toda_em_uso():
    """Entrada morta na allow-list é armadilha: some do código e ninguém nota."""
    linhas = costura._linhas_relevantes()
    for arquivo, trecho, motivo in costura.LIBERADOS:
        assert any(nome == arquivo and trecho in linha for nome, _n, linha in linhas), (
            f"entrada da allow-list não corresponde a nenhuma linha real: "
            f"{arquivo} / {trecho!r} ({motivo})"
        )
