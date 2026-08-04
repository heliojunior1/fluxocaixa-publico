"""Repartição da projeção por grupo de fonte (spec fonte-recurso R8–R9).

`definir_reparticao` grava o CONJUNTO atômico (soma = 100); `repartir_valor`
distribui um valor pelos grupos L/V/N (não classificado = conservador, fora
do veredicto da F7.2); `sugestao_do_historico` calcula os percentuais
observados nos lançamentos estampados por fonte (F9.2) — sugestão de tela,
gravar é decisão humana.
"""
from datetime import date
from decimal import Decimal

from ..auth.contexto import cod_pessoa_atual
from ..models import FonteRecurso, Lancamento, Qualificador, QualificadorFonte
from ..models.base import db
from ..models.fonte_recurso import GRUPO_LIVRE, GRUPO_VINCULADO
from .validacao import RegraNegocioError

#: Grupo do que não tem repartição — fora do veredicto autorizativo (F7.2).
GRUPO_NAO_CLASSIFICADO = 'N'

CEM = Decimal(100)


def reparticoes_de(seq_qualificador: int, vigencia: int) -> list[QualificadorFonte]:
    return (QualificadorFonte.query
            .filter_by(seq_qualificador=seq_qualificador,
                       num_ano_vigencia=vigencia, ind_status='A')
            .all())


def definir_reparticao(seq_qualificador: int, vigencia: int,
                       percentuais: list[tuple[int, Decimal]]) -> list[QualificadorFonte]:
    """Substitui o conjunto do (qualificador, vigência) — atômico (R8)."""
    qualificador = Qualificador.query.get(seq_qualificador)
    if qualificador is None or qualificador.ind_status != 'A' or not qualificador.is_folha():
        raise RegraNegocioError("Repartição exige qualificador folha ativo")
    if qualificador.tipo_fluxo != 'receita':
        raise RegraNegocioError("Repartição é de qualificador de receita")
    if not percentuais:
        raise RegraNegocioError("Nenhum percentual informado")

    soma = Decimal(0)
    for seq_fonte, pct in percentuais:
        pct = Decimal(pct)
        if pct <= 0:
            raise RegraNegocioError("Percentual deve ser positivo")
        fonte = FonteRecurso.query.get(seq_fonte)
        if fonte is None or fonte.ind_status != 'A':
            raise RegraNegocioError("Fonte de recursos inexistente ou inativa")
        soma += pct
    if soma != CEM:
        raise RegraNegocioError(
            "A soma dos percentuais da repartição deve ser exatamente 100")

    # substituição atômica: inativa o conjunto anterior e grava o novo
    for antiga in reparticoes_de(seq_qualificador, vigencia):
        antiga.ind_status = 'I'
        antiga.dat_alteracao = date.today()
        antiga.cod_pessoa_alteracao = cod_pessoa_atual()

    novas = []
    for seq_fonte, pct in percentuais:
        nova = QualificadorFonte(
            seq_qualificador=seq_qualificador,
            seq_fonte_recurso=seq_fonte,
            pct_reparticao=Decimal(pct).quantize(Decimal("0.0001")),
            num_ano_vigencia=vigencia,
            ind_status='A',
            cod_pessoa_inclusao=cod_pessoa_atual(),
        )
        db.session.add(nova)
        novas.append(nova)
    db.session.commit()
    return novas


def repartir_valor(seq_qualificador: int, vigencia: int, valor: Decimal) -> dict:
    """Distribui `valor` pelos grupos 'L'/'V'/'N' (R9). Sem repartição → 'N'
    integral — NUNCA livre (conservador, fora do veredicto)."""
    valor = Decimal(valor)
    grupos = {GRUPO_LIVRE: Decimal("0.00"), GRUPO_VINCULADO: Decimal("0.00"),
              GRUPO_NAO_CLASSIFICADO: Decimal("0.00")}

    reparticoes = reparticoes_de(seq_qualificador, vigencia)
    if not reparticoes:
        grupos[GRUPO_NAO_CLASSIFICADO] = valor.quantize(Decimal("0.01"))
        return grupos

    for reparticao in reparticoes:
        fonte = FonteRecurso.query.get(reparticao.seq_fonte_recurso)
        parcela = (valor * Decimal(reparticao.pct_reparticao) / CEM)
        grupos[fonte.grupo] += parcela
    for grupo in (GRUPO_LIVRE, GRUPO_VINCULADO):
        grupos[grupo] = grupos[grupo].quantize(Decimal("0.01"))
    return grupos


def sugestao_do_historico(seq_qualificador: int) -> list[dict]:
    """Percentuais observados nos lançamentos estampados por fonte (F9.2).

    Magnitudes (o sinal não interessa à repartição); lançamento sem fonte
    fica fora da base. Sugestão de TELA — gravar é decisão humana (D3).
    """
    lancamentos = (Lancamento.query
                   .filter(Lancamento.seq_qualificador == seq_qualificador,
                           Lancamento.ind_status == 'A',
                           Lancamento.seq_fonte_recurso.isnot(None))
                   .all())
    por_fonte: dict = {}
    total = Decimal(0)
    for lancamento in lancamentos:
        magnitude = abs(Decimal(lancamento.val_lancamento))
        por_fonte[lancamento.seq_fonte_recurso] = (
            por_fonte.get(lancamento.seq_fonte_recurso, Decimal(0)) + magnitude)
        total += magnitude
    if total == 0:
        return []
    return [
        {'seq_fonte_recurso': seq_fonte,
         'pct': (soma / total * CEM).quantize(Decimal("0.01"))}
        for seq_fonte, soma in sorted(por_fonte.items())
    ]
