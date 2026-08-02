"""Programação de desembolso — cotas do decreto (spec desembolso R21–R22)."""
from datetime import date
from decimal import Decimal

from ..auth.contexto import cod_pessoa_atual
from ..models import Orgao, ProgramacaoDesembolso
from ..models.base import db
from .validacao import RegraNegocioError

ZERO = Decimal("0.00")


def registrar_cota(num_ano: int, num_mes: int, cod_orgao: int,
                   val_cota: Decimal, dsc_referencia_ato: str,
                   seq_qualificador: int | None = None,
                   seq_fonte_recurso: int | None = None) -> ProgramacaoDesembolso:
    """Revisão INATIVA a anterior da mesma chave e insere (R21)."""
    if not (1 <= num_mes <= 12):
        raise RegraNegocioError("Mês da cota inválido")
    if Decimal(val_cota) <= 0:
        raise RegraNegocioError("Valor da cota deve ser positivo")
    if not (dsc_referencia_ato or "").strip():
        raise RegraNegocioError("Referência do ato (decreto/portaria) é obrigatória")
    orgao = Orgao.query.get(cod_orgao)
    if orgao is None or orgao.ind_status != 'A':
        raise RegraNegocioError("Órgão inexistente ou inativo")

    anterior = ProgramacaoDesembolso.query.filter_by(
        num_ano=num_ano, num_mes=num_mes, cod_orgao=cod_orgao,
        seq_qualificador=seq_qualificador, ind_status='A').first()
    if anterior is not None:
        anterior.ind_status = 'I'
        anterior.dat_alteracao = date.today()
        anterior.cod_pessoa_alteracao = cod_pessoa_atual()

    cota = ProgramacaoDesembolso(
        num_ano=num_ano, num_mes=num_mes, cod_orgao=cod_orgao,
        seq_qualificador=seq_qualificador, seq_fonte_recurso=seq_fonte_recurso,
        val_cota=Decimal(val_cota).quantize(Decimal("0.01")),
        dsc_referencia_ato=dsc_referencia_ato.strip()[:120],
        ind_status='A', cod_pessoa_inclusao=cod_pessoa_atual())
    db.session.add(cota)
    db.session.commit()
    return cota


def cotas_do_mes(num_ano: int, num_mes: int) -> Decimal:
    """Σ das cotas ativas do (ano, mês) — a precedência do previsto (R22)."""
    total = ZERO
    for cota in ProgramacaoDesembolso.query.filter_by(
            num_ano=num_ano, num_mes=num_mes, ind_status='A').all():
        total += Decimal(cota.val_cota)
    return total.quantize(Decimal("0.01"))


def meses_programados(num_ano: int) -> set[int]:
    return {c.num_mes for c in ProgramacaoDesembolso.query.filter_by(
        num_ano=num_ano, ind_status='A').all()}


def visao_anual(num_ano: int) -> list[dict]:
    """Cota × liberado × pago por órgão, mês a mês (R22) — o único recorte
    por órgão legítimo do previsto (a programação TEM órgão)."""
    from ..models import Liberacao
    from ..models.liberacao import SITUACAO_CONFIRMADA
    from .liberacao_service import consumo_da_liberacao

    por_orgao: dict = {}
    for cota in ProgramacaoDesembolso.query.filter_by(
            num_ano=num_ano, ind_status='A').all():
        orgao = por_orgao.setdefault(cota.cod_orgao, {
            'cota': {m: ZERO for m in range(1, 13)},
            'liberado': {m: ZERO for m in range(1, 13)},
            'pago': {m: ZERO for m in range(1, 13)},
        })
        orgao['cota'][cota.num_mes] += Decimal(cota.val_cota)

    for liberacao in Liberacao.query.filter_by(
            ind_status='A', cod_situacao=SITUACAO_CONFIRMADA).all():
        if liberacao.dat_liberacao.year != num_ano:
            continue
        orgao = por_orgao.setdefault(liberacao.cod_orgao, {
            'cota': {m: ZERO for m in range(1, 13)},
            'liberado': {m: ZERO for m in range(1, 13)},
            'pago': {m: ZERO for m in range(1, 13)},
        })
        mes = liberacao.dat_liberacao.month
        orgao['liberado'][mes] += Decimal(liberacao.val_liberacao)
        orgao['pago'][mes] += consumo_da_liberacao(liberacao.seq_liberacao)

    return [
        {'cod_orgao': cod, **dados}
        for cod, dados in sorted(por_orgao.items())
    ]
