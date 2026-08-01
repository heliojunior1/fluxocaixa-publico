"""Varredura estrutural da costura `valor_com_sinal` (F6.1a, R6).

A golden de caracterização NÃO consegue vigiar isto na F6.1a: enquanto a
costura é a identidade, esquecer um site de agregação não muda nenhum número —
só quebraria depois, na F6.1b, que é exatamente onde não queremos surpresa.
Daí a varredura, no mesmo espírito do `test_completude_permissoes.py`.

Regra: em módulo de agregação (`repositories/`, `services/relatorio/`),
`val_lancamento` só pode aparecer nos usos explicitamente liberados abaixo —
gravação e exibição de UMA linha. Qualquer outro uso é agregação e deve passar
por `Lancamento.valor_com_sinal`.
"""
from __future__ import annotations

from pathlib import Path

TERMO = "val_lancamento"

# Diretórios varridos (onde vive agregação de lançamento)
def _raiz() -> Path:
    return Path(__file__).resolve().parent.parent / "fluxocaixa"


DIRETORIOS = ("repositories", "services/relatorio")

# Módulos de agregação fora desses diretórios. ⚠️ Estes entraram só depois: a
# F6.1b passou com 4 leituras de INSTÂNCIA (`lanc.val_lancamento`) intactas aqui
# — a substituição em lote casava `Lancamento.val_lancamento`, o atributo da
# classe — e a varredura não olhava para cá, apesar de o CLAUDE.md afirmar que
# olhava. Resultado: a série histórica de despesa inverteu de sinal em silêncio.
ARQUIVOS = (
    "services/formula_engine.py",
    "services/modelos_economicos_service.py",
    "services/backtest_service.py",
    "services/projecao_versao_service.py",
    "services/previsao_service.py",
    "services/simulador_cenario_service.py",
)

# ---------------------------------------------------------------------------
# Allow-list: (arquivo, trecho que deve aparecer na linha, motivo)
# Cada entrada é uma decisão consciente de "isto NÃO neta".
# ---------------------------------------------------------------------------
LIBERADOS: tuple[tuple[str, str, str], ...] = (
    # --- gravação: o valor cru é o que se persiste -------------------------
    ("lancamento_repository.py", "val_lancamento=data.val_lancamento",
     "gravação: create() persiste o valor recebido"),
    ("lancamento_repository.py", "lanc.val_lancamento = data.val_lancamento",
     "gravação: update() persiste o valor recebido"),

    # --- ordenação da listagem por nome de coluna --------------------------
    ("lancamento_repository.py", "'val_lancamento'",
     "listagem: nome de coluna aceito em sort_by (não é agregação)"),

    # --- exibição de UMA linha (extrato / drill-down) ----------------------
    ("dfc_service.py", 'float(r.val_lancamento)',
     "extrato: valor de um lançamento individual no drill-down"),
)


def _alvos() -> list:
    arquivos = []
    for diretorio in DIRETORIOS:
        arquivos += sorted((_raiz() / diretorio).rglob("*.py"))
    arquivos += [_raiz() / nome for nome in ARQUIVOS]
    return arquivos


def _linhas_relevantes() -> list[tuple[str, int, str]]:
    achados: list[tuple[str, int, str]] = []
    for arquivo in _alvos():
        for numero, linha in enumerate(
            arquivo.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if TERMO not in linha:
                continue
            despido = linha.strip()
            if despido.startswith("#"):
                continue  # comentário não é código
            achados.append((arquivo.name, numero, despido))
    return achados


def violacoes() -> list[str]:
    """Linhas que leem `val_lancamento` cru fora da allow-list."""
    saida: list[str] = []
    for nome, numero, linha in _linhas_relevantes():
        liberada = any(
            nome == arquivo and trecho in linha
            for arquivo, trecho, _motivo in LIBERADOS
        )
        if not liberada:
            saida.append(f"{nome}:{numero}  {linha}")
    return saida
