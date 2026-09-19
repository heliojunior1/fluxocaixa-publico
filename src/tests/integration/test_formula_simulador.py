"""Regressões: contexto por qualificador, parâmetros úteis e edição do cenário."""
from decimal import Decimal
from types import SimpleNamespace as Obj

import pytest


@pytest.fixture
def catalogo(app, monkeypatch):
    from fluxocaixa.repositories import formula_repository as repo

    def formula(tipo, seq, expressao, *, ativo='A', folha=True):
        q = Obj(seq_qualificador=seq, num_qualificador=str(seq),
                dsc_qualificador=f'Rubrica teste {tipo}', tipo_fluxo=tipo,
                ind_status=ativo, is_folha=lambda: folha)
        return Obj(qualificador=q, seq_qualificador=seq,
                   nom_formula=f'Fórmula teste {tipo}',
                   dsc_formula_expressao=expressao)

    formulas = [formula('receita', 900001, 'base * (1 + ipca)'),
                formula('despesa', 900002, 'base * (1 + ipca) + acrescimo'),
                formula('receita', 900003, 'ignorado', ativo='I'),
                formula('despesa', 900004, 'ignorado', folha=False)]
    monkeypatch.setattr(repo, 'get_all_formulas', lambda: formulas)
    monkeypatch.setattr(repo, 'get_all_parametros_globais', lambda: [
        Obj(nom_parametro='ipca', dsc_parametro='Inflação de teste', cod_tipo='P'),
        Obj(nom_parametro='nao_usado', dsc_parametro='Não utilizado', cod_tipo='V'),
    ])
    return formulas


def test_contexto_exibe_vinculo_e_somente_parametros_aplicaveis(catalogo):
    from fluxocaixa.services.formula_cenario_service import contexto_formulas

    contexto = contexto_formulas()
    assert len(contexto['formulas_por_tipo']['receita']) == 1
    assert len(contexto['formulas_por_tipo']['despesa']) == 1
    assert '900002' in contexto['formulas_por_tipo']['despesa'][0]['qualificador']
    parametros = {p['nome']: p for p in contexto['parametros_formula']}
    assert set(parametros) == {'ipca', 'acrescimo'}
    assert {u['tipo_fluxo'] for u in parametros['ipca']['usos']} == {'receita', 'despesa'}


@pytest.mark.parametrize('valor', ['', 'abc', 'NaN', 'Infinity', '1e12'])
def test_parametro_invalido_recusado_antes_de_criar(catalogo, client, valor):
    from fluxocaixa.models import SimuladorCenario

    antes = SimuladorCenario.query.count()
    resposta = client.post('/simulador/criar', data={
        'nom_cenario': 'Fórmula inválida teste', 'ano_base': '2080',
        'cod_periodicidade': 'ANUAL', 'num_periodos': '1',
        'tipo_cenario_receita': 'FORMULA', 'formula_param_ipca': valor,
    }, follow_redirects=False)
    assert resposta.status_code == 400
    assert SimuladorCenario.query.count() == antes


def test_editar_preserva_valores_e_remove_parametros_sem_uso(catalogo, client):
    from fluxocaixa.repositories import formula_repository as repo

    dados = {'nom_cenario': 'Fórmulas por qualificador teste', 'ano_base': '2080',
             'cod_periodicidade': 'ANUAL', 'num_periodos': '1',
             'cod_metodo_base': 'VALOR_FIXO', 'valor_fixo_cenario': '100',
             'tipo_cenario_receita': 'FORMULA', 'tipo_cenario_despesa': 'FORMULA',
             'formula_param_ipca': '0.045', 'formula_param_acrescimo': '20',
             'formula_param_nao_usado': '999'}
    resposta = client.post('/simulador/criar', data=dados, follow_redirects=False)
    assert resposta.status_code == 303
    url = resposta.headers['location']
    seq = int(url.rsplit('/', 1)[1])
    pagina = client.get(f'{url}/editar')
    assert pagina.status_code == 200
    assert 'id="formula_despesa"' in pagina.text
    assert '900002 — Rubrica teste despesa' in pagina.text
    assert 'value="0.045000"' in pagina.text
    assert 'name="formula_param_nao_usado"' not in pagina.text
    assert {v.nom_parametro for v in repo.get_valores_cenario(seq)} == {'ipca', 'acrescimo'}

    from fluxocaixa.services.formula_engine import projetar_cenario_formula
    for tipo, esperado in [('receita', 104.5), ('despesa', 124.5)]:
        df = projetar_cenario_formula(seq, 2080, 1, tipo,
                                     metodo_base='VALOR_FIXO', config_base={'valor': 100})
        assert len(df) == 1
        assert df.iloc[0]['valor_projetado'] == pytest.approx(esperado)

    dados['tipo_cenario_despesa'] = 'MANUAL'
    dados['formula_param_ipca'] = '0'
    assert client.post(f'{url}/atualizar', data=dados, follow_redirects=False).status_code == 303
    assert {v.nom_parametro: v.val_parametro for v in repo.get_valores_cenario(seq)} == {'ipca': Decimal('0')}
    dados['tipo_cenario_receita'] = 'MANUAL'
    assert client.post(f'{url}/atualizar', data=dados, follow_redirects=False).status_code == 303
    assert repo.get_valores_cenario(seq) == []


def test_sem_formula_mostra_orientacao_e_recusa_metodo(catalogo, client):
    catalogo.clear()
    pagina = client.get('/simulador/novo')
    assert 'Nenhuma fórmula cadastrada para qualificadores folha ativos de despesa' in pagina.text
    resposta = client.post('/simulador/criar', data={
        'nom_cenario': 'Sem fórmulas teste', 'tipo_cenario_despesa': 'FORMULA',
        'cod_periodicidade': 'ANUAL', 'num_periodos': '1',
    }, follow_redirects=False)
    assert resposta.status_code == 400
    assert 'Nenhuma fórmula aplicável' in resposta.json()['detail']
