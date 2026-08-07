"""Reservas financeiras e bloqueios judiciais (spec desembolso R19–R20).

Valor corrente SEMPRE derivado dos eventos; administrativa acima do
disponível exige confirmação, bloqueio judicial nunca (não é escolha — só
alerta); liberar bloqueio exige a referência da ordem de desbloqueio.
"""
from datetime import date
from decimal import Decimal

from ..auth.contexto import cod_pessoa_atual
from ..models import FonteRecurso, ReservaFinanceira
from ..models.base import db
from ..models.reserva_financeira import (
    EVENTO_CONSTITUICAO,
    EVENTO_LIBERACAO,
    EVENTO_REDUCAO,
    EVENTO_REFORCO,
    TIPO_ADMINISTRATIVA,
    TIPO_JUDICIAL,
    ReservaEvento,
)
from .validacao import RegraNegocioError

ZERO = Decimal("0.00")

_SINAL = {EVENTO_CONSTITUICAO: 1, EVENTO_REFORCO: 1,
          EVENTO_REDUCAO: -1, EVENTO_LIBERACAO: -1}


def valor_corrente(seq_reserva: int) -> Decimal:
    """Σ(constituição + reforços − reduções − liberações) — derivado, sempre."""
    total = ZERO
    for evento in ReservaEvento.query.filter_by(seq_reserva=seq_reserva).all():
        total += _SINAL.get(evento.cod_tipo_evento, 0) * Decimal(evento.val_evento)
    return total.quantize(Decimal("0.01"))


def _evento(reserva: ReservaFinanceira, tipo: str, valor: Decimal,
            referencia: str | None) -> None:
    if reserva.cod_tipo_reserva == TIPO_JUDICIAL and not (referencia or "").strip():
        raise RegraNegocioError(
            "Evento de bloqueio judicial exige referência documental da ordem")
    db.session.add(ReservaEvento(
        seq_reserva=reserva.seq_reserva, cod_tipo_evento=tipo,
        val_evento=Decimal(valor).quantize(Decimal("0.01")),
        dsc_referencia_documental=(referencia or "").strip() or None,
        dat_evento=date.today(), cod_pessoa_evento=cod_pessoa_atual()))


def constituir_reserva(
    cod_tipo_reserva: str,
    seq_fonte_recurso: int,
    val_reserva: Decimal,
    dsc_motivo: str,
    dat_inicio_vigencia: date,
    dat_fim_vigencia: date | None = None,
    dsc_referencia_processo: str | None = None,
    seq_conta: int | None = None,
    confirmado: bool = False,
) -> dict:
    """Constitui a reserva com o evento de constituição (R19).

    Administrativa acima do disponível do grupo exige `confirmado=true`;
    bloqueio judicial NUNCA pede confirmação — retorna `alerta` quando o
    grupo fica insuficiente.
    """
    from ..repositories.saldo_fundo_repository import saldo_bruto_por_grupo

    if cod_tipo_reserva not in (TIPO_ADMINISTRATIVA, TIPO_JUDICIAL):
        raise RegraNegocioError("Tipo de reserva inválido")
    val_reserva = Decimal(val_reserva)
    if val_reserva <= 0:
        raise RegraNegocioError("Valor da reserva deve ser positivo")
    if not (dsc_motivo or "").strip():
        raise RegraNegocioError("Motivo da reserva é obrigatório")

    fonte = FonteRecurso.query.get(seq_fonte_recurso)
    if fonte is None or fonte.ind_status != 'A':
        raise RegraNegocioError("Fonte de recursos inexistente ou inativa")

    if cod_tipo_reserva == TIPO_JUDICIAL and not (dsc_referencia_processo or "").strip():
        raise RegraNegocioError(
            "Bloqueio judicial exige a referência do processo/ofício")

    # Disponível LÍQUIDO do grupo (change tipo-instrumento-financeiro):
    # reservar contra aplicação com carência inflaria o disponível.
    disponivel = (saldo_bruto_por_grupo()[fonte.grupo]["liquido"]
                  - reservas_vigentes_do_grupo(fonte.grupo, date.today()))
    alerta = None
    if val_reserva > disponivel:
        if cod_tipo_reserva == TIPO_ADMINISTRATIVA and not confirmado:
            raise RegraNegocioError(
                "Reserva acima do disponível do grupo exige confirmação explícita")
        # judicial: não é escolha — registra e ALERTA (nunca bloqueia)
        alerta = ("Grupo fica insuficiente com este bloqueio"
                  if cod_tipo_reserva == TIPO_JUDICIAL else None)

    reserva = ReservaFinanceira(
        cod_tipo_reserva=cod_tipo_reserva,
        seq_fonte_recurso=seq_fonte_recurso,
        seq_conta=seq_conta,
        dsc_motivo=dsc_motivo.strip()[:255],
        dsc_referencia_processo=(dsc_referencia_processo or "").strip() or None,
        dat_inicio_vigencia=dat_inicio_vigencia,
        dat_fim_vigencia=dat_fim_vigencia,
        ind_status='A',
        cod_pessoa_inclusao=cod_pessoa_atual())
    db.session.add(reserva)
    db.session.flush()
    _evento(reserva, EVENTO_CONSTITUICAO, val_reserva,
            reserva.dsc_referencia_processo)
    db.session.commit()
    return {'reserva': reserva, 'alerta': alerta}


def _get_ou_erro(seq_reserva: int) -> ReservaFinanceira:
    reserva = ReservaFinanceira.query.get(seq_reserva)
    if reserva is None or reserva.ind_status != 'A':
        raise RegraNegocioError("Reserva inexistente")
    return reserva


def reforcar_reserva(seq_reserva: int, valor: Decimal,
                     referencia: str | None = None) -> ReservaFinanceira:
    reserva = _get_ou_erro(seq_reserva)
    if Decimal(valor) <= 0:
        raise RegraNegocioError("Valor do reforço deve ser positivo")
    _evento(reserva, EVENTO_REFORCO, Decimal(valor), referencia)
    db.session.commit()
    return reserva


def reduzir_reserva(seq_reserva: int, valor: Decimal,
                    referencia: str | None = None) -> ReservaFinanceira:
    reserva = _get_ou_erro(seq_reserva)
    valor = Decimal(valor)
    if valor <= 0:
        raise RegraNegocioError("Valor da redução deve ser positivo")
    if valor > valor_corrente(seq_reserva):
        raise RegraNegocioError("Redução acima do valor corrente da reserva")
    _evento(reserva, EVENTO_REDUCAO, valor, referencia)
    db.session.commit()
    return reserva


def liberar_reserva(seq_reserva: int,
                    referencia: str | None = None) -> ReservaFinanceira:
    """Libera o valor corrente inteiro — no judicial, exige a ordem (R19)."""
    reserva = _get_ou_erro(seq_reserva)
    corrente = valor_corrente(seq_reserva)
    if corrente <= 0:
        raise RegraNegocioError("Reserva sem valor corrente para liberar")
    _evento(reserva, EVENTO_LIBERACAO, corrente, referencia)
    db.session.commit()
    return reserva


def listar_reservas() -> list[dict]:
    return [
        {'reserva': r, 'valor_corrente': valor_corrente(r.seq_reserva)}
        for r in ReservaFinanceira.query.filter_by(ind_status='A')
        .order_by(ReservaFinanceira.dat_inicio_vigencia.desc()).all()
    ]


def reservas_vigentes_do_grupo(grupo: str, referencia: date) -> Decimal:
    """A parcela da SUBTRAÇÃO ÚNICA da simulação (R20): vigentes na data,
    do grupo da fonte atingida, com valor corrente positivo."""
    total = ZERO
    for reserva in ReservaFinanceira.query.filter_by(ind_status='A').all():
        if reserva.dat_inicio_vigencia > referencia:
            continue
        if reserva.dat_fim_vigencia is not None and reserva.dat_fim_vigencia < referencia:
            continue
        if reserva.fonte_recurso.grupo != grupo:
            continue
        corrente = valor_corrente(reserva.seq_reserva)
        if corrente > 0:
            total += corrente
    return total.quantize(Decimal("0.01"))
