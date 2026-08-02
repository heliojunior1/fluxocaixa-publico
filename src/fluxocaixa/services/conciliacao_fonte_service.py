"""Conciliação operacional × contábil por fonte (spec fonte-recurso R10–R12)."""
from datetime import date
from decimal import Decimal

from ..auth.contexto import cod_pessoa_atual
from ..models import DisponibilidadeContabil, FonteRecurso, ReservaFinanceira
from ..models.base import db
from .validacao import RegraNegocioError

ZERO = Decimal("0.00")

SITUACAO_CONCILIADA = 'CONCILIADA'
#: difere — o rótulo NOMEIA o que a diferença contém (itens que só a
#: contabilidade vê); nunca divergência anônima
SITUACAO_A_EXPLICAR = 'A_EXPLICAR'
#: só operacional — neutro, ausência de carga não é divergência
SITUACAO_SEM_CONTABIL = 'SEM_CONTABIL'

ROTULO_A_EXPLICAR = ("a explicar: obrigações financeiras, restos a pagar e "
                     "consignações — itens que só a contabilidade vê")


def classificar_situacao(operacional: Decimal | None,
                         contabil: Decimal | None) -> str:
    """Situação NOMEADA da fonte (R12) — função pura, unit-testada."""
    if contabil is None:
        return SITUACAO_SEM_CONTABIL
    if (operacional or ZERO) == contabil:
        return SITUACAO_CONCILIADA
    return SITUACAO_A_EXPLICAR


def registrar_disponibilidade(dat_referencia: date, codigo_fonte: str,
                              val_disponibilidade: Decimal) -> DisponibilidadeContabil:
    """Carga contábil (R10) — revisão INATIVA a anterior da (data, fonte)."""
    from .fonte_recurso_service import obter_ou_criar_pendente

    if not (codigo_fonte or "").strip():
        raise RegraNegocioError("Código da fonte é obrigatório")
    fonte = obter_ou_criar_pendente(codigo_fonte, dat_referencia.year)

    anterior = DisponibilidadeContabil.query.filter_by(
        dat_referencia=dat_referencia,
        seq_fonte_recurso=fonte.seq_fonte_recurso, ind_status='A').first()
    if anterior is not None:
        anterior.ind_status = 'I'
        anterior.dat_alteracao = date.today()
        anterior.cod_pessoa_alteracao = cod_pessoa_atual()

    registro = DisponibilidadeContabil(
        dat_referencia=dat_referencia,
        seq_fonte_recurso=fonte.seq_fonte_recurso,
        val_disponibilidade=Decimal(val_disponibilidade).quantize(Decimal("0.01")),
        ind_status='A', cod_pessoa_inclusao=cod_pessoa_atual())
    db.session.add(registro)
    db.session.commit()
    return registro


def reservas_vigentes_da_fonte(seq_fonte_recurso: int, referencia: date) -> Decimal:
    """Espelho por-fonte do `reservas_vigentes_do_grupo` (F7.4)."""
    from .reserva_service import valor_corrente

    total = ZERO
    for reserva in ReservaFinanceira.query.filter_by(
            seq_fonte_recurso=seq_fonte_recurso, ind_status='A').all():
        if reserva.dat_inicio_vigencia > referencia:
            continue
        if reserva.dat_fim_vigencia is not None and reserva.dat_fim_vigencia < referencia:
            continue
        corrente = valor_corrente(reserva.seq_reserva)
        if corrente > 0:
            total += corrente
    return total.quantize(Decimal("0.01"))


def operacional_por_fonte(referencia: date | None = None) -> dict:
    """Bruto por fonte − reservas vigentes DA fonte — derivada, nunca
    persistida (R11)."""
    from ..repositories.saldo_fundo_repository import saldo_bruto_por_fonte

    referencia = referencia or date.today()
    return {seq: (bruto - reservas_vigentes_da_fonte(seq, referencia)).quantize(Decimal("0.01"))
            for seq, bruto in saldo_bruto_por_fonte().items()}


def conciliar(dat_referencia: date) -> list[dict]:
    """Operacional × contábil por fonte, situação nomeada (R12)."""
    operacional = operacional_por_fonte(dat_referencia)
    contabil = {
        registro.seq_fonte_recurso: Decimal(registro.val_disponibilidade)
        for registro in DisponibilidadeContabil.query.filter_by(
            dat_referencia=dat_referencia, ind_status='A').all()
    }

    linhas = []
    for seq in sorted(set(operacional) | set(contabil)):
        fonte = FonteRecurso.query.get(seq)
        val_operacional = operacional.get(seq)
        val_contabil = contabil.get(seq)
        diferenca = ((val_operacional or ZERO) - (val_contabil or ZERO)).quantize(Decimal("0.01"))
        linhas.append({
            'fonte': fonte,
            'operacional': val_operacional,
            'contabil': val_contabil,
            'diferenca': diferenca,
            'situacao': classificar_situacao(val_operacional, val_contabil),
        })
    return linhas
