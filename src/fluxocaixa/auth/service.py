"""Serviço de autenticação: hash bcrypt e verificação de credenciais.

Senhas nunca são persistidas nem logadas em texto claro (spec controle-acesso R5).
"""
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt

from ..config import modo_demo
from ..models.base import db
from ..models.usuario import Usuario

logger = logging.getLogger(__name__)

TAMANHO_MINIMO_SENHA = 12
# bcrypt trunca em 72 bytes (não caracteres) — o teto é explícito para que
# senhas longas de mesmo prefixo não virem a mesma credencial em silêncio.
TAMANHO_MAXIMO_SENHA_BYTES = 72

MAX_FALHAS_LOGIN = int(os.getenv("LOGIN_MAX_FALHAS", 5))
BLOQUEIO_LOGIN_SEGUNDOS = int(os.getenv("LOGIN_BLOQUEIO_SEGUNDOS", 15 * 60))

# Hash fixo e descartável para o caminho "usuário não existe" — paga o mesmo
# custo de bcrypt e fecha a enumeração por tempo de resposta (R14).
_HASH_DESCARTAVEL = bcrypt.hashpw(b"hash-descartavel", bcrypt.gensalt()).decode("ascii")

# Lista CURTA e honesta: cobre a senha que a pessoa escolheria com pressa, em
# pt-BR e en, mais as derivadas óbvias do domínio. NÃO é proteção contra
# dicionário — essa é o bloqueio (R14). Registrar a diferença evita que a lista
# cresça achando que resolve o outro problema.
SENHAS_COMUNS = frozenset({
    "123456", "1234567", "12345678", "123456789", "1234567890",
    "senha", "senha123", "senha1234", "minhasenha", "password",
    "password1", "password123", "passw0rd", "qwerty", "qwerty123",
    "abc123", "abcd1234", "111111", "000000", "iloveyou",
    "admin", "admin123", "administrador", "root", "root123",
    "usuario", "usuario123", "teste", "teste123", "mudar123",
    "trocar123", "primeiroacesso", "acesso123", "brasil123",
    "fluxocaixa", "fluxodecaixa", "fluxocaixa123", "tesouraria",
    "tesouraria123", "financeiro", "financeiro123", "contabilidade",
})


def _agora(agora=None):
    return agora or datetime.now()


def _esta_bloqueado(usuario: Usuario, agora=None) -> bool:
    # ⚠️ Em MODO DEMO não há bloqueio. A demo é aberta e TODOS os visitantes
    # compartilham a MESMA conta: cinco erros de digitação de um visitante
    # qualquer — ou de alguém agindo de propósito — trancariam a instância
    # inteira por 15 minutos. O bloqueio protege uma conta de um atacante; aqui
    # ele viraria o próprio ataque.
    if modo_demo():
        return False
    if not usuario.dat_bloqueio_login:
        return False
    fim = usuario.dat_bloqueio_login + timedelta(seconds=BLOQUEIO_LOGIN_SEGUNDOS)
    if _agora(agora) < fim:
        return True
    # Bloqueio expirado: limpa para o usuário legítimo voltar ao normal.
    usuario.dat_bloqueio_login = None
    usuario.qtd_falhas_login = 0
    db.session.commit()
    return False


def _registrar_falha(usuario: Usuario, agora=None) -> None:
    if modo_demo():
        return
    usuario.qtd_falhas_login = (usuario.qtd_falhas_login or 0) + 1
    if usuario.qtd_falhas_login >= MAX_FALHAS_LOGIN:
        usuario.dat_bloqueio_login = _agora(agora)
        logger.warning(
            "Login bloqueado por %s falhas consecutivas: %s",
            usuario.qtd_falhas_login, usuario.nom_usuario,
        )
    db.session.commit()


def _zerar_falhas(usuario: Usuario) -> None:
    if usuario.qtd_falhas_login or usuario.dat_bloqueio_login:
        usuario.qtd_falhas_login = 0
        usuario.dat_bloqueio_login = None
        db.session.commit()



def gerar_hash(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), hash_armazenado.encode("ascii"))
    except ValueError:
        return False


def autenticar(login: str, senha: str, agora=None) -> Optional[Usuario]:
    """Retorna o usuário se as credenciais forem válidas e ele estiver ativo.

    Falha sempre da mesma forma (None) — não revela se o login existe.
    """
    usuario = Usuario.query.filter_by(nom_usuario=(login or "").strip().lower()).first()
    if usuario is None or usuario.ind_status != 'A':
        # Tempo constante (R14): retornar aqui sem executar bcrypt tornava a
        # resposta mediçãovelmente mais rápida para login inexistente — e a
        # enumeração ficava disponível mesmo com a mensagem idêntica. bcrypt
        # custa ~100 ms de propósito; é justamente isso que vaza.
        verificar_senha(senha or "", _HASH_DESCARTAVEL)
        return None

    if _esta_bloqueado(usuario, agora=agora):
        # Durante o bloqueio a senha CORRETA também é recusada. É o que torna o
        # bloqueio útil: se ela passasse, ele só atrasaria o ataque pelo tempo
        # de contar até o limite.
        verificar_senha(senha or "", _HASH_DESCARTAVEL)
        return None

    if not verificar_senha(senha or "", usuario.txt_hash_senha):
        _registrar_falha(usuario, agora=agora)
        return None

    _zerar_falhas(usuario)
    return usuario


def validar_nova_senha(
    nova_senha: str, hash_atual: str, login: str | None = None
) -> Optional[str]:
    """Valida a nova senha; retorna mensagem de erro ou None se válida (R5)."""
    nova_senha = nova_senha or ""
    if len(nova_senha) < TAMANHO_MINIMO_SENHA:
        return f"A nova senha deve ter ao menos {TAMANHO_MINIMO_SENHA} caracteres"
    # bcrypt TRUNCA silenciosamente em 72 bytes: sem o teto, duas senhas longas
    # de mesmo prefixo passam a ser a mesma credencial, sem nada avisar.
    if len(nova_senha.encode("utf-8")) > TAMANHO_MAXIMO_SENHA_BYTES:
        return (
            f"A nova senha deve ter no máximo {TAMANHO_MAXIMO_SENHA_BYTES} bytes "
            "(o algoritmo de hash ignora o excedente)"
        )
    if nova_senha.strip().lower() in SENHAS_COMUNS:
        return "A nova senha é fácil de adivinhar; escolha outra"
    if login and login.strip().lower() in nova_senha.lower():
        return "A nova senha não pode conter o nome de usuário"
    if verificar_senha(nova_senha, hash_atual):
        return "A nova senha deve ser diferente da atual"
    return None


def definir_senha(usuario: Usuario, nova_senha: str, troca_pendente: bool = False) -> None:
    usuario.txt_hash_senha = gerar_hash(nova_senha)
    usuario.ind_troca_senha = 'S' if troca_pendente else 'N'
    # Revoga as sessões abertas (R13): trocar a senha é o gesto padrão de
    # resposta a comprometimento, e sem isso o cookie roubado seguiria válido
    # até expirar.
    usuario.num_versao_credencial = (usuario.num_versao_credencial or 1) + 1
    db.session.commit()
