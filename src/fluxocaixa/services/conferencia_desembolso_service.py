"""Conferência do desembolso — três visões DERIVADAS (spec desembolso R14–R16).

⚠️ Liberação não movimenta caixa: o controle de liberações é saldo de
CONTROLE; o bancário vem dos lançamentos/saldos; a conciliação liga os dois.
A série diária é CONTÍNUA (dia sem movimento = zeros) e a diferença da
conciliação é CATEGORIZADA (transferência interna neutra primeiro — a causa
mais comum —, depois "a investigar / possível ordem judicial").
"""
from datetime import date, timedelta
from decimal import Decimal

from ..auth.contexto import cod_pessoa_atual
from ..models import Conferencia, Liberacao, LiberacaoEvento, Pagamento, PagamentoLiberacao
from ..models.base import db
from ..models.liberacao import (
    APROPRIACAO,
    ESTORNO,
    EVENTO_CANCELAMENTO,
    SITUACAO_CANCELADA,
    SITUACAO_CONFIRMADA,
)
from .transferencia_service import total_do_dia as transferencias_do_dia
from .validacao import RegraNegocioError

ZERO = Decimal("0.00")


def _dias(inicio: date, fim: date) -> list[date]:
    return [inicio + timedelta(days=i) for i in range((fim - inicio).days + 1)]


def _apurados(inicio: date, fim: date) -> dict:
    return {
        c.dat_conferencia: c
        for c in Conferencia.query.filter(
            Conferencia.dat_conferencia.between(inicio, fim),
            Conferencia.ind_status == 'A').all()
    }


def informar_apurado(dia: date, val_liberacoes: Decimal | None = None,
                     val_pagamentos: Decimal | None = None) -> Conferencia:
    """Registra o apurado externo do dia (R16) — upsert pelo grão diário."""
    registro = Conferencia.query.get(dia)
    if registro is None:
        registro = Conferencia(dat_conferencia=dia, ind_status='A',
                               cod_pessoa_inclusao=cod_pessoa_atual())
        db.session.add(registro)
    if val_liberacoes is not None:
        registro.val_apurado_liberacoes = Decimal(val_liberacoes).quantize(Decimal("0.01"))
    if val_pagamentos is not None:
        registro.val_apurado_pagamentos = Decimal(val_pagamentos).quantize(Decimal("0.01"))
    registro.dat_alteracao = date.today()
    registro.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return registro


# ---------------------------------------------------------------------------
# 1 · Controle de liberações (saldo de CONTROLE — não é caixa)
# ---------------------------------------------------------------------------

def visao_controle(inicio: date, fim: date) -> list[dict]:
    if inicio > fim:
        raise RegraNegocioError("Período inválido")

    # movimentos por dia (D2 do change): liberações pela dat_liberacao das
    # confirmadas; apropriações/estornos e cancelamentos pela dat_evento
    liberacoes_dia: dict = {}
    for liberacao in Liberacao.query.filter_by(
            ind_status='A', cod_situacao=SITUACAO_CONFIRMADA).all():
        d = liberacao.dat_liberacao
        liberacoes_dia[d] = liberacoes_dia.get(d, ZERO) + Decimal(liberacao.val_liberacao)

    apropriacoes_dia: dict = {}
    for evento in PagamentoLiberacao.query.all():
        sinal = 1 if evento.cod_tipo_evento == APROPRIACAO else -1
        if evento.cod_tipo_evento not in (APROPRIACAO, ESTORNO):
            continue
        d = evento.dat_evento
        apropriacoes_dia[d] = apropriacoes_dia.get(d, ZERO) + sinal * Decimal(evento.val_apropriado)

    cancelamentos_dia: dict = {}
    for evento in LiberacaoEvento.query.filter_by(
            cod_tipo_evento=EVENTO_CANCELAMENTO).all():
        liberacao = evento.liberacao
        if liberacao is None or liberacao.ind_status != 'A':
            continue
        if liberacao.cod_situacao != SITUACAO_CANCELADA:
            continue
        d = evento.dat_evento
        cancelamentos_dia[d] = cancelamentos_dia.get(d, ZERO) + Decimal(liberacao.val_liberacao)

    # pendente anterior ao início: soma de tudo antes do período
    pendente = ZERO
    todas_datas = set(liberacoes_dia) | set(apropriacoes_dia) | set(cancelamentos_dia)
    for d in sorted(dd for dd in todas_datas if dd < inicio):
        pendente += (liberacoes_dia.get(d, ZERO) - apropriacoes_dia.get(d, ZERO)
                     - cancelamentos_dia.get(d, ZERO))

    apurados = _apurados(inicio, fim)
    linhas = []
    for d in _dias(inicio, fim):
        anterior = pendente
        liberacoes = liberacoes_dia.get(d, ZERO)
        apropriacoes = apropriacoes_dia.get(d, ZERO)
        cancelamentos = cancelamentos_dia.get(d, ZERO)
        pendente = anterior + liberacoes - apropriacoes - cancelamentos
        apurado = apurados.get(d)
        apurado_liberacoes = (Decimal(apurado.val_apurado_liberacoes)
                              if apurado is not None and apurado.val_apurado_liberacoes is not None
                              else None)
        if apurado_liberacoes is None:
            situacao_apurado = 'NEUTRO'   # sem apurado ≠ divergente (R16)
        elif apurado_liberacoes == liberacoes:
            situacao_apurado = 'CONFERIDO'
        else:
            situacao_apurado = 'DIVERGENTE'
        linhas.append({
            'dia': d, 'pendente_anterior': anterior.quantize(Decimal("0.01")),
            'liberacoes': liberacoes.quantize(Decimal("0.01")),
            'apropriacoes': apropriacoes.quantize(Decimal("0.01")),
            'cancelamentos': cancelamentos.quantize(Decimal("0.01")),
            'pendente_final': pendente.quantize(Decimal("0.01")),
            'apurado_liberacoes': apurado_liberacoes,
            'situacao_apurado': situacao_apurado,
        })
    return linhas


# ---------------------------------------------------------------------------
# 2 · Financeira (saldo BANCÁRIO)
# ---------------------------------------------------------------------------

def visao_financeira(inicio: date, fim: date) -> list[dict]:
    from ..models import Lancamento
    from ..repositories.saldo_fundo_repository import agregado_por_conta

    entradas_dia: dict = {}
    saidas_dia: dict = {}
    for lancamento in Lancamento.query.filter(
            Lancamento.ind_status == 'A',
            Lancamento.dat_lancamento.between(inicio, fim)).all():
        valor = Decimal(lancamento.val_lancamento)
        d = lancamento.dat_lancamento
        if lancamento.cod_tipo_lancamento == 'C':
            entradas_dia[d] = entradas_dia.get(d, ZERO) + valor
        else:
            saidas_dia[d] = saidas_dia.get(d, ZERO) + valor

    registrados = {}
    for linha in agregado_por_conta(inicio, fim):
        d = linha['dat_saldo'] if isinstance(linha['dat_saldo'], date) else date.fromisoformat(str(linha['dat_saldo']))
        registrados[d] = registrados.get(d, ZERO) + linha['val_saldo']

    linhas = []
    for d in _dias(inicio, fim):
        linhas.append({
            'dia': d,
            'entradas': entradas_dia.get(d, ZERO).quantize(Decimal("0.01")),
            'saidas': saidas_dia.get(d, ZERO).quantize(Decimal("0.01")),
            'saldo_registrado': (registrados[d].quantize(Decimal("0.01"))
                                 if d in registrados else None),
        })
    return linhas


# ---------------------------------------------------------------------------
# 3 · Conciliação categorizada (R15)
# ---------------------------------------------------------------------------

def visao_conciliacao(inicio: date, fim: date) -> list[dict]:
    from ..models import Lancamento

    pagamentos_dia: dict = {}
    for pagamento in Pagamento.query.filter(
            Pagamento.ind_status == 'A',
            Pagamento.dat_pagamento.between(inicio, fim)).all():
        d = pagamento.dat_pagamento
        pagamentos_dia[d] = pagamentos_dia.get(d, ZERO) + Decimal(pagamento.val_pagamento)

    saidas_dia: dict = {}
    for lancamento in Lancamento.query.filter(
            Lancamento.ind_status == 'A',
            Lancamento.cod_tipo_lancamento == 'D',
            Lancamento.dat_lancamento.between(inicio, fim)).all():
        d = lancamento.dat_lancamento
        saidas_dia[d] = saidas_dia.get(d, ZERO) + Decimal(lancamento.val_lancamento)

    linhas = []
    for d in _dias(inicio, fim):
        pagamentos = pagamentos_dia.get(d, ZERO)
        saidas = saidas_dia.get(d, ZERO)
        diferenca = saidas - pagamentos
        transferencias = transferencias_do_dia(d)
        if diferenca > 0:
            neutra = min(diferenca, transferencias)
            investigar = diferenca - neutra
        else:
            neutra = ZERO
            investigar = ZERO
        linhas.append({
            'dia': d,
            'pagamentos': pagamentos.quantize(Decimal("0.01")),
            'saidas': saidas.quantize(Decimal("0.01")),
            'diferenca': diferenca.quantize(Decimal("0.01")),
            'transferencia_neutra': neutra.quantize(Decimal("0.01")),
            'a_investigar': investigar.quantize(Decimal("0.01")),
            'conciliado': diferenca == 0 or investigar == 0,
        })
    return linhas
