"""Dotação + créditos adicionais (spec execucao-orcamentaria R1–R3)."""
from datetime import date
from decimal import Decimal

from ..auth.contexto import cod_pessoa_atual
from ..models import CreditoAdicional, Dotacao, Qualificador
from ..models.base import db
from ..models.dotacao import TIPO_CREDITO_REDUCAO, TIPOS_CREDITO_SOMA
from .validacao import RegraNegocioError

ZERO = Decimal("0.00")


def _validar_qualificador(seq_qualificador: int) -> Qualificador:
    qualificador = Qualificador.query.get(seq_qualificador)
    if qualificador is None or qualificador.ind_status != 'A' or not qualificador.is_folha():
        raise RegraNegocioError("Qualificador da dotação deve ser folha ativa")
    if qualificador.tipo_fluxo != 'despesa':
        raise RegraNegocioError("Dotação é de despesa — qualificador de receita não é aceito")
    return qualificador


def dotacao_de(num_ano: int, seq_qualificador: int) -> Dotacao | None:
    return Dotacao.query.filter_by(
        num_ano=num_ano, seq_qualificador=seq_qualificador, ind_status='A').first()


def criar_dotacao(num_ano: int, seq_qualificador: int,
                  val_dotacao_inicial: Decimal,
                  commit: bool = True) -> Dotacao:
    _validar_qualificador(seq_qualificador)
    if Decimal(val_dotacao_inicial) < 0:
        raise RegraNegocioError("Valor da dotação inicial não pode ser negativo")
    if dotacao_de(num_ano, seq_qualificador) is not None:
        raise RegraNegocioError("Já existe dotação ativa para este ano e qualificador")
    dotacao = Dotacao(
        num_ano=num_ano, seq_qualificador=seq_qualificador,
        val_dotacao_inicial=Decimal(val_dotacao_inicial).quantize(Decimal("0.01")),
        ind_status='A', cod_pessoa_inclusao=cod_pessoa_atual())
    db.session.add(dotacao)
    if commit:
        db.session.commit()
    else:
        # lote de importação atômico (importacao-arquivos R8)
        db.session.flush()
    return dotacao


def somar_eventos(inicial: Decimal, eventos: list[tuple[str, Decimal]]) -> Decimal:
    """Inicial + créditos (S/E/X) − reduções (R) — a aritmética pura do R2."""
    total = Decimal(inicial)
    for tipo, valor in eventos:
        if tipo == TIPO_CREDITO_REDUCAO:
            total -= Decimal(valor)
        else:
            total += Decimal(valor)
    return total.quantize(Decimal("0.01"))


def dotacao_atualizada(dotacao: Dotacao) -> Decimal:
    """SEMPRE derivada dos eventos (R2) — nunca coluna."""
    eventos = [(c.cod_tipo_credito, Decimal(c.val_credito))
               for c in CreditoAdicional.query.filter_by(
                   seq_dotacao=dotacao.seq_dotacao, ind_status='A').all()]
    return somar_eventos(Decimal(dotacao.val_dotacao_inicial), eventos)


def registrar_credito(seq_dotacao: int, cod_tipo_credito: str,
                      val_credito: Decimal, dat_credito: date,
                      dsc_referencia_ato: str) -> CreditoAdicional:
    """Evento imutável (R1) — corrigir é lançar o evento contrário."""
    dotacao = Dotacao.query.get(seq_dotacao)
    if dotacao is None or dotacao.ind_status != 'A':
        raise RegraNegocioError("Dotação inexistente ou inativa")
    if cod_tipo_credito not in TIPOS_CREDITO_SOMA + (TIPO_CREDITO_REDUCAO,):
        raise RegraNegocioError("Tipo de crédito inválido")
    if Decimal(val_credito) <= 0:
        raise RegraNegocioError("Valor do crédito deve ser positivo")
    if not (dsc_referencia_ato or "").strip():
        raise RegraNegocioError("Referência do ato (lei/decreto) é obrigatória")
    if cod_tipo_credito == TIPO_CREDITO_REDUCAO and \
            Decimal(val_credito) > dotacao_atualizada(dotacao):
        raise RegraNegocioError(
            "Redução acima da dotação atualizada — a dotação não pode ficar negativa")

    credito = CreditoAdicional(
        seq_dotacao=seq_dotacao, cod_tipo_credito=cod_tipo_credito,
        val_credito=Decimal(val_credito).quantize(Decimal("0.01")),
        dat_credito=dat_credito,
        dsc_referencia_ato=dsc_referencia_ato.strip()[:120],
        ind_status='A', cod_pessoa_inclusao=cod_pessoa_atual())
    db.session.add(credito)
    db.session.commit()
    return credito


def teto_do_autorizado(num_ano: int, seq_qualificador: int) -> Decimal | None:
    """Dotação atualizada quando houver; senão a LOA (R3) — origem única do
    teto da F7.3a."""
    from .previsto_loa_service import loa_do_qualificador

    dotacao = dotacao_de(num_ano, seq_qualificador)
    if dotacao is not None:
        return dotacao_atualizada(dotacao)
    return loa_do_qualificador(num_ano, seq_qualificador)


def visao_do_ano(num_ano: int) -> list[dict]:
    """Inicial × Σ créditos × Σ reduções × atualizada por qualificador."""
    linhas = []
    for dotacao in Dotacao.query.filter_by(num_ano=num_ano, ind_status='A').all():
        somas = ZERO
        reducoes = ZERO
        for credito in CreditoAdicional.query.filter_by(
                seq_dotacao=dotacao.seq_dotacao, ind_status='A').all():
            if credito.cod_tipo_credito == TIPO_CREDITO_REDUCAO:
                reducoes += Decimal(credito.val_credito)
            else:
                somas += Decimal(credito.val_credito)
        linhas.append({
            'dotacao': dotacao,
            'creditos': somas.quantize(Decimal("0.01")),
            'reducoes': reducoes.quantize(Decimal("0.01")),
            'atualizada': dotacao_atualizada(dotacao),
        })
    linhas.sort(key=lambda item: item['dotacao'].qualificador.num_qualificador)
    return linhas
