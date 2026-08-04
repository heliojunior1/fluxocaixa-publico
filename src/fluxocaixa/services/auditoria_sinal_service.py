"""Auditoria de coerência entre sinal e tipo de lançamento (spec R7, F6.1a).

Serviu à F6.1a para dimensionar a migração; na F6.1b passou a ser o **vigia do
invariante**. Os dois motivos sobreviveram intactos ao flip, só mudou a
condição — no modelo novo o sinal vive no tipo, então:

    RECEITA_NEGATIVA  ≡  tipo 'C' com val_lancamento < 0
    DESPESA_POSITIVA  ≡  tipo 'D' com val_lancamento < 0  (pois -(-x) = +x)

Ou seja: as duas formas continuam sendo "o valor com sinal contradiz o tipo".
Desde a F6.1b `val_lancamento` deveria ser sempre positivo (invariante do
serviço e do DTO), então qualquer linha aqui só pode ter entrado por escrita
direta no banco.

Esta auditoria **apenas reporta**. Não altera, não inativa, não corrige.
"""
from decimal import Decimal

from sqlalchemy import extract, or_

from ..models import Lancamento
from ..models.base import db
from .dominio_lancamento import TIPO_ENTRADA, TIPO_SAIDA, resolver_tipo

MOTIVO_RECEITA_NEGATIVA = 'RECEITA_NEGATIVA'
MOTIVO_DESPESA_POSITIVA = 'DESPESA_POSITIVA'


def auditar_coerencia_sinal_tipo(
    seq_conta: int | None = None,
    ano: int | None = None,
    limite_amostra: int = 50,
) -> dict:
    """Lançamentos ativos cujo sinal do valor discorda do tipo.

    Args:
        seq_conta: restringe a uma conta (opcional).
        ano: restringe a um exercício (opcional).
        limite_amostra: tamanho máximo da amostra retornada.

    Returns:
        `{total, por_motivo, amostra}` — `amostra` com seq, data, valor,
        qualificador e motivo por linha. Somente leitura.
    """
    cod_entrada = resolver_tipo(TIPO_ENTRADA).cod_tipo_lancamento
    cod_saida = resolver_tipo(TIPO_SAIDA).cod_tipo_lancamento

    query = db.session.query(Lancamento).filter(Lancamento.ind_status == 'A')
    if seq_conta is not None:
        query = query.filter(Lancamento.seq_conta == seq_conta)
    if ano is not None:
        query = query.filter(extract('year', Lancamento.dat_lancamento) == ano)

    # Valor negativo é a única forma de incoerência no modelo 'C'/'D': o sinal
    # do fluxo vem do tipo, então val_lancamento < 0 contradiz o tipo em ambos.
    incoerentes = query.filter(
        Lancamento.val_lancamento < 0,
        or_(Lancamento.cod_tipo_lancamento == cod_entrada,
            Lancamento.cod_tipo_lancamento == cod_saida),
    ).order_by(Lancamento.dat_lancamento, Lancamento.seq_lancamento).all()

    por_motivo = {MOTIVO_RECEITA_NEGATIVA: 0, MOTIVO_DESPESA_POSITIVA: 0}
    amostra = []
    for lancamento in incoerentes:
        motivo = (
            MOTIVO_RECEITA_NEGATIVA
            if lancamento.cod_tipo_lancamento == cod_entrada
            else MOTIVO_DESPESA_POSITIVA
        )
        por_motivo[motivo] += 1
        if len(amostra) < limite_amostra:
            amostra.append({
                'seq_lancamento': lancamento.seq_lancamento,
                'dat_lancamento': lancamento.dat_lancamento,
                'val_lancamento': Decimal(str(lancamento.val_lancamento)),
                'seq_qualificador': lancamento.seq_qualificador,
                'num_qualificador': (
                    lancamento.qualificador.num_qualificador
                    if lancamento.qualificador else None
                ),
                'motivo': motivo,
            })

    return {
        'total': len(incoerentes),
        'por_motivo': por_motivo,
        'amostra': amostra,
    }


__all__ = [
    'MOTIVO_DESPESA_POSITIVA',
    'MOTIVO_RECEITA_NEGATIVA',
    'auditar_coerencia_sinal_tipo',
]
