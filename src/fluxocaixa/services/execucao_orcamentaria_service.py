"""Execução orçamentária E/L/P (spec execucao-orcamentaria R4–R7)."""
from datetime import date
from decimal import Decimal

from ..auth.contexto import cod_pessoa_atual
from ..models import ExecucaoEvento, ExecucaoOrcamentaria, Orgao, Qualificador
from ..models.base import db
from ..models.execucao_orcamentaria import (
    ESTAGIO_EMPENHO,
    ESTAGIO_LIQUIDACAO,
    ESTAGIO_PAGAMENTO,
    EVENTO_ANULACAO,
    EVENTO_INSCRICAO,
    EVENTO_REFORCO,
    PAI_DO_ESTAGIO,
)
from .validacao import RegraNegocioError

ZERO = Decimal("0.00")
NOMES_ESTAGIO = {ESTAGIO_EMPENHO: "empenho", ESTAGIO_LIQUIDACAO: "liquidação",
                 ESTAGIO_PAGAMENTO: "pagamento orçamentário"}


def validar_cadeia(cod_estagio: str, estagio_do_pai: str | None) -> None:
    """Cadeia estrita E→L→P (R4) — função pura, unit-testada."""
    if cod_estagio not in NOMES_ESTAGIO:
        raise RegraNegocioError("Estágio da execução inválido (use E, L ou P)")
    exigido = PAI_DO_ESTAGIO.get(cod_estagio)
    if exigido is None:
        if estagio_do_pai is not None:
            raise RegraNegocioError("Empenho não referencia documento-pai")
        return
    if estagio_do_pai != exigido:
        raise RegraNegocioError(
            f"{NOMES_ESTAGIO[cod_estagio].capitalize()} deve referenciar "
            f"um(a) {NOMES_ESTAGIO[exigido]} ativo(a)")


def valor_corrente(seq_execucao: int) -> Decimal:
    """Σ I + Σ R − Σ A — SEMPRE derivado (R4)."""
    total = ZERO
    for evento in ExecucaoEvento.query.filter_by(
            seq_execucao=seq_execucao, ind_status='A').all():
        valor = Decimal(evento.val_evento)
        total += -valor if evento.cod_tipo_evento == EVENTO_ANULACAO else valor
    return total.quantize(Decimal("0.01"))


def consumido_pelos_filhos(seq_execucao: int) -> Decimal:
    total = ZERO
    for filho in ExecucaoOrcamentaria.query.filter_by(
            seq_documento_pai=seq_execucao, ind_status='A').all():
        total += valor_corrente(filho.seq_execucao)
    return total.quantize(Decimal("0.01"))


def _evento(documento: ExecucaoOrcamentaria, tipo: str, valor: Decimal,
            dat_evento: date, referencia: str | None = None) -> None:
    db.session.add(ExecucaoEvento(
        seq_execucao=documento.seq_execucao, cod_tipo_evento=tipo,
        val_evento=Decimal(valor).quantize(Decimal("0.01")),
        dat_evento=dat_evento, dsc_referencia=referencia,
        ind_status='A', cod_pessoa_inclusao=cod_pessoa_atual()))


def registrar_documento(cod_estagio: str, num_documento: str, num_ano: int,
                        cod_orgao: int, seq_qualificador: int,
                        val_documento: Decimal, dat_documento: date,
                        codigo_fonte: str | None = None,
                        num_documento_pai: str | None = None) -> ExecucaoOrcamentaria:
    """Documento + evento I na MESMA transação (R4–R6)."""
    from .fonte_recurso_service import obter_ou_criar_pendente

    pai = None
    if num_documento_pai:
        # busca por número em qualquer estágio: pai de estágio ERRADO deve
        # falhar como violação de cadeia (R4), não como "não encontrado"
        pai = ExecucaoOrcamentaria.query.filter_by(
            num_documento=num_documento_pai, num_ano=num_ano,
            ind_status='A').first()
        if pai is None:
            raise RegraNegocioError(
                f"Documento-pai '{num_documento_pai}' não encontrado no ano {num_ano}")
    validar_cadeia(cod_estagio, pai.cod_estagio if pai else None)
    if PAI_DO_ESTAGIO.get(cod_estagio) and pai is None:
        raise RegraNegocioError(
            f"{NOMES_ESTAGIO[cod_estagio].capitalize()} exige o documento-pai")

    if Decimal(val_documento) <= 0:
        raise RegraNegocioError("Valor do documento deve ser positivo")
    if ExecucaoOrcamentaria.query.filter_by(
            cod_estagio=cod_estagio, num_documento=num_documento,
            num_ano=num_ano, ind_status='A').first() is not None:
        raise RegraNegocioError(
            f"Documento '{num_documento}' já existe no estágio e ano")
    orgao = Orgao.query.get(cod_orgao)
    if orgao is None or orgao.ind_status != 'A':
        raise RegraNegocioError("Órgão inexistente ou inativo")
    qualificador = Qualificador.query.get(seq_qualificador)
    if qualificador is None or qualificador.ind_status != 'A' or not qualificador.is_folha():
        raise RegraNegocioError("Qualificador do documento deve ser folha ativa")
    if qualificador.tipo_fluxo != 'despesa':
        raise RegraNegocioError("Execução orçamentária é de despesa")

    # fonte: código cru → catálogo com auto-cadastro pendente (R6); filho sem
    # fonte herda a do pai; divergente é recusada (monofonte na cadeia)
    seq_fonte = None
    if codigo_fonte:
        seq_fonte = obter_ou_criar_pendente(codigo_fonte, num_ano).seq_fonte_recurso
    if pai is not None:
        if seq_fonte is None:
            seq_fonte = pai.seq_fonte_recurso
        elif pai.seq_fonte_recurso is not None and seq_fonte != pai.seq_fonte_recurso:
            raise RegraNegocioError(
                "Fonte do documento diverge da fonte do documento-pai")

    if pai is not None:
        disponivel = valor_corrente(pai.seq_execucao) - consumido_pelos_filhos(pai.seq_execucao)
        if Decimal(val_documento) > disponivel:
            raise RegraNegocioError(
                f"Valor excede o saldo do documento-pai (disponível R$ {disponivel})")

    documento = ExecucaoOrcamentaria(
        cod_estagio=cod_estagio, num_documento=num_documento.strip()[:30],
        num_ano=num_ano, cod_orgao=cod_orgao, seq_qualificador=seq_qualificador,
        seq_fonte_recurso=seq_fonte,
        seq_documento_pai=pai.seq_execucao if pai else None,
        dat_documento=dat_documento, ind_status='A',
        cod_pessoa_inclusao=cod_pessoa_atual())
    db.session.add(documento)
    db.session.flush()
    _evento(documento, EVENTO_INSCRICAO, val_documento, dat_documento)
    db.session.commit()
    return documento


def registrar_evento(seq_execucao: int, cod_tipo_evento: str, val_evento: Decimal,
                     dat_evento: date, referencia: str | None = None) -> None:
    """Reforço/anulação — imutáveis; guardas de estouro nos DOIS sentidos (R5)."""
    documento = ExecucaoOrcamentaria.query.get(seq_execucao)
    if documento is None or documento.ind_status != 'A':
        raise RegraNegocioError("Documento inexistente ou inativo")
    if cod_tipo_evento not in (EVENTO_REFORCO, EVENTO_ANULACAO):
        raise RegraNegocioError("Tipo de evento inválido (use R ou A)")
    if Decimal(val_evento) <= 0:
        raise RegraNegocioError("Valor do evento deve ser positivo")

    corrente = valor_corrente(seq_execucao)
    if cod_tipo_evento == EVENTO_ANULACAO:
        piso = consumido_pelos_filhos(seq_execucao)
        if corrente - Decimal(val_evento) < piso:
            raise RegraNegocioError(
                "Anulação deixaria o documento abaixo do consumido pelos "
                f"documentos-filho (R$ {piso})")
    elif documento.seq_documento_pai is not None:
        disponivel = (valor_corrente(documento.seq_documento_pai)
                      - consumido_pelos_filhos(documento.seq_documento_pai))
        if Decimal(val_evento) > disponivel:
            raise RegraNegocioError(
                f"Reforço excede o saldo do documento-pai (disponível R$ {disponivel})")

    _evento(documento, cod_tipo_evento, val_evento, dat_evento, referencia)
    db.session.commit()


def liquidado_nao_pago(num_ano: int) -> dict:
    """Σ correntes das L − Σ correntes das P filhas — derivado (R7), por
    órgão e total; é o número que a F8.4 consome."""
    por_orgao: dict = {}
    total = ZERO
    for liquidacao in ExecucaoOrcamentaria.query.filter_by(
            cod_estagio=ESTAGIO_LIQUIDACAO, num_ano=num_ano, ind_status='A').all():
        pendente = (valor_corrente(liquidacao.seq_execucao)
                    - consumido_pelos_filhos(liquidacao.seq_execucao))
        por_orgao[liquidacao.cod_orgao] = por_orgao.get(liquidacao.cod_orgao, ZERO) + pendente
        total += pendente
    return {'por_orgao': {k: v.quantize(Decimal("0.01")) for k, v in por_orgao.items()},
            'total': total.quantize(Decimal("0.01"))}


def liquidado_nao_pago_do(num_ano: int, cod_orgao: int,
                          seq_qualificador: int) -> Decimal | None:
    """Estoque de liquidado não pago do recorte (F8.4) — None quando NÃO há
    liquidação importada (órgão fora do funil não ganha atrito)."""
    liquidacoes = ExecucaoOrcamentaria.query.filter_by(
        cod_estagio=ESTAGIO_LIQUIDACAO, num_ano=num_ano, cod_orgao=cod_orgao,
        seq_qualificador=seq_qualificador, ind_status='A').all()
    if not liquidacoes:
        return None
    total = ZERO
    for liquidacao in liquidacoes:
        total += (valor_corrente(liquidacao.seq_execucao)
                  - consumido_pelos_filhos(liquidacao.seq_execucao))
    return total.quantize(Decimal("0.01"))


def fontes_do_liquidado(num_ano: int, cod_orgao: int,
                        seq_qualificador: int) -> set[int]:
    """Fontes estampadas nas liquidações PENDENTES (> 0) do recorte (F8.4)."""
    fontes = set()
    for liquidacao in ExecucaoOrcamentaria.query.filter_by(
            cod_estagio=ESTAGIO_LIQUIDACAO, num_ano=num_ano, cod_orgao=cod_orgao,
            seq_qualificador=seq_qualificador, ind_status='A').all():
        pendente = (valor_corrente(liquidacao.seq_execucao)
                    - consumido_pelos_filhos(liquidacao.seq_execucao))
        if pendente > 0 and liquidacao.seq_fonte_recurso is not None:
            fontes.add(liquidacao.seq_fonte_recurso)
    return fontes


def funil_do_ano(num_ano: int) -> dict:
    """Empenhado × liquidado × pago × liquidado não pago (R7)."""
    somas = {ESTAGIO_EMPENHO: ZERO, ESTAGIO_LIQUIDACAO: ZERO, ESTAGIO_PAGAMENTO: ZERO}
    documentos = ExecucaoOrcamentaria.query.filter_by(
        num_ano=num_ano, ind_status='A').all()
    for documento in documentos:
        somas[documento.cod_estagio] += valor_corrente(documento.seq_execucao)
    return {
        'empenhado': somas[ESTAGIO_EMPENHO].quantize(Decimal("0.01")),
        'liquidado': somas[ESTAGIO_LIQUIDACAO].quantize(Decimal("0.01")),
        'pago': somas[ESTAGIO_PAGAMENTO].quantize(Decimal("0.01")),
        'liquidado_nao_pago': liquidado_nao_pago(num_ano)['total'],
        'documentos': documentos,
    }
