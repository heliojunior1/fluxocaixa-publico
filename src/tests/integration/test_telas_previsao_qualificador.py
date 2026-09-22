"""Telas da previsão por qualificador — ponta a ponta pela web (TestClient).

Cobre o caminho HTML das rotas novas: árvore de métodos, marcação por
formulário, cobertura, fórmula própria, duplicar, setores, propostas,
planilha-modelo e importação com preview → confirmação.

Ilha: plano do exercício 2098, receita "1.87", despesa "2.87". Import tardio
de `fluxocaixa` (isolamento de banco da suíte).
"""
import json
import re
from datetime import date
from decimal import Decimal

import pytest

EXERCICIO = 2098


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from sqlalchemy import or_

    from fluxocaixa.models import (
        Lancamento,
        ProjecaoVersao,
        Qualificador,
        SetorPrevisao,
        SimuladorCenario,
    )

    db = _db()
    db.session.rollback()
    for c in (SimuladorCenario.query.filter(SimuladorCenario.nom_cenario.like("CEN_TELA_MQ%"))
              .order_by(SimuladorCenario.seq_simulador_cenario.desc()).all()):
        for v in ProjecaoVersao.query.filter_by(seq_simulador_cenario=c.seq_simulador_cenario).all():
            db.session.delete(v)
        db.session.flush()
        db.session.delete(c)
        db.session.flush()
    quals = Qualificador.query.filter(
        Qualificador.num_ano_exercicio == EXERCICIO,
        or_(Qualificador.num_qualificador.like("1.87%"),
            Qualificador.num_qualificador.like("2.87%"))).all()
    seqs = [q.seq_qualificador for q in quals]
    if seqs:
        for lanc in Lancamento.query.filter(Lancamento.seq_qualificador.in_(seqs)).all():
            db.session.delete(lanc)
        for q in quals:
            q.seq_setor_previsao = None
        db.session.flush()
        for q in sorted(quals, key=lambda q: -len(q.num_qualificador)):
            db.session.delete(q)
            db.session.flush()
    for s in SetorPrevisao.query.filter(SetorPrevisao.sgl_setor.like("TELAMQ%")).all():
        db.session.delete(s)
    db.session.commit()


@pytest.fixture()
def ilha(client):
    from fluxocaixa.models import Lancamento, Qualificador
    from fluxocaixa.models.lancamento import TIPO_CREDITO
    from fluxocaixa.services.dominio_lancamento import resolver_origem
    from fluxocaixa.services.simulador_cenario_service import criar_simulador_cenario

    _limpar()
    db = _db()
    origem = resolver_origem("Manual").cod_origem_lancamento
    nos = {}
    for codigo, pai, realizado in (("1.87", None, None), ("1.87.1", "1.87", "300.00"),
                                   ("1.87.2", "1.87", "100.00")):
        q = Qualificador(num_qualificador=codigo, dsc_qualificador=f"Tela MQ {codigo}",
                         num_ano_exercicio=EXERCICIO, ind_status='A',
                         cod_qualificador_pai=nos[pai].seq_qualificador if pai else None)
        db.session.add(q)
        db.session.flush()
        nos[codigo] = q
        if realizado:
            db.session.add(Lancamento(
                dat_lancamento=date(2097, 3, 10), seq_qualificador=q.seq_qualificador,
                val_lancamento=Decimal(realizado), cod_tipo_lancamento=TIPO_CREDITO,
                cod_origem_lancamento=origem, cod_pessoa_inclusao=1, ind_status='A'))
    db.session.commit()
    cenario = criar_simulador_cenario(
        nom_cenario="CEN_TELA_MQ", dsc_cenario="tela", ano_base=EXERCICIO, num_periodos=12,
        tipo_cenario_receita='', config_receita={}, tipo_cenario_despesa='',
        config_despesa={}, user_id=1, json_config_base=json.dumps({"anos": [2097]}))
    yield {'cenario': cenario, **nos}
    _limpar()


def test_arvore_marcacao_e_cobertura(client, ilha):
    id = ilha['cenario'].seq_simulador_cenario
    bloco = ilha['1.87'].seq_qualificador

    resp = client.get(f'/simulador/{id}/metodos')
    assert resp.status_code == 200
    assert 'data-testid="arvore-metodos"' in resp.text
    assert 'data-testid="no-1.87.1"' in resp.text

    resp = client.post(f'/simulador/{id}/metodos', data={
        'seq_qualificador': bloco, 'cod_metodo': 'VALOR_FIXO', 'valor_anual': '1200'},
        follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers['location'].endswith(f'/simulador/{id}/metodos?no={bloco}')

    resp = client.get(f'/simulador/{id}/metodos?no={bloco}&cobertura=1')
    assert resp.status_code == 200
    assert 'data-testid="painel-cobertura"' in resp.text
    assert 'data-testid="painel-no"' in resp.text
    # a folha herda do bloco e a árvore mostra de onde veio
    linha = re.search(r'data-testid="no-1\.87\.1" data-origem="(\w+)" data-metodo="(\w*)"', resp.text)
    assert linha.groups() == ('HERDADA', 'VALOR_FIXO')


def test_metodo_invalido_vira_mensagem_e_nao_500(client, ilha):
    id = ilha['cenario'].seq_simulador_cenario
    resp = client.post(f'/simulador/{id}/metodos', data={
        'seq_qualificador': ilha['1.87.1'].seq_qualificador, 'cod_metodo': 'LOA'},
        headers={'accept': 'text/html'}, follow_redirects=False)
    assert resp.status_code == 303


def test_formula_propria_e_duplicar(client, ilha):
    from fluxocaixa.models import SimuladorCenario
    from fluxocaixa.services.metodo_qualificador_service import formula_da_folha

    id = ilha['cenario'].seq_simulador_cenario
    folha = ilha['1.87.2'].seq_qualificador
    resp = client.post(f'/simulador/{id}/formulas/{folha}',
                       data={'expressao': 'base * 1.1', 'no': folha}, follow_redirects=False)
    assert resp.status_code == 303
    assert formula_da_folha(id, folha) == ('base * 1.1', 'CENARIO')

    resp = client.post(f'/simulador/{id}/duplicar',
                       data={'nom_cenario': 'CEN_TELA_MQ copia'}, follow_redirects=False)
    assert resp.status_code == 303
    copia = SimuladorCenario.query.filter_by(nom_cenario='CEN_TELA_MQ copia').one()
    assert resp.headers['location'].endswith(f'/simulador/{copia.seq_simulador_cenario}/metodos')
    assert copia.seq_cenario_origem == id
    assert formula_da_folha(copia.seq_simulador_cenario, folha) == ('base * 1.1', 'CENARIO')
    assert 'data-testid="origem-copia"' in client.get(
        f'/simulador/{copia.seq_simulador_cenario}/metodos').text


def test_setores_e_propostas(client, ilha):
    from fluxocaixa.models import SetorPrevisao

    assert client.get('/previsao/setores').status_code == 200
    resp = client.post('/previsao/setores', data={'sgl_setor': 'TELAMQ', 'nom_setor': 'Setor tela'},
                       follow_redirects=False)
    assert resp.status_code == 303
    setor = SetorPrevisao.query.filter_by(sgl_setor='TELAMQ', ind_status='A').one()
    resp = client.post('/previsao/setores/recorte', data={
        'seq_qualificador': ilha['1.87.2'].seq_qualificador,
        'seq_setor_previsao': setor.seq_setor_previsao}, follow_redirects=False)
    assert resp.status_code == 303
    assert 'data-testid="setor-TELAMQ"' in client.get('/previsao/setores').text

    id = ilha['cenario'].seq_simulador_cenario
    resp = client.post(f'/simulador/{id}/setor',
                       data={'seq_setor_previsao': setor.seq_setor_previsao}, follow_redirects=False)
    assert resp.status_code == 303
    assert 'data-testid="cenario-setorial"' in client.get(f'/simulador/{id}/metodos').text
    assert client.get('/previsao/propostas').status_code == 200


def test_planilha_modelo_e_importacao(client, ilha):
    from fluxocaixa.services.metodo_qualificador_service import (
        carregar_marcacoes,
        config_da_marcacao,
    )

    id = ilha['cenario'].seq_simulador_cenario
    resp = client.get(f'/simulador/{id}/metodos/modelo-csv')
    assert resp.status_code == 200
    assert resp.content.decode('utf-8-sig').startswith('codigo;descricao;mes;valor')
    assert '1.87.1;' in resp.content.decode('utf-8-sig')

    csv = "codigo;mes;valor\n1.87.1;1;10,00\n1.87.1;2;20,00\n1.87;3;5,00\n"
    resp = client.post(f'/simulador/{id}/metodos/importar',
                       files={'arquivo': ('proposta.csv', csv.encode('utf-8'), 'text/csv')})
    assert resp.status_code == 200
    token = re.search(r'/importacoes/([\w-]+)/confirmar', resp.text).group(1)
    resp = client.post(f'/importacoes/{token}/confirmar', follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers['location'] == f'/simulador/{id}/metodos'

    marcacao = carregar_marcacoes(id)[ilha['1.87.1'].seq_qualificador]
    assert marcacao.cod_metodo == 'VALOR_FIXO'
    assert config_da_marcacao(marcacao) == {'valores_mensais': {'1': 10.0, '2': 20.0}}
    # "1.87" é bloco: linha recusada no preview, nada gravado para ele
    assert ilha['1.87'].seq_qualificador not in carregar_marcacoes(id)


# ---------------------------------------------------------------------------
# Formulário do simulador — modo "método por qualificador"
# ---------------------------------------------------------------------------

def _form_base(nome):
    return {'nom_cenario': nome, 'dsc_cenario': 'form', 'ano_base': str(EXERCICIO),
            'cod_periodicidade': 'MENSAL', 'num_periodos': '12',
            'cod_metodo_base': 'MEDIA_SIMPLES', 'modo_projecao': 'QUALIFICADOR'}


def test_formulario_oferece_a_escolha_do_modo(client, ilha):
    corpo = client.get('/simulador/novo').text
    assert 'data-testid="modo-projecao"' in corpo
    assert 'data-testid="arvore-metodos-form"' in corpo


def test_criar_por_qualificador_grava_as_marcacoes_junto(client, ilha):
    from fluxocaixa.models import CenarioConfig, SimuladorCenario
    from fluxocaixa.services.metodo_qualificador_service import (
        carregar_marcacoes,
        config_da_marcacao,
    )

    bloco, folha = ilha['1.87'].seq_qualificador, ilha['1.87.2'].seq_qualificador
    dados = {**_form_base('CEN_TELA_MQ form'),
             f'metodo_{bloco}': 'VALOR_FIXO', f'param_{bloco}': '1200',
             f'metodo_{folha}': 'PERCENTUAL', f'param_{folha}': '10',
             f'metodo_{ilha["1.87.1"].seq_qualificador}': ''}
    resp = client.post('/simulador/criar', data=dados, follow_redirects=False)
    assert resp.status_code == 303
    cenario = SimuladorCenario.query.filter_by(nom_cenario='CEN_TELA_MQ form').one()
    assert resp.headers['location'] == f'/simulador/{cenario.seq_simulador_cenario}/metodos?cobertura=1'
    # modo por qualificador: sem padrão nas pernas
    assert CenarioConfig.query.filter_by(
        seq_simulador_cenario=cenario.seq_simulador_cenario).count() == 0
    marcacoes = carregar_marcacoes(cenario.seq_simulador_cenario)
    assert set(marcacoes) == {bloco, folha}
    assert config_da_marcacao(marcacoes[bloco]) == {'valor_anual': 1200.0}
    assert config_da_marcacao(marcacoes[folha])['percentual'] == 10.0


def test_criar_por_qualificador_invalido_nao_grava_nada(client, ilha):
    from fluxocaixa.models import SimuladorCenario

    bloco = ilha['1.87'].seq_qualificador
    dados = {**_form_base('CEN_TELA_MQ invalido'), f'metodo_{bloco}': 'VALOR_FIXO',
             f'param_{bloco}': ''}
    resp = client.post('/simulador/criar', data=dados, headers={'accept': 'text/html'},
                       follow_redirects=False)
    assert resp.status_code == 303  # flash + volta ao formulário
    assert SimuladorCenario.query.filter_by(nom_cenario='CEN_TELA_MQ invalido').count() == 0


def test_editar_por_qualificador_sincroniza_marcacoes(client, ilha):
    from fluxocaixa.services.metodo_qualificador_service import (
        MANTER,
        carregar_marcacoes,
        definir_marcacao,
    )

    id = ilha['cenario'].seq_simulador_cenario
    bloco, f1, f2 = (ilha[c].seq_qualificador for c in ('1.87', '1.87.1', '1.87.2'))
    definir_marcacao(id, bloco, 'VALOR_FIXO', {'valor_anual': '100'}, 1)
    definir_marcacao(id, f1, 'VALOR_FIXO', {'valores_mensais': {'1': '5'}}, 1)  # não editável no form

    corpo = client.get(f'/simulador/{id}/editar').text
    assert f'value="{MANTER}" selected' in corpo  # a mensal aparece como "manter"

    dados = {**_form_base('CEN_TELA_MQ'), f'metodo_{bloco}': '',
             f'metodo_{f1}': MANTER, f'metodo_{f2}': 'MODELO:MEDIA_CRESCIMENTO'}
    resp = client.post(f'/simulador/{id}/atualizar', data=dados, follow_redirects=False)
    assert resp.status_code == 303
    marcacoes = carregar_marcacoes(id)
    assert bloco not in marcacoes                       # '' = voltou a herdar
    assert marcacoes[f1].cod_metodo == 'VALOR_FIXO'     # MANTER preservou
    assert marcacoes[f2].cod_metodo == 'MODELO'
