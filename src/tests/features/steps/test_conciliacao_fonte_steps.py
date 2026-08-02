"""Steps BDD — conciliação por fonte (spec fonte-recurso R10–R12).

Vigência-ilha 2057 (fontes 1.502/9.777, data 2057-06-30) — a conciliação
varre as cargas da data e o saldo por fonte (vazio na ilha: as fontes não
têm fundo classificado, então a operacional entra como ausente/zero).
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../fonte-recurso/conciliacao_fonte.feature")


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _fonte(codigo, vigencia):
    from fluxocaixa.models import FonteRecurso

    ident, fonte = codigo.split(".", 1)
    return FonteRecurso.query.filter_by(
        cod_identificador_exercicio=ident, cod_fonte_stn=fonte,
        num_exercicio_vigencia=vigencia, ind_status='A').first()


@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(12345)


@given(parsers.parse('a fonte "{codigo}" cadastrada na vigência {vigencia:d} como "{vinculada}"'))
def fonte_cadastrada(app, codigo, vigencia, vinculada):
    from fluxocaixa.services.fonte_recurso_service import criar_fonte

    _db().session.rollback()
    if _fonte(codigo, vigencia) is None:
        ident, fonte = codigo.split(".", 1)
        criar_fonte(ident, fonte, f"Fonte de teste {codigo}", vigencia,
                    vinculada='L' if vinculada == 'livre' else 'V')


@when(parsers.parse('importo disponibilidade contábil de {valor} para a fonte "{codigo}" na data "{dat}"'))
def importa_disponibilidade(app, valor, codigo, dat):
    from fluxocaixa.services.conciliacao_fonte_service import registrar_disponibilidade

    registrar_disponibilidade(date.fromisoformat(dat), codigo, Decimal(valor))


@when(parsers.parse('concilio a data "{dat}"'))
def concilia(app, contexto, dat):
    from fluxocaixa.services.conciliacao_fonte_service import conciliar

    contexto["linhas"] = conciliar(date.fromisoformat(dat))


@then(parsers.parse('a disponibilidade contábil da fonte "{codigo}" da vigência {vigencia:d} em "{dat}" é {valor}'))
def disponibilidade_e(app, codigo, vigencia, dat, valor):
    from fluxocaixa.models import DisponibilidadeContabil

    _db().session.expire_all()
    fonte = _fonte(codigo, vigencia)
    ativas = DisponibilidadeContabil.query.filter_by(
        dat_referencia=date.fromisoformat(dat),
        seq_fonte_recurso=fonte.seq_fonte_recurso, ind_status='A').all()
    assert len(ativas) == 1, f"esperava 1 carga ativa, veio {len(ativas)}"
    assert Decimal(ativas[0].val_disponibilidade) == \
        Decimal(valor).quantize(Decimal("0.01"))


@then(parsers.parse('existe {qtd:d} carga inativa da fonte "{codigo}" da vigência {vigencia:d} em "{dat}"'))
def cargas_inativas(app, qtd, codigo, vigencia, dat):
    from fluxocaixa.models import DisponibilidadeContabil

    fonte = _fonte(codigo, vigencia)
    inativas = DisponibilidadeContabil.query.filter_by(
        dat_referencia=date.fromisoformat(dat),
        seq_fonte_recurso=fonte.seq_fonte_recurso, ind_status='I').all()
    assert len(inativas) == qtd


@then(parsers.parse('a fonte "{codigo}" da vigência {vigencia:d} existe vinculada e pendente de revisão'))
def fonte_pendente(app, codigo, vigencia):
    fonte = _fonte(codigo, vigencia)
    assert fonte is not None, f"fonte {codigo} não auto-cadastrada"
    assert fonte.ind_vinculada == 'V'
    assert fonte.ind_pendente_revisao == 'S'


@then(parsers.parse('a conciliação da fonte "{codigo}" da vigência {vigencia:d} mostra situação "{situacao}" com diferença {diferenca}'))
def conciliacao_da_fonte(contexto, codigo, vigencia, situacao, diferenca):
    fonte = _fonte(codigo, vigencia)
    linha = next((l for l in contexto["linhas"]
                  if l["fonte"].seq_fonte_recurso == fonte.seq_fonte_recurso), None)
    assert linha is not None, f"fonte {codigo} fora da conciliação"
    assert linha["situacao"] == situacao, linha
    assert linha["diferenca"] == Decimal(diferenca).quantize(Decimal("0.01")), linha
