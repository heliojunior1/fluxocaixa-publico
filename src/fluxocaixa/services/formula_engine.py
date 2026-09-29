"""Motor de avaliação de fórmulas parametrizáveis.

Este módulo é o coração do sistema de fórmulas. Ele é responsável por:
- Extrair variáveis de expressões matemáticas
- Validar expressões sintaticamente
- Avaliar expressões com variáveis substituídas
- Calcular a 'base' histórica de uma rubrica por diferentes métodos
- Projetar valores usando fórmulas parametrizadas

Usa a biblioteca py_expression_eval para avaliação segura (sem eval()).
"""

from datetime import date

import pandas as pd
from py_expression_eval import Parser

from .validacao import RegraNegocioError

# Parser compartilhado (thread-safe para leitura)
_parser = Parser()


def extrair_variaveis(expressao: str) -> list[str]:
    """Extrai os nomes das variáveis de uma expressão matemática.

    Args:
        expressao: Expressão como 'base * (1 + ipca) * (1 + pib * elasticidade)'

    Returns:
        Lista de nomes de variáveis, ex: ['base', 'ipca', 'pib', 'elasticidade']
    """
    try:
        expr = _parser.parse(expressao)
        return sorted(expr.variables())
    except Exception:
        return []


def validar_formula(expressao: str) -> tuple[bool, str | None]:
    """Valida se uma expressão é sintaticamente correta.

    Args:
        expressao: Expressão a validar

    Returns:
        Tupla (valida, mensagem_erro). Se válida, mensagem_erro é None.
    """
    if not expressao or not expressao.strip():
        return False, 'Expressão vazia'

    try:
        _parser.parse(expressao)
        return True, None
    except Exception as e:
        # SÓ o parse (previsao R12): avaliar com valores de teste recusava
        # fórmula válida com singularidade neles (ex. `base / (x - 1)` com 1.0)
        # e deixava passar a divisão por zero que só aparece em runtime —
        # tratada em `avaliar_formula`, com mensagem própria.
        return False, f'Erro na expressão: {e!s}'


def avaliar_formula(expressao: str, variaveis: dict[str, float]) -> float:
    """Avalia uma expressão matemática com os valores das variáveis informados.

    Args:
        expressao: Expressão como 'base * (1 + ipca)'
        variaveis: Dicionário {nome_variavel: valor}, ex: {'base': 1000, 'ipca': 0.045}

    Returns:
        Resultado numérico da avaliação

    Raises:
        ValueError: Se a expressão for inválida ou faltar variáveis
    """
    try:
        expr = _parser.parse(expressao)
        vars_necessarias = set(expr.variables())
        vars_disponiveis = set(variaveis.keys())
        faltantes = vars_necessarias - vars_disponiveis

        if faltantes:
            raise ValueError(
                f'Variáveis não informadas: {", ".join(sorted(faltantes))}'
            )

        resultado = expr.evaluate(variaveis)
        return float(resultado)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f'Erro ao avaliar expressão: {e!s}')


def listar_anos_disponiveis(seq_qualificador: int) -> list[int]:
    """Retorna lista de anos que possuem dados históricos para um qualificador.

    Consulta a tabela de lançamentos para encontrar todos os anos distintos
    com dados para o qualificador informado.

    Args:
        seq_qualificador: ID do qualificador

    Returns:
        Lista de anos ordenados em ordem decrescente, ex: [2024, 2023, 2022]
    """
    from sqlalchemy import extract

    from ..models import Lancamento, db

    anos = (
        db.session.query(
            extract('year', Lancamento.dat_lancamento).label('ano')
        )
        .filter(Lancamento.seq_qualificador.in_(
            _seqs_da_rubrica(seq_qualificador)))
        .filter(Lancamento.ind_status == 'A')
        .distinct()
        .order_by(extract('year', Lancamento.dat_lancamento).desc())
        .all()
    )
    return [int(a.ano) for a in anos]


def _seqs_da_rubrica(seq_qualificador):
    """F10.2 (previsao R17): a série é da rubrica (raiz), não do seq."""
    from .serie_historica import seqs_da_rubrica

    return seqs_da_rubrica(seq_qualificador)


def listar_todos_anos_disponiveis() -> list[int]:
    """Retorna lista de todos os anos distintos com dados históricos (qualquer qualificador).

    Usado para popular a seção de configuração de base no cenário, onde o usuário
    seleciona quais anos usar para o cálculo da base.

    Returns:
        Lista de anos ordenados em ordem decrescente, ex: [2025, 2024, 2023, 2022]
    """
    from sqlalchemy import extract

    from ..models import Lancamento
    from ..models.base import SessionLocal

    session = SessionLocal()
    # `extract`, nunca `strftime`: portável SQLite/PostgreSQL (R11)
    year_col = extract('year', Lancamento.dat_lancamento)
    anos = (
        session.query(year_col.label('ano'))
        .filter(Lancamento.ind_status == 'A')
        .distinct()
        .order_by(year_col.desc())
        .all()
    )
    return [int(a.ano) for a in anos if a.ano is not None]


def calcular_base(
    seq_qualificador: int,
    mes: int,
    metodo: str,
    config: dict,
) -> float:
    """Calcula o valor da 'base' para um mês específico usando dados históricos.

    Args:
        seq_qualificador: ID do qualificador
        mes: Mês para o qual calcular a base (1-12)
        metodo: 'MEDIA_SIMPLES', 'MEDIA_PONDERADA', ou 'VALOR_FIXO'
        config: Configuração do método, ex:
            MEDIA_SIMPLES:   {"anos": [2023, 2024]}
            MEDIA_PONDERADA: {"anos": [2022,2023,2024], "pesos": {"2022":1,"2023":2,"2024":3}}
            VALOR_FIXO:      {"valor": 150000.00}

    Returns:
        Valor calculado da base
    """
    if metodo == 'VALOR_FIXO':
        return float(config.get('valor', 0))

    anos = config.get('anos', [])
    if not anos:
        return 0.0

    # Buscar valores históricos para o mês nos anos selecionados
    valores_por_ano = _buscar_valores_historicos_mes(seq_qualificador, mes, anos)

    if not valores_por_ano:
        return 0.0

    if metodo == 'MEDIA_SIMPLES':
        return sum(valores_por_ano.values()) / len(valores_por_ano)

    elif metodo == 'MEDIA_PONDERADA':
        pesos = config.get('pesos', {})
        soma_ponderada = 0.0
        soma_pesos = 0.0

        for ano, valor in valores_por_ano.items():
            peso = float(pesos.get(str(ano), 1))
            soma_ponderada += valor * peso
            soma_pesos += peso

        if soma_pesos == 0:
            return 0.0
        return soma_ponderada / soma_pesos

    return 0.0


def _buscar_valores_historicos_mes(
    seq_qualificador: int,
    mes: int,
    anos: list[int],
) -> dict[int, float]:
    """Busca valores históricos de um qualificador para um mês em vários anos.

    Args:
        seq_qualificador: ID do qualificador
        mes: Mês (1-12)
        anos: Lista de anos para buscar

    Returns:
        Dicionário {ano: valor_total_do_mes}
    """
    from sqlalchemy import and_, extract, func

    from ..models import Lancamento, db

    resultados = (
        db.session.query(
            extract('year', Lancamento.dat_lancamento).label('ano'),
            func.sum(Lancamento.valor_com_sinal).label('total'),
        )
        .filter(
            and_(
                Lancamento.seq_qualificador.in_(
                    _seqs_da_rubrica(seq_qualificador)),
                extract('month', Lancamento.dat_lancamento) == mes,
                extract('year', Lancamento.dat_lancamento).in_(anos),
                Lancamento.ind_status == 'A',
            )
        )
        .group_by(extract('year', Lancamento.dat_lancamento))
        .all()
    )
    # Erro de banco SOBE (R11): `except → {}` fazia o cenário inteiro
    # projetar zero com aparência de dado apurado.
    return {int(r.ano): float(r.total) for r in resultados}


def projetar_com_formula(
    seq_qualificador: int,
    ano_base: int,
    meses: int,
    expressao: str,
    metodo_base: str,
    config_base: dict,
    parametros: dict[str, float],
) -> pd.DataFrame:
    """Projeta valores usando uma fórmula parametrizada (modo mensal)."""
    from dateutil.relativedelta import relativedelta

    records = []
    data_inicio = date(ano_base, 1, 1)

    for i in range(meses):
        data_mes = data_inicio + relativedelta(months=i)
        mes = data_mes.month
        base = calcular_base(seq_qualificador, mes, metodo_base, config_base)
        variaveis = dict(parametros)
        variaveis['base'] = base
        try:
            valor_projetado = avaliar_formula(expressao, variaveis)
        except ValueError as exc:
            # NUNCA projetar a base em silêncio (previsao R12): parâmetro
            # faltante virava projeção indistinguível de fórmula = `base`.
            raise RegraNegocioError(
                f"Fórmula da rubrica {seq_qualificador} não pôde ser "
                f"avaliada: {exc}")

        records.append({
            'data': data_mes,
            'seq_qualificador': seq_qualificador,
            'valor_projetado': valor_projetado,
        })

    if not records:
        return pd.DataFrame(columns=['data', 'seq_qualificador', 'valor_projetado'])
    return pd.DataFrame(records)


def calcular_base_anual(
    seq_qualificador: int,
    metodo: str,
    config: dict,
) -> float:
    """Calcula o valor base anual (soma dos 12 meses) dos anos selecionados.

    Args:
        seq_qualificador: ID do qualificador
        metodo: 'MEDIA_SIMPLES', 'MEDIA_PONDERADA', ou 'VALOR_FIXO'
        config: Configuração do método

    Returns:
        Valor calculado da base anual
    """
    if metodo == 'VALOR_FIXO':
        return float(config.get('valor', 0))

    anos = config.get('anos', [])
    if not anos:
        return 0.0

    valores_por_ano = _buscar_valores_historicos_anual(seq_qualificador, anos)
    if not valores_por_ano:
        return 0.0

    if metodo == 'MEDIA_SIMPLES':
        return sum(valores_por_ano.values()) / len(valores_por_ano)

    elif metodo == 'MEDIA_PONDERADA':
        pesos = config.get('pesos', {})
        soma_ponderada = 0.0
        soma_pesos = 0.0
        for ano, valor in valores_por_ano.items():
            peso = float(pesos.get(str(ano), 1))
            soma_ponderada += valor * peso
            soma_pesos += peso
        if soma_pesos == 0:
            return 0.0
        return soma_ponderada / soma_pesos

    return 0.0


def _buscar_valores_historicos_anual(
    seq_qualificador: int,
    anos: list[int],
) -> dict[int, float]:
    """Busca totais anuais (soma de todos os meses) para um qualificador."""
    from sqlalchemy import and_, extract, func

    from ..models import Lancamento, db

    resultados = (
        db.session.query(
            extract('year', Lancamento.dat_lancamento).label('ano'),
            func.sum(Lancamento.valor_com_sinal).label('total'),
        )
        .filter(
            and_(
                Lancamento.seq_qualificador.in_(
                    _seqs_da_rubrica(seq_qualificador)),
                extract('year', Lancamento.dat_lancamento).in_(anos),
                Lancamento.ind_status == 'A',
            )
        )
        .group_by(extract('year', Lancamento.dat_lancamento))
        .all()
    )
    return {int(r.ano): float(r.total) for r in resultados}


def projetar_com_formula_anual(
    seq_qualificador: int,
    ano_base: int,
    periodos: int,
    expressao: str,
    metodo_base: str,
    config_base: dict,
    parametros: dict[str, float],
) -> pd.DataFrame:
    """Projeta valores usando uma fórmula parametrizada (modo anual)."""
    records = []
    base = calcular_base_anual(seq_qualificador, metodo_base, config_base)

    for i in range(periodos):
        ano_projetado = ano_base + i
        data_ref = date(ano_projetado, 1, 1)
        variaveis = dict(parametros)
        variaveis['base'] = base
        try:
            valor_projetado = avaliar_formula(expressao, variaveis)
        except ValueError as exc:
            raise RegraNegocioError(
                f"Fórmula da rubrica {seq_qualificador} não pôde ser "
                f"avaliada: {exc}")
        records.append({
            'data': data_ref,
            'seq_qualificador': seq_qualificador,
            'valor_projetado': valor_projetado,
        })

    if not records:
        return pd.DataFrame(columns=['data', 'seq_qualificador', 'valor_projetado'])
    return pd.DataFrame(records)


def listar_formulas_aplicaveis(tipo_fluxo: str | None = None):
    """Mesmo conjunto no formulário e no cálculo: fórmula e folha ativas."""
    from ..repositories import formula_repository as f_repo

    return [f for f in f_repo.get_all_formulas()
            if f.qualificador is not None
            and f.qualificador.ind_status == 'A'
            and f.qualificador.tipo_fluxo in ('receita', 'despesa')
            and (tipo_fluxo is None or f.qualificador.tipo_fluxo == tipo_fluxo)
            and f.qualificador.is_folha()]


def expressoes_do_cenario(seq_simulador_cenario: int | None,
                          tipo_fluxo: str | None = None) -> list:
    """[(folha, expressão)] que o cenário projeta por fórmula (RN18).

    A biblioteca (`flc_rubrica_formula`) vale por referência; a fórmula
    PRÓPRIA do cenário (`flc_cenario_formula`) vence a da biblioteca e também
    cobre folha que a biblioteca não tem. Mesmos critérios de folha ativa de
    `listar_formulas_aplicaveis`.
    """
    from ..models import CenarioFormula

    por_folha = {f.qualificador.seq_qualificador: (f.qualificador, f.dsc_formula_expressao)
                 for f in listar_formulas_aplicaveis(tipo_fluxo)}
    if seq_simulador_cenario:
        for propria in CenarioFormula.query.filter_by(
                seq_simulador_cenario=seq_simulador_cenario).all():
            folha = propria.qualificador
            if (folha is None or folha.ind_status != 'A' or not folha.is_folha()
                    or folha.tipo_fluxo not in ('receita', 'despesa')
                    or (tipo_fluxo is not None and folha.tipo_fluxo != tipo_fluxo)):
                continue
            por_folha[folha.seq_qualificador] = (folha, propria.dsc_formula_expressao)
    return [por_folha[seq] for seq in sorted(por_folha)]


def projetar_cenario_formula(
    seq_simulador_cenario: int,
    ano_base: int,
    periodos: int,
    tipo_fluxo: str,
    periodicidade: str = 'ANUAL',
    metodo_base: str = 'MEDIA_SIMPLES',
    config_base: dict | None = None,
) -> pd.DataFrame:
    """Projeta receitas ou despesas usando fórmulas para todas as rubricas configuradas.

    A configuração de base (método, anos, pesos) vem do cenário, não da fórmula individual.

    Args:
        seq_simulador_cenario: ID do cenário simulador
        ano_base: Ano base para projeção
        periodos: Número de períodos a projetar (anos para ANUAL)
        tipo_fluxo: 'receita' ou 'despesa'
        periodicidade: 'ANUAL', 'MENSAL', etc.
        metodo_base: Método de cálculo da base (do cenário)
        config_base: Configuração da base (do cenário)

    Returns:
        DataFrame com colunas ['data', 'seq_qualificador', 'valor_projetado']
    """
    from ..repositories import formula_repository as f_repo

    if config_base is None:
        config_base = {}

    # Buscar valores dos parâmetros definidos para este cenário
    valores_cenario = f_repo.get_valores_cenario(seq_simulador_cenario)
    parametros = {v.nom_parametro: float(v.val_parametro) for v in valores_cenario}

    all_records = []
    for folha, expressao in expressoes_do_cenario(seq_simulador_cenario, tipo_fluxo):
        if periodicidade == 'ANUAL':
            df = projetar_com_formula_anual(
                seq_qualificador=folha.seq_qualificador,
                ano_base=ano_base,
                periodos=periodos,
                expressao=expressao,
                metodo_base=metodo_base,
                config_base=config_base,
                parametros=parametros,
            )
        else:
            df = projetar_com_formula(
                seq_qualificador=folha.seq_qualificador,
                ano_base=ano_base,
                meses=periodos,
                expressao=expressao,
                metodo_base=metodo_base,
                config_base=config_base,
                parametros=parametros,
            )

        if len(df) > 0:
            all_records.append(df)

    if not all_records:
        return pd.DataFrame(columns=['data', 'seq_qualificador', 'valor_projetado'])

    return pd.concat(all_records, ignore_index=True)


# ==================== Projeções por Crescimento ====================


def _faixa_de_meses(ano: int, mes_ini: int, mes_fim: int) -> tuple[date, date]:
    """Faixa de datas sargável (CLAUDE.md: filtro de período é FAIXA)."""
    import calendar

    return (date(ano, mes_ini, 1),
            date(ano, mes_fim, calendar.monthrange(ano, mes_fim)[1]))


def _soma_acumulada(seq_qualificadores: list[int], ano: int, mes_ini: int, mes_fim: int) -> float:
    """Magnitude do acumulado [mes_ini, mes_fim] do ano (previsao R17).

    Duas correções da change corrigir-motores-de-previsao: (1) a lista é
    expandida pela RAIZ — com o `seq` cru, depois de abrir um exercício o ano
    de referência (gravado no plano anterior) somava zero e o crescimento
    projetava zero; (2) é o absoluto da SOMA com sinal, não a soma dos
    absolutos — um estorno reduz o acumulado em vez de aumentá-lo.
    """
    from sqlalchemy import func

    from ..models import Lancamento
    from ..models.base import SessionLocal
    from .serie_historica import seqs_das_rubricas

    inicio, fim = _faixa_de_meses(ano, mes_ini, mes_fim)
    session = SessionLocal()
    # erro de banco SOBE (R11)
    total = (
        session.query(func.sum(Lancamento.valor_com_sinal))
        .filter(
            Lancamento.seq_qualificador.in_(seqs_das_rubricas(seq_qualificadores)),
            Lancamento.dat_lancamento >= inicio,
            Lancamento.dat_lancamento <= fim,
            Lancamento.ind_status == 'A',
        )
        .scalar()
    )
    return abs(float(total)) if total else 0.0


def _perfil_sazonal(seq_qualificadores: list[int], ano: int) -> dict[int, float]:
    """Perfil sazonal de um ano: {mes: proporção}, soma = 1.0.

    Magnitude de cada mês = absoluto da soma com sinal do mês (R17), série
    costurada pela raiz. Ano sem movimento → distribuição uniforme (1/12).
    """
    from sqlalchemy import extract, func

    from ..models import Lancamento
    from ..models.base import SessionLocal
    from .serie_historica import seqs_das_rubricas

    inicio, fim = _faixa_de_meses(ano, 1, 12)
    session = SessionLocal()
    mes_col = extract('month', Lancamento.dat_lancamento)
    resultados = (
        session.query(
            mes_col.label('mes'),
            func.sum(Lancamento.valor_com_sinal).label('total')
        )
        .filter(
            Lancamento.seq_qualificador.in_(seqs_das_rubricas(seq_qualificadores)),
            Lancamento.dat_lancamento >= inicio,
            Lancamento.dat_lancamento <= fim,
            Lancamento.ind_status == 'A',
        )
        .group_by(mes_col)
        .all()
    )

    valores = {int(r.mes): abs(float(r.total or 0)) for r in resultados}
    total_ano = sum(valores.values())

    if total_ano > 0:
        return {m: valores.get(m, 0) / total_ano for m in range(1, 13)}
    # Uniforme SÓ aqui: caso de negócio explícito (ano sem movimento) —
    # nunca como máscara de erro de banco (R11).
    return {m: 1.0 / 12 for m in range(1, 13)}


def _perfil_sazonal_medio(seq_qualificadores: list[int], anos: list[int]) -> dict[int, float]:
    """Média dos perfis sazonais de vários anos.

    Args:
        seq_qualificadores: Lista de IDs dos qualificadores
        anos: Lista de anos para calcular a média

    Returns:
        Dicionário {mês: proporção média}
    """
    if not anos:
        return {m: 1.0 / 12 for m in range(1, 13)}

    perfis = [_perfil_sazonal(seq_qualificadores, ano) for ano in anos]

    resultado = {}
    for mes in range(1, 13):
        valores_mes = [p.get(mes, 0) for p in perfis]
        resultado[mes] = sum(valores_mes) / len(valores_mes)

    return resultado


def projetar_crescimento_ultimo_ano(
    seq_qualificadores: list[int],
    ano_projecao: int,
    ano_referencia: int,
    mes_referencia: int,
    num_periodos: int = 12,
) -> pd.DataFrame:
    """Projeção por Crescimento do Último Ano.

    Calcula a taxa de crescimento do acumulado parcial do ano de projeção
    vs. o mesmo período do ano de referência, e extrapola para o ano completo.

    Fórmula:
        taxa = Acum(ano_projecao, 1..M) / Acum(ano_referencia, 1..M)
        projecao_total = taxa × Total(ano_referencia)

    Os meses já realizados (1..M) usam o valor real.
    Os meses restantes (M+1..12) são distribuídos pelo perfil sazonal do ano de referência.

    Args:
        seq_qualificadores: Lista de IDs dos qualificadores a projetar
        ano_projecao: Ano que está sendo projetado (ex: 2026)
        ano_referencia: Ano de referência para a taxa de crescimento (ex: 2025)
        mes_referencia: Até que mês existem dados reais no ano de projeção
        num_periodos: Número de meses a projetar (padrão 12)

    Returns:
        DataFrame com colunas: data, valor_projetado
    """
    # 1. Calcular acumulados parciais
    acum_atual = _soma_acumulada(seq_qualificadores, ano_projecao, 1, mes_referencia)
    acum_referencia = _soma_acumulada(seq_qualificadores, ano_referencia, 1, mes_referencia)
    total_referencia = _soma_acumulada(seq_qualificadores, ano_referencia, 1, 12)

    # 2. Calcular taxa de crescimento
    if acum_referencia > 0:
        taxa_crescimento = acum_atual / acum_referencia
    else:
        taxa_crescimento = 1.0

    # 3. Projeção total do ano
    projecao_total = taxa_crescimento * total_referencia

    # 4. Distribuir: meses reais + saldo pelo perfil (conserva o total — R23)
    perfil = _perfil_sazonal(seq_qualificadores, ano_referencia)
    return _projecao_que_conserva_o_total(
        seq_qualificadores, ano_projecao, mes_referencia, projecao_total, perfil)


def projetar_media_crescimento_anos(
    seq_qualificadores: list[int],
    ano_projecao: int,
    anos_referencia: list[int],
    mes_referencia: int,
    num_periodos: int = 12,
) -> pd.DataFrame:
    """Projeção por Média de Crescimento de Anos Selecionados.

    Calcula a taxa de projeção (Total/Acumulado parcial) para cada ano
    de referência, faz a média das taxas, e aplica ao acumulado parcial
    do ano de projeção. Suaviza distorções de anos atípicos.

    Fórmula:
        taxa_i = Total(ano_i) / Acum(ano_i, 1..M)
        taxa_media = mean(taxa_i)
        projecao_total = Acum(ano_projecao, 1..M) × taxa_media

    Args:
        seq_qualificadores: Lista de IDs dos qualificadores a projetar
        ano_projecao: Ano que está sendo projetado (ex: 2026)
        anos_referencia: Lista de anos para média (ex: [2023, 2024, 2025])
        mes_referencia: Até que mês existem dados reais no ano de projeção
        num_periodos: Número de meses a projetar (padrão 12)

    Returns:
        DataFrame com colunas: data, valor_projetado
    """
    if not anos_referencia:
        return pd.DataFrame(columns=['data', 'valor_projetado'])

    # 1. Calcular taxa para cada ano de referência
    taxas = []
    for ano in anos_referencia:
        acum_parcial = _soma_acumulada(seq_qualificadores, ano, 1, mes_referencia)
        total_ano = _soma_acumulada(seq_qualificadores, ano, 1, 12)

        if acum_parcial > 0:
            taxas.append(total_ano / acum_parcial)

    # 2. Média das taxas
    if taxas:
        taxa_media = sum(taxas) / len(taxas)
    else:
        taxa_media = 1.0

    # 3. Aplicar ao acumulado atual
    acum_atual = _soma_acumulada(seq_qualificadores, ano_projecao, 1, mes_referencia)
    projecao_total = acum_atual * taxa_media

    # 4. Distribuir: meses reais + saldo pelo perfil sazonal médio (R23)
    perfil = _perfil_sazonal_medio(seq_qualificadores, anos_referencia)
    return _projecao_que_conserva_o_total(
        seq_qualificadores, ano_projecao, mes_referencia, projecao_total, perfil)


def _projecao_que_conserva_o_total(seq_qualificadores: list[int], ano_projecao: int,
                                   mes_referencia: int, projecao_total: float,
                                   perfil: dict[int, float]) -> pd.DataFrame:
    """Doze meses cuja SOMA é o total projetado pela taxa (R23).

    Meses até a referência recebem o realizado; o SALDO (total − realizado)
    vai para os meses seguintes pelo perfil RENORMALIZADO nesses meses. Antes
    cada mês futuro era `total × perfil(mês)`: só fecha a conta quando o peso
    dos meses realizados no perfil é exatamente o inverso da taxa — verdade no
    crescimento do último ano (perfil do mesmo ano de referência), falso na
    MÉDIA de crescimento (taxa média × perfil médio): medido R$ 1.399,98 para
    um total de R$ 1.600,00. Centavos exatos, resíduo no mês de maior peso.
    Saldo negativo (o realizado já passou do total) → futuros zerados e a
    degradação declarada em `attrs`.
    """
    realizados = {mes: round(_soma_acumulada(seq_qualificadores, ano_projecao, mes, mes), 2)
                  for mes in range(1, mes_referencia + 1)}
    futuros = list(range(mes_referencia + 1, 13))
    saldo = round(round(projecao_total, 2) - sum(realizados.values()), 2)
    aviso = None
    if saldo < 0:
        aviso = (f"O realizado até o mês {mes_referencia} ({sum(realizados.values()):.2f}) "
                 f"já supera o total projetado ({projecao_total:.2f}): meses "
                 "seguintes projetados em zero")
        saldo = 0.0
    pesos = {mes: perfil.get(mes, 0.0) for mes in futuros}
    if futuros and sum(pesos.values()) <= 0:
        pesos = {mes: 1.0 for mes in futuros}  # perfil sem peso nos futuros
    total_pesos = sum(pesos.values()) or 1.0
    partes = {mes: round(saldo * peso / total_pesos, 2) for mes, peso in pesos.items()}
    if partes:
        maior = max(pesos, key=pesos.get)
        partes[maior] = round(partes[maior] + saldo - sum(partes.values()), 2)
    registros = [{'data': date(ano_projecao, mes, 1),
                  'valor_projetado': realizados.get(mes, partes.get(mes, 0.0))}
                 for mes in range(1, 13)]
    resultado = pd.DataFrame(registros)
    if aviso:
        resultado.attrs['degradacao'] = aviso
    return resultado

