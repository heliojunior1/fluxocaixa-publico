"""Ciclo de vida da liberação financeira (spec desembolso R1–R4).

Criação (rascunho) → confirmação → cancelamento, sempre com o livro de
eventos gravado NA MESMA transação do estado (D1 do change). O saldo
liberado pendente é derivado aqui — origem única, nunca persistido (D3).
Apropriar/estornar são operações internas (a UI chega na F7.1b).
"""
from datetime import date, timedelta
from decimal import Decimal

from ..auth.contexto import cod_pessoa_atual
from ..models import FonteRecurso, Liberacao, LiberacaoEvento, Orgao, PagamentoLiberacao, Qualificador
from ..models.base import db
from ..models.liberacao import (
    APROPRIACAO,
    ESTORNO,
    EVENTO_CANCELAMENTO,
    EVENTO_CONFIRMACAO,
    EVENTO_CRIACAO,
    NATUREZA_DISCRICIONARIA,
    NATUREZAS,
    SITUACAO_CANCELADA,
    SITUACAO_CONFIRMADA,
    SITUACAO_RASCUNHO,
)
from .validacao import RegraNegocioError


def _get_ou_erro(seq_liberacao: int) -> Liberacao:
    liberacao = Liberacao.query.get(seq_liberacao)
    if liberacao is None or liberacao.ind_status != 'A':
        raise RegraNegocioError("Liberação inexistente")
    return liberacao


def _evento(liberacao: Liberacao, tipo: str, justificativa: str | None = None,
            referencia_snapshot: str | None = None) -> None:
    db.session.add(LiberacaoEvento(
        seq_liberacao=liberacao.seq_liberacao,
        cod_tipo_evento=tipo,
        dsc_justificativa=justificativa,
        dsc_referencia_snapshot=referencia_snapshot,
        dat_evento=date.today(),
        cod_pessoa_evento=cod_pessoa_atual(),
    ))


def criar_liberacao(
    dat_liberacao: date,
    cod_orgao: int,
    seq_qualificador: int,
    seq_fonte_recurso: int | None,
    val_liberacao: Decimal,
    dsc_liberacao: str | None = None,
    dsc_justificativa: str | None = None,
    cod_natureza_obrigacao: str = NATUREZA_DISCRICIONARIA,
    dsc_base_legal: str | None = None,
    dat_prevista_desembolso: date | None = None,
) -> Liberacao:
    """Cria a liberação em RASCUNHO, com o evento de criação (R1/R2)."""
    orgao = Orgao.query.get(cod_orgao)
    if orgao is None or orgao.ind_status != 'A':
        raise RegraNegocioError("Órgão inexistente ou inativo")

    qualificador = Qualificador.query.get(seq_qualificador)
    if qualificador is None or qualificador.ind_status != 'A' or not qualificador.is_folha():
        raise RegraNegocioError("Liberação exige qualificador folha ativo")
    if qualificador.tipo_fluxo != 'despesa':
        raise RegraNegocioError("Liberação exige qualificador de despesa")

    # obrigatória e SEM default — pré-marcar seria classificação silenciosa
    if seq_fonte_recurso is None:
        raise RegraNegocioError("Fonte de recursos é obrigatória na liberação")
    fonte = FonteRecurso.query.get(seq_fonte_recurso)
    if fonte is None or fonte.ind_status != 'A':
        raise RegraNegocioError("Fonte de recursos inexistente ou inativa")

    if val_liberacao is None or Decimal(val_liberacao) <= 0:
        raise RegraNegocioError("Valor da liberação deve ser positivo")

    if cod_natureza_obrigacao not in NATUREZAS:
        raise RegraNegocioError("Natureza da obrigação inválida")

    liberacao = Liberacao(
        dat_liberacao=dat_liberacao,
        dat_prevista_desembolso=dat_prevista_desembolso or dat_liberacao,
        cod_orgao=cod_orgao,
        seq_qualificador=seq_qualificador,
        seq_fonte_recurso=seq_fonte_recurso,
        val_liberacao=Decimal(val_liberacao).quantize(Decimal("0.01")),
        dsc_liberacao=(dsc_liberacao or "").strip() or None,
        dsc_justificativa=(dsc_justificativa or "").strip() or None,
        cod_natureza_obrigacao=cod_natureza_obrigacao,
        dsc_base_legal=(dsc_base_legal or "").strip() or None,
        cod_situacao=SITUACAO_RASCUNHO,
        ind_status='A',
        cod_pessoa_inclusao=cod_pessoa_atual(),
    )
    db.session.add(liberacao)
    db.session.flush()
    _evento(liberacao, EVENTO_CRIACAO)
    db.session.commit()
    return liberacao


def confirmar_liberacao(seq_liberacao: int,
                        referencia_snapshot: str | None = None,
                        confirmado: bool = False) -> Liberacao:
    """rascunho → confirmada, com evento (R2) e teto da LOA (R18).

    Exceder o autorizado do qualificador é ALERTA consciente, nunca bloqueio:
    sem `confirmado=true` recusa citando o excedente; com ele, confirma e o
    evento registra o excedente. O teto é a dotação atualizada quando houver
    (F8.1); sem dotação, a LOA."""
    from .previsto_loa_service import excedente_do_teto

    liberacao = _get_ou_erro(seq_liberacao)
    if liberacao.cod_situacao != SITUACAO_RASCUNHO:
        raise RegraNegocioError("Só liberação em rascunho pode ser confirmada")

    justificativas = []
    excedente = excedente_do_teto(liberacao)
    if excedente is not None:
        if not confirmado:
            raise RegraNegocioError(
                "Liberação excede o autorizado do exercício em "
                f"R$ {excedente} — confirme explicitamente para prosseguir")
        justificativas.append(f"Teto do autorizado excedido em R$ {excedente}")

    # F8.4 (R23–R24): gates pelo liquidado não pago — SÓ quando o recorte tem
    # liquidação importada; a liberação INDIVIDUAL é comparada com o estoque
    # (que já é líquido dos P — abater as confirmadas dupla-contaria)
    from .execucao_orcamentaria_service import (
        fontes_do_liquidado,
        liquidado_nao_pago_do,
    )

    ano = liberacao.dat_liberacao.year
    estoque = liquidado_nao_pago_do(ano, liberacao.cod_orgao,
                                    liberacao.seq_qualificador)
    if estoque is not None:
        excedente_liquidado = Decimal(liberacao.val_liberacao) - estoque
        if excedente_liquidado > 0:
            if not confirmado:
                raise RegraNegocioError(
                    "Liberação excede o liquidado não pago do órgão em "
                    f"R$ {excedente_liquidado.quantize(Decimal('0.01'))} — "
                    "confirme explicitamente para prosseguir")
            justificativas.append(
                "Liquidado não pago excedido em "
                f"R$ {excedente_liquidado.quantize(Decimal('0.01'))}")
        fontes = fontes_do_liquidado(ano, liberacao.cod_orgao,
                                     liberacao.seq_qualificador)
        if fontes and liberacao.seq_fonte_recurso not in fontes:
            if not confirmado:
                raise RegraNegocioError(
                    "Fonte da liberação diverge das fontes do liquidado não "
                    "pago do órgão — confirme explicitamente para prosseguir")
            justificativas.append("Fonte divergente do liquidado não pago")

    liberacao.cod_situacao = SITUACAO_CONFIRMADA
    liberacao.dat_alteracao = date.today()
    liberacao.cod_pessoa_alteracao = cod_pessoa_atual()
    _evento(liberacao, EVENTO_CONFIRMACAO,
            justificativa=" · ".join(justificativas) or None,
            referencia_snapshot=referencia_snapshot)
    db.session.commit()
    return liberacao


def devolver_a_rascunho(seq_liberacao: int) -> None:
    """Não existe (R2) — confirmada não volta a rascunho."""
    raise RegraNegocioError("Liberação confirmada não volta a rascunho")


def cancelar_liberacao(seq_liberacao: int, justificativa: str | None = None,
                       confirmado: bool = False) -> Liberacao:
    """rascunho/confirmada → cancelada, com evento e justificativa (R2)."""
    liberacao = _get_ou_erro(seq_liberacao)
    if liberacao.cod_situacao == SITUACAO_CANCELADA:
        raise RegraNegocioError("Liberação já está cancelada")

    if liberacao.cod_situacao == SITUACAO_CONFIRMADA:
        if not confirmado:
            raise RegraNegocioError(
                "Cancelar liberação confirmada exige confirmação explícita")
        if consumo_da_liberacao(seq_liberacao) > 0:
            raise RegraNegocioError(
                "Liberação possui apropriações — estorne-as antes de cancelar")

    liberacao.cod_situacao = SITUACAO_CANCELADA
    liberacao.dat_alteracao = date.today()
    liberacao.cod_pessoa_alteracao = cod_pessoa_atual()
    _evento(liberacao, EVENTO_CANCELAMENTO,
            justificativa=(justificativa or "").strip() or None)
    db.session.commit()
    return liberacao


# ---------------------------------------------------------------------------
# Apropriação (interno — a UI/regra de candidatas chega na F7.1b)
# ---------------------------------------------------------------------------

def consumo_da_liberacao(seq_liberacao: int) -> Decimal:
    """Consumo = Σ apropriações − Σ estornos (linhas-evento, nunca coluna)."""
    total = Decimal("0.00")
    for evento in PagamentoLiberacao.query.filter_by(seq_liberacao=seq_liberacao).all():
        if evento.cod_tipo_evento == APROPRIACAO:
            total += Decimal(evento.val_apropriado)
        elif evento.cod_tipo_evento == ESTORNO:
            total -= Decimal(evento.val_apropriado)
    return total.quantize(Decimal("0.01"))


def saldo_liberado_pendente(seq_fonte_recurso: int | None = None,
                            cod_orgao: int | None = None,
                            seq_qualificador: int | None = None) -> Decimal:
    """Pendente = Σ confirmadas − consumo (R3). Derivado — ORIGEM ÚNICA.

    Rascunhos e canceladas ficam fora. Enquanto a F7.1b não existir, o número
    É o total liberado não baixado (a tela rotula).
    """
    q = Liberacao.query.filter_by(ind_status='A', cod_situacao=SITUACAO_CONFIRMADA)
    if seq_fonte_recurso is not None:
        q = q.filter(Liberacao.seq_fonte_recurso == seq_fonte_recurso)
    if cod_orgao is not None:
        q = q.filter(Liberacao.cod_orgao == cod_orgao)
    if seq_qualificador is not None:
        q = q.filter(Liberacao.seq_qualificador == seq_qualificador)

    total = Decimal("0.00")
    for liberacao in q.all():
        total += Decimal(liberacao.val_liberacao)
        total -= consumo_da_liberacao(liberacao.seq_liberacao)
    return total.quantize(Decimal("0.01"))


# ---------------------------------------------------------------------------
# Visão semanal (R4)
# ---------------------------------------------------------------------------

def semana_util_de(referencia: date) -> list[date]:
    """Segunda a sexta da semana da data de referência."""
    segunda = referencia - timedelta(days=referencia.weekday())
    return [segunda + timedelta(days=i) for i in range(5)]


def visao_semanal(referencia: date) -> dict:
    """Liberações da semana útil agrupadas por natureza (não gerenciável ×
    discricionária) → órgão, com totais por dia e por semana."""
    dias = semana_util_de(referencia)
    liberacoes = (Liberacao.query
                  .filter(Liberacao.ind_status == 'A',
                          Liberacao.cod_situacao != SITUACAO_CANCELADA,
                          Liberacao.dat_liberacao >= dias[0],
                          Liberacao.dat_liberacao <= dias[-1])
                  .order_by(Liberacao.dat_liberacao)
                  .all())

    grupos: dict = {}
    totais_dia = {d: Decimal("0.00") for d in dias}
    for liberacao in liberacoes:
        chave_grupo = 'nao_gerenciavel' if liberacao.nao_gerenciavel else 'discricionaria'
        grupo = grupos.setdefault(chave_grupo, {})
        orgao = grupo.setdefault(liberacao.cod_orgao, [])
        orgao.append(liberacao)
        totais_dia[liberacao.dat_liberacao] += Decimal(liberacao.val_liberacao)

    return {
        'dias': dias,
        'grupos': grupos,
        'totais_dia': totais_dia,
        'total_semana': sum(totais_dia.values(), Decimal("0.00")),
    }
