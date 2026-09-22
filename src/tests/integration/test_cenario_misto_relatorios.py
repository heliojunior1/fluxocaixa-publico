"""Cenário MISTO (vários métodos por qualificador) atravessando os relatórios.

Criado pelo FORMULÁRIO do simulador no modo "método por qualificador":
valor fixo num bloco, Holt-Winters, percentual e fórmula em folhas de receita;
LOA, média histórica e "sem projeção" na despesa. Depois: publica a versão e
abre TODO relatório que lê projeção — DFC projetado, resumo, previsão de
receita, controle de despesa, previsão × realizado, simulação de
disponibilidade — e o backtest, cuja recomendação volta ao cenário.

Ilha própria e autossuficiente (não depende do seed, que outros testes
alteram): plano do exercício 2086, receita "1.86", despesa "2.86", 36 meses
de realizado sazonal em 2083–2085, LOA 2086 e fórmula de biblioteca.
"""
import math
from datetime import date
from decimal import Decimal

import pytest

ANO = 2086
NOME = "CEN_MISTO_REL"
PLANO = (  # código, pai, base mensal do realizado (None = bloco)
    ("1.86", None, None), ("1.86.1", "1.86", None),
    ("1.86.1.1", "1.86.1", 3000), ("1.86.1.2", "1.86.1", 1000),
    ("1.86.2", "1.86", 5000), ("1.86.3", "1.86", 800), ("1.86.4", "1.86", 600),
    ("2.86", None, None),
    ("2.86.1", "2.86", 2000), ("2.86.2", "2.86", 1500), ("2.86.3", "2.86", 300),
)


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from sqlalchemy import or_, text

    from fluxocaixa.models import (
        Lancamento,
        Loa,
        ProjecaoVersao,
        Qualificador,
        RubricaFormula,
        SimuladorCenario,
    )

    db = _db()
    db.session.rollback()
    for c in (SimuladorCenario.query.filter(SimuladorCenario.nom_cenario.like(f"{NOME}%"))
              .order_by(SimuladorCenario.seq_simulador_cenario.desc()).all()):
        for v in ProjecaoVersao.query.filter_by(seq_simulador_cenario=c.seq_simulador_cenario).all():
            db.session.delete(v)
        db.session.flush()
        db.session.delete(c)
        db.session.flush()
    quals = Qualificador.query.filter(
        Qualificador.num_ano_exercicio == ANO,
        or_(Qualificador.num_qualificador.like("1.86%"),
            Qualificador.num_qualificador.like("2.86%"))).all()
    seqs = [q.seq_qualificador for q in quals]
    if seqs:
        for modelo in (Lancamento, Loa, RubricaFormula):
            for linha in modelo.query.filter(modelo.seq_qualificador.in_(seqs)).all():
                db.session.delete(linha)
        db.session.execute(text(
            "DELETE FROM flc_backtest_recomendacao WHERE seq_qualificador IN "
            f"({','.join(map(str, seqs))})"))
        db.session.flush()
        for q in sorted(quals, key=lambda q: -len(q.num_qualificador)):
            db.session.delete(q)
            db.session.flush()
    db.session.commit()


@pytest.fixture()
def escolha(client):
    from fluxocaixa.models import Lancamento, Loa, Qualificador, RubricaFormula
    from fluxocaixa.models.lancamento import TIPO_CREDITO, TIPO_DEBITO
    from fluxocaixa.services.dominio_lancamento import resolver_origem

    _limpar()
    db = _db()
    origem = resolver_origem("Manual").cod_origem_lancamento
    nos = {}
    for codigo, pai, base in PLANO:
        q = Qualificador(num_qualificador=codigo, dsc_qualificador=f"Misto {codigo}",
                         num_ano_exercicio=ANO, ind_status='A',
                         cod_qualificador_pai=nos[pai] if pai else None)
        db.session.add(q)
        db.session.flush()
        nos[codigo] = q.seq_qualificador
        if base is None:
            continue
        for ano in (ANO - 3, ANO - 2, ANO - 1):
            crescimento = 1 + 0.05 * (ano - (ANO - 3))
            for mes in range(1, 13):
                valor = base * crescimento * (1 + 0.2 * math.sin(mes / 12 * 2 * math.pi))
                db.session.add(Lancamento(
                    dat_lancamento=date(ano, mes, 10), seq_qualificador=q.seq_qualificador,
                    val_lancamento=Decimal(f"{valor:.2f}"),
                    cod_tipo_lancamento=TIPO_CREDITO if codigo.startswith("1") else TIPO_DEBITO,
                    cod_origem_lancamento=origem, cod_pessoa_inclusao=1, ind_status='A'))
    db.session.add(Loa(num_ano=ANO, seq_qualificador=nos["2.86.1"], val_loa=Decimal("30000.00"),
                       ind_status='A'))
    db.session.add(RubricaFormula(seq_qualificador=nos["1.86.4"], nom_formula="Misto",
                                  dsc_formula_expressao="base * (1 + taxa_misto_rel)",
                                  ind_status='A'))
    db.session.commit()
    yield {
        'bloco': nos["1.86.1"],
        'folhas_bloco': [nos["1.86.1.1"], nos["1.86.1.2"]],
        'holt': nos["1.86.2"],
        'percentual': nos["1.86.3"],
        'formula': nos["1.86.4"],
        'loa': nos["2.86.1"],
        'media': nos["2.86.2"],
        'sem': nos["2.86.3"],
    }
    _limpar()


def _criar_pelo_formulario(client, e) -> int:
    from fluxocaixa.models import SimuladorCenario

    dados = {
        'nom_cenario': NOME, 'dsc_cenario': 'misto', 'ano_base': str(ANO),
        'cod_periodicidade': 'MENSAL', 'num_periodos': '12',
        'cod_metodo_base': 'MEDIA_SIMPLES', 'anos_selecionados_cenario': f'[{ANO - 1}]',
        'modo_projecao': 'QUALIFICADOR',
        f"metodo_{e['bloco']}": 'VALOR_FIXO', f"param_{e['bloco']}": '5000000',
        f"metodo_{e['holt']}": 'MODELO:HOLT_WINTERS',
        f"metodo_{e['percentual']}": 'PERCENTUAL', f"param_{e['percentual']}": '4.5',
        f"metodo_{e['loa']}": 'LOA',
        f"metodo_{e['media']}": 'MODELO:MEDIA_HISTORICA',
        f"metodo_{e['sem']}": 'SEM_PROJECAO', f"param_{e['sem']}": 'rubrica descontinuada',
    }
    dados[f"metodo_{e['formula']}"] = 'FORMULA'
    dados['formula_param_taxa_misto_rel'] = '0.04'
    resp = client.post('/simulador/criar', data=dados, follow_redirects=False)
    assert resp.status_code == 303, resp.text[:500]
    return SimuladorCenario.query.filter_by(nom_cenario=NOME).one().seq_simulador_cenario


def _projetado_por_folha(resultado) -> dict:
    saida: dict = {}
    for chave in ('projecao_receita_detalhada', 'projecao_despesa_detalhada'):
        df = resultado.get(chave)
        if df is None or not len(df):
            continue
        for seq, grupo in df.groupby('seq_qualificador'):
            saida[int(seq)] = (float(grupo['valor_projetado'].sum()), set(grupo['cod_metodo']))
    return saida


def test_cenario_misto_projeta_e_os_relatorios_funcionam(client, escolha):
    from fluxocaixa.services.metodo_qualificador_service import cobertura
    from fluxocaixa.services.relatorio.dfc_projecao import resolver_projecao
    from fluxocaixa.services.simulador_cenario_service import executar_simulacao, get_simulador

    e = escolha
    id = _criar_pelo_formulario(client, e)

    # 1. Cada método projetou a sua rubrica, com o rastro do método
    resultado = executar_simulacao(id)
    por_folha = _projetado_por_folha(resultado)
    esperados = {e['holt']: 'MODELO', e['percentual']: 'PERCENTUAL',
                 e['loa']: 'LOA', e['media']: 'MODELO', e['formula']: 'FORMULA'}
    for folha in e['folhas_bloco']:
        esperados[folha] = 'VALOR_FIXO'
    for seq, metodo in esperados.items():
        assert seq in por_folha, f"rubrica {seq} ({metodo}) sem projeção"
        total, metodos = por_folha[seq]
        assert total > 0, f"rubrica {seq} ({metodo}) projetou zero"
        assert metodos == {metodo}
    # valor fixo do bloco distribuído: soma exata
    assert round(sum(por_folha[f][0] for f in e['folhas_bloco']), 2) == 5000000.00
    assert por_folha[e['sem']][0] == 0

    cob = cobertura(get_simulador(id), resultado)
    status = {i['seq_qualificador']: i['status'] for p in ('C', 'D') for i in cob[p]}
    assert status[e['sem']] == 'DECLARADA'
    assert all(status[s] == 'PROJETADA' for s in esperados)

    # 2. Telas do cenário
    assert client.get(f'/simulador/{id}').status_code == 200
    assert client.get(f'/simulador/{id}/metodos?cobertura=1').status_code == 200
    assert client.get(f'/simulador/{id}/editar').status_code == 200

    # 3. Publica (confirmado cobre lacuna eventual; aqui a ilha está coberta)
    resp = client.post(f'/simulador/{id}/historico/salvar', data={
        'nom_versao': 'misto v1', 'publicar': 'S', 'confirmado': 'S'}, follow_redirects=False)
    assert resp.status_code == 303
    assert client.get(f'/simulador/{id}/historico').status_code == 200

    # 4. Porta única: o que os relatórios leem é a versão publicada, por folha
    mapa, origem = resolver_projecao(id, ANO)
    assert origem['ao_vivo'] is False
    lidos = {seq for (seq, _t, _m), v in mapa.items() if v}
    assert set(esperados) <= lidos
    assert None not in lidos  # nada agregado sem rubrica

    # 5. Relatórios que usam projeção
    resp = client.post('/relatorios/dfc', data={'estrategia': 'projetado', 'cenario_id': str(id),
                                                 'periodo': 'ano', 'mes_ano': str(ANO)})
    assert resp.status_code == 200 and 'flash-erro' not in resp.text
    resp = client.post('/relatorios/resumo', data={'estrategia': 'projetado', 'cenario_id': str(id),
                                                    'ano': str(ANO)})
    assert resp.status_code == 200 and 'flash-erro' not in resp.text

    receita_ids = [e['holt'], e['percentual'], *e['folhas_bloco']]
    dados = client.get('/relatorios/previsao-receita/data', params={
        'ano': ANO, 'cenario': id, 'qualificadores': ','.join(map(str, receita_ids))}).json()
    previsto = {c['qualificador_id']: c['previsao_total'] for c in dados['composicao_anual']}
    assert all(previsto[s] > 0 for s in receita_ids), previsto
    assert dados['projecao_origem']['ao_vivo'] is False

    despesa_ids = [e['loa'], e['media']]
    dados = client.get('/relatorios/controle-despesa/data', params={
        'ano': ANO, 'cenario': id, 'qualificadores': ','.join(map(str, despesa_ids))}).json()
    assert dados['kpis']['previsao_total'] > 0
    previsto = {c['qualificador_id']: c['previsao_total'] for c in dados['execucao_por_grupo']}
    assert all(previsto[s] > 0 for s in despesa_ids), previsto

    resp = client.get('/relatorios/previsao-realizado/data', params={
        'ano': ANO, 'cenario': id, 'qualificadores': ','.join(map(str, receita_ids + despesa_ids))})
    assert resp.status_code == 200
    assert resp.json()['tabela']

    resp = client.get('/simulacao-desembolso', params={'cenario': id, 'ano': ANO, 'mes': 1})
    assert resp.status_code == 200 and 'flash-erro' not in resp.text

    for pagina in ('/relatorios/indicadores', '/relatorios/analise-comparativa',
                   '/relatorios/kpis', '/relatorios/previsao-receita',
                   '/relatorios/controle-despesa', '/relatorios/previsao-realizado'):
        assert client.get(pagina).status_code == 200, pagina


def test_backtest_e_recomendacao_voltam_ao_cenario_misto(client, escolha):
    from fluxocaixa.services.metodo_qualificador_service import (
        carregar_marcacoes,
        recomendacoes_aplicaveis,
    )
    from fluxocaixa.services.simulador_cenario_service import get_simulador

    e = escolha
    id = _criar_pelo_formulario(client, e)

    assert client.get('/relatorios/backtest').status_code == 200
    resp = client.post('/relatorios/backtest/executar', json={
        'anos_treino': [ANO - 3, ANO - 2], 'anos_teste': [ANO - 1],
        'modelos': ['MEDIA_HISTORICA', 'CRESCIMENTO_ANO', 'HOLT_WINTERS'],
        'qualificadores_ids': [e['percentual'], e['holt']],
    })
    assert resp.status_code == 200, resp.text[:500]
    resultado = resp.json()
    assert 'error' not in resultado

    resp = client.post('/relatorios/backtest/salvar-recomendacao', json=resultado)
    assert resp.status_code == 200, resp.text[:300]

    recomendacoes = recomendacoes_aplicaveis(get_simulador(id))
    alvos = {r['seq_qualificador'] for r in recomendacoes} & {e['percentual'], e['holt']}
    assert alvos, f"nenhuma recomendação aplicável: {recomendacoes}"
    resp = client.post(f'/simulador/{id}/recomendacoes',
                       data={'seq_qualificador': [str(s) for s in alvos]}, follow_redirects=False)
    assert resp.status_code == 303
    marcacoes = carregar_marcacoes(id)
    assert all(marcacoes[s].cod_metodo == 'MODELO' for s in alvos)
    # o cenário continua executando depois de aplicar as recomendações
    assert client.get(f'/simulador/{id}/metodos?cobertura=1').status_code == 200
