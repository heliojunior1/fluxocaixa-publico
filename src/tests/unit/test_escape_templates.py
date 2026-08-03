"""Guarda anti-regressão do escape de HTML dinâmico (spec relatorios R21).

Change: escapar-html-dinamico-relatorios.

No espírito de `test_completude_permissoes.py` (rota sem `requer(...)` derruba a
suíte) e de `test_costura_valor_com_sinal.py` (leitura crua da coluna de valor
fora da allow-list derruba a suíte).

Por que a guarda é a parte que não pode faltar: o defeito não estava num
template, estava em SETE. Isso não é sete descuidos — é a ausência de um
mecanismo que torne o descuido visível.
"""
import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[3] / "templates"

# Campos que carregam texto de CADASTRO (livre, digitado pelo usuário).
# Casar por nome conhecido, e não por qualquer interpolação: escapar número
# formatado ou classe CSS seria ruído, e guarda ruidosa é guarda que alguém
# desliga.
CAMPOS_DE_TEXTO = (
    "dsc_",
    "descricao",
    "nome",
    "name",
    "label",
    "mensagem",
)

# `${...}` cujo conteúdo cita um campo de texto e NÃO passa por escHtml.
_INTERPOLACAO = re.compile(r"\$\{([^}]*)\}")


def _linhas_de_risco(texto: str) -> list[tuple[int, str]]:
    """Interpolações de texto de cadastro dentro de trecho que vira HTML."""
    achados = []
    em_html = False
    for numero, linha in enumerate(texto.splitlines(), start=1):
        # Heurística de contexto: a atribuição a innerHTML (ou o acúmulo de uma
        # string que será atribuída) abre um bloco de construção de HTML.
        if re.search(r"(innerHTML\s*=|innerHTML\s*\+=|\w*[Hh]tml\s*\+?=)", linha):
            em_html = True
        if em_html and ("`;" in linha or linha.strip() == "`" or "';" in linha):
            achados.extend(_conferir(numero, linha))
            em_html = False
            continue
        if em_html:
            achados.extend(_conferir(numero, linha))
    return achados


def _conferir(numero: int, linha: str) -> list[tuple[int, str]]:
    fora = []
    for expressao in _INTERPOLACAO.findall(linha):
        if "escHtml" in expressao:
            continue
        alvo = expressao.lower()
        if any(campo in alvo for campo in CAMPOS_DE_TEXTO):
            fora.append((numero, expressao.strip()))
    return fora


def test_guarda_enxerga_os_templates():
    """Guarda que varre zero arquivo passa sempre — e é pior que guarda nenhuma.

    Sem esta verificação, mover a pasta de templates ou errar o `parents[n]`
    deixaria o teste verde para sempre, exatamente enquanto deixa de proteger.
    """
    arquivos = list(TEMPLATES.glob("*.html"))
    assert len(arquivos) > 20, (
        f"a guarda encontrou só {len(arquivos)} template(s) em {TEMPLATES} — "
        "o caminho está errado e a verificação está vazia")


def test_texto_de_cadastro_nao_entra_cru_em_innerhtml():
    ofensas = {}
    for arquivo in sorted(TEMPLATES.glob("*.html")):
        achados = _linhas_de_risco(arquivo.read_text(encoding="utf-8"))
        if achados:
            ofensas[arquivo.name] = achados

    assert not ofensas, (
        "Texto de cadastro interpolado em HTML sem `escHtml` "
        "(spec relatorios R21):\n"
        + "\n".join(
            f"  {nome}:{linha} → ${{{expr}}}"
            for nome, achados in ofensas.items()
            for linha, expr in achados
        )
        + "\n\nUse `escHtml(...)` (static/js/seguranca.js) na interpolação."
    )
