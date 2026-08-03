"""Unitários da auditoria e da revogação de sessão (spec controle-acesso R13).

Change: sessao-revalidada-e-revogavel. Import de `fluxocaixa` é TARDIO.
"""
import pytest


def test_fora_de_requisicao_usa_o_fallback():
    """Seeds e scripts continuam gravando — o fallback ali é intencional."""
    from fluxocaixa.auth.contexto import cod_pessoa_atual, definir_usuario_corrente

    definir_usuario_corrente(None)
    assert cod_pessoa_atual() == 1


def test_em_requisicao_sem_usuario_falha_explicitamente():
    """Gravar com `cod_pessoa=1` produziria dado ERRADO com aparência de certo.

    A trilha de auditoria passaria a mentir sem que nada acusasse — falhar é o
    comportamento correto (R9).
    """
    from fluxocaixa.auth.contexto import (
        UsuarioCorrenteAusenteError,
        cod_pessoa_atual,
        definir_usuario_corrente,
        marcar_em_requisicao,
    )

    definir_usuario_corrente(None)
    marcar_em_requisicao()
    with pytest.raises(UsuarioCorrenteAusenteError):
        cod_pessoa_atual()


def test_em_requisicao_com_usuario_devolve_o_usuario():
    from fluxocaixa.auth.contexto import (
        cod_pessoa_atual,
        definir_usuario_corrente,
        marcar_em_requisicao,
    )

    marcar_em_requisicao()
    definir_usuario_corrente(42)
    assert cod_pessoa_atual() == 42


def test_definir_senha_incrementa_a_versao_de_credencial(app):
    """É o que revoga as outras sessões — inclusive a roubada."""
    from fluxocaixa.auth.service import definir_senha, gerar_hash
    from fluxocaixa.models.base import db
    from fluxocaixa.models.usuario import Usuario

    usuario = Usuario(
        nom_usuario="versao.teste", nom_completo="Versão",
        txt_hash_senha=gerar_hash("Senha-Inicial-1"),
        ind_troca_senha='N', ind_status='A',
    )
    db.session.add(usuario)
    db.session.commit()

    antes = usuario.num_versao_credencial
    definir_senha(usuario, "Senha-Nova-2")
    assert usuario.num_versao_credencial == antes + 1


def test_limite_de_inatividade_e_configuravel(monkeypatch):
    import importlib

    monkeypatch.setenv("SESSAO_INATIVIDADE_SEGUNDOS", "120")
    from fluxocaixa.auth import dependencies

    recarregado = importlib.reload(dependencies)
    try:
        assert recarregado.INATIVIDADE_MAX_SEGUNDOS == 120
    finally:
        monkeypatch.delenv("SESSAO_INATIVIDADE_SEGUNDOS", raising=False)
        importlib.reload(dependencies)
