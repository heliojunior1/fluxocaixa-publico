"""Pagamentos do desembolso (spec desembolso R6–R8).

Criação/alteração/exclusão alinhadas às convenções e o fluxo de apropriação
pagamento↔liberação: candidatas do mesmo órgão/qualificador/fonte, estouro
proibido nos dois sentidos (pendente nunca negativo), estorno como
linha-evento e **fonte herdada da apropriação** (monofonte — nunca editada
diretamente no pagamento).
"""
from datetime import date
from decimal import Decimal

from ..auth.contexto import cod_pessoa_atual
from ..domain import PagamentoCreate, PagamentoOut
from ..models import Liberacao, Pagamento, PagamentoLiberacao
from ..models.base import db
from ..models.liberacao import APROPRIACAO, ESTORNO, SITUACAO_CONFIRMADA
from ..repositories import PagamentoRepository
from .liberacao_service import consumo_da_liberacao
from .validacao import RegraNegocioError


def list_pagamentos(repo: PagamentoRepository | None = None):
    repo = repo or PagamentoRepository()
    return repo.list_pagamentos(), repo.list_orgaos(), repo.list_qualificadores()


def _get_ou_erro(seq_pagamento: int) -> Pagamento:
    pagamento = Pagamento.query.get(seq_pagamento)
    if pagamento is None or pagamento.ind_status != 'A':
        raise RegraNegocioError("Pagamento inexistente")
    return pagamento


def create_pagamento(data: PagamentoCreate, repo: PagamentoRepository | None = None) -> PagamentoOut:
    # Escrita NOVA exige qualificador; a coluna fica nullable pelo legado (R6)
    if data.seq_qualificador is None:
        raise RegraNegocioError("Pagamento exige qualificador")
    if data.val_pagamento is None or Decimal(data.val_pagamento) <= 0:
        raise RegraNegocioError("Valor do pagamento deve ser positivo")
    repo = repo or PagamentoRepository()
    pag = repo.create(data)
    return PagamentoOut(
        seq_pagamento=pag.seq_pagamento,
        dat_pagamento=pag.dat_pagamento,
        cod_orgao=pag.cod_orgao,
        seq_qualificador=pag.seq_qualificador,
        val_pagamento=pag.val_pagamento,
        dsc_pagamento=pag.dsc_pagamento,
    )


def alterar_pagamento(seq_pagamento: int, val_pagamento: Decimal | None = None,
                      dsc_pagamento: str | None = None,
                      seq_qualificador: int | None = None) -> Pagamento:
    """Alteração com a trava do apropriado (R6)."""
    pagamento = _get_ou_erro(seq_pagamento)
    if val_pagamento is not None:
        val_pagamento = Decimal(val_pagamento)
        if val_pagamento <= 0:
            raise RegraNegocioError("Valor do pagamento deve ser positivo")
        if val_pagamento < consumo_do_pagamento(seq_pagamento):
            raise RegraNegocioError(
                "Valor não pode ficar abaixo do total já apropriado")
        pagamento.val_pagamento = val_pagamento.quantize(Decimal("0.01"))
    if dsc_pagamento is not None:
        pagamento.dsc_pagamento = dsc_pagamento.strip() or None
    if seq_qualificador is not None:
        pagamento.seq_qualificador = seq_qualificador
    pagamento.dat_alteracao = date.today()
    pagamento.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return pagamento


def excluir_pagamento(seq_pagamento: int, confirmado: bool = False) -> Pagamento:
    """Exclusão LÓGICA, com trava de apropriação (R6)."""
    pagamento = _get_ou_erro(seq_pagamento)
    if not confirmado:
        raise RegraNegocioError("Excluir pagamento exige confirmação explícita")
    if consumo_do_pagamento(seq_pagamento) > 0:
        raise RegraNegocioError(
            "Pagamento possui apropriações — estorne-as antes de excluir")
    pagamento.ind_status = 'I'
    pagamento.dat_alteracao = date.today()
    pagamento.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return pagamento


# ---------------------------------------------------------------------------
# Apropriação (R7/R8)
# ---------------------------------------------------------------------------

def consumo_do_pagamento(seq_pagamento: int) -> Decimal:
    """Σ apropriações − Σ estornos do pagamento (linhas-evento)."""
    total = Decimal("0.00")
    for evento in PagamentoLiberacao.query.filter_by(seq_pagamento=seq_pagamento).all():
        if evento.cod_tipo_evento == APROPRIACAO:
            total += Decimal(evento.val_apropriado)
        elif evento.cod_tipo_evento == ESTORNO:
            total -= Decimal(evento.val_apropriado)
    return total.quantize(Decimal("0.01"))


def candidatas_para(seq_pagamento: int) -> list[dict]:
    """Liberações candidatas: confirmadas, mesmo órgão/qualificador, com
    saldo, da fonte herdada (se houver) — mais antiga primeiro (R7/R8)."""
    pagamento = _get_ou_erro(seq_pagamento)
    if pagamento.seq_qualificador is None:
        return []  # legado sem qualificador não tem candidata (D1)

    q = (Liberacao.query
         .filter_by(ind_status='A', cod_situacao=SITUACAO_CONFIRMADA,
                    cod_orgao=pagamento.cod_orgao,
                    seq_qualificador=pagamento.seq_qualificador)
         .order_by(Liberacao.dat_liberacao))
    if pagamento.seq_fonte_recurso is not None:
        q = q.filter(Liberacao.seq_fonte_recurso == pagamento.seq_fonte_recurso)

    candidatas = []
    for liberacao in q.all():
        saldo = Decimal(liberacao.val_liberacao) - consumo_da_liberacao(liberacao.seq_liberacao)
        if saldo > 0:
            candidatas.append({'liberacao': liberacao, 'saldo_restante': saldo})
    return candidatas


def apropriar_pagamento(seq_pagamento: int,
                        apropriacoes: list[tuple[int, Decimal]]) -> Pagamento:
    """Aprova apropriações em lote — estouro PROIBIDO nos dois sentidos (R7)
    e fonte herdada da primeira liberação (R8)."""
    pagamento = _get_ou_erro(seq_pagamento)
    if not apropriacoes:
        raise RegraNegocioError("Nenhuma apropriação informada")

    disponivel_pagamento = (Decimal(pagamento.val_pagamento)
                            - consumo_do_pagamento(seq_pagamento))

    for seq_liberacao, valor in apropriacoes:
        valor = Decimal(valor)
        if valor <= 0:
            raise RegraNegocioError("Valor apropriado deve ser positivo")

        liberacao = Liberacao.query.get(seq_liberacao)
        if (liberacao is None or liberacao.ind_status != 'A'
                or liberacao.cod_situacao != SITUACAO_CONFIRMADA):
            raise RegraNegocioError("Liberação candidata inexistente ou não confirmada")
        if (liberacao.cod_orgao != pagamento.cod_orgao
                or liberacao.seq_qualificador != pagamento.seq_qualificador):
            raise RegraNegocioError(
                "Liberação não é candidata (órgão/qualificador diferentes)")
        # monofonte por herança (R8): a primeira estampa; as demais têm de bater
        if (pagamento.seq_fonte_recurso is not None
                and liberacao.seq_fonte_recurso != pagamento.seq_fonte_recurso):
            raise RegraNegocioError(
                "Pagamento é monofonte — liberação de fonte diferente da herdada")

        saldo_liberacao = (Decimal(liberacao.val_liberacao)
                           - consumo_da_liberacao(seq_liberacao))
        if valor > saldo_liberacao:
            raise RegraNegocioError(
                "Apropriação acima do saldo restante da liberação é proibida")
        if valor > disponivel_pagamento:
            raise RegraNegocioError(
                "Soma das apropriações excede o valor do pagamento")

        db.session.add(PagamentoLiberacao(
            seq_pagamento=seq_pagamento,
            seq_liberacao=seq_liberacao,
            cod_tipo_evento=APROPRIACAO,
            val_apropriado=valor.quantize(Decimal("0.01")),
            dat_evento=date.today(),
            cod_pessoa_evento=cod_pessoa_atual(),
        ))
        disponivel_pagamento -= valor
        if pagamento.seq_fonte_recurso is None:
            pagamento.seq_fonte_recurso = liberacao.seq_fonte_recurso

    pagamento.dat_alteracao = date.today()
    pagamento.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return pagamento


def estornar_apropriacao(seq_pagamento_liberacao: int) -> Pagamento:
    """Estorno = linha-evento 'E' que devolve saldo; zerar o consumo limpa a
    fonte herdada (R8). Edição/exclusão de apropriação não existem."""
    apropriacao = PagamentoLiberacao.query.get(seq_pagamento_liberacao)
    if apropriacao is None or apropriacao.cod_tipo_evento != APROPRIACAO:
        raise RegraNegocioError("Apropriação inexistente")
    pagamento = _get_ou_erro(apropriacao.seq_pagamento)

    db.session.add(PagamentoLiberacao(
        seq_pagamento=apropriacao.seq_pagamento,
        seq_liberacao=apropriacao.seq_liberacao,
        cod_tipo_evento=ESTORNO,
        val_apropriado=apropriacao.val_apropriado,
        dat_evento=date.today(),
        cod_pessoa_evento=cod_pessoa_atual(),
    ))
    db.session.flush()
    if consumo_do_pagamento(pagamento.seq_pagamento) == 0:
        pagamento.seq_fonte_recurso = None
    pagamento.dat_alteracao = date.today()
    pagamento.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return pagamento


def apropriacoes_do(seq_pagamento: int) -> list[PagamentoLiberacao]:
    return (PagamentoLiberacao.query
            .filter_by(seq_pagamento=seq_pagamento)
            .order_by(PagamentoLiberacao.seq_pagamento_liberacao)
            .all())
