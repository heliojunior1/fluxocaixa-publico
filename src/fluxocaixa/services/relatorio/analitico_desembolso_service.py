"""Painel analítico do desembolso (spec desembolso R26).

Somente leitura sobre dados derivados — nenhuma tabela, nenhum snapshot.
⚠️ O pendente NUNCA é recalculado com fórmula própria: o pago de cada
liberação vem de `consumo_da_liberacao` (F7.1a, origem única) — o risco
clássico de um painel gerencial é o número divergir da tela transacional.
"""
from datetime import date
from decimal import Decimal

from ...models import Liberacao, PagamentoLiberacao
from ...models.liberacao import (
    APROPRIACAO,
    ESTORNO,
    SITUACAO_CONFIRMADA,
)

ZERO = Decimal("0.00")

NOMES_NATUREZA = {
    'D': 'Discricionária',
    'O': 'Constitucional/legal',
    'J': 'Judicial',
    'F': 'Folha',
    'V': 'Dívida',
}
NOMES_GRUPO = {'L': 'Livre', 'V': 'Vinculado'}


def evolucao_mensal(confirmacoes: list[tuple[date, Decimal]],
                    eventos: list[tuple[date, str, Decimal]],
                    ano: int) -> dict:
    """{mes: pendente acumulado ao fim do mês} — função pura (R26).

    Confirmações posicionadas pela data da liberação, apropriações/estornos
    pela data do evento (mesmo critério temporal da visão de controle da
    conferência F7.1c).
    """
    resultado = {}
    for mes in range(1, 13):
        fim = date(ano, mes + 1, 1) if mes < 12 else date(ano + 1, 1, 1)
        liberado = sum((valor for dat, valor in confirmacoes if dat < fim), ZERO)
        consumido = ZERO
        for dat, tipo, valor in eventos:
            if dat >= fim:
                continue
            consumido += valor if tipo == APROPRIACAO else -valor
        resultado[mes] = (liberado - consumido).quantize(Decimal("0.01"))
    return resultado


def dados_analitico(ano: int) -> dict:
    """As três visões do painel, tudo derivado na leitura."""
    from ..liberacao_service import consumo_da_liberacao

    confirmadas = [
        liberacao for liberacao in Liberacao.query.filter_by(
            ind_status='A', cod_situacao=SITUACAO_CONFIRMADA).all()
        if liberacao.dat_liberacao.year == ano
    ]

    por_orgao: dict = {}
    por_natureza: dict = {}
    por_grupo: dict = {}
    confirmacoes = []
    eventos = []
    total_liberado = ZERO

    for liberacao in confirmadas:
        valor = Decimal(liberacao.val_liberacao)
        pago = consumo_da_liberacao(liberacao.seq_liberacao)
        total_liberado += valor

        linha = por_orgao.setdefault(
            liberacao.cod_orgao, {'liberado': ZERO, 'pago': ZERO})
        linha['liberado'] += valor
        linha['pago'] += pago

        por_natureza[liberacao.cod_natureza_obrigacao] = \
            por_natureza.get(liberacao.cod_natureza_obrigacao, ZERO) + valor
        grupo = liberacao.fonte_recurso.grupo
        por_grupo[grupo] = por_grupo.get(grupo, ZERO) + valor

        confirmacoes.append((liberacao.dat_liberacao, valor))
        for evento in PagamentoLiberacao.query.filter_by(
                seq_liberacao=liberacao.seq_liberacao).all():
            if evento.cod_tipo_evento in (APROPRIACAO, ESTORNO):
                eventos.append((evento.dat_evento, evento.cod_tipo_evento,
                                Decimal(evento.val_apropriado)))

    def _pct(valor: Decimal) -> Decimal | None:
        if total_liberado == 0:
            return None
        return (valor / total_liberado * 100).quantize(Decimal("0.01"))

    return {
        'ano': ano,
        'total_liberado': total_liberado.quantize(Decimal("0.01")),
        'por_orgao': {
            cod: {
                'liberado': linha['liberado'].quantize(Decimal("0.01")),
                'pago': linha['pago'].quantize(Decimal("0.01")),
                'pendente': (linha['liberado'] - linha['pago']).quantize(Decimal("0.01")),
            }
            for cod, linha in sorted(por_orgao.items())
        },
        'por_natureza': {
            natureza: {'liberado': valor.quantize(Decimal("0.01")),
                       'pct': _pct(valor),
                       'nome': NOMES_NATUREZA.get(natureza, natureza)}
            for natureza, valor in sorted(por_natureza.items())
        },
        'por_grupo_fonte': {
            grupo: {'liberado': valor.quantize(Decimal("0.01")),
                    'pct': _pct(valor),
                    'nome': NOMES_GRUPO.get(grupo, grupo)}
            for grupo, valor in sorted(por_grupo.items())
        },
        'evolucao_pendente': evolucao_mensal(confirmacoes, eventos, ano),
    }
