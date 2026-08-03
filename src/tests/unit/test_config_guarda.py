"""Unitários da guarda de configuração (spec infraestrutura-banco R10).

Change: hardening-configuracao-producao. A função é PURA sobre um mapa de
variáveis, então a matriz de combinações cabe aqui sem subir aplicação.
"""
import pytest

CHAVE_OK = "a" * 64


def _validar(**env):
    from fluxocaixa.config_guarda import validar_configuracao

    return validar_configuracao(env)


def test_configuracao_de_demo_legitima_passa():
    """Demo COM dados de demo é o uso legítimo — não pode ser bloqueado."""
    _validar(DEMO_MODE="true", SEED_DEMO_DATA="true")


def test_demo_sobre_dados_reais_aborta():
    from fluxocaixa.config_guarda import ConfiguracaoInseguraError

    with pytest.raises(ConfiguracaoInseguraError) as exc:
        _validar(DEMO_MODE="true", SEED_DEMO_DATA="false")
    assert "SEED_DEMO_DATA" in str(exc.value)


def test_demo_em_producao_aborta():
    from fluxocaixa.config_guarda import ConfiguracaoInseguraError

    with pytest.raises(ConfiguracaoInseguraError):
        _validar(DEMO_MODE="true", APP_ENV="prod", SECRET_KEY=CHAVE_OK)


def test_producao_sem_chave_aborta():
    from fluxocaixa.config_guarda import ConfiguracaoInseguraError

    with pytest.raises(ConfiguracaoInseguraError) as exc:
        _validar(APP_ENV="prod")
    assert "SECRET_KEY" in str(exc.value)


def test_producao_com_placeholder_do_env_example_aborta():
    """O placeholder é PÚBLICO — copiá-lo é pior que não definir a variável."""
    from fluxocaixa.config_guarda import ConfiguracaoInseguraError

    with pytest.raises(ConfiguracaoInseguraError):
        _validar(APP_ENV="prod", SECRET_KEY="your-secret-key-here")


def test_producao_com_chave_curta_aborta():
    from fluxocaixa.config_guarda import ConfiguracaoInseguraError

    with pytest.raises(ConfiguracaoInseguraError):
        _validar(APP_ENV="prod", SECRET_KEY="curta-demais")


def test_producao_com_chave_valida_passa():
    _validar(APP_ENV="prod", SECRET_KEY=CHAVE_OK)


def test_ambiente_vazio_passa():
    """Desenvolvimento sem nada definido continua subindo."""
    _validar()


def test_env_example_nao_declara_variavel_morta():
    """Configuração morta em arquivo de exemplo é ativamente enganosa: faz
    alguém "conferir se o debug está off" e receber falsa confirmação."""
    import re
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[3]
    exemplo = raiz / ".env.example"
    declaradas = {
        m.group(1)
        for linha in exemplo.read_text(encoding="utf-8").splitlines()
        if (m := re.match(r"^([A-Z_][A-Z0-9_]*)=", linha.strip()))
    }
    assert declaradas, "o exemplo de ambiente não declara nada"

    fontes = " ".join(
        p.read_text(encoding="utf-8")
        for p in (raiz / "src" / "fluxocaixa").rglob("*.py")
    )
    mortas = [v for v in declaradas if v not in fontes]
    assert not mortas, f"variáveis declaradas e nunca lidas pelo código: {mortas}"


def test_env_example_nao_traz_segredo_copiavel():
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[3]
    linhas = (raiz / ".env.example").read_text(encoding="utf-8").splitlines()
    for linha in linhas:
        if linha.strip().startswith("SECRET_KEY="):
            valor = linha.split("=", 1)[1].strip()
            assert valor == "", (
                "SECRET_KEY no exemplo deve ficar VAZIA: um valor copiável num "
                "repositório público é pior que variável ausente — o fallback "
                "dá chave aleatória, o placeholder dá chave conhecida"
            )
