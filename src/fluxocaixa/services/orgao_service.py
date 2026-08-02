"""CRUD de órgãos (spec desembolso R5).

Órgão é dimensão SOMENTE do desembolso (seção 5.1 do módulo): qualifica
liberações e pagamentos, nunca lançamento/projeção. PK = código orçamentário.
"""
from datetime import date

from ..auth.contexto import cod_pessoa_atual
from ..models import Liberacao, Orgao
from ..models.base import db
from .validacao import RegraNegocioError


def _get_ou_erro(cod_orgao: int) -> Orgao:
    orgao = Orgao.query.get(cod_orgao)
    if orgao is None:
        raise RegraNegocioError("Órgão inexistente")
    return orgao


def criar_orgao(cod_orgao: int, nom_orgao: str) -> Orgao:
    nom = (nom_orgao or "").strip()
    if not nom:
        raise RegraNegocioError("Nome do órgão é obrigatório")
    if Orgao.query.get(cod_orgao) is not None:
        raise RegraNegocioError("Já existe um órgão com este código")
    orgao = Orgao(cod_orgao=cod_orgao, nom_orgao=nom[:100], ind_status='A',
                  cod_pessoa_inclusao=cod_pessoa_atual())
    db.session.add(orgao)
    db.session.commit()
    return orgao


def alterar_orgao(cod_orgao: int, nom_orgao: str) -> Orgao:
    orgao = _get_ou_erro(cod_orgao)
    nom = (nom_orgao or "").strip()
    if not nom:
        raise RegraNegocioError("Nome do órgão é obrigatório")
    orgao.nom_orgao = nom[:100]
    orgao.dat_alteracao = date.today()
    orgao.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return orgao


def inativar_orgao(cod_orgao: int) -> Orgao:
    """Inativação bloqueada por liberação ativa apontando para o órgão."""
    orgao = _get_ou_erro(cod_orgao)
    tem_liberacao = Liberacao.query.filter_by(
        cod_orgao=cod_orgao, ind_status='A').first()
    if tem_liberacao is not None:
        raise RegraNegocioError(
            "Órgão possui liberações ativas e não pode ser inativado")
    orgao.ind_status = 'I'
    orgao.dat_alteracao = date.today()
    orgao.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return orgao


def listar_orgaos(status: str | None = None) -> list[Orgao]:
    q = Orgao.query
    if status in ('ativo', 'inativo'):
        q = q.filter(Orgao.ind_status == ('A' if status == 'ativo' else 'I'))
    return q.order_by(Orgao.cod_orgao).all()
