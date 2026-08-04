"""Guarda estrutural do ferramental (infraestrutura-banco R11).

No espírito de `test_costura_valor_com_sinal` e `test_completude_permissoes`:
a suíte falha se a base de código acusar violação de lint (um `NameError`
latente não pode sobreviver a uma suíte verde — já aconteceu, ver F6.5 no
CLAUDE.md), se dependência de teste voltar ao build de produção ou se o
`pyproject.toml` voltar a declarar uma segunda lista de dependências.

Import tardio não se aplica: nada aqui importa `fluxocaixa`.
"""
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]

# Dependências que jamais podem entrar no build de produção
# (render.yaml instala requirements.txt).
DEPENDENCIAS_DE_TESTE = ("pytest", "pytest-bdd", "ruff", "pip-audit")


def _linhas_de_requisitos(caminho: Path) -> list[str]:
    linhas = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith(("#", "-r")):
            linhas.append(linha)
    return linhas


def _nome_do_pacote(linha: str) -> str:
    for separador in (">=", "==", "<=", "<", ">", "~=", "["):
        linha = linha.split(separador)[0]
    return linha.strip().lower().replace("_", "-")


def test_ruff_limpo():
    """`ruff check` limpo sobre a base — a régua vive no pyproject.toml."""
    pytest.importorskip("ruff", reason="ruff não instalado (requirements-dev)")
    resultado = subprocess.run(
        [sys.executable, "-m", "ruff", "check",
         str(RAIZ / "src" / "fluxocaixa"), str(RAIZ / "src" / "tests")],
        capture_output=True, text=True, cwd=RAIZ,
    )
    assert resultado.returncode == 0, (
        "ruff acusou violações:\n" + resultado.stdout + resultado.stderr)


def test_requirements_sem_dependencia_de_teste():
    pacotes = {_nome_do_pacote(l) for l in
               _linhas_de_requisitos(RAIZ / "requirements.txt")}
    intrusos = pacotes.intersection(DEPENDENCIAS_DE_TESTE)
    assert not intrusos, (
        f"dependência de teste no build de produção: {sorted(intrusos)} — "
        "mover para requirements-dev.txt")


def test_requirements_dev_traz_as_de_teste():
    dev = RAIZ / "requirements-dev.txt"
    assert dev.exists(), "requirements-dev.txt ausente"
    conteudo = dev.read_text(encoding="utf-8")
    assert "-r requirements.txt" in conteudo, (
        "requirements-dev.txt deve incluir -r requirements.txt (um comando "
        "instala o ambiente completo)")
    pacotes = {_nome_do_pacote(l) for l in _linhas_de_requisitos(dev)}
    faltando = {"pytest", "pytest-bdd", "ruff"} - pacotes
    assert not faltando, f"faltam em requirements-dev.txt: {sorted(faltando)}"


def test_pyproject_sem_segunda_lista_de_dependencias():
    """A fonte canônica é requirements.txt — lista parcial no pyproject
    produz `pip install .` quebrado com aparência de sucesso."""
    conteudo = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10
        dentro_do_project = False
        for linha in conteudo.splitlines():
            linha_limpa = linha.strip()
            if linha_limpa.startswith("["):
                dentro_do_project = linha_limpa == "[project]"
            elif dentro_do_project and linha_limpa.startswith("dependencies"):
                pytest.fail("pyproject.toml declara [project].dependencies — "
                            "a fonte única é requirements.txt")
        return
    dados = tomllib.loads(conteudo)
    assert "dependencies" not in dados.get("project", {}), (
        "pyproject.toml declara [project].dependencies — a fonte única é "
        "requirements.txt")
