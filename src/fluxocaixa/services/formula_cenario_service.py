"""Fórmulas aplicáveis e parâmetros do formulário de simulação."""
from decimal import Decimal, InvalidOperation

from ..repositories import formula_repository as repo
from .formula_engine import extrair_variaveis, listar_formulas_aplicaveis
from .validacao import RegraNegocioError


def contexto_formulas(seq_cenario: int | None = None) -> dict:
    globais = {p.nom_parametro: p for p in repo.get_all_parametros_globais()}
    valores = {v.nom_parametro: v.val_parametro
               for v in repo.get_valores_cenario(seq_cenario)} if seq_cenario else {}
    formulas_por_tipo = {'receita': [], 'despesa': []}
    parametros = {}
    for formula in listar_formulas_aplicaveis():
        q = formula.qualificador
        variaveis = [v for v in extrair_variaveis(formula.dsc_formula_expressao)
                     if v != 'base']
        formulas_por_tipo[q.tipo_fluxo].append({
            'nome': formula.nom_formula,
            'expressao': formula.dsc_formula_expressao,
            'qualificador': f'{q.num_qualificador} — {q.dsc_qualificador}',
            'variaveis': variaveis,
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
                'formula': formula.nom_formula,
            })
    return {'formulas_por_tipo': formulas_por_tipo,
            'parametros_formula': [parametros[n] for n in sorted(parametros)]}


def parametros_do_formulario(form) -> dict:
    """Valida só as variáveis utilizadas pelos métodos escolhidos."""
    tipos = {tipo for tipo in ('receita', 'despesa')
             if form.get(f'tipo_cenario_{tipo}') == 'FORMULA'}
    if not tipos:
        return {}
    contexto = contexto_formulas()
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
