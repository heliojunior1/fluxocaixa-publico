"""Fábrica de usuários de teste com perfil (compartilhada por steps BDD)."""

SENHA_PERFIL_TESTES = "Senha-Perfil-123"


def criar_usuario_com_perfil(cod_perfil: str):
    """Cria (ou recria) um usuário ativo vinculado ao perfil informado.

    Retorna (login, senha, seq_usuario).
    """
    from fluxocaixa.auth.service import gerar_hash
    from fluxocaixa.models import Perfil, Usuario, UsuarioPerfil
    from fluxocaixa.models.base import db

    login = f"teste_{cod_perfil.lower()}"

    db.session.rollback()
    existente = Usuario.query.filter_by(nom_usuario=login).first()
    if existente:
        UsuarioPerfil.query.filter_by(seq_usuario=existente.seq_usuario).delete()
        db.session.delete(existente)
        db.session.commit()

    usuario = Usuario(
        nom_usuario=login,
        nom_completo=f"Usuário de teste ({cod_perfil})",
        txt_hash_senha=gerar_hash(SENHA_PERFIL_TESTES),
        ind_troca_senha='N',
        ind_status='A',
    )
    db.session.add(usuario)
    db.session.commit()

    perfil = Perfil.query.filter_by(cod_perfil=cod_perfil).first()
    assert perfil is not None, f"Perfil {cod_perfil} não seedado"
    db.session.add(UsuarioPerfil(seq_usuario=usuario.seq_usuario, seq_perfil=perfil.seq_perfil))
    db.session.commit()

    return login, SENHA_PERFIL_TESTES, usuario.seq_usuario
