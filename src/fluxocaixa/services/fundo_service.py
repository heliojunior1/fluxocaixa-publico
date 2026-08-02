"""Ciclo de vida do fundo (spec saldo-por-fundo R7–R12).

Cadastro manual, alteração de descrição, aprovação de auto-cadastrados,
inativação lógica com bloqueio por saldo ativo, listagem filtrada e o
upsert interno consumido pelas importações (F2.3).
"""
from datetime import date

from ..auth.contexto import cod_pessoa_atual
from ..models import Fundo, SaldoContaFundo
from ..models.base import db
from .origem_saldo import resolver_sistema, resolver_tipo
from .validacao import RegraNegocioError

COD_MIN, COD_MAX = 4, 10
DSC_MAX = 120


def _validar_codigo(cod: str) -> str:
    cod = (cod or "").strip()
    if not (COD_MIN <= len(cod) <= COD_MAX):
        raise RegraNegocioError("Código do fundo deve ter entre 4 e 10 caracteres")
    return cod


def _validar_descricao(dsc: str) -> str:
    dsc = (dsc or "").strip()
    if not dsc:
        raise RegraNegocioError("Descrição do fundo é obrigatória")
    if len(dsc) > DSC_MAX:
        raise RegraNegocioError("Descrição do fundo deve ter até 120 caracteres")
    return dsc


def _get_ou_erro(seq_fundo: int) -> Fundo:
    fundo = Fundo.query.get(seq_fundo)
    if fundo is None:
        raise RegraNegocioError("Fundo inexistente")
    return fundo


def criar_fundo(cod_fundo: str, dsc_fundo: str) -> Fundo:
    """Cadastro manual: tipo MANUAL, sem sistema, aprovado (R8)."""
    cod_fundo = _validar_codigo(cod_fundo)
    dsc_fundo = _validar_descricao(dsc_fundo)
    if Fundo.query.filter_by(cod_fundo=cod_fundo).first() is not None:
        raise RegraNegocioError("Já existe um fundo com este código")

    tipo = resolver_tipo('MANUAL')
    resolver_sistema('MANUAL', None)  # coerência (nenhum sistema)
    fundo = Fundo(
        cod_fundo=cod_fundo,
        dsc_fundo=dsc_fundo,
        seq_tipo_origem=tipo.seq_tipo_origem_saldo,
        seq_sistema_origem=None,
        ind_pendente_revisao='N',
        ind_status='A',
        cod_pessoa_inclusao=cod_pessoa_atual(),
    )
    db.session.add(fundo)
    db.session.commit()
    return fundo


def alterar_fundo(seq_fundo: int, dsc_fundo: str, novo_cod: str | None = None) -> Fundo:
    """Altera apenas a descrição; código e origem são imutáveis (R9)."""
    fundo = _get_ou_erro(seq_fundo)
    if novo_cod is not None and novo_cod.strip() != fundo.cod_fundo:
        raise RegraNegocioError("O código do fundo não pode ser alterado")
    fundo.dsc_fundo = _validar_descricao(dsc_fundo)
    fundo.dat_alteracao = date.today()
    fundo.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return fundo


def aprovar_fundo(seq_fundo: int, dsc: str | None = None) -> Fundo:
    """Zera a pendência preservando origem/data; dsc opcional (R10)."""
    fundo = _get_ou_erro(seq_fundo)
    if fundo.ind_pendente_revisao != 'S':
        raise RegraNegocioError("Fundo não está pendente de revisão")
    if dsc is not None and dsc.strip():
        fundo.dsc_fundo = _validar_descricao(dsc)
    fundo.ind_pendente_revisao = 'N'
    fundo.dat_alteracao = date.today()
    fundo.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return fundo


def inativar_fundo(seq_fundo: int) -> Fundo:
    """Inativação lógica bloqueada por saldo ativo (R11)."""
    fundo = _get_ou_erro(seq_fundo)
    tem_saldo = SaldoContaFundo.query.filter_by(seq_fundo=seq_fundo, ind_status='A').first()
    if tem_saldo is not None:
        raise RegraNegocioError("Fundo possui saldos ativos e não pode ser inativado")
    fundo.ind_status = 'I'
    fundo.dat_alteracao = date.today()
    fundo.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return fundo


def classificar_fundo(seq_fundo: int, seq_fonte_recurso: int | None) -> Fundo:
    """Classifica o fundo numa fonte de recursos — ou remove a classificação
    (spec saldo-por-fundo R21).

    Fundo sem fonte é PENDENTE de classificação: fica fora do grupo livre nas
    leituras de disponibilidade (conservador). A ponte pressupõe fundo
    mono-fonte; fundo multi-fonte não recebe FK e permanece pendente.
    """
    from ..models import FonteRecurso

    fundo = _get_ou_erro(seq_fundo)
    if seq_fonte_recurso is not None:
        fonte = FonteRecurso.query.get(seq_fonte_recurso)
        if fonte is None or fonte.ind_status != 'A':
            raise RegraNegocioError("Fonte de recursos inexistente ou inativa")
    fundo.seq_fonte_recurso = seq_fonte_recurso
    fundo.dat_alteracao = date.today()
    fundo.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return fundo


def listar_fundos(cod=None, dsc=None, status=None, pendente=None) -> list[Fundo]:
    """Lista filtrada (AND), ordenada por código (R7)."""
    q = Fundo.query
    if cod:
        q = q.filter(Fundo.cod_fundo.ilike(f"%{cod.strip()}%"))
    if dsc:
        q = q.filter(Fundo.dsc_fundo.ilike(f"%{dsc.strip()}%"))
    if status in ('ativo', 'inativo'):
        q = q.filter(Fundo.ind_status == ('A' if status == 'ativo' else 'I'))
    if pendente is True:
        q = q.filter(Fundo.ind_pendente_revisao == 'S')
    elif pendente is False:
        q = q.filter(Fundo.ind_pendente_revisao == 'N')
    return q.order_by(Fundo.cod_fundo).all()


def contar_pendentes() -> int:
    return Fundo.query.filter_by(ind_status='A', ind_pendente_revisao='S').count()


def garantir_fundo_geral() -> Fundo:
    """Fundo padrão 'GERAL' (saldo sem discriminação por fundo) — MANUAL,
    aprovado. Criado idempotentemente; usado pela migração do legado e pelo
    import CSV de transição da tela (F2.4)."""
    fundo = Fundo.query.filter_by(cod_fundo='GERAL').first()
    if fundo is not None:
        return fundo
    tipo = resolver_tipo('MANUAL')
    fundo = Fundo(
        cod_fundo='GERAL',
        dsc_fundo='Saldo geral da conta',
        seq_tipo_origem=tipo.seq_tipo_origem_saldo,
        seq_sistema_origem=None,
        ind_pendente_revisao='N',
        ind_status='A',
        cod_pessoa_inclusao=cod_pessoa_atual(),
    )
    db.session.add(fundo)
    db.session.commit()
    return fundo


def upsert_fundo_pendente(cod_fundo: str, dsc_fundo: str,
                          sigla_sistema: str | None = None) -> Fundo:
    """Operação interna para importações (R12) — sem rota HTTP.

    Código existente (qualquer estado) → retorna sem alterar nada.
    Inexistente → cria pendente com data de auto-cadastro e a origem conforme
    a chamada: com sistema → AUTOMATIZADO; sem sistema → IMPORTADO (caso CSV).
    """
    existente = Fundo.query.filter_by(cod_fundo=(cod_fundo or "").strip()).first()
    if existente is not None:
        return existente

    sigla_tipo = 'AUTOMATIZADO' if sigla_sistema else 'IMPORTADO'
    tipo = resolver_tipo(sigla_tipo)
    sistema = resolver_sistema(sigla_tipo, sigla_sistema)
    fundo = Fundo(
        cod_fundo=cod_fundo.strip(),
        dsc_fundo=(dsc_fundo or "").strip()[:DSC_MAX],
        seq_tipo_origem=tipo.seq_tipo_origem_saldo,
        seq_sistema_origem=sistema.seq_sistema_origem if sistema else None,
        ind_pendente_revisao='S',
        dat_auto_cadastro=date.today(),
        ind_status='A',
        cod_pessoa_inclusao=cod_pessoa_atual(),
    )
    db.session.add(fundo)
    db.session.commit()
    return fundo
