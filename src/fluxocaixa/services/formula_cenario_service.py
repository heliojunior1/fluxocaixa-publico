"""Fórmulas aplicáveis e parâmetros do formulário de simulação."""
from decimal import Decimal, InvalidOperation

from ..repositories import formula_repository as repo
from .formula_engine import expressoes_do_cenario, extrair_variaveis, validar_formula
from .validacao import RegraNegocioError

NOME_FORMULA_PROPRIA = 'Própria do cenário'


def contexto_formulas(seq_cenario: int | None = None) -> dict:
    """Fórmulas que o cenário usa e os parâmetros que elas consomem.

    Com cenário, a fórmula PRÓPRIA dele aparece no lugar da da biblioteca
    (RN18) — a tela mostra o que será de fato aplicado."""
    globais = {p.nom_parametro: p for p in repo.get_all_parametros_globais()}
    valores = {v.nom_parametro: v.val_parametro
               for v in repo.get_valores_cenario(seq_cenario)} if seq_cenario else {}
    biblioteca = {f.seq_qualificador: f for f in repo.get_all_formulas()}
    formulas_por_tipo = {'receita': [], 'despesa': []}
    parametros = {}
    for q, expressao in expressoes_do_cenario(seq_cenario):
        da_biblioteca = biblioteca.get(q.seq_qualificador)
        propria = (da_biblioteca is None
                   or da_biblioteca.dsc_formula_expressao != expressao)
        nome = NOME_FORMULA_PROPRIA if propria else da_biblioteca.nom_formula
        variaveis = [v for v in extrair_variaveis(expressao) if v != 'base']
        formulas_por_tipo[q.tipo_fluxo].append({
            'nome': nome,
            'expressao': expressao,
            'qualificador': f'{q.num_qualificador} — {q.dsc_qualificador}',
            'variaveis': variaveis,
            'propria': propria,
        })
        for nome in variaveis:
            global_ = globais.get(nome)
            parametro = parametros.setdefault(nome, {
                'nome': nome,
                'descricao': global_.dsc_parametro if global_ else '',
                'tipo': global_.cod_tipo if global_ else None,
                'valor': str(valores[nome]) if nome in valores else '',
                'usos': [],
            })
            parametro['usos'].append({
                'tipo_fluxo': q.tipo_fluxo,
                'qualificador': f'{q.num_qualificador} — {q.dsc_qualificador}',
                'formula': nome,
            })
    return {'formulas_por_tipo': formulas_por_tipo,
            'parametros_formula': [parametros[n] for n in sorted(parametros)]}


def parametros_do_formulario(form, seq_cenario: int | None = None) -> dict:
    """Valida só as variáveis utilizadas pelos métodos escolhidos."""
    tipos = {tipo for tipo in ('receita', 'despesa')
             if form.get(f'tipo_cenario_{tipo}') == 'FORMULA'}
    if not tipos:
        return {}
    contexto = contexto_formulas(seq_cenario)
    for tipo in tipos:
        if not contexto['formulas_por_tipo'][tipo]:
            raise RegraNegocioError(
                f'Nenhuma fórmula aplicável à {tipo}. Cadastre uma fórmula '
                'para um qualificador folha ativo ou escolha outro método.')
    valores = {}
    for parametro in contexto['parametros_formula']:
        if not any(uso['tipo_fluxo'] in tipos for uso in parametro['usos']):
            continue
        nome = parametro['nome']
        raw = str(form.get(f'formula_param_{nome}', '')).strip()
        if not raw:
            raise RegraNegocioError(f'Informe o parâmetro de fórmula "{nome}".')
        try:
            valor = Decimal(raw)
        except InvalidOperation:
            raise RegraNegocioError(f'Valor inválido para o parâmetro "{nome}".')
        if not valor.is_finite() or abs(valor) >= Decimal('1e12'):
            raise RegraNegocioError(f'Valor inválido para o parâmetro "{nome}".')
        valores[nome] = valor
    return valores


def parametros_informados(form) -> dict:
    """Modo "por qualificador": grava os parâmetros de fórmula PREENCHIDOS.
    Não exige todos — qual fórmula entra depende das marcações, e parâmetro
    faltante vira lacuna citando a variável na cobertura (RN08)."""
    valores = {}
    for chave in form.keys():
        if not chave.startswith('formula_param_'):
            continue
        raw = str(form.get(chave) or '').strip()
        if not raw:
            continue
        nome = chave[len('formula_param_'):]
        try:
            valor = Decimal(raw)
        except InvalidOperation:
            raise RegraNegocioError(f'Valor inválido para o parâmetro "{nome}".')
        if not valor.is_finite() or abs(valor) >= Decimal('1e12'):
            raise RegraNegocioError(f'Valor inválido para o parâmetro "{nome}".')
        valores[nome] = valor
    return valores


# ==================== Fórmula própria do cenário (RN18) ====================

def definir_formula_propria(seq_simulador_cenario: int, seq_qualificador: int,
                            expressao: str, user_id: int | None = None):
    """Grava a fórmula PRÓPRIA do cenário para a folha. A biblioteca e os
    outros cenários não mudam. Expressão igual à da biblioteca remove a
    própria (volta a valer por referência)."""
    from ..auth.contexto import cod_pessoa_atual
    from ..models import CenarioFormula, Qualificador, SimuladorCenario
    from ..models.base import db

    simulador = SimuladorCenario.query.get(seq_simulador_cenario)
    if simulador is None or simulador.ind_status != 'A':
        raise RegraNegocioError("Cenário inexistente ou inativo")
    folha = Qualificador.query.get(seq_qualificador)
    if folha is None or folha.ind_status != 'A' or not folha.is_folha():
        raise RegraNegocioError("Fórmula só se aplica a qualificador folha ativo")
    expressao = (expressao or '').strip()
    valida, erro = validar_formula(expressao)
    if not valida:
        raise RegraNegocioError(erro)

    atual = CenarioFormula.query.filter_by(
        seq_simulador_cenario=seq_simulador_cenario,
        seq_qualificador=seq_qualificador).first()
    da_biblioteca = repo.get_formula_by_qualificador(seq_qualificador)
    if da_biblioteca is not None and da_biblioteca.dsc_formula_expressao == expressao:
        if atual is not None:
            db.session.delete(atual)
            db.session.commit()
        return None
    if atual is None:
        atual = CenarioFormula(seq_simulador_cenario=seq_simulador_cenario,
                               seq_qualificador=seq_qualificador,
                               cod_pessoa_inclusao=user_id or cod_pessoa_atual())
        db.session.add(atual)
    atual.dsc_formula_expressao = expressao
    db.session.commit()
    return atual


def remover_formula_propria(seq_simulador_cenario: int, seq_qualificador: int) -> bool:
    from ..models import CenarioFormula
    from ..models.base import db

    atual = CenarioFormula.query.filter_by(
        seq_simulador_cenario=seq_simulador_cenario,
        seq_qualificador=seq_qualificador).first()
    if atual is None:
        return False
    db.session.delete(atual)
    db.session.commit()
    return True


def cenarios_afetados_pela_biblioteca(seq_qualificador: int) -> list:
    """Cenários ativos que usam a fórmula da BIBLIOTECA desta folha por
    referência (RN18) — alterar a biblioteca muda a projeção ao vivo deles.
    Versões publicadas nunca mudam. Cenário com fórmula própria fica de fora.
    """
    from ..models import (
        CenarioConfig,
        CenarioFormula,
        Qualificador,
        SimuladorCenario,
    )
    from .metodo_qualificador_service import (
        FORMULA,
        carregar_marcacoes,
        marcacao_resolvida,
        perna_do_qualificador,
    )

    folha = Qualificador.query.get(seq_qualificador)
    if folha is None:
        return []
    perna = perna_do_qualificador(folha)
    com_propria = {c.seq_simulador_cenario for c in CenarioFormula.query.filter_by(
        seq_qualificador=seq_qualificador).all()}
    afetados = []
    for cenario in SimuladorCenario.query.filter_by(ind_status='A').order_by(
            SimuladorCenario.nom_cenario).all():
        if cenario.seq_simulador_cenario in com_propria:
            continue
        marcacoes = carregar_marcacoes(cenario.seq_simulador_cenario)
        marcacao, _ = marcacao_resolvida(folha, marcacoes)
        if marcacao is not None:
            usa = marcacao.cod_metodo == FORMULA
        else:
            config = CenarioConfig.query.filter_by(
                seq_simulador_cenario=cenario.seq_simulador_cenario,
                cod_tipo_lancamento=perna).first()
            usa = config is not None and config.cod_tipo_modelo == FORMULA
        if usa:
            afetados.append(cenario)
    return afetados
