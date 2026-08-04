"""Steps BDD — tipo 'C'/'D' com valor positivo (spec cadastros-nucleo R2, R9–R11).

Ilha de datas 2038 (2019 é da rede de caracterização; 2022–2037 do seed e das
demais features).
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../cadastros-nucleo/tipo_lancamento_cd.feature")

ANO = 2038
DIA = date(ANO, 4, 10)
QUAL_RECEITA = "1.98.1"
QUAL_DESPESA = "2.98.1"


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar_ilha():
    from sqlalchemy import extract

    from fluxocaixa.models import EtlStaging, Lancamento, Mapeamento

    db = _db()
    db.session.rollback()
    Lancamento.query.filter(
        extract("year", Lancamento.dat_lancamento) == ANO
    ).delete(synchronize_session=False)
    EtlStaging.query.filter_by(num_ano_exercicio=ANO).delete(synchronize_session=False)
    for mapeamento in Mapeamento.query.filter_by(num_ano_exercicio=ANO).all():
        db.session.delete(mapeamento)
    db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar_ilha()
    yield
    _limpar_ilha()


def _qualificador(num: str):
    from fluxocaixa.models import Qualificador

    db = _db()
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    if q is not None:
        return q
    partes = num.split(".")
    pai = _qualificador(".".join(partes[:-1])) if len(partes) > 1 else None
    q = Qualificador(num_qualificador=num, dsc_qualificador=f"Rubrica convergência {num}",
                     cod_qualificador_pai=pai.seq_qualificador if pai else None)
    db.session.add(q)
    db.session.commit()
    return q


def _lancamentos_da_ilha():
    from sqlalchemy import extract

    from fluxocaixa.models import Lancamento

    return Lancamento.query.filter(
        extract("year", Lancamento.dat_lancamento) == ANO
    ).all()


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given(parsers.parse('um lançamento gravado com tipo "{tipo}" e valor "{valor}" na ilha de convergência'),
       target_fixture="lancamento")
def lancamento_gravado(app, tipo, valor):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.services.dominio_lancamento import resolver_origem

    db = _db()
    qual = QUAL_RECEITA if tipo == "C" else QUAL_DESPESA
    lanc = Lancamento(
        dat_lancamento=DIA,
        seq_qualificador=_qualificador(qual).seq_qualificador,
        val_lancamento=Decimal(valor),
        cod_tipo_lancamento=tipo,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        cod_pessoa_inclusao=1,
        ind_status='A',
    )
    db.session.add(lanc)
    db.session.commit()
    return lanc


@given(parsers.parse('um mapeamento de convergência do tipo {tipo_map} com uma linha de staging de "{valor}"'),
       target_fixture="mapeamento")
def mapeamento_com_staging(app, contexto, tipo_map, valor):
    return _montar_mapeamento(contexto, tipo_map, valor, inverter=False)


@given(parsers.parse('um mapeamento de convergência do tipo {tipo_map} com inversão de sinal e uma linha de staging de "{valor}"'),
       target_fixture="mapeamento")
def mapeamento_com_inversao(app, contexto, tipo_map, valor):
    return _montar_mapeamento(contexto, tipo_map, valor, inverter=True)


def _montar_mapeamento(contexto, tipo_map: str, valor: str, inverter: bool):
    from fluxocaixa.models import (
        EtlStaging,
        FonteExtracao,
        ItemMapeamento,
        Mapeamento,
        SistemaOrigem,
    )
    from fluxocaixa.models.extracao import ExecucaoExtracao

    from .conftest_regra import TERMOS_PADRAO, criar_termo, termo_por_nome

    db = _db()
    # A regra do item precisa do dicionário de termos (F4.2)
    for nom, origem, campo, tipo in TERMOS_PADRAO:
        if termo_por_nome(nom) is None:
            criar_termo(nom, origem, campo, tipo)

    sistema = SistemaOrigem.query.filter_by(txt_sigla="SIS_CONVERG").first()
    if sistema is None:
        sistema = SistemaOrigem(txt_sigla="SIS_CONVERG",
                                dsc_sistema_origem="Sistema convergência")
        db.session.add(sistema)
        db.session.commit()

    fonte = FonteExtracao.query.filter_by(nom_fonte="Fonte convergência").first()
    if fonte is None:
        fonte = FonteExtracao(
            nom_fonte="Fonte convergência", cod_tipo_conector="FAKE_CONV",
            cod_destino="LANCAMENTO", seq_sistema_origem=sistema.seq_sistema_origem,
            json_config={}, ind_status='A',
        )
        db.session.add(fonte)
        db.session.commit()

    execucao = ExecucaoExtracao(
        seq_fonte_extracao=fonte.seq_fonte_extracao, dat_inicio_execucao=DIA,
        cod_disparo="MANUAL", cod_status="SUCESSO",
        dat_janela_inicio=DIA, dat_janela_fim=DIA,
    )
    db.session.add(execucao)
    db.session.flush()

    qual = QUAL_RECEITA if tipo_map == "receita" else QUAL_DESPESA
    db.session.add(EtlStaging(
        seq_fonte_extracao=fonte.seq_fonte_extracao,
        seq_execucao_extracao=execucao.seq_execucao_extracao,
        num_ano_exercicio=ANO, dat_referencia=DIA,
        val_referencia=Decimal(valor),
        json_atributos={"natureza": "9999"},
        ind_status_processamento='0',
    ))
    mapeamento = Mapeamento(
        num_ano_exercicio=ANO,
        seq_sistema_origem=sistema.seq_sistema_origem,
        dsc_mapeamento="Mapeamento convergência", ind_status='A',
    )
    mapeamento.itens.append(ItemMapeamento(
        seq_qualificador=_qualificador(qual).seq_qualificador,
        txt_regra="Natureza começa com '9999'",
        ind_inversao_sinal='1' if inverter else '0', ind_status='A',
    ))
    db.session.add(mapeamento)
    db.session.commit()
    contexto["sistema"] = sistema
    contexto["qual"] = _qualificador(qual)
    return mapeamento


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when("consulto os tipos de lançamento cadastrados")
def consulta_tipos(app, contexto):
    from fluxocaixa.models import TipoLancamento

    contexto["tipos"] = {
        t.cod_tipo_lancamento: t.dsc_tipo_lancamento for t in TipoLancamento.query.all()
    }


@when("somo o valor com sinal da ilha de convergência")
def soma_ilha(contexto):
    from sqlalchemy import extract, func

    from fluxocaixa.models import Lancamento

    total = (
        _db().session.query(func.sum(Lancamento.valor_com_sinal))
        .filter(Lancamento.ind_status == 'A',
                extract('year', Lancamento.dat_lancamento) == ANO)
        .scalar()
    )
    contexto["soma"] = Decimal(str(total or 0)).quantize(Decimal("0.01"))


@when(parsers.parse('crio um lançamento de convergência com valor "{valor}"'))
def cria_lancamento(app, contexto, valor):
    from fluxocaixa.domain import LancamentoCreate
    from fluxocaixa.services.dominio_lancamento import (
        TIPO_ENTRADA,
        resolver_origem,
        resolver_tipo,
    )
    from fluxocaixa.services.lancamento_service import create_lancamento
    from fluxocaixa.services.validacao import RegraNegocioError

    dados = LancamentoCreate(
        dat_lancamento=DIA,
        seq_qualificador=_qualificador(QUAL_RECEITA).seq_qualificador,
        val_lancamento=Decimal(valor),
        cod_tipo_lancamento=resolver_tipo(TIPO_ENTRADA).cod_tipo_lancamento,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
    )
    try:
        contexto["criado"] = create_lancamento(dados)
    except RegraNegocioError as erro:
        contexto["erro"] = erro


@when("o processamento de convergência roda")
def processa(contexto, mapeamento):
    from fluxocaixa.services.processamento_service import processar_sistema_origem

    contexto["resultado"] = processar_sistema_origem(
        contexto["sistema"].seq_sistema_origem
    )


@when(parsers.parse('importo lançamentos de convergência com tipos "{tipo1}" e "{tipo2}"'))
def importa_dois_tipos(app, contexto, tipo1, tipo2):
    _importar(contexto, [(QUAL_DESPESA, tipo1, "100.00"),
                         (QUAL_DESPESA, tipo2, "200.00")])


@when(parsers.parse('importo um lançamento de convergência com tipo "{tipo}"'))
def importa_tipo(app, contexto, tipo):
    _importar(contexto, [(QUAL_RECEITA, tipo, "100.00")])


@when(parsers.parse('importo um lançamento de convergência com valor "{valor}"'))
def importa_valor(app, contexto, valor):
    _importar(contexto, [(QUAL_RECEITA, "Entrada", valor)])


def _importar(contexto, linhas):
    """CSV em memória — o serviço recebe (bytes, filename) e casa o
    qualificador pela DESCRIÇÃO."""
    from fluxocaixa.services.lancamento_service import import_lancamentos_service

    corpo = ["Data,Qualificador,Tipo,Valor (R$)"]
    for qual_num, tipo, valor in linhas:
        descricao = _qualificador(qual_num).dsc_qualificador
        corpo.append(f"{DIA.isoformat()},{descricao},{tipo},{valor}")
    conteudo = "\n".join(corpo).encode("utf-8")
    contexto["import"] = import_lancamentos_service(conteudo, "lancamentos.csv")


@when("baixo o modelo de importação de lançamentos")
def baixa_modelo(client, contexto):
    contexto["modelo"] = client.get("/saldos/template-xlsx")


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('existe o tipo "{cod}" com descrição "{dsc}"'))
def existe_tipo(contexto, cod, dsc):
    assert contexto["tipos"].get(cod) == dsc, f"tipos={contexto['tipos']}"


@then(parsers.parse('resolver o tipo pela descrição "{dsc}" devolve o código "{cod}"'))
def resolve_por_descricao(app, dsc, cod):
    from fluxocaixa.services.dominio_lancamento import resolver_tipo

    assert resolver_tipo(dsc).cod_tipo_lancamento == cod


@then(parsers.parse('o lançamento tem valor absoluto "{valor}"'))
def valor_absoluto(lancamento, valor):
    assert Decimal(str(lancamento.val_lancamento)) == Decimal(valor)


@then(parsers.parse('o valor com sinal do lançamento é "{valor}"'))
def valor_com_sinal(lancamento, valor):
    assert Decimal(str(lancamento.valor_com_sinal)) == Decimal(valor)


@then(parsers.parse('a soma é "{valor}"'))
def soma_confere(contexto, valor):
    assert contexto["soma"] == Decimal(valor)


@then(parsers.parse('recebo erro de negócio de convergência mencionando "{trecho}"'))
def erro_com_trecho(contexto, trecho):
    assert "erro" in contexto, "esperava RegraNegocioError"
    assert trecho.lower() in str(contexto["erro"]).lower()


@then("recebo erro de negócio de convergência")
def erro_qualquer(contexto):
    assert "erro" in contexto, "esperava RegraNegocioError"


@then("nenhum lançamento é criado na ilha de convergência")
def nenhum_lancamento(contexto):
    assert _lancamentos_da_ilha() == []


@then("o lançamento é criado na ilha de convergência")
def lancamento_criado(contexto):
    assert "erro" not in contexto, f"erro inesperado: {contexto.get('erro')}"
    assert len(_lancamentos_da_ilha()) == 1


@then(parsers.parse('o lançamento gerado tem tipo "{tipo}" e valor "{valor}"'))
def lancamento_gerado(contexto, tipo, valor):
    lancs = _lancamentos_da_ilha()
    assert len(lancs) == 1, f"esperava 1 lançamento, vieram {len(lancs)}"
    assert lancs[0].cod_tipo_lancamento == tipo
    assert Decimal(str(lancs[0].val_lancamento)) == Decimal(valor)
    contexto["gerado"] = lancs[0]


@then("o lançamento gerado está no qualificador do mapeamento")
def lancamento_no_qualificador(contexto):
    assert contexto["gerado"].seq_qualificador == contexto["qual"].seq_qualificador


@then("as duas linhas são aceitas como débito")
def duas_como_debito(contexto):
    resultado = contexto["import"]
    lancs = _lancamentos_da_ilha()
    assert len(lancs) == 2, f"resultado={resultado} lancs={len(lancs)}"
    assert all(l.cod_tipo_lancamento == 'D' for l in lancs)


@then("a importação de convergência reporta erro na linha")
def import_com_erro(contexto):
    resultado = contexto["import"]
    erros = resultado.get("erros") or resultado.get("linhas_com_erro") or []
    assert erros, f"esperava erro de linha, veio {resultado}"
    assert _lancamentos_da_ilha() == []


@then("todas as linhas de exemplo têm valor positivo")
def modelo_positivo(contexto):
    import io

    import openpyxl

    resposta = contexto["modelo"]
    assert resposta.status_code == 200
    planilha = openpyxl.load_workbook(io.BytesIO(resposta.content))
    aba = planilha.active
    coluna_valor = [c.value for c in aba[1]].index("Valor (R$)")
    valores = [
        linha[coluna_valor]
        for linha in aba.iter_rows(min_row=2, values_only=True)
        if linha[coluna_valor] is not None
    ]
    assert valores, "modelo sem linhas de exemplo"
    assert all(float(v) > 0 for v in valores), valores
