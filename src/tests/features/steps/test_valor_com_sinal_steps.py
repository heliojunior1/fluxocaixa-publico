"""Steps BDD — costura `valor_com_sinal`, auditoria e rede (spec R6–R8).

Ataque na camada de serviço/repositório. A massa reusa a ilha 2019 da rede de
caracterização (`tests/caracterizacao.py`), que é hermética ao seed demo.
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ... import caracterizacao as carac
from ... import costura as guarda

scenarios("../cadastros-nucleo/valor_com_sinal.feature")

ANO = carac.ANO
DIA = carac.DIA_BASE


@pytest.fixture()
def contexto():
    return {}


@pytest.fixture(autouse=True)
def _ilha_limpa(app):
    """Cada cenário começa com a ilha vazia e a deixa vazia."""
    carac.limpar_massa()
    yield
    carac.limpar_massa()


def _db():
    from fluxocaixa.models.base import db

    return db


def _lancar(qual: str, valor: str, tipo: str, seq_conta=None,
            dat: date | None = None, origem: str = "Manual"):
    carac._lancamento(qual, valor, dat or DIA, tipo, seq_conta, origem_desc=origem)


def _auditar(**kwargs):
    from fluxocaixa.services.auditoria_sinal_service import (
        auditar_coerencia_sinal_tipo,
    )

    return auditar_coerencia_sinal_tipo(**kwargs)


def _seqs_da_amostra(resultado) -> set[int]:
    return {item["seq_lancamento"] for item in resultado["amostra"]}


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given(parsers.parse('uma receita de "{receita}" e uma despesa de "{despesa}" na ilha de caracterização'))
def receita_e_despesa(receita, despesa):
    _lancar(carac.QUAL_RECEITA, receita, "Entrada")
    _lancar(carac.QUAL_DESPESA, despesa, "Saída")


@given(parsers.parse('uma conta de caracterização com entrada de "{entrada}" e saída de "{saida}" no mesmo dia'),
       target_fixture="conta")
def conta_com_movimento(entrada, saida):
    conta = carac._conta(carac.CONTA_A)
    _lancar(carac.QUAL_RECEITA, entrada, "Entrada", seq_conta=conta.seq_conta)
    _lancar(carac.QUAL_DESPESA, saida, "Saída", seq_conta=conta.seq_conta)
    return conta


@given("um cenário de projeção com versão publicada e realizado a apurar na ilha",
       target_fixture="versao")
def cenario_com_versao(contexto):
    from datetime import datetime

    from fluxocaixa.models import ProjecaoValor, ProjecaoVersao, SimuladorCenario

    db = _db()
    # Realizado precisa estar em mês FECHADO — a ilha 2019 já é passado
    _lancar(carac.QUAL_RECEITA, "500.00", "Entrada")
    _lancar(carac.QUAL_DESPESA, "-200.00", "Saída")

    cenario = SimuladorCenario(
        nom_cenario="Cenário costura", dsc_cenario="R6", ano_base=ANO,
        num_periodos=12, cod_periodicidade='MENSAL', ind_status='A',
    )
    db.session.add(cenario)
    db.session.commit()
    versao = ProjecaoVersao(
        seq_simulador_cenario=cenario.seq_simulador_cenario,
        nom_versao="v1 costura", dat_versao=datetime(2026, 1, 1, 12, 0, 0),
        ind_publicado='S',
    )
    db.session.add(versao)
    db.session.commit()
    for qual, tipo in ((carac.QUAL_RECEITA, 'C'), (carac.QUAL_DESPESA, 'D')):
        db.session.add(ProjecaoValor(
            seq_projecao_versao=versao.seq_projecao_versao,
            seq_qualificador=carac._qualificador(qual).seq_qualificador,
            cod_tipo=tipo, ano=ANO, num_periodo=DIA.month, val_projetado=Decimal("1.00"),
        ))
    db.session.commit()
    return versao


def _lancar_incoerente(qual_num: str, cod_tipo: str, valor: str):
    """Escreve direto no model: desde a F6.1b o serviço impõe valor > 0, e a
    incoerência que a auditoria vigia só entra por escrita direta no banco."""
    from fluxocaixa.models import Lancamento
    from fluxocaixa.services.dominio_lancamento import resolver_origem

    db = _db()
    db.session.add(Lancamento(
        dat_lancamento=DIA,
        seq_qualificador=carac._qualificador(qual_num).seq_qualificador,
        val_lancamento=Decimal(valor),
        cod_tipo_lancamento=cod_tipo,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        cod_pessoa_inclusao=1,
        ind_status='A',
    ))
    db.session.commit()
    return _ultimo_lancamento()


@given(parsers.parse('um lançamento de receita com valor "{valor}" na ilha de caracterização'),
       target_fixture="lancamento")
def receita_com_valor(app, valor):
    return _lancar_incoerente(carac.QUAL_RECEITA, 'C', valor)


@given(parsers.parse('um lançamento de despesa com valor "{valor}" na ilha de caracterização'),
       target_fixture="lancamento")
def despesa_com_valor(app, valor):
    return _lancar_incoerente(carac.QUAL_DESPESA, 'D', valor)


@given("apenas lançamentos coerentes na ilha de caracterização")
def apenas_coerentes():
    _lancar(carac.QUAL_RECEITA, "1000.00", "Entrada")
    _lancar(carac.QUAL_DESPESA, "-300.00", "Saída")


@given("o snapshot de caracterização coletado", target_fixture="snapshot_base")
def snapshot_base():
    carac.montar_massa()
    return carac.coletar_snapshot()


def _ultimo_lancamento():
    from fluxocaixa.models import Lancamento

    return (
        Lancamento.query.order_by(Lancamento.seq_lancamento.desc()).first()
    )


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when("varro os repositórios e os serviços de relatório em busca de leitura crua")
def varre_costura(contexto):
    contexto["violacoes"] = guarda.violacoes()


@when("somo o valor com sinal do período da ilha")
def soma_com_sinal(contexto):
    from sqlalchemy import extract, func

    from fluxocaixa.models import Lancamento

    db = _db()
    total = (
        db.session.query(func.sum(Lancamento.valor_com_sinal))
        .filter(Lancamento.ind_status == 'A',
                extract('year', Lancamento.dat_lancamento) == ANO)
        .scalar()
    )
    contexto["soma"] = Decimal(str(total or 0)).quantize(Decimal("0.01"))


@when("consulto as somas de entradas e de saídas da conta no dia")
def somas_da_conta(contexto, conta):
    from fluxocaixa.repositories.lancamento_repository import LancamentoRepository

    repo = LancamentoRepository()
    contexto["entradas"] = repo.get_sum_by_account_on_date_positive(
        seq_conta=conta.seq_conta, on_date=DIA)
    contexto["saidas"] = repo.get_sum_by_account_on_date_negative(
        seq_conta=conta.seq_conta, on_date=DIA)


@when("atualizo os realizados da versão a partir dos lançamentos")
def atualiza_realizados(contexto, versao):
    from fluxocaixa.services.projecao_versao_service import (
        atualizar_realizados_de_lancamentos,
    )

    contexto["atualizados"] = atualizar_realizados_de_lancamentos(
        versao.seq_projecao_versao
    )
    contexto["versao"] = versao


@when("executo a auditoria de coerência")
def executa_auditoria(contexto):
    contexto["auditoria"] = _auditar(ano=ANO)


@when("executo a auditoria de coerência restrita à ilha")
def executa_auditoria_ilha(contexto):
    contexto["auditoria"] = _auditar(ano=ANO)


@when("coleto o snapshot de caracterização")
def coleta_snapshot(contexto):
    carac.montar_massa()
    contexto["snapshot"] = carac.coletar_snapshot()


@when("coleto o snapshot de caracterização duas vezes")
def coleta_duas_vezes(contexto):
    carac.montar_massa()
    contexto["snapshot"] = carac.coletar_snapshot()
    contexto["snapshot2"] = carac.coletar_snapshot()


@when("um valor de um relatório coberto muda")
def muda_um_valor(contexto, snapshot_base):
    import copy

    mutado = copy.deepcopy(snapshot_base)
    mutado["kpis"]["receita_despesa"]["receita"] = "999999.99"
    contexto["snapshot_mutado"] = mutado


@when("inspeciono a massa da caracterização")
def inspeciona_massa(contexto):
    from sqlalchemy import extract

    from fluxocaixa.models import Lancamento

    carac.montar_massa()
    contexto["lancamentos"] = Lancamento.query.filter(
        extract('year', Lancamento.dat_lancamento) == ANO,
        Lancamento.ind_status == 'A',
    ).all()


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('nenhuma referência a "{termo}" aparece fora da allow-list'))
def sem_violacoes(contexto, termo):
    assert contexto["violacoes"] == [], (
        f"leitura crua de {termo}:\n  " + "\n  ".join(contexto["violacoes"])
    )


@then(parsers.parse('a soma é "{valor}"'))
def soma_confere(contexto, valor):
    assert contexto["soma"] == Decimal(valor)


@then("a soma coincide com o total de receita menos despesa do DFC do período")
def soma_bate_com_dfc(contexto):
    from fluxocaixa.services.relatorio.dfc_service import get_dfc_data

    dfc = get_dfc_data("ano", ANO, None, list(range(1, 13)), "realizado", None)
    total_dfc = Decimal(str(sum(dfc["totals"]))).quantize(Decimal("0.01"))
    assert total_dfc == contexto["soma"], f"DFC={total_dfc} soma={contexto['soma']}"


@then(parsers.parse('a soma de entradas é "{valor}"'))
def entradas_conferem(contexto, valor):
    assert Decimal(str(contexto["entradas"])).quantize(Decimal("0.01")) == Decimal(valor)


@then(parsers.parse('a soma de saídas é "{valor}"'))
def saidas_conferem(contexto, valor):
    assert Decimal(str(contexto["saidas"])).quantize(Decimal("0.01")) == Decimal(valor)


@then("o realizado de receita foi gravado")
def realizado_receita(contexto):
    _assert_realizado(contexto, 'C')


@then("o realizado de despesa foi gravado")
def realizado_despesa(contexto):
    _assert_realizado(contexto, 'D')


def _assert_realizado(contexto, cod_tipo: str):
    from fluxocaixa.models import ProjecaoValor

    linhas = ProjecaoValor.query.filter_by(
        seq_projecao_versao=contexto["versao"].seq_projecao_versao,
        cod_tipo=cod_tipo,
    ).all()
    assert linhas, f"nenhuma linha de projeção do tipo {cod_tipo}"
    assert any(l.val_realizado is not None and Decimal(str(l.val_realizado)) != 0
               for l in linhas), (
        f"realizado do tipo {cod_tipo} não foi gravado — o mapa de tipo "
        f"provavelmente devolveu None (regressão do {{1:'R',2:'D'}})"
    )


@then(parsers.parse('o lançamento consta na auditoria com motivo "{motivo}"'))
def consta_na_auditoria(contexto, lancamento, motivo):
    resultado = contexto["auditoria"]
    assert lancamento.seq_lancamento in _seqs_da_amostra(resultado)
    item = next(i for i in resultado["amostra"]
                if i["seq_lancamento"] == lancamento.seq_lancamento)
    assert item["motivo"] == motivo
    assert resultado["por_motivo"][motivo] >= 1


@then("a auditoria da ilha não retorna nenhum lançamento")
def auditoria_vazia(contexto):
    assert contexto["auditoria"]["total"] == 0
    assert contexto["auditoria"]["amostra"] == []


@then("o valor, o tipo e a situação do lançamento permanecem inalterados")
def lancamento_intacto(contexto, lancamento):
    from fluxocaixa.models import Lancamento

    _db().session.expire_all()
    atual = Lancamento.query.get(lancamento.seq_lancamento)
    assert Decimal(str(atual.val_lancamento)) == Decimal(str(lancamento.val_lancamento))
    assert atual.cod_tipo_lancamento == lancamento.cod_tipo_lancamento
    assert atual.ind_status == 'A'


@then("há snapshot para cada relatório coberto")
def snapshot_completo(contexto):
    for relatorio in carac.RELATORIOS_COBERTOS:
        assert relatorio in contexto["snapshot"], f"falta {relatorio}"


@then("os dois snapshots são idênticos")
def snapshots_iguais(contexto):
    assert carac.diferencas(contexto["snapshot"], contexto["snapshot2"]) == []


@then("a comparação com o snapshot acusa o relatório e o campo divergentes")
def comparacao_acusa(contexto, snapshot_base):
    divergencias = carac.diferencas(snapshot_base, contexto["snapshot_mutado"])
    assert divergencias, "a rede não acusou a divergência"
    assert any("kpis" in d and "receita" in d for d in divergencias), divergencias


@then(parsers.parse('todo lançamento da massa tem valor positivo e tipo "{c}" ou "{d}"'))
def massa_coerente(contexto, c, d):
    for lancamento in contexto["lancamentos"]:
        assert lancamento.val_lancamento > 0, lancamento.seq_lancamento
        assert lancamento.cod_tipo_lancamento in (c, d), lancamento.seq_lancamento


@then("há lançamento de crédito e lançamento de débito")
def tem_credito_e_debito(contexto):
    from fluxocaixa.models.lancamento import TIPO_CREDITO, TIPO_DEBITO

    tipos = {l.cod_tipo_lancamento for l in contexto["lancamentos"]}
    assert TIPO_CREDITO in tipos and TIPO_DEBITO in tipos, tipos


@then("há lançamento sem conta vinculada")
def tem_sem_conta(contexto):
    assert any(l.seq_conta is None for l in contexto["lancamentos"])


@then(parsers.parse('há lançamento de origem "{origem}"'))
def tem_origem(contexto, origem):
    from fluxocaixa.services.dominio_lancamento import resolver_origem

    cod = resolver_origem(origem).cod_origem_lancamento
    assert any(l.cod_origem_lancamento == cod for l in contexto["lancamentos"])
