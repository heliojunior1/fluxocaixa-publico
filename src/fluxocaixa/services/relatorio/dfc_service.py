"""DFC (Demonstração de Fluxo de Caixa) service - Cash Flow Statement.

Estratégia Projetado (spec relatorios R9–R13, F5.2): a árvore realizada é
montada como sempre e a projeção do cenário é aplicada como PÓS-PROCESSO —
folhas recebem o projetado, pais são recompostos em pós-ordem, totais e
saldos recalculados. Mês fechado nunca é tocado (R9). Quando a estratégia é
Projetado, o relatório ganha uma coluna TOTAIS (a visão mensal de mês aberto
projeta o TOTAL do mês — dias zerados — e precisa de onde exibi-lo, como na
referência); no Realizado o layout permanece o de sempre.
"""
import calendar
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import extract

from ...models import Lancamento, Qualificador
from ...repositories import qualificador_repository
from ...repositories.lancamento_repository import LancamentoRepository
from ...repositories.saldo_conta_repository import SaldoContaRepository
from ...utils.constants import DAY_ABBR_PT, MONTH_ABBR_PT, MONTH_NAME_PT
from ..validacao import RegraNegocioError

ROTULO_LINHA_SINTETICA = "Projeção do cenário (não detalhada)"


def _e_projetado(estrategia: str | None) -> bool:
    return (estrategia or "").strip().lower() == "projetado"


def get_dfc_data(
    periodo: str,
    ano_selecionado: int,
    mes_selecionado: int | None,
    meses_selecionados: list[int],
    estrategia: str,
    cenario_selecionado_id: int | None
) -> dict:
    """Get DFC (Cash Flow Statement) data.

    Args:
        periodo: 'mes' or 'ano'
        ano_selecionado: Year to analyze
        mes_selecionado: Month if periodo='mes' (1-12)
        meses_selecionados: List of months if periodo='ano'
        estrategia: 'realizado' or 'projetado'
        cenario_selecionado_id: Scenario ID if strategy is 'projetado'

    Returns:
        Dictionary with DFC hierarchical data and totals
    """
    hoje = date.today()
    projetado = _e_projetado(estrategia)
    if projetado and not cenario_selecionado_id:
        raise RegraNegocioError(
            "Selecione um cenário de previsão para a estratégia Projetado."
        )

    if periodo == "mes":
        col_range = range(
            1, calendar.monthrange(ano_selecionado, mes_selecionado)[1] + 1
        )
        extractor = extract("day", Lancamento.dat_lancamento)
    else:
        col_range = range(1, 13)
        extractor = extract("month", Lancamento.dat_lancamento)

    # Initialize repositories
    lancamento_repo = LancamentoRepository()
    saldo_repo = SaldoContaRepository()

    # Get initial bank balance from day before period
    if periodo == "mes":
        data_inicial = date(ano_selecionado, mes_selecionado, 1)
    else:
        primeiro_mes = min(col_range)
        data_inicial = date(ano_selecionado, primeiro_mes, 1)

    data_saldo_anterior = data_inicial - timedelta(days=1)
    # `is None` = ausência de registro → carry; zero REGISTRADO é respeitado
    saldo_banco_inicial = saldo_repo.get_saldo_total_by_date(data_saldo_anterior)
    if saldo_banco_inicial is None:
        saldo_banco_inicial = saldo_repo.get_latest_saldo_total_before_date(data_saldo_anterior)

    # Get actual lancamentos using repository
    if periodo == "mes":
        resultados_reais = lancamento_repo.get_grouped_by_qualificador_and_period(
            ano=ano_selecionado,
            mes=mes_selecionado,
            groupby_column=extract("day", Lancamento.dat_lancamento)
        )
    else:
        # Get results with month grouping, filtered by selected months
        resultados_reais = lancamento_repo.get_grouped_by_qualificador_and_period(
            ano=ano_selecionado,
            meses=meses_selecionados,
            groupby_column=extractor
        )

    valores_reais = {}
    for seq, col, total in resultados_reais:
        valores_reais.setdefault(seq, {})[int(col)] = float(total or 0)

    # R20: quais qualificadores têm projeção endereçada a si. Resolvido ANTES
    # da árvore porque `build_node` precisa saber se um nó-pai tem movimento
    # próprio mesmo sem lançamentos — o caso da folha que virou pai depois de a
    # versão ter sido publicada.
    seqs_com_projecao: set = set()
    if projetado and cenario_selecionado_id:
        if _meses_abertos(periodo, ano_selecionado, mes_selecionado, hoje):
            from .dfc_projecao import resolver_projecao

            mapa_previo, _origem_previa = resolver_projecao(
                cenario_selecionado_id, ano_selecionado
            )
            seqs_com_projecao = {
                seq for (seq, _t, _m), valor in mapa_previo.items()
                if seq is not None and valor
            }

    def _tem_projecao_propria(seq) -> bool:
        return seq in seqs_com_projecao

    # Build hierarchical tree from root qualificadores.
    # F10.4 (R28): a árvore é a do PLANO RESOLVIDO do ano do relatório — com
    # dois exercícios vivos, misturar planos duplicaria cada nó.
    from ..qualificador_service import resolver_exercicio_do_plano

    qualificadores_root = qualificador_repository.get_root_qualificadores(
        resolver_exercicio_do_plano(ano_selecionado))

    def build_node(q: Qualificador) -> dict:
        """Recursively build DFC node with values and children."""
        proprios = [
            valores_reais.get(q.seq_qualificador, {}).get(c, 0) for c in col_range
        ]
        proj_flags = [False] * len(proprios)

        children = [build_node(f) for f in q.filhos if f.ind_status == "A"]

        # ⚠️ R20: nó que tem FILHOS e movimento PRÓPRIO ganha uma linha filha
        # com a sua parcela, e passa a ser a soma dos filhos — em vez de somar
        # o próprio por dentro.
        #
        # Motivo: `_recompor_pais` (estratégia Projetado) SUBSTITUI o pai pela
        # soma dos filhos. Com a parcela embutida, ela sumia nos meses
        # fechados. Materializá-la como filho torna o invariante "pai é a soma
        # dos filhos" VERDADEIRO POR CONSTRUÇÃO, e `_recompor_pais` não precisa
        # de exceção alguma.
        #
        # E como a linha é FOLHA, `_projetar_folhas` a alcança e lê a projeção
        # endereçada ao próprio nó — que antes ficava no mapa sem ser lida
        # (acontece quando uma folha vira pai depois da versão publicada).
        tem_proprio = any(proprios) or _tem_projecao_propria(q.seq_qualificador)
        if children and tem_proprio:
            children.insert(0, {
                "id": q.seq_qualificador,
                # marcador que distingue a linha do nó de mesmo id — o
                # drill-down usa isto para NÃO expandir os descendentes
                "proprio": True,
                "name": f"{q.dsc_qualificador} (próprio)",
                "number": q.num_qualificador,
                "level": q.nivel + 1,
                "values": list(proprios),
                "proj": [False] * len(proprios),
                "children": [],
            })
            proprios = [0] * len(proprios)

        vals = list(proprios)
        for child in children:
            vals = [v + cv for v, cv in zip(vals, child["values"])]
            proj_flags = [p or cp for p, cp in zip(proj_flags, child["proj"])]

        return {
            "id": q.seq_qualificador,
            "name": q.dsc_qualificador,
            "number": q.num_qualificador,
            "level": q.nivel,
            "values": vals,
            "proj": proj_flags,
            "children": children,
        }

    dfc_data = [build_node(r) for r in qualificadores_root]

    # Raízes por TIPO DE FLUXO (origem única), nunca por número mágico (R22):
    # renumerar a raiz (a F6.7 permite, com cascata) fazia os totais zerarem
    # em silêncio. Sem raiz resolvível → erro explícito, nunca relatório
    # zerado com cara de válido.
    raizes_por_tipo: dict = {}
    for _q_raiz, _node_raiz in zip(qualificadores_root, dfc_data):
        raizes_por_tipo.setdefault(_q_raiz.tipo_fluxo, _node_raiz)
    if 'receita' not in raizes_por_tipo or 'despesa' not in raizes_por_tipo:
        faltantes = [t for t in ('receita', 'despesa') if t not in raizes_por_tipo]
        raise RegraNegocioError(
            "A árvore de qualificadores não tem raiz ativa de "
            + " e ".join(faltantes)
            + " — verifique a numeração das raízes (1.x receita, 2.x despesa)")

    # Build headers
    if periodo == "mes":
        headers = ["Nome"] + [
            f"{d:02d}/{DAY_ABBR_PT[date(ano_selecionado, mes_selecionado, d).weekday()]}"
            for d in col_range
        ]
    else:
        headers = ["Nome"] + [MONTH_ABBR_PT[m] for m in col_range]

    # ---------------------------------------------------------------- R9–R13
    projecao_origem = None
    meses_projetados: list[int] = []
    if projetado:
        meses_abertos = _meses_abertos(periodo, ano_selecionado, mes_selecionado, hoje)
        # Ícone de cabeçalho por índice de coluna: só faz sentido na visão
        # anual (coluna = mês); na mensal o sinal fica nas flags de célula.
        meses_projetados = meses_abertos if periodo == "ano" else []

        # Coluna TOTAIS: a visão mensal projeta o TOTAL do mês; a coluna
        # existe sempre que a estratégia é Projetado (layout estável).
        headers.append("TOTAIS")
        for raiz in dfc_data:
            _acrescentar_totais(raiz)

        if meses_abertos:
            from .dfc_projecao import resolver_projecao

            mapa, projecao_origem = resolver_projecao(
                cenario_selecionado_id, ano_selecionado
            )
            n_colunas = len(col_range) + 1
            for raiz in dfc_data:
                _projetar_folhas(raiz, mapa, periodo, meses_abertos, len(col_range))
            _inserir_linhas_sinteticas(
                raizes_por_tipo, mapa, periodo, meses_abertos, n_colunas
            )
            for raiz in dfc_data:
                _recompor_pais(raiz)

    # Calculate totals based on root nodes 1 (Receita) and 2 (Despesa)
    n_cols_total = len(col_range) + (1 if projetado else 0)
    totals = [0] * n_cols_total

    receita_node = raizes_por_tipo['receita']
    despesa_node = raizes_por_tipo['despesa']

    for i in range(n_cols_total):
        # Sum values: Receita (positive) + Despesa (negative)
        totals[i] = receita_node["values"][i] + despesa_node["values"][i]

    meses_nomes = MONTH_NAME_PT

    # Calculate accumulated bank balances for each column
    saldos_banco_anterior = []  # Saldo at start of each day/month
    saldos_banco_final = []      # Saldo at end of each day/month
    resultado_dia = []           # Net result (receitas - despesas)

    saldo_acumulado = saldo_banco_inicial
    for total_col in totals[: len(col_range)]:
        saldos_banco_anterior.append(saldo_acumulado)
        resultado_dia.append(total_col)
        saldo_acumulado += total_col
        saldos_banco_final.append(saldo_acumulado)
    if projetado:
        # Coluna TOTAIS: do saldo inicial ao final do período inteiro
        saldos_banco_anterior.append(saldo_banco_inicial)
        resultado_dia.append(totals[-1])
        saldos_banco_final.append(saldo_banco_inicial + totals[-1])

    return {
        "headers": headers,
        "dre_data": dfc_data,
        "totals": totals,
        "meses_projetados": meses_projetados,
        "meses_nomes": meses_nomes,
        "saldos_banco_anterior": saldos_banco_anterior,
        "saldos_banco_final": saldos_banco_final,
        "resultado_dia": resultado_dia,
        "projecao_origem": projecao_origem,
    }


# --------------------------------------------------------------------------
# Aplicação da projeção (R11/R13) — pós-processo sobre a árvore realizada
# --------------------------------------------------------------------------

def _meses_abertos(periodo: str, ano: int, mes: int | None, hoje: date) -> list[int]:
    """Meses correntes/futuros do recorte consultado (fechado = realizado)."""
    if periodo == "mes":
        aberto = (ano, mes) >= (hoje.year, hoje.month)
        return [mes] if aberto else []
    if ano < hoje.year:
        return []
    if ano > hoje.year:
        return list(range(1, 13))
    return list(range(hoje.month, 13))


def _acrescentar_totais(node: dict) -> None:
    for filho in node["children"]:
        _acrescentar_totais(filho)
    node["values"] = list(node["values"]) + [sum(node["values"])]
    node["proj"] = list(node["proj"]) + [False]


def _total_projetado(mapa: dict, seq, mes: int) -> Decimal:
    return sum(
        (valor for (s, _tipo, m), valor in mapa.items() if s == seq and m == mes),
        Decimal("0.00"),
    )


def _projetar_folhas(node: dict, mapa: dict, periodo: str,
                     meses_abertos: list[int], n_cols: int) -> None:
    """Fixa o projetado nas folhas; pais são recompostos depois (pós-ordem)."""
    if node["children"]:
        for filho in node["children"]:
            _projetar_folhas(filho, mapa, periodo, meses_abertos, n_cols)
        return

    if periodo == "mes":
        # Previsão pura do mês aberto: dias zerados, TOTAIS = projetado
        mes = meses_abertos[0]
        node["values"] = [0.0] * n_cols + [
            float(_total_projetado(mapa, node["id"], mes))
        ]
        node["proj"] = [True] * (n_cols + 1)
    else:
        for mes in meses_abertos:
            node["values"][mes - 1] = float(
                _total_projetado(mapa, node["id"], mes)
            )
            node["proj"][mes - 1] = True
        node["values"][-1] = sum(node["values"][:-1])


def _inserir_linhas_sinteticas(raizes_por_tipo: dict, mapa: dict, periodo: str,
                               meses_abertos: list[int], n_colunas: int) -> None:
    """Projeção agregada (sem qualificador) vira linha sob a raiz do tipo (R13).

    A raiz vem RESOLVIDA por tipo_fluxo (R22) — mesma resolução dos totais."""
    for cod_tipo, tipo_fluxo in (('C', 'receita'), ('D', 'despesa')):
        valores_mes = {
            m: sum(
                (v for (s, t, mm), v in mapa.items()
                 if s is None and t == cod_tipo and mm == m),
                Decimal("0.00"),
            )
            for m in meses_abertos
        }
        if not any(valores_mes.values()):
            continue
        raiz = raizes_por_tipo.get(tipo_fluxo)
        if raiz is None:
            continue

        vals = [0.0] * (n_colunas - 1)
        flags = [False] * (n_colunas - 1)
        if periodo == "mes":
            flags = [True] * (n_colunas - 1)
            total = float(valores_mes[meses_abertos[0]])
        else:
            for mes in meses_abertos:
                vals[mes - 1] = float(valores_mes[mes])
                flags[mes - 1] = True
            total = sum(vals)
        raiz["children"].append({
            # id 0 = nó sintético (não é um qualificador; drill-down trata)
            "id": 0,
            "name": ROTULO_LINHA_SINTETICA,
            "number": "—",
            "level": raiz["level"] + 1,
            "values": vals + [total],
            "proj": flags + [periodo == "mes"],
            "children": [],
        })


def _recompor_pais(node: dict) -> None:
    """Pós-ordem: cada pai passa a ser a soma dos filhos em todas as colunas."""
    if not node["children"]:
        return
    for filho in node["children"]:
        _recompor_pais(filho)
    n = len(node["values"])
    node["values"] = [
        sum(filho["values"][i] for filho in node["children"]) for i in range(n)
    ]
    node["proj"] = [
        any(filho["proj"][i] for filho in node["children"]) for i in range(n)
    ]


def get_dfc_eventos(
    seq: int,
    periodo: str,
    col: int,
    mes_ano: str,
    estrategia: str,
    cenario_id: int | None,
    proprio: bool = False,
) -> dict:
    """Get detailed events (lancamentos) for a specific DFC cell.

    Célula projetada não lista lançamentos: informa a origem da projeção
    (cenário + versão publicada ou cálculo ao vivo) — spec R11.
    """
    hoje = date.today()
    if periodo == "mes":
        ano, mes_alvo = [int(x) for x in mes_ano.split("-")]
        celula_aberta = (ano, mes_alvo) >= (hoje.year, hoje.month)
    else:
        ano = int(mes_ano)
        mes_alvo = col
        celula_aberta = ano > hoje.year or (ano == hoje.year and col >= hoje.month)

    if _e_projetado(estrategia) and cenario_id and celula_aberta:
        return _eventos_projetados(seq, ano, mes_alvo, cenario_id, proprio)

    # ⚠️ `proprio=True` = a linha de movimento próprio do nó (R20). Ela leva o
    # `seq` REAL do qualificador, então sem este desvio o recorte
    # `[seq] + descendentes` devolveria a subárvore inteira — exatamente o que a
    # linha NÃO representa. É o preço de ela não ter id sintético como a R13:
    # precisa do seq real para saber de quem são os lançamentos.
    qual = qualificador_repository.get_qualificador_by_id(seq)
    if proprio:
        ids = [seq]
    else:
        ids = (
            [seq] + [f.seq_qualificador for f in qual.get_todos_filhos()]
            if qual else [seq]
        )

    # Initialize repository
    lancamento_repo = LancamentoRepository()

    if periodo == "mes":
        registros = lancamento_repo.get_lancamentos_by_qualificador_and_period(
            seq_qualificador=seq,
            ano=ano,
            mes=mes_alvo,
            dia=col,
            qualificador_ids=ids
        )
    else:
        registros = lancamento_repo.get_by_qualificadores_and_month_year(
            qualificador_ids=ids,
            ano=ano,
            mes=col
        )

    eventos = [
        {
            "data": r.dat_lancamento.strftime("%d/%m/%Y"),
            "descricao": f"{r.qualificador.num_qualificador} - {r.qualificador.dsc_qualificador}",
            "valor": float(r.val_lancamento),
            "tipo": r.tipo.dsc_tipo_lancamento,
            "origem": r.origem.dsc_origem_lancamento,
        }
        for r in registros
    ]

    total = sum(e["valor"] for e in eventos)
    return {"eventos": eventos, "total": total}


def _eventos_projetados(seq: int, ano: int, mes: int, cenario_id: int,
                        proprio: bool = False) -> dict:
    """Item informativo com a origem da projeção no lugar dos lançamentos."""
    from .dfc_projecao import resolver_projecao

    mapa, origem = resolver_projecao(cenario_id, ano)

    if seq == 0:  # linha sintética (projeção agregada)
        chaves = {None}
    elif proprio:  # linha de movimento próprio (R20): só o nó, sem descendentes
        chaves = {seq}
    else:
        qual = qualificador_repository.get_qualificador_by_id(seq)
        chaves = {seq} | (
            {f.seq_qualificador for f in qual.get_todos_filhos()} if qual else set()
        )
    total = float(sum(
        (v for (s, _t, m), v in mapa.items() if s in chaves and m == mes),
        Decimal("0.00"),
    ))

    if origem["ao_vivo"]:
        descricao = (
            f"Projeção do cenário \"{origem['nom_cenario']}\" — cálculo ao vivo"
        )
        origem_rotulo = "Cálculo ao vivo"
    else:
        descricao = (
            f"Projeção do cenário \"{origem['nom_cenario']}\" — "
            f"versão publicada \"{origem['nom_versao']}\""
        )
        origem_rotulo = "Versão publicada"

    evento = {
        "data": "—",
        "descricao": descricao,
        "valor": total,
        "tipo": "Projetado",
        "origem": origem_rotulo,
    }
    return {"eventos": [evento], "total": total}
