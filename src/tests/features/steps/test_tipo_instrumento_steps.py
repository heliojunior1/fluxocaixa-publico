"""Steps BDD — tipo de instrumento financeiro e liquidez (change
tipo-instrumento-financeiro; specs saldo-por-fundo R22, fonte-recurso R5,
desembolso R9).

Ilha 2042. Os asserts de grupo usam DATA específica (recorte isolado); o de
simulação usa DELTA (o grupo é global entre features). Import tardio de
`fluxocaixa` (isolamento de banco da suíte).
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../saldo-por-fundo/tipo_instrumento.feature")

USUARIO_SESSAO = 12345
VIGENCIA = 2042


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _fundo(cod):
    from fluxocaixa.models import Fundo

    return Fundo.query.filter_by(cod_fundo=cod).first()


def _tipo(sigla):
    from fluxocaixa.models import TipoInstrumento

    return TipoInstrumento.query.filter_by(txt_sigla=sigla).first()


def _fonte(codigo: str, vigencia: int):
    from fluxocaixa.models import FonteRecurso

    ident, fonte = codigo.split(".", 1)
    return FonteRecurso.query.filter_by(
        cod_identificador_exercicio=ident, cod_fonte_stn=fonte,
        num_exercicio_vigencia=vigencia, ind_status='A').first()


def _executar(contexto, fn):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        contexto["resultado_op"] = fn()
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


def _criar_instrumento(cod, dsc, sigla_tipo=None, liquidez='S', vencimento=None):
    from fluxocaixa.services.fundo_service import criar_fundo

    tipo = _tipo(sigla_tipo) if sigla_tipo else None
    return criar_fundo(
        cod, dsc,
        seq_tipo_instrumento=tipo.seq_tipo_instrumento if tipo else None,
        ind_liquidez_imediata=liquidez,
        dat_vencimento=date.fromisoformat(vencimento) if vencimento else None,
    )


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(USUARIO_SESSAO)


@given('o fundo padrão "GERAL" garantido')
def geral_garantido(app):
    from fluxocaixa.services.fundo_service import garantir_fundo_geral

    _db().session.rollback()
    garantir_fundo_geral()


@given(parsers.parse('um fundo manual "{cod}" chamado "{dsc}"'))
def fundo_manual(app, cod, dsc):
    _db().session.rollback()
    if _fundo(cod) is None:
        _criar_instrumento(cod, dsc)


@given(parsers.parse('a fonte de instrumentos "{codigo}" cadastrada na vigência {vigencia:d} como "{vinculada}"'))
def fonte_cadastrada(app, codigo, vigencia, vinculada):
    from fluxocaixa.services.fonte_recurso_service import criar_fonte

    _db().session.rollback()
    if _fonte(codigo, vigencia) is None:
        ident, fonte = codigo.split(".", 1)
        criar_fonte(ident, fonte, f"Fonte instrumento {codigo}", vigencia,
                    vinculada='L' if vinculada == 'livre' else 'V')


@given(parsers.parse('uma conta de instrumentos "{ref}"'), target_fixture="conta")
def conta_instrumentos(app, ref):
    from fluxocaixa.models import ContaBancaria

    db = _db()
    db.session.rollback()
    banco, agencia, num = ref.split("/")
    conta = ContaBancaria.query.filter_by(
        cod_banco=banco, num_agencia=agencia, num_conta=num).first()
    if conta is None:
        conta = ContaBancaria(cod_banco=banco, num_agencia=agencia,
                              num_conta=num, dsc_conta='Conta instrumentos BDD')
        db.session.add(conta)
        db.session.commit()
    return conta


def _instrumento_com_saldo(conta, cod, sigla_tipo, liquidez, codigo_fonte,
                           vigencia, valor, dat):
    from fluxocaixa.services.fundo_service import classificar_fundo
    from fluxocaixa.services.saldo_fundo_service import gravar_saldo

    _db().session.rollback()
    fundo = _fundo(cod)
    if fundo is None:
        fundo = _criar_instrumento(cod, f"Instrumento {cod}",
                                   sigla_tipo=sigla_tipo, liquidez=liquidez)
    classificar_fundo(fundo.seq_fundo, _fonte(codigo_fonte, vigencia).seq_fonte_recurso)
    gravar_saldo(seq_conta=conta.seq_conta, seq_fundo=fundo.seq_fundo,
                 dat_saldo=date.fromisoformat(dat), val_saldo=Decimal(valor))


@given(parsers.parse('um instrumento líquido "{cod}" na fonte "{codigo}" da vigência {vigencia:d} com saldo de {valor} nessa conta em "{dat}"'))
def instrumento_liquido(app, conta, cod, codigo, vigencia, valor, dat):
    _instrumento_com_saldo(conta, cod, 'FUNDO', 'S', codigo, vigencia, valor, dat)


@given(parsers.parse('um instrumento "{cod}" tipo "{sigla}" sem liquidez imediata na fonte "{codigo}" da vigência {vigencia:d} com saldo de {valor} nessa conta em "{dat}"'))
def instrumento_carencia(app, conta, cod, sigla, codigo, vigencia, valor, dat):
    _instrumento_com_saldo(conta, cod, sigla, 'N', codigo, vigencia, valor, dat)


@given(parsers.parse('um cenário publicado vazio "{nome}" para {ano:d}'),
       target_fixture="cenario_atual")
def cenario_publicado_vazio(app, nome, ano):
    from fluxocaixa.models import ProjecaoVersao, SimuladorCenario

    _db().session.rollback()
    cenario = SimuladorCenario.query.filter_by(nom_cenario=nome).first()
    if cenario is not None:
        return cenario

    cenario = SimuladorCenario(
        nom_cenario=nome, dsc_cenario='Cenário BDD tipo-instrumento',
        ano_base=ano - 1, num_periodos=12, cod_periodicidade='MENSAL',
        ind_status='A')
    _db().session.add(cenario)
    _db().session.flush()
    _db().session.add(ProjecaoVersao(
        seq_simulador_cenario=cenario.seq_simulador_cenario,
        nom_versao='v1 BDD', ind_publicado='S'))
    _db().session.commit()
    return cenario


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when(parsers.parse('cadastro o fundo "{cod}" chamado "{dsc}"'))
def cadastro_fundo_simples(app, contexto, cod, dsc):
    _db().session.rollback()
    _executar(contexto, lambda: _criar_instrumento(cod, dsc))


@when(parsers.parse('cadastro o instrumento "{cod}" chamado "{dsc}" com tipo "{sigla}", liquidez "{liq}" e vencimento "{venc}"'))
def cadastro_instrumento_completo(app, contexto, cod, dsc, sigla, liq, venc):
    _db().session.rollback()
    _executar(contexto, lambda: _criar_instrumento(
        cod, dsc, sigla_tipo=sigla, liquidez=liq, vencimento=venc))


@when(parsers.parse('cadastro o instrumento "{cod}" chamado "{dsc}" com o tipo inexistente'))
def cadastro_tipo_inexistente(app, contexto, cod, dsc):
    from fluxocaixa.services.fundo_service import criar_fundo

    _db().session.rollback()
    _executar(contexto, lambda: criar_fundo(
        cod, dsc, seq_tipo_instrumento=99999999))


@when(parsers.parse('o upsert interno cria o instrumento desconhecido "{cod}"'))
def upsert_cria(app, contexto, cod):
    from fluxocaixa.services.fundo_service import upsert_fundo_pendente

    _db().session.rollback()
    _executar(contexto, lambda: upsert_fundo_pendente(cod, f"Instrumento {cod}"))


@when(parsers.parse('altero o instrumento "{cod}" para tipo "{sigla}", liquidez "{liq}" e vencimento "{venc}"'))
def altero_instrumento(app, contexto, cod, sigla, liq, venc):
    from fluxocaixa.services.fundo_service import alterar_fundo

    _db().session.rollback()
    fundo = _fundo(cod)
    _executar(contexto, lambda: alterar_fundo(
        fundo.seq_fundo, fundo.dsc_fundo,
        seq_tipo_instrumento=_tipo(sigla).seq_tipo_instrumento,
        ind_liquidez_imediata=liq,
        dat_vencimento=date.fromisoformat(venc)))


def _simular(nome_cenario, grupo, ano):
    from fluxocaixa.models import SimuladorCenario
    from fluxocaixa.services.simulacao_desembolso_service import simular

    cenario = SimuladorCenario.query.filter_by(nom_cenario=nome_cenario).first()
    return simular(cenario.seq_simulador_cenario, ano, grupo=grupo)


@when(parsers.parse('simulo o grupo "{grupo}" para {ano:d} com o cenário "{nome}" e registro a referência'))
def simulo_e_registro(app, contexto, grupo, ano, nome):
    _db().session.rollback()
    sim = _simular(nome, grupo, ano)
    contexto["ref_saldo_inicial"] = sim["saldo_inicial"]
    contexto["ref_carencia"] = sim["saldo_carencia"]


@when(parsers.parse('acrescento o instrumento "{cod}" tipo "{sigla}" sem liquidez imediata na fonte "{codigo}" da vigência {vigencia:d} com saldo de {valor} nessa conta em "{dat}"'))
def acrescento_carencia(app, conta, cod, sigla, codigo, vigencia, valor, dat):
    _instrumento_com_saldo(conta, cod, sigla, 'N', codigo, vigencia, valor, dat)


@when(parsers.parse('simulo novamente o grupo "{grupo}" para {ano:d} com o cenário "{nome}"'))
def simulo_novamente(app, contexto, grupo, ano, nome):
    _db().session.expire_all()
    contexto["sim"] = _simular(nome, grupo, ano)


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('os tipos de instrumento "{t1}", "{t2}", "{t3}", "{t4}" e "{t5}" existem ativos'))
def tipos_existem(app, t1, t2, t3, t4, t5):
    _db().session.expire_all()
    for sigla in (t1, t2, t3, t4, t5):
        tipo = _tipo(sigla)
        assert tipo is not None and tipo.ind_status == 'A', f"tipo {sigla} ausente"


@then(parsers.parse('o instrumento "{cod}" tem tipo "{sigla}" e liquidez imediata "{liq}"'))
def instrumento_tem_tipo(app, cod, sigla, liq):
    _db().session.expire_all()
    fundo = _fundo(cod)
    assert fundo is not None
    assert fundo.seq_tipo_instrumento == _tipo(sigla).seq_tipo_instrumento
    assert fundo.ind_liquidez_imediata == liq


@then(parsers.parse('o instrumento "{cod}" tem vencimento "{venc}"'))
def instrumento_tem_vencimento(app, cod, venc):
    _db().session.expire_all()
    assert _fundo(cod).dat_vencimento == date.fromisoformat(venc)


@then(parsers.parse('a operação de instrumento é rejeitada com a mensagem "{msg}"'))
def operacao_rejeitada(contexto, msg):
    assert contexto["erro"] == msg, f"esperava '{msg}', veio '{contexto['erro']}'"


@then(parsers.parse('o grupo "{grupo}" em "{dat}" tem {liquido} líquidos e {carencia} com carência'))
def grupo_liquido_carencia(app, grupo, dat, liquido, carencia):
    from fluxocaixa.repositories.saldo_fundo_repository import saldo_bruto_por_grupo

    _db().session.expire_all()
    grupos = saldo_bruto_por_grupo(date.fromisoformat(dat))
    assert grupos[grupo]["liquido"] == Decimal(liquido).quantize(Decimal("0.01")), \
        f"líquido {grupo}: {grupos[grupo]['liquido']}"
    assert grupos[grupo]["carencia"] == Decimal(carencia).quantize(Decimal("0.01")), \
        f"carência {grupo}: {grupos[grupo]['carencia']}"


@then(parsers.parse('a soma de líquido e carência dos grupos em "{dat}" é igual ao agregado da conta de instrumentos em "{dat2}"'))
def soma_fecha(app, conta, dat, dat2):
    from fluxocaixa.repositories.saldo_fundo_repository import (
        agregado_por_conta,
        saldo_bruto_por_grupo,
    )

    _db().session.expire_all()
    ref = date.fromisoformat(dat)
    grupos = saldo_bruto_por_grupo(ref)
    total = grupos["total"]["liquido"] + grupos["total"]["carencia"]
    agregado = agregado_por_conta(ref, ref, seq_conta=conta.seq_conta)
    total_agregado = sum((linha["val_saldo"] for linha in agregado), Decimal("0.00"))
    assert total == total_agregado, f"grupos {total} != agregado {total_agregado}"


@then(parsers.parse('o saldo operacional da fonte "{codigo}" da vigência {vigencia:d} considera {valor}'))
def operacional_da_fonte(app, codigo, vigencia, valor):
    from fluxocaixa.services.conciliacao_fonte_service import operacional_por_fonte

    _db().session.expire_all()
    fonte = _fonte(codigo, vigencia)
    operacional = operacional_por_fonte(date.today())
    assert operacional[fonte.seq_fonte_recurso] == \
        Decimal(valor).quantize(Decimal("0.01")), \
        f"operacional: {operacional.get(fonte.seq_fonte_recurso)}"


@then("o saldo inicial da simulação não se moveu")
def saldo_inicial_nao_moveu(contexto):
    assert contexto["sim"]["saldo_inicial"] == contexto["ref_saldo_inicial"], \
        (f"saldo inicial moveu: {contexto['ref_saldo_inicial']} → "
         f"{contexto['sim']['saldo_inicial']}")


@then(parsers.parse('a carência informada pela simulação aumentou em {valor}'))
def carencia_aumentou(contexto, valor):
    delta = contexto["sim"]["saldo_carencia"] - contexto["ref_carencia"]
    assert delta == Decimal(valor).quantize(Decimal("0.01")), \
        f"delta carência: {delta}"
