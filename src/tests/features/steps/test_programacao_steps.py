"""Steps BDD — programação de desembolso (spec desembolso R21–R22).

Ilha 2045 — ano sem LOA, cotas nem realizado de outros módulos (o previsto
mensal soma a LOA de despesa do ano INTEIRO, então a ilha protege o assert
de precedência).
"""
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .conftest_regra import garantir_qualificador

scenarios("../desembolso/programacao.feature")


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(12345)


@given(parsers.parse('um órgão "{cod:d}" chamado "{nom}"'))
def orgao_cadastrado(app, cod, nom):
    from fluxocaixa.models import Orgao
    from fluxocaixa.services.orgao_service import criar_orgao

    _db().session.rollback()
    if Orgao.query.get(cod) is None:
        criar_orgao(cod, nom)


@given(parsers.parse('um qualificador folha de despesa "{num}" com LOA de {valor} no ano {ano:d}'))
def qualificador_com_loa(app, num, valor, ano):
    from fluxocaixa.models import Loa

    q = garantir_qualificador(num)
    if not Loa.query.filter_by(num_ano=ano, seq_qualificador=q.seq_qualificador).first():
        _db().session.add(Loa(num_ano=ano, seq_qualificador=q.seq_qualificador,
                              val_loa=Decimal(valor), ind_status='A'))
        _db().session.commit()


@given(parsers.parse('uma cota de {valor} para o órgão "{cod:d}" em {ano:d}-{mes:d} com o ato "{ato}"'))
@when(parsers.parse('registro uma cota de {valor} para o órgão "{cod:d}" em {ano:d}-{mes:d} com o ato "{ato}"'))
def registra_cota(app, contexto, valor, cod, ano, mes, ato):
    from fluxocaixa.services.programacao_service import registrar_cota

    registrar_cota(num_ano=ano, num_mes=mes, cod_orgao=cod,
                   val_cota=Decimal(valor), dsc_referencia_ato=ato)
    contexto["erro"] = None


@when(parsers.parse('registro uma cota de {valor} para o órgão "{cod:d}" em {ano:d}-{mes:d} sem ato'))
def registra_cota_sem_ato(app, contexto, valor, cod, ano, mes):
    from fluxocaixa.services.programacao_service import registrar_cota
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        registrar_cota(num_ano=ano, num_mes=mes, cod_orgao=cod,
                       val_cota=Decimal(valor), dsc_referencia_ato="")
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@when(parsers.parse('consulto o previsto mensal de {ano:d}'))
def consulta_previsto(app, contexto, ano):
    from fluxocaixa.services.previsto_loa_service import previsto_mensal

    contexto["previsto"] = previsto_mensal(ano)


@then(parsers.parse('a cota vigente do órgão "{cod:d}" em {ano:d}-{mes:d} é {valor}'))
def cota_vigente(app, cod, ano, mes, valor):
    from fluxocaixa.models import ProgramacaoDesembolso

    _db().session.expire_all()
    ativas = ProgramacaoDesembolso.query.filter_by(
        num_ano=ano, num_mes=mes, cod_orgao=cod, ind_status='A').all()
    assert len(ativas) == 1, f"esperava 1 cota ativa, veio {len(ativas)}"
    assert Decimal(ativas[0].val_cota) == Decimal(valor).quantize(Decimal("0.01"))


@then(parsers.parse('existe {qtd:d} cota inativa do órgão "{cod:d}" em {ano:d}-{mes:d}'))
def cotas_inativas(app, qtd, cod, ano, mes):
    from fluxocaixa.models import ProgramacaoDesembolso

    inativas = ProgramacaoDesembolso.query.filter_by(
        num_ano=ano, num_mes=mes, cod_orgao=cod, ind_status='I').all()
    assert len(inativas) == qtd, f"esperava {qtd} inativa(s), veio {len(inativas)}"


@then(parsers.parse('o previsto do mês {mes:d} de {ano:d} é {valor}'))
def previsto_do_mes(contexto, mes, ano, valor):
    assert contexto["previsto"][mes] == Decimal(valor).quantize(Decimal("0.01")), \
        contexto["previsto"]


@then(parsers.parse('a operação de programação é rejeitada com a mensagem "{mensagem}"'))
def operacao_rejeitada(contexto, mensagem):
    assert contexto["erro"] == mensagem, f"esperava {mensagem!r}, veio {contexto['erro']!r}"
