"""Ciclo de vida do fundo/instrumento financeiro (spec saldo-por-fundo
R7–R12, R22).

Cadastro manual, alteração, aprovação de auto-cadastrados, inativação
lógica com bloqueio por saldo ativo, listagem filtrada e o upsert interno
consumido pelas importações (F2.3). Desde o change
tipo-instrumento-financeiro, todo fundo carrega o tipo de instrumento
(FUNDO, CONTA_MOVIMENTO, CDB, ...) e os atributos de liquidez.
"""
from datetime import date

from ..auth.contexto import cod_pessoa_atual
from ..models import Fundo, SaldoContaFundo, TipoInstrumento
from ..models.base import db
from .origem_saldo import resolver_sistema, resolver_tipo
from .validacao import RegraNegocioError

COD_MIN, COD_MAX = 4, 10
DSC_MAX = 120

TIPO_INSTRUMENTO_DEFAULT = 'FUNDO'
TIPO_CONTA_MOVIMENTO = 'CONTA_MOVIMENTO'


def resolver_tipo_instrumento(sigla: str) -> TipoInstrumento:
    """Tipo de instrumento ativo pela sigla (seeds e defaults internos)."""
    tipo = TipoInstrumento.query.filter_by(txt_sigla=sigla, ind_status='A').first()
    if tipo is None:
        raise RegraNegocioError("Tipo de instrumento inexistente ou inativo")
    return tipo


def _validar_tipo_instrumento(seq_tipo_instrumento: int | None) -> int:
    """None → default FUNDO; seq informado tem de existir e estar ativo."""
    if seq_tipo_instrumento is None:
        return resolver_tipo_instrumento(TIPO_INSTRUMENTO_DEFAULT).seq_tipo_instrumento
    tipo = TipoInstrumento.query.get(seq_tipo_instrumento)
    if tipo is None or tipo.ind_status != 'A':
        raise RegraNegocioError("Tipo de instrumento inexistente ou inativo")
    return tipo.seq_tipo_instrumento


def _validar_liquidez(ind: str) -> str:
    ind = (ind or 'S').strip().upper()
    if ind not in ('S', 'N'):
        raise RegraNegocioError("Liquidez imediata deve ser 'S' ou 'N'")
    return ind


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


def criar_fundo(cod_fundo: str, dsc_fundo: str,
                seq_tipo_instrumento: int | None = None,
                ind_liquidez_imediata: str = 'S',
                dat_vencimento: date | None = None) -> Fundo:
    """Cadastro manual: tipo de origem MANUAL, sem sistema, aprovado (R8).

    Tipo de instrumento default FUNDO; liquidez default 'S' (R22). O default
    vem da ausência do parâmetro, nunca sobrescreve valor explícito do form.
    """
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
        seq_tipo_instrumento=_validar_tipo_instrumento(seq_tipo_instrumento),
        ind_liquidez_imediata=_validar_liquidez(ind_liquidez_imediata),
        dat_vencimento=dat_vencimento,
        ind_pendente_revisao='N',
        ind_status='A',
        cod_pessoa_inclusao=cod_pessoa_atual(),
    )
    db.session.add(fundo)
    db.session.commit()
    return fundo


def alterar_fundo(seq_fundo: int, dsc_fundo: str, novo_cod: str | None = None,
                  seq_tipo_instrumento: int | None = None,
                  ind_liquidez_imediata: str | None = None,
                  dat_vencimento: date | None = ...) -> Fundo:
    """Altera descrição e atributos de classificação — tipo de instrumento,
    liquidez e vencimento (R9/R22); código e origem são imutáveis.

    `dat_vencimento` usa sentinela `...`: None explícito LIMPA o vencimento
    (instrumento que voltou a ser sem prazo); ausência preserva.
    """
    fundo = _get_ou_erro(seq_fundo)
    if novo_cod is not None and novo_cod.strip() != fundo.cod_fundo:
        raise RegraNegocioError("O código do fundo não pode ser alterado")
    fundo.dsc_fundo = _validar_descricao(dsc_fundo)
    if seq_tipo_instrumento is not None:
        fundo.seq_tipo_instrumento = _validar_tipo_instrumento(seq_tipo_instrumento)
    if ind_liquidez_imediata is not None:
        fundo.ind_liquidez_imediata = _validar_liquidez(ind_liquidez_imediata)
    if dat_vencimento is not ...:
        fundo.dat_vencimento = dat_vencimento
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


def listar_fundos(cod=None, dsc=None, status=None, pendente=None,
                  seq_tipo_instrumento=None) -> list[Fundo]:
    """Lista filtrada (AND), ordenada por código (R7; filtro de tipo R13)."""
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
    if seq_tipo_instrumento is not None:
        q = q.filter(Fundo.seq_tipo_instrumento == seq_tipo_instrumento)
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
        # Criado pela máquina com semântica conhecida: é a conta movimento
        # (R22 — a exceção deliberada ao default FUNDO).
        seq_tipo_instrumento=resolver_tipo_instrumento(
            TIPO_CONTA_MOVIMENTO).seq_tipo_instrumento,
        ind_liquidez_imediata='S',
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
        # Auto-cadastro nasce FUNDO líquido (R22): o conservadorismo da
        # disponibilidade já vem da fonte nula (fora do livre); nascer sem
        # liquidez zeraria a disponibilidade de instalação que nunca
        # classificou instrumento algum.
        seq_tipo_instrumento=resolver_tipo_instrumento(
            TIPO_INSTRUMENTO_DEFAULT).seq_tipo_instrumento,
        ind_liquidez_imediata='S',
        ind_pendente_revisao='S',
        dat_auto_cadastro=date.today(),
        ind_status='A',
        cod_pessoa_inclusao=cod_pessoa_atual(),
    )
    db.session.add(fundo)
    db.session.commit()
    return fundo
