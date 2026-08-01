"""Service para o histórico de projeções (versões salvas)."""
import json
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import func

from ..models import db, ProjecaoVersao, ProjecaoValor, Lancamento
from ..repositories import projecao_versao_repository as repo
from . import periodo_resolver
# ⚠️ Import do MÓDULO, não dos nomes: `from ... import executar_simulacao`
# congela a função no momento do import, e um teste que faz stub no simulador
# ANTES deste módulo ser importado deixava o stub grudado para o resto da
# suíte (ordem de coleta virava resultado de teste).
from . import simulador_cenario_service
from .simulador_cenario_service import obter_simulador_completo


def _tipo_lancamento_para_projecao() -> Dict:
    """Mapa cod_tipo_lancamento → cod_tipo de `flc_projecao_valor` ('C'/'D').

    Resolvido em runtime pela DESCRIÇÃO (`dominio_lancamento`), nunca pelo
    código: o antigo `{1: 'R', 2: 'D'}` presumia a ordem do seed, que é
    incidental, e ia quebrar em silêncio na F6.1b — chave inexistente vira
    `None`, o laço faz `continue` e TODOS os realizados iriam a zero sem erro.
    Funciona com os inteiros de hoje e com 'C'/'D' depois, sem nova edição.
    """
    from .dominio_lancamento import TIPO_ENTRADA, TIPO_SAIDA, resolver_tipo

    return {
        resolver_tipo(TIPO_ENTRADA).cod_tipo_lancamento: 'C',
        resolver_tipo(TIPO_SAIDA).cod_tipo_lancamento: 'D',
    }


def _periodicidade_do_cenario(simulador) -> str:
    """Periodicidade do cenário, normalizada. Sem cenário, MENSAL."""
    return periodo_resolver.normalizar(
        getattr(simulador, 'cod_periodicidade', None) or periodo_resolver.MENSAL)


def _periodicidade_da_versao(versao) -> str:
    """Periodicidade do cenário dono da versão — o par (ano, período) só tem
    sentido junto dela; ler `num_periodo` sem ela é como ler um número sem
    unidade."""
    from ..models import SimuladorCenario

    cenario = SimuladorCenario.query.get(versao.seq_simulador_cenario)
    return _periodicidade_do_cenario(cenario)


# ==================== Salvar nova versão ====================

def salvar_projecao_como_versao(
    seq_simulador_cenario: int,
    nom_versao: str,
    dsc_motivo: Optional[str] = None,
    user_id: Optional[int] = None,
    publicar: bool = False,
) -> ProjecaoVersao:
    """Executa a simulação atual do cenário e persiste como uma versão.

    Cria header em flc_projecao_versao + linhas em flc_projecao_valor numa
    única transação. Se algo falhar, faz rollback.
    """
    if not nom_versao or not nom_versao.strip():
        raise ValueError("nom_versao é obrigatório")

    resultado = simulador_cenario_service.executar_simulacao(seq_simulador_cenario)
    if resultado is None:
        raise ValueError(f"Simulação não pôde ser executada para cenário {seq_simulador_cenario}")

    cenario_completo = obter_simulador_completo(seq_simulador_cenario)
    periodicidade = _periodicidade_do_cenario(cenario_completo.get('simulador'))
    json_inputs = _serializar_inputs(cenario_completo)
    json_resumo = json.dumps({
        'total_receita': float(resultado['resumo']['total_receita'] or 0),
        'total_despesa': float(resultado['resumo']['total_despesa'] or 0),
        'saldo_final': float(resultado['resumo']['saldo_final'] or 0),
    })

    try:
        versao = ProjecaoVersao(
            seq_simulador_cenario=seq_simulador_cenario,
            nom_versao=nom_versao.strip(),
            dsc_motivo=(dsc_motivo or '').strip() or None,
            dat_versao=datetime.now(),
            cod_pessoa=user_id,
            ind_publicado='S' if publicar else 'N',
            json_inputs=json_inputs,
            json_resumo=json_resumo,
        )
        repo.create_versao(versao)

        valores = _montar_linhas_valor(versao.seq_projecao_versao, resultado,
                                       periodicidade)
        repo.bulk_insert_valores(valores)

        repo.commit()
        return versao
    except Exception:
        repo.rollback()
        raise


def _serializar_inputs(cenario_completo: Optional[Dict]) -> str:
    """Serializa config + ajustes do cenário para auditoria (json_inputs)."""
    if not cenario_completo:
        return json.dumps({})

    def _config(secao):
        cfg = secao.get('config') if secao else None
        if not cfg:
            return None
        return {
            'cod_tipo_modelo': cfg.cod_tipo_modelo,
            'cod_tipo_lancamento': cfg.cod_tipo_lancamento,
            'json_configuracao': cfg.json_configuracao,
        }

    def _ajustes(secao):
        return [
            {
                'seq_qualificador': a.seq_qualificador,
                'ano': a.ano,
                'mes': a.mes,
                'cod_tipo_ajuste': a.cod_tipo_ajuste,
                'val_ajuste': float(a.val_ajuste) if a.val_ajuste else 0,
            }
            for a in (secao.get('ajustes') or [])
        ]

    simulador = cenario_completo.get('simulador')
    return json.dumps({
        'simulador': {
            'nom_cenario': simulador.nom_cenario if simulador else None,
            'ano_base': simulador.ano_base if simulador else None,
            'num_periodos': simulador.num_periodos if simulador else None,
            'cod_periodicidade': getattr(simulador, 'cod_periodicidade', None),
            'cod_metodo_base': getattr(simulador, 'cod_metodo_base', None),
            'json_config_base': getattr(simulador, 'json_config_base', None),
        },
        'receita': {
            'config': _config(cenario_completo.get('receita')),
            'ajustes': _ajustes(cenario_completo.get('receita') or {}),
        },
        'despesa': {
            'config': _config(cenario_completo.get('despesa')),
            'ajustes': _ajustes(cenario_completo.get('despesa') or {}),
        },
    }, default=str)


def _montar_linhas_valor(seq_versao: int, resultado: Dict,
                         periodicidade: str = 'MENSAL') -> List[Dict]:
    """Constrói lista de dicts para bulk_insert em flc_projecao_valor.

    Prefere o DataFrame `_detalhada` (com seq_qualificador). Se não houver
    (modelos agregados como ARIMA/HOLT_WINTERS), persiste com
    seq_qualificador NULL — o total ainda é consultável.
    """
    linhas: List[Dict] = []

    receita_df = resultado.get('projecao_receita_detalhada')
    if receita_df is None or len(receita_df) == 0:
        receita_df = resultado.get('projecao_receita')
    linhas.extend(_df_para_linhas(receita_df, seq_versao, 'C', periodicidade))

    despesa_df = resultado.get('projecao_despesa_detalhada')
    if despesa_df is None or len(despesa_df) == 0:
        despesa_df = resultado.get('projecao_despesa')
    linhas.extend(_df_para_linhas(despesa_df, seq_versao, 'D', periodicidade))

    return linhas


def _df_para_linhas(df, seq_versao: int, cod_tipo: str,
                    periodicidade: str = 'MENSAL') -> List[Dict]:
    if df is None or len(df) == 0:
        return []
    out: List[Dict] = []
    for _, row in df.iterrows():
        data = row.get('data')
        if pd.isna(data):
            continue
        # F6.3: o par (ano, período) vem do resolver. Para SEMANAL o ano é o
        # ano ISO — 29/12/2025 grava sob 2026, não 2025.
        ano, num_periodo = periodo_resolver.resolver(
            data.date() if hasattr(data, 'date') else data, periodicidade)
        seq_q = row.get('seq_qualificador') if 'seq_qualificador' in df.columns else None
        if pd.isna(seq_q):
            seq_q = None
        elif seq_q is not None:
            seq_q = int(seq_q)
        valor = row.get('valor_projetado', 0)
        if pd.isna(valor):
            valor = 0
        out.append({
            'seq_projecao_versao': seq_versao,
            'seq_qualificador': seq_q,
            'cod_tipo': cod_tipo,
            'ano': ano,
            'num_periodo': num_periodo,
            'val_projetado': float(valor),
        })
    return out


# ==================== Listagem / leitura ====================

def list_versoes(seq_simulador_cenario: int) -> List[Dict]:
    """Lista versões com resumo expandido para a tela de histórico."""
    versoes = repo.list_versoes_by_simulador(seq_simulador_cenario)
    out = []
    for v in versoes:
        resumo = {}
        if v.json_resumo:
            try:
                resumo = json.loads(v.json_resumo)
            except (json.JSONDecodeError, TypeError):
                resumo = {}
        out.append({
            'seq_projecao_versao': v.seq_projecao_versao,
            'nom_versao': v.nom_versao,
            'dsc_motivo': v.dsc_motivo,
            'dat_versao': v.dat_versao,
            'ind_publicado': v.ind_publicado,
            'cod_pessoa': v.cod_pessoa,
            'total_receita': resumo.get('total_receita', 0),
            'total_despesa': resumo.get('total_despesa', 0),
            'saldo_final': resumo.get('saldo_final', 0),
        })
    return out


def get_versao_detalhe(seq_projecao_versao: int) -> Optional[Dict]:
    versao = repo.get_versao_by_id(seq_projecao_versao)
    if versao is None:
        return None
    valores = repo.get_valores_by_versao(seq_projecao_versao)
    resumo = {}
    if versao.json_resumo:
        try:
            resumo = json.loads(versao.json_resumo)
        except (json.JSONDecodeError, TypeError):
            resumo = {}

    periodicidade = _periodicidade_da_versao(versao)
    receita_linhas = []
    despesa_linhas = []
    for v in valores:
        item = {
            'seq_qualificador': v.seq_qualificador,
            'qualificador_desc': v.qualificador.dsc_qualificador if v.qualificador else None,
            'ano': v.ano,
            'num_periodo': v.num_periodo,
            # `mes` é DERIVADO (F6.3), não lido: a coluna não existe mais.
            'mes': periodo_resolver.mes_do_periodo(periodicidade, v.ano, v.num_periodo),
            'rotulo_periodo': periodo_resolver.rotulo_periodo(
                periodicidade, v.ano, v.num_periodo),
            'val_projetado': float(v.val_projetado or 0),
            'val_realizado': float(v.val_realizado) if v.val_realizado is not None else None,
        }
        if v.cod_tipo == 'C':
            receita_linhas.append(item)
        else:
            despesa_linhas.append(item)

    return {
        'versao': versao,
        'resumo': resumo,
        'receita': receita_linhas,
        'despesa': despesa_linhas,
    }


def comparar_versoes(seq_versao_a: int, seq_versao_b: int) -> Optional[Dict]:
    versao_a = repo.get_versao_by_id(seq_versao_a)
    versao_b = repo.get_versao_by_id(seq_versao_b)
    if versao_a is None or versao_b is None:
        return None
    if versao_a.seq_simulador_cenario != versao_b.seq_simulador_cenario:
        raise ValueError("Versões pertencem a cenários diferentes")

    linhas = repo.get_comparativo(seq_versao_a, seq_versao_b)

    # Enriquecer com descrição do qualificador (consulta única em batch).
    seq_quals = {l['seq_qualificador'] for l in linhas if l['seq_qualificador']}
    desc_map = {}
    if seq_quals:
        from ..models import Qualificador
        for q in Qualificador.query.filter(Qualificador.seq_qualificador.in_(seq_quals)).all():
            desc_map[q.seq_qualificador] = q.dsc_qualificador

    periodicidade = _periodicidade_da_versao(versao_a)
    for l in linhas:
        l['qualificador_desc'] = desc_map.get(l['seq_qualificador'])
        l['mes'] = periodo_resolver.mes_do_periodo(
            periodicidade, l['ano'], l['num_periodo'])
        l['rotulo_periodo'] = periodo_resolver.rotulo_periodo(
            periodicidade, l['ano'], l['num_periodo'])

    total_a = sum(l['val_a'] for l in linhas)
    total_b = sum(l['val_b'] for l in linhas)
    return {
        'versao_a': versao_a,
        'versao_b': versao_b,
        'linhas': linhas,
        'total_a': total_a,
        'total_b': total_b,
        'delta_total': total_b - total_a,
    }


# ==================== Mutações administrativas ====================

def deletar_versao(seq_projecao_versao: int) -> int:
    return repo.delete_versao(seq_projecao_versao)


def publicar_versao(seq_projecao_versao: int) -> Optional[ProjecaoVersao]:
    return repo.publicar_versao(seq_projecao_versao)


# ==================== Frustração x Excesso (RF-24) ====================

def atualizar_realizados_de_lancamentos(
    seq_projecao_versao: int,
    ate_data: Optional[date] = None,
) -> int:
    """Preenche val_realizado em ProjecaoValor agregando flc_lancamento.

    Considera apenas os períodos já FECHADOS em relação a `ate_data` (default:
    hoje) — o período corrente é parcial e não deve sobrescrever o projetado.

    ⚠️ F6.3: o casamento é pelo PERÍODO da periodicidade do cenário, resolvido
    da data do lançamento — não mais pelo mês. É aqui que o resolver ganha
    função: antes, um cenário quinzenal recebia o realizado do mês inteiro na
    "quinzena" de mesmo número.

    A agregação em SQL vai só até o DIA (`GROUP BY` na data, portável
    SQLite/PostgreSQL); a dobra em períodos é Python, porque semana ISO não
    existe no SQLite (design D3). O grão diário mantém o round-trip único.

    Retorna a quantidade de linhas atualizadas.
    """
    versao = repo.get_versao_by_id(seq_projecao_versao)
    if versao is None:
        raise ValueError(f"Versão {seq_projecao_versao} não encontrada")

    periodicidade = _periodicidade_da_versao(versao)
    ate = ate_data or date.today()
    periodo_corrente = periodo_resolver.resolver(ate, periodicidade)
    inicio_corrente = periodo_resolver.data_inicial_do_periodo(
        periodicidade, periodo_corrente.ano, periodo_corrente.periodo)

    # 1. Chaves (qualificador, tipo, ano, período) da versão, só nos períodos
    #    fechados. A ordem lexicográfica de (ano, período) é a ordem do tempo
    #    em todas as periodicidades — no SEMANAL o `ano` é o ano ISO, o mesmo
    #    que o resolver devolve para `ate`.
    linhas_versao = (
        db.session.query(
            ProjecaoValor.seq_qualificador,
            ProjecaoValor.cod_tipo,
            ProjecaoValor.ano,
            ProjecaoValor.num_periodo,
        )
        .filter(ProjecaoValor.seq_projecao_versao == seq_projecao_versao)
        .filter(ProjecaoValor.seq_qualificador.isnot(None))
        .all()
    )
    chaves_fechadas = [
        (sq, tipo, ano, periodo)
        for sq, tipo, ano, periodo in linhas_versao
        if (ano, periodo) < tuple(periodo_corrente)
    ]
    if not chaves_fechadas:
        return 0

    # 2. Agrega flc_lancamento por (qualificador, tipo, DIA) e dobra em
    #    períodos no Python. O recorte por data vem do menor período fechado
    #    até o início do corrente — recortar por ANO CIVIL perderia as viradas
    #    de ano ISO do SEMANAL.
    seq_quals = {sq for sq, _, _, _ in chaves_fechadas}
    inicio = min(
        periodo_resolver.data_inicial_do_periodo(periodicidade, ano, periodo)
        for _, _, ano, periodo in chaves_fechadas
    )

    rows = (
        db.session.query(
            Lancamento.seq_qualificador,
            Lancamento.cod_tipo_lancamento,
            Lancamento.dat_lancamento,
            func.sum(Lancamento.valor_com_sinal).label('total'),
        )
        .filter(Lancamento.ind_status == 'A')
        .filter(Lancamento.seq_qualificador.in_(seq_quals))
        .filter(Lancamento.dat_lancamento >= inicio)
        .filter(Lancamento.dat_lancamento < inicio_corrente)
        .group_by(
            Lancamento.seq_qualificador,
            Lancamento.cod_tipo_lancamento,
            Lancamento.dat_lancamento,
        )
        .all()
    )
    mapa_tipo = _tipo_lancamento_para_projecao()
    realizados_idx: Dict[Tuple[int, str, int, int], float] = {}
    for sq, cod_tipo_lanc, data_lanc, total in rows:
        tipo = mapa_tipo.get(cod_tipo_lanc)
        if tipo is None:
            continue
        ano, num_periodo = periodo_resolver.resolver(data_lanc, periodicidade)
        chave = (int(sq), tipo, ano, num_periodo)
        realizados_idx[chave] = realizados_idx.get(chave, 0.0) + float(total or 0)

    # 3. Períodos fechados sem lançamento ficam com 0 — "fechado e zerado".
    realizados: List[Tuple[int, str, int, int, float]] = [
        (sq, tipo, ano, periodo, realizados_idx.get((sq, tipo, ano, periodo), 0.0))
        for sq, tipo, ano, periodo in chaves_fechadas
    ]

    return repo.atualizar_realizado(seq_projecao_versao, realizados)
