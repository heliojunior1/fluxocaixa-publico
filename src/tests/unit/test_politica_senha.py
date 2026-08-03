"""Unitários da política de senha (spec controle-acesso R5).

Change: endurecer-credenciais-e-antibruteforce. Import de `fluxocaixa` TARDIO.
"""
import pytest


@pytest.fixture()
def hash_atual():
    from fluxocaixa.auth.service import gerar_hash

    return gerar_hash("Senha-Atual-Valida-1")


@pytest.mark.parametrize("senha", ["", "curta1", "onzecaract"])
def test_senha_curta_e_recusada(senha, hash_atual):
    from fluxocaixa.auth.service import validar_nova_senha

    assert "ao menos" in (validar_nova_senha(senha, hash_atual) or "")


def test_senha_no_limite_minimo_passa(hash_atual):
    from fluxocaixa.auth.service import validar_nova_senha

    assert validar_nova_senha("Doze-Caract1", hash_atual) is None


def test_senha_acima_de_72_bytes_e_recusada(hash_atual):
    """bcrypt TRUNCA em 72 bytes: sem o teto, duas senhas longas de mesmo
    prefixo viram a MESMA credencial, sem nada avisar."""
    from fluxocaixa.auth.service import validar_nova_senha

    assert "72" in (validar_nova_senha("A" * 73, hash_atual) or "")


def test_limite_e_em_bytes_nao_em_caracteres(hash_atual):
    """Acentuada tem 2 bytes por caractere em UTF-8 — 40 caracteres, 80 bytes."""
    from fluxocaixa.auth.service import validar_nova_senha

    assert "72" in (validar_nova_senha("ã" * 40, hash_atual) or "")


# Só senhas comuns COM 12+ caracteres: abaixo disso a checagem de comprimento
# dispara antes e o teste não provaria a lista.
@pytest.mark.parametrize("senha", [
    "fluxodecaixa", "fluxocaixa123", "tesouraria123",
    "administrador", "primeiroacesso", "financeiro123",
])
def test_senha_comum_e_recusada(senha, hash_atual):
    from fluxocaixa.auth.service import SENHAS_COMUNS, validar_nova_senha

    assert senha in SENHAS_COMUNS, "massa do teste fora da lista"
    assert "adivinhar" in (validar_nova_senha(senha, hash_atual) or "")


def test_senha_que_contem_o_login_e_recusada(hash_atual):
    from fluxocaixa.auth.service import validar_nova_senha

    mensagem = validar_nova_senha("maria.silva-2026", hash_atual, login="maria.silva")
    assert "nome de usuário" in (mensagem or "")


def test_senha_igual_a_atual_e_recusada(hash_atual):
    from fluxocaixa.auth.service import validar_nova_senha

    assert "diferente" in (validar_nova_senha("Senha-Atual-Valida-1", hash_atual) or "")


def test_senha_valida_passa(hash_atual):
    from fluxocaixa.auth.service import validar_nova_senha

    assert validar_nova_senha("Senha-Nova-Robusta-9", hash_atual, login="maria") is None
