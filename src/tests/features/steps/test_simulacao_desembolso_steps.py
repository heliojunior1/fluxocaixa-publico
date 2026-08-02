"""Steps BDD — simulação de disponibilidade (spec desembolso R9–R12).

Ilha 2040 (cenário/fontes/qualificadores próprios). Os cenários de veredicto
usam o grupo 'V' com saldo/colchão controlados — o grupo 'L' recebe
vazamentos de rascunhos de outros módulos (clamp do horizonte) e serve só às
asserções que dependem apenas do mapa da projeção.
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .conftest_regra import garantir_qualificador

scenarios("../desembolso/simulacao.feature")

USUARIO_SESSAO = 12345


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


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


def _periodo(contexto, mes):
    return next(p for p in contexto["sim"]["periodos"] if p["mes"] == mes)


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(USUARIO_SESSAO)


@given(parsers.parse('um órgão "{cod:d}" chamado "{nom}"'))
def orgao_cadastrado(app, cod, nom):
    from fluxocaixa.models import Orgao
    from fluxocaixa.services.orgao_service import criar_orgao

    _db().session.rollback()
    if Orgao.query.get(cod) is None:
        criar_orgao(cod, nom)


@given(parsers.parse('a fonte "{codigo}" cadastrada na vigência {vigencia:d} como "{vinculada}"'))
def fonte_cadastrada(app, codigo, vigencia, vinculada):
    from fluxocaixa.services.fonte_recurso_service import criar_fonte

    _db().session.rollback()
    if _fonte(codigo, vigencia) is None:
        ident, fonte = codigo.split(".", 1)
        criar_fonte(ident, fonte, f"Fonte de teste {codigo}", vigencia,
                    vinculada='L' if vinculada == 'livre' else 'V')


@given(parsers.parse('um qualificador folha de receita "{num}" repartido 100% na fonte "{codigo}" da vigência {vigencia:d}'))
def qualificador_repartido(app, num, codigo, vigencia):
    from fluxocaixa.services.reparticao_fonte_service import (
        definir_reparticao, reparticoes_de)

    q = garantir_qualificador(num)
    if not reparticoes_de(q.seq_qualificador, vigencia):
        definir_reparticao(q.seq_qualificador, vigencia,
                           [(_fonte(codigo, vigencia).seq_fonte_recurso, Decimal("100"))])


@given(parsers.parse('um qualificador folha de receita "{num}" sem repartição'))
@given(parsers.parse('um qualificador folha de despesa "{num}"'))
def qualificador_simples(app, num):
    garantir_qualificador(num)


@given(parsers.parse('um cenário publicado "{nome}" para {ano:d} com receita mensal de {rec1} em "{q1}", receita mensal de {rec2} em "{q2}" e despesa mensal de {desp} em "{q3}"'),
       target_fixture="cenario_atual")
def cenario_publicado(app, nome, ano, rec1, q1, rec2, q2, desp, q3):
    from fluxocaixa.models import ProjecaoValor, ProjecaoVersao, SimuladorCenario

    _db().session.rollback()
    cenario = SimuladorCenario.query.filter_by(nom_cenario=nome).first()
    if cenario is not None:
        return cenario

    cenario = SimuladorCenario(
        nom_cenario=nome, dsc_cenario='Cenário BDD F7.2',
        ano_base=ano - 1, num_periodos=12, cod_periodicidade='MENSAL',
        ind_status='A')
    _db().session.add(cenario)
    _db().session.flush()

    versao = ProjecaoVersao(
        seq_simulador_cenario=cenario.seq_simulador_cenario,
        nom_versao='v1 BDD', ind_publicado='S')
    _db().session.add(versao)
    _db().session.flush()

    valores = [(q1, 'C', Decimal(rec1)), (q2, 'C', Decimal(rec2)),
               (q3, 'D', Decimal(desp))]
    for num, tipo, valor in valores:
        q = garantir_qualificador(num)
        for periodo in range(1, 13):
            _db().session.add(ProjecaoValor(
                seq_projecao_versao=versao.seq_projecao_versao,
                seq_qualificador=q.seq_qualificador,
                cod_tipo=tipo, ano=ano, num_periodo=periodo,
                val_projetado=valor))
    _db().session.commit()
    return cenario


def _criar_liberacao_prevista(situacao, valor, cod, num, codigo, vigencia, prevista):
    from fluxocaixa.services.liberacao_service import (
        confirmar_liberacao, criar_liberacao)

    q = garantir_qualificador(num)
    fonte = _fonte(codigo, vigencia)
    dat_prevista = date.fromisoformat(prevista)
    liberacao = criar_liberacao(
        dat_liberacao=dat_prevista, cod_orgao=cod,
        seq_qualificador=q.seq_qualificador,
        seq_fonte_recurso=fonte.seq_fonte_recurso,
        val_liberacao=Decimal(valor),
        dat_prevista_desembolso=dat_prevista)
    if situacao == 'C':
        return confirmar_liberacao(liberacao.seq_liberacao)
    return liberacao


@given(parsers.parse('uma liberação confirmada de {valor} no órgão "{cod:d}", qualificador "{num}", fonte "{codigo}" da vigência {vigencia:d}, prevista para "{prevista}"'),
       target_fixture="liberacao_atual")
def liberacao_confirmada(app, valor, cod, num, codigo, vigencia, prevista):
    return _criar_liberacao_prevista('C', valor, cod, num, codigo, vigencia, prevista)


@given(parsers.parse('uma liberação em rascunho de {valor} no órgão "{cod:d}", qualificador "{num}", fonte "{codigo}" da vigência {vigencia:d}, prevista para "{prevista}"'),
       target_fixture="liberacao_atual")
def liberacao_rascunho(app, valor, cod, num, codigo, vigencia, prevista):
    return _criar_liberacao_prevista('R', valor, cod, num, codigo, vigencia, prevista)


@given(parsers.parse('o colchão do grupo "{grupo}" definido como {valor}'))
def colchao_definido(app, grupo, valor):
    from fluxocaixa.services.simulacao_desembolso_service import definir_colchao

    definir_colchao(Decimal(valor), grupo=grupo)


@given(parsers.parse('um saldo de {valor} num fundo da fonte "{codigo}" da vigência {vigencia:d} em "{dat}"'))
def saldo_no_grupo(app, valor, codigo, vigencia, dat):
    from fluxocaixa.models import ContaBancaria, Fundo
    from fluxocaixa.services.fundo_service import classificar_fundo, criar_fundo
    from fluxocaixa.services.saldo_fundo_service import gravar_saldo

    db = _db()
    db.session.rollback()
    fonte = _fonte(codigo, vigencia)
    num_conta = f"SIM-{dat[-2:]}"
    conta = ContaBancaria.query.filter_by(
        cod_banco='001', num_agencia='0001', num_conta=num_conta).first()
    if conta is None:
        conta = ContaBancaria(cod_banco='001', num_agencia='0001',
                              num_conta=num_conta, dsc_conta='Conta simulação BDD')
        db.session.add(conta)
        db.session.commit()
    cod_fundo = f"96{dat[-2:]}"
    fundo = Fundo.query.filter_by(cod_fundo=cod_fundo).first()
    if fundo is None:
        fundo = criar_fundo(cod_fundo, f'Fundo simulação {cod_fundo}')
    classificar_fundo(fundo.seq_fundo, fonte.seq_fonte_recurso)
    gravar_saldo(seq_conta=conta.seq_conta, seq_fundo=fundo.seq_fundo,
                 dat_saldo=date.fromisoformat(dat), val_saldo=Decimal(valor))


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when(parsers.parse('simulo o grupo "{grupo}" no modo "{modo}" de {ano:d} a partir do mês {mes:d} por {qtd:d} meses'))
def simula(app, contexto, cenario_atual, grupo, modo, ano, mes, qtd):
    from fluxocaixa.services.simulacao_desembolso_service import simular

    contexto["sim"] = simular(cenario_atual.seq_simulador_cenario, ano,
                              grupo=grupo, modo=modo, mes_inicial=mes,
                              qtd_meses=qtd)


@when(parsers.parse('confirmo o lote do grupo "{grupo}" de {ano:d} a partir do mês {mes:d} com a justificativa "{just}"'))
def confirma_lote_just(app, contexto, cenario_atual, grupo, ano, mes, just):
    from fluxocaixa.services.simulacao_desembolso_service import confirmar_lote

    _executar(contexto, lambda: confirmar_lote(
        cenario_atual.seq_simulador_cenario, ano, grupo=grupo,
        mes_inicial=mes, justificativa=just))


@when(parsers.parse('confirmo o lote do grupo "{grupo}" de {ano:d} a partir do mês {mes:d}'))
def confirma_lote(app, contexto, cenario_atual, grupo, ano, mes):
    from fluxocaixa.services.simulacao_desembolso_service import confirmar_lote

    _executar(contexto, lambda: confirmar_lote(
        cenario_atual.seq_simulador_cenario, ano, grupo=grupo, mes_inicial=mes))


@when(parsers.parse('confirmo o lote do grupo "{grupo}" de {ano:d} no modo "{modo}"'))
def confirma_lote_modo(app, contexto, cenario_atual, grupo, ano, modo):
    from fluxocaixa.services.simulacao_desembolso_service import confirmar_lote

    _executar(contexto, lambda: confirmar_lote(
        cenario_atual.seq_simulador_cenario, ano, grupo=grupo, modo=modo))


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('as receitas do mês {mes:d} são {valor}'))
def receitas_do_mes(contexto, mes, valor):
    assert _periodo(contexto, mes)["receitas"] == Decimal(valor).quantize(Decimal("0.01"))


@then(parsers.parse('o total não classificado é {valor}'))
def nao_classificado(contexto, valor):
    assert contexto["sim"]["nao_classificado"] == Decimal(valor).quantize(Decimal("0.01"))


@then(parsers.parse('as despesas ajustadas do mês {mes:d} são {valor}'))
def despesas_do_mes(contexto, mes, valor):
    assert _periodo(contexto, mes)["despesas_ajustadas"] == Decimal(valor).quantize(Decimal("0.01")), \
        _periodo(contexto, mes)


@then(parsers.parse('o pendente do mês {mes:d} é {valor}'))
def pendente_do_mes(contexto, mes, valor):
    assert _periodo(contexto, mes)["pendente"] == Decimal(valor).quantize(Decimal("0.01"))


@then(parsers.parse('o veredicto é "{veredicto}"'))
def veredicto(contexto, veredicto):
    assert contexto["sim"]["veredicto"] == veredicto, contexto["sim"]["veredicto"]


@then("a simulação acusa insuficiência estrutural")
def estrutural(contexto):
    assert contexto["sim"]["estrutural"] is not None
    assert contexto["sim"]["estrutural"]["faltante"] > 0


@then(parsers.parse('a operação de simulação é rejeitada com a mensagem "{mensagem}"'))
def simulacao_rejeitada(contexto, mensagem):
    assert contexto["erro"] == mensagem, f"esperava {mensagem!r}, veio {contexto['erro']!r}"


@then("cancelo essa liberação de teste")
def cancela_liberacao_teste(app, liberacao_atual):
    """Limpeza dentro do cenário: o rascunho gigante não pode vazar para os
    cenários seguintes do mesmo grupo."""
    from fluxocaixa.services.liberacao_service import cancelar_liberacao

    cancelar_liberacao(liberacao_atual.seq_liberacao, justificativa="limpeza BDD")


@then("o lote foi confirmado com snapshot")
def lote_confirmado(contexto):
    from fluxocaixa.models import SimulacaoDesembolso

    assert contexto["erro"] is None, contexto["erro"]
    snapshot = contexto["resultado_op"]
    assert isinstance(snapshot, SimulacaoDesembolso)
    assert snapshot.json_snapshot["veredicto"] in ("OK", "ALERTA")
    contexto["snapshot"] = snapshot


@then("essa liberação está confirmada com evento referenciando o snapshot")
def liberacao_referencia_snapshot(contexto, liberacao_atual):
    from fluxocaixa.models import LiberacaoEvento

    _db().session.expire_all()
    assert liberacao_atual.cod_situacao == 'C'
    evento = (LiberacaoEvento.query
              .filter_by(seq_liberacao=liberacao_atual.seq_liberacao,
                         cod_tipo_evento='CONFIRMACAO')
              .first())
    assert evento is not None
    assert evento.dsc_referencia_snapshot == contexto["snapshot"].referencia
