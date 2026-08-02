"""Ciclo de vida do catálogo de fontes de recurso (spec fonte-recurso R1–R4).

CRUD com unicidade composta entre ativos, aprovação de auto-cadastradas,
inativação bloqueada por fundo ativo e o `obter_ou_criar_pendente` consumido
pelas cargas (fonte desconhecida nasce VINCULADA + pendente — errar para
baixo, nunca para cima).
"""
from datetime import date

from ..auth.contexto import cod_pessoa_atual
from ..models import FonteRecurso, Fundo
from ..models.base import db
from ..models.fonte_recurso import (
    IDENTIFICADORES_EXERCICIO,
    IND_LIVRE,
    IND_VINCULADA,
    ORIGEM_LOCAL,
    ORIGEM_STN,
)
from .validacao import RegraNegocioError

DSC_MAX = 200


def parsear_codigo(codigo: str) -> tuple[str, str, str | None]:
    """Decompõe um código de fonte em (identificador, fonte_stn, detalhamento).

    Aceita ``1.500``, ``1.500.0001`` e a forma curta de 3 dígitos (``500``),
    que assume o exercício corrente ('1') — é como a fonte costuma chegar nas
    cargas do sistema de origem.
    """
    partes = [p.strip() for p in (codigo or "").strip().split(".") if p.strip()]
    if len(partes) == 1 and len(partes[0]) == 3 and partes[0].isdigit():
        return "1", partes[0], None
    if len(partes) >= 2 and partes[0] in IDENTIFICADORES_EXERCICIO:
        detalhamento = ".".join(partes[2:]) or None
        return partes[0], partes[1], detalhamento
    raise RegraNegocioError(f"Código de fonte inválido: '{codigo}'")


def _validar(identificador: str, fonte_stn: str, dsc: str, vinculada: str) -> None:
    if identificador not in IDENTIFICADORES_EXERCICIO:
        raise RegraNegocioError("Identificador de exercício deve ser 1, 2 ou 9")
    if not (fonte_stn or "").isdigit() or len(fonte_stn) != 3:
        raise RegraNegocioError("Fonte STN deve ter exatamente 3 dígitos")
    if not (dsc or "").strip():
        raise RegraNegocioError("Descrição da fonte é obrigatória")
    if vinculada not in (IND_LIVRE, IND_VINCULADA):
        raise RegraNegocioError("Vinculação deve ser 'L' (livre) ou 'V' (vinculada)")


def _buscar_ativa(exercicio: int, identificador: str, fonte_stn: str,
                  detalhamento: str | None) -> FonteRecurso | None:
    return FonteRecurso.query.filter_by(
        num_exercicio_vigencia=exercicio,
        cod_identificador_exercicio=identificador,
        cod_fonte_stn=fonte_stn,
        cod_detalhamento=detalhamento,
        ind_status='A',
    ).first()


def _get_ou_erro(seq_fonte_recurso: int) -> FonteRecurso:
    fonte = FonteRecurso.query.get(seq_fonte_recurso)
    if fonte is None:
        raise RegraNegocioError("Fonte de recursos inexistente")
    return fonte


def criar_fonte(
    identificador: str,
    fonte_stn: str,
    dsc: str,
    exercicio: int,
    vinculada: str = IND_VINCULADA,
    detalhamento: str | None = None,
    grupo_destinacao: str | None = None,
    origem: str = ORIGEM_LOCAL,
    pendente: bool = False,
) -> FonteRecurso:
    """Cadastro de fonte — unicidade composta ENTRE ATIVOS (R1)."""
    identificador = (identificador or "").strip()
    fonte_stn = (fonte_stn or "").strip()
    detalhamento = (detalhamento or "").strip() or None
    _validar(identificador, fonte_stn, dsc, vinculada)
    if _buscar_ativa(exercicio, identificador, fonte_stn, detalhamento) is not None:
        raise RegraNegocioError(
            "Já existe fonte ativa com este código nesta vigência")

    fonte = FonteRecurso(
        cod_identificador_exercicio=identificador,
        cod_fonte_stn=fonte_stn,
        cod_detalhamento=detalhamento,
        num_exercicio_vigencia=int(exercicio),
        dsc_fonte_recurso=dsc.strip()[:DSC_MAX],
        ind_vinculada=vinculada,
        cod_origem_classificacao=origem if origem in (ORIGEM_STN, ORIGEM_LOCAL) else ORIGEM_LOCAL,
        dsc_grupo_destinacao=(grupo_destinacao or "").strip() or None,
        ind_pendente_revisao='S' if pendente else 'N',
        ind_status='A',
        cod_pessoa_inclusao=cod_pessoa_atual(),
    )
    db.session.add(fonte)
    db.session.commit()
    return fonte


def alterar_fonte(
    seq_fonte_recurso: int,
    dsc: str | None = None,
    vinculada: str | None = None,
    grupo_destinacao: str | None = None,
) -> FonteRecurso:
    """Altera descrição/vinculação/grupo; código e vigência são imutáveis (R1)."""
    fonte = _get_ou_erro(seq_fonte_recurso)
    if dsc is not None:
        if not dsc.strip():
            raise RegraNegocioError("Descrição da fonte é obrigatória")
        fonte.dsc_fonte_recurso = dsc.strip()[:DSC_MAX]
    if vinculada is not None:
        if vinculada not in (IND_LIVRE, IND_VINCULADA):
            raise RegraNegocioError("Vinculação deve ser 'L' (livre) ou 'V' (vinculada)")
        fonte.ind_vinculada = vinculada
    if grupo_destinacao is not None:
        fonte.dsc_grupo_destinacao = grupo_destinacao.strip() or None
    fonte.dat_alteracao = date.today()
    fonte.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return fonte


def aprovar_fonte(seq_fonte_recurso: int, vinculada: str | None = None) -> FonteRecurso:
    """Zera a pendência de uma fonte auto-cadastrada, com ajuste opcional."""
    fonte = _get_ou_erro(seq_fonte_recurso)
    if fonte.ind_pendente_revisao != 'S':
        raise RegraNegocioError("Fonte não está pendente de revisão")
    if vinculada is not None:
        if vinculada not in (IND_LIVRE, IND_VINCULADA):
            raise RegraNegocioError("Vinculação deve ser 'L' (livre) ou 'V' (vinculada)")
        fonte.ind_vinculada = vinculada
    fonte.ind_pendente_revisao = 'N'
    fonte.dat_alteracao = date.today()
    fonte.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return fonte


def inativar_fonte(seq_fonte_recurso: int) -> FonteRecurso:
    """Inativação bloqueada por fundo ativo apontando para a fonte (R6)."""
    fonte = _get_ou_erro(seq_fonte_recurso)
    tem_fundo = Fundo.query.filter_by(
        seq_fonte_recurso=seq_fonte_recurso, ind_status='A').first()
    if tem_fundo is not None:
        raise RegraNegocioError(
            "Fonte possui fundos ativos classificados nela e não pode ser inativada")
    fonte.ind_status = 'I'
    fonte.dat_alteracao = date.today()
    fonte.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return fonte


def listar_fontes(exercicio: int | None = None, status: str | None = None,
                  pendente: bool | None = None) -> list[FonteRecurso]:
    q = FonteRecurso.query
    if exercicio is not None:
        q = q.filter(FonteRecurso.num_exercicio_vigencia == exercicio)
    if status in ('ativo', 'inativo'):
        q = q.filter(FonteRecurso.ind_status == ('A' if status == 'ativo' else 'I'))
    if pendente is True:
        q = q.filter(FonteRecurso.ind_pendente_revisao == 'S')
    return q.order_by(
        FonteRecurso.num_exercicio_vigencia.desc(),
        FonteRecurso.cod_identificador_exercicio,
        FonteRecurso.cod_fonte_stn,
    ).all()


#: Chaves de atributo aceitas para a fonte, em ordem de prioridade (F9.2 D1).
CHAVES_ATRIBUTO_FONTE = ("fonte_recurso", "cod_fonte", "fonte")


def resolver_fonte_de_atributos(atributos: dict | None, exercicio: int) -> int | None:
    """Resolve a fonte de recursos dos `json_atributos` de uma linha de staging.

    Retorna o `seq_fonte_recurso` (auto-cadastrando pendente se preciso) ou
    None — a fonte é dimensão OPCIONAL: atributo ausente ou valor não
    parseável NUNCA bloqueia a classificação (spec automacao-lancamentos R17).
    """
    if not atributos:
        return None
    for chave in CHAVES_ATRIBUTO_FONTE:
        valor = atributos.get(chave)
        if valor is None or not str(valor).strip():
            continue
        try:
            return obter_ou_criar_pendente(str(valor), exercicio).seq_fonte_recurso
        except RegraNegocioError:
            return None  # valor sujo → sem fonte; lixo não vira fonte nova
    return None


def obter_ou_criar_pendente(codigo: str, exercicio: int,
                            dsc: str | None = None) -> FonteRecurso:
    """Operação interna para cargas (R4) — sem rota HTTP.

    Fonte existente ativa (qualquer estado de revisão) → retorna sem alterar.
    Inexistente → cria **VINCULADA + pendente de revisão** (nunca livre): errar
    para baixo na disponibilidade é prudência.
    """
    identificador, fonte_stn, detalhamento = parsear_codigo(codigo)
    existente = _buscar_ativa(exercicio, identificador, fonte_stn, detalhamento)
    if existente is not None:
        return existente
    return criar_fonte(
        identificador, fonte_stn,
        dsc or f"Fonte {identificador}.{fonte_stn} (auto-cadastrada)",
        exercicio,
        vinculada=IND_VINCULADA,
        detalhamento=detalhamento,
        origem=ORIGEM_LOCAL,
        pendente=True,
    )
