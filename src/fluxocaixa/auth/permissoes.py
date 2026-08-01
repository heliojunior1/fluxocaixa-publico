"""Autorização por permissão verbo+recurso (spec controle-acesso R8).

Uso por rota (anotação explícita, auditável por grep):

    @router.get('/saldos', dependencies=[requer('FC_CONS_LANCAMENTO')])

O teste de completude (test_completude_permissoes.py) falha para qualquer
rota de negócio sem essa anotação.
"""
from fastapi import Depends, Request

from .dependencies import exigir_login


class PermissaoNegadaError(Exception):
    def __init__(self, cod_permissao: str):
        self.cod_permissao = cod_permissao


def permissoes_do_request(request: Request) -> set:
    """Permissões do usuário logado, memoizadas por request."""
    cache = getattr(request.state, "permissoes", None)
    if cache is not None:
        return cache

    seq_usuario = request.session.get("seq_usuario")
    permissoes = _consultar_permissoes(seq_usuario) if seq_usuario else set()
    request.state.permissoes = permissoes
    return permissoes


def _consultar_permissoes(seq_usuario: int) -> set:
    from ..models import Perfil, PerfilPermissao, Permissao, UsuarioPerfil
    from ..models.base import db

    linhas = (
        db.session.query(Permissao.cod_permissao)
        .join(PerfilPermissao, PerfilPermissao.seq_permissao == Permissao.seq_permissao)
        .join(Perfil, Perfil.seq_perfil == PerfilPermissao.seq_perfil)
        .join(UsuarioPerfil, UsuarioPerfil.seq_perfil == Perfil.seq_perfil)
        .filter(
            UsuarioPerfil.seq_usuario == seq_usuario,
            Permissao.ind_status == 'A',
            Perfil.ind_status == 'A',
        )
        .all()
    )
    return {cod for (cod,) in linhas}


def requer(cod_permissao: str):
    """Dependency de rota: exige login (F1.2) + a permissão informada."""

    async def verificar(request: Request, seq_usuario: int = Depends(exigir_login)):
        if cod_permissao not in permissoes_do_request(request):
            raise PermissaoNegadaError(cod_permissao)

    # Marcador lido pelo teste de completude (R8)
    verificar.__requer_permissao__ = cod_permissao
    return Depends(verificar)
