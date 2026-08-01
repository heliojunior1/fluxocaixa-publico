"""Fonte da projeção do DFC (spec relatorios R10/R12, design D1/D2/D4).

Resolve os números do cenário para a estratégia Projetado num contrato único:
`{(seq_qualificador | None, cod_tipo 'C'|'D', mes): Decimal}` do ano
consultado, mais a origem (`ao_vivo`, nome do cenário/versão).

Caminhos, na ordem: (1) última versão PUBLICADA do cenário em
`flc_projecao_valor`; (2) sem publicada, `executar_simulacao` ao vivo,
normalizada pelo MESMO `_montar_linhas_valor` que grava versões — os dois
caminhos produzem o mesmo shape por construção.

Sinal aplicado pela perna: 'C' preserva, 'D' nega. Desde a F6.2 (R6) **todo
motor devolve magnitude**, então o `abs()` de normalização aqui é redundante —
ficou como cinto de segurança para versões gravadas antes da convergência, que
podem ter valor assinado.

Cenário de periodicidade ANUAL: o total anual por qualificador é
redistribuído pelo perfil mensal do realizado do ano-base, EXCLUINDO
lançamentos de qualificador inativo (mesmo critério da árvore realizada —
correção portada da referência); sem histórico, 1/12.
"""
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import extract, func

from ...models import Lancamento, Qualificador, SimuladorCenario
from ...models.base import db
from ...repositories import projecao_versao_repository
from .. import periodo_resolver
from ..dominio_lancamento import TIPO_ENTRADA, TIPO_SAIDA, resolver_tipo
from ..validacao import RegraNegocioError

_UM_DOZE_AVOS = Decimal("1") / Decimal("12")
_TIPO_LANCAMENTO_POR_COD = {'C': TIPO_ENTRADA, 'D': TIPO_SAIDA}


def _dec(valor) -> Decimal:
    return Decimal(str(valor if valor is not None else 0))


def resolver_projecao(cenario_id: int, ano: int) -> tuple[dict, dict]:
    """Retorna (mapa {(seq|None, tipo, mes): Decimal já com sinal}, origem)."""
    cenario = SimuladorCenario.query.get(cenario_id)
    if cenario is None or cenario.ind_status != 'A':
        raise RegraNegocioError("Cenário de previsão não encontrado ou inativo.")

    # F6.3: a projeção é gravada no período da SUA periodicidade; o DFC é
    # mensal. O mês vem do resolver (`mes_do_periodo`), não de uma coluna.
    periodicidade = periodo_resolver.normalizar(
        cenario.cod_periodicidade or periodo_resolver.MENSAL)

    versao = projecao_versao_repository.get_ultima_publicada(cenario_id)
    if versao is not None:
        bruto = _mapa_da_versao(versao, ano, periodicidade)
        origem = {
            "ao_vivo": False,
            "nom_cenario": cenario.nom_cenario,
            "nom_versao": versao.nom_versao,
        }
    else:
        bruto = _mapa_ao_vivo(cenario_id, ano, periodicidade)
        origem = {
            "ao_vivo": True,
            "nom_cenario": cenario.nom_cenario,
            "nom_versao": None,
        }

    if periodicidade == periodo_resolver.ANUAL:
        bruto = _redistribuir_por_perfil(bruto, cenario.ano_base)

    mapa = {
        (seq, tipo, mes): (valor if tipo == 'C' else -valor).quantize(Decimal("0.01"))
        for (seq, tipo, mes), valor in bruto.items()
    }
    return mapa, origem


def _mapa_da_versao(versao, ano: int, periodicidade: str) -> dict:
    from ...models import ProjecaoValor

    linhas = ProjecaoValor.query.filter_by(
        seq_projecao_versao=versao.seq_projecao_versao, ano=ano
    ).all()
    bruto: dict = {}
    for linha in linhas:
        # ANUAL devolve mês `None` — a redistribuição por perfil logo adiante
        # é justamente quem transforma o total do ano em doze meses.
        mes = periodo_resolver.mes_do_periodo(periodicidade, linha.ano,
                                              linha.num_periodo)
        chave = (linha.seq_qualificador, linha.cod_tipo, mes)
        bruto[chave] = bruto.get(chave, Decimal("0")) + abs(_dec(linha.val_projetado))
    return bruto


def _mapa_ao_vivo(cenario_id: int, ano: int, periodicidade: str) -> dict:
    """Fallback sem versão publicada: simula agora e normaliza no mesmo shape."""
    from ..projecao_versao_service import _montar_linhas_valor
    from ..simulador_cenario_service import executar_simulacao

    try:
        resultado = executar_simulacao(cenario_id)
    except RegraNegocioError:
        raise
    except Exception as exc:  # simulador pode depender de libs de ML opcionais
        raise RegraNegocioError(
            "Não foi possível calcular a projeção ao vivo do cenário "
            f"selecionado ({type(exc).__name__}). Publique uma versão da "
            "projeção no simulador para usá-la no relatório."
        )
    if resultado is None:
        raise RegraNegocioError(
            "Não foi possível calcular a projeção do cenário selecionado."
        )
    bruto: dict = {}
    for linha in _montar_linhas_valor(0, resultado, periodicidade):
        if linha["ano"] != ano:
            continue
        mes = periodo_resolver.mes_do_periodo(periodicidade, linha["ano"],
                                              linha["num_periodo"])
        chave = (linha["seq_qualificador"], linha["cod_tipo"], mes)
        bruto[chave] = bruto.get(chave, Decimal("0")) + abs(_dec(linha["val_projetado"]))
    return bruto


# --------------------------------------------------------------------------
# Perfil mensal histórico (R12)
# --------------------------------------------------------------------------

def perfil_mensal_ativo(
    seq_qualificadores: list[int] | None,
    cod_tipo: str,
    ano_base: int | None,
) -> dict[int, Decimal]:
    """{mês: fração} do realizado do ano-base, só de qualificadores ativos.

    `seq_qualificadores=None` calcula o perfil do tipo inteiro (caso da
    projeção agregada). Sem realizado no ano-base ⇒ 1/12 uniforme.
    """
    if not ano_base:
        return {m: _UM_DOZE_AVOS for m in range(1, 13)}

    mes_col = extract("month", Lancamento.dat_lancamento)
    query = (
        db.session.query(mes_col.label("mes"),
                         func.sum(func.abs(Lancamento.valor_com_sinal)))
        .join(Qualificador,
              Qualificador.seq_qualificador == Lancamento.seq_qualificador)
        .filter(
            Lancamento.ind_status == 'A',
            Qualificador.ind_status == 'A',
            extract("year", Lancamento.dat_lancamento) == ano_base,
        )
    )
    if seq_qualificadores is not None:
        query = query.filter(Lancamento.seq_qualificador.in_(seq_qualificadores))
    else:
        tipo = resolver_tipo(_TIPO_LANCAMENTO_POR_COD[cod_tipo])
        query = query.filter(
            Lancamento.cod_tipo_lancamento == tipo.cod_tipo_lancamento
        )

    valores = {int(mes): _dec(total) for mes, total in query.group_by("mes").all()}
    total_ano = sum(valores.values(), Decimal("0"))
    if total_ano <= 0:
        return {m: _UM_DOZE_AVOS for m in range(1, 13)}
    return {m: valores.get(m, Decimal("0")) / total_ano for m in range(1, 13)}


def _redistribuir_por_perfil(bruto: dict, ano_base: int | None) -> dict:
    """Total anual de cada (qualificador, tipo) rateado pelo perfil mensal."""
    totais: dict = {}
    for (seq, tipo, _mes), valor in bruto.items():
        totais[(seq, tipo)] = totais.get((seq, tipo), Decimal("0")) + valor

    redistribuido: dict = {}
    for (seq, tipo), total in totais.items():
        perfil = perfil_mensal_ativo([seq] if seq is not None else None,
                                     tipo, ano_base)
        for mes in range(1, 13):
            redistribuido[(seq, tipo, mes)] = (total * perfil[mes]).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
    return redistribuido
