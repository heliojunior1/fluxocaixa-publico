"""Serviço de autenticação: hash bcrypt e verificação de credenciais.

Senhas nunca são persistidas nem logadas em texto claro (spec controle-acesso R5).
"""
from typing import Optional

import bcrypt

from ..models.base import db
from ..models.usuario import Usuario

TAMANHO_MINIMO_SENHA = 8


def gerar_hash(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), hash_armazenado.encode("ascii"))
    except ValueError:
        return False


def autenticar(login: str, senha: str) -> Optional[Usuario]:
    """Retorna o usuário se as credenciais forem válidas e ele estiver ativo.

    Falha sempre da mesma forma (None) — não revela se o login existe.
    """
    usuario = Usuario.query.filter_by(nom_usuario=(login or "").strip().lower()).first()
    if usuario is None or usuario.ind_status != 'A':
        return None
    if not verificar_senha(senha or "", usuario.txt_hash_senha):
        return None
    return usuario


def validar_nova_senha(nova_senha: str, hash_atual: str) -> Optional[str]:
    """Valida a nova senha; retorna mensagem de erro ou None se válida."""
    if len(nova_senha or "") < TAMANHO_MINIMO_SENHA:
        return "A nova senha deve ter ao menos 8 caracteres"
    if verificar_senha(nova_senha, hash_atual):
        return "A nova senha deve ser diferente da atual"
    return None


def definir_senha(usuario: Usuario, nova_senha: str, troca_pendente: bool = False) -> None:
    usuario.txt_hash_senha = gerar_hash(nova_senha)
    usuario.ind_troca_senha = 'S' if troca_pendente else 'N'
    db.session.commit()
