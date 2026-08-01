"""Cadastro do dicionário de termos de regra (spec automacao-lancamentos R5).

Cada órgão define seus termos: é comum esse dicionário viver hardcoded no
código do ETL; aqui é cadastro.
"""
from datetime import date

from ..auth.contexto import cod_pessoa_atual
from ..models import TermoRegra
from ..models.base import db
from ..models.termo_regra import (
    COLUNAS_PERMITIDAS,
    ORIGEM_COLUNA,
    ORIGENS_VALIDAS,
    TIPOS_VALIDOS,
)
from .validacao import RegraNegocioError


def _validar(nom_termo, cod_origem_campo, nom_campo, cod_tipo, seq_atual=None):
    if not (nom_termo or '').strip():
        raise RegraNegocioError("O nome do termo é obrigatório")
    if not (nom_campo or '').strip():
        raise RegraNegocioError("O campo do termo é obrigatório")
    if cod_origem_campo not in ORIGENS_VALIDAS:
        raise RegraNegocioError(
            f"Origem de campo inválida: '{cod_origem_campo}' "
            f"(use {' ou '.join(ORIGENS_VALIDAS)})"
        )
    if cod_tipo not in TIPOS_VALIDOS:
        raise RegraNegocioError(
            f"Tipo inválido: '{cod_tipo}' (use {', '.join(TIPOS_VALIDOS)})"
        )

    if cod_origem_campo == ORIGEM_COLUNA:
        # Whitelist: regra de negócio não alcança coluna de controle da staging
        if nom_campo not in COLUNAS_PERMITIDAS:
            raise RegraNegocioError(
                f"O campo '{nom_campo}' não é permitido para termo de coluna "
                f"(disponíveis: {', '.join(sorted(COLUNAS_PERMITIDAS))})"
            )
        esperado = COLUNAS_PERMITIDAS[nom_campo]
        if cod_tipo != esperado:
            raise RegraNegocioError(
                f"O campo '{nom_campo}' é do tipo {esperado}, não {cod_tipo}"
            )

    # unicidade do nome entre ATIVOS
    consulta = TermoRegra.query.filter_by(nom_termo=nom_termo, ind_status='A')
    if seq_atual is not None:
        consulta = consulta.filter(TermoRegra.seq_termo_regra != seq_atual)
    if consulta.first() is not None:
        raise RegraNegocioError(f"Já existe um termo ativo com o nome '{nom_termo}'")


def criar_termo(nom_termo, cod_origem_campo, nom_campo, cod_tipo) -> TermoRegra:
    _validar(nom_termo, cod_origem_campo, nom_campo, cod_tipo)
    termo = TermoRegra(
        nom_termo=nom_termo.strip(),
        cod_origem_campo=cod_origem_campo,
        nom_campo=nom_campo.strip(),
        cod_tipo=cod_tipo,
        ind_status='A',
        cod_pessoa_inclusao=cod_pessoa_atual(),
    )
    db.session.add(termo)
    db.session.commit()
    return termo


def alterar_termo(seq_termo_regra, nom_termo, cod_origem_campo, nom_campo, cod_tipo):
    termo = TermoRegra.query.get(seq_termo_regra)
    if termo is None or termo.ind_status != 'A':
        raise RegraNegocioError("Termo inexistente ou inativo")
    _validar(nom_termo, cod_origem_campo, nom_campo, cod_tipo, seq_atual=seq_termo_regra)
    termo.nom_termo = nom_termo.strip()
    termo.cod_origem_campo = cod_origem_campo
    termo.nom_campo = nom_campo.strip()
    termo.cod_tipo = cod_tipo
    termo.dat_alteracao = date.today()
    termo.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return termo


def inativar_termo(seq_termo_regra) -> None:
    termo = TermoRegra.query.get(seq_termo_regra)
    if termo is None or termo.ind_status != 'A':
        raise RegraNegocioError("Termo inexistente ou inativo")
    termo.ind_status = 'I'
    termo.dat_alteracao = date.today()
    termo.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()


def listar_termos(apenas_ativos: bool = True) -> list[TermoRegra]:
    consulta = TermoRegra.query
    if apenas_ativos:
        consulta = consulta.filter_by(ind_status='A')
    return consulta.order_by(TermoRegra.nom_termo).all()


__all__ = ['criar_termo', 'alterar_termo', 'inativar_termo', 'listar_termos']
