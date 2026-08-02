"""Steps BDD — conferência do desembolso (spec desembolso R14–R16). Ilha 2041."""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .conftest_regra import garantir_qualificador

scenarios("../desembolso/conferencia.feature")


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


@given(parsers.parse('a fonte "{codigo}" cadastrada na vigência {vigencia:d} como "{vinculada}"'))
def fonte_cadastrada(app, codigo, vigencia, vinculada):
    from fluxocaixa.services.fonte_recurso_service import criar_fonte

    _db().session.rollback()
    if _fonte(codigo, vigencia) is None:
        ident, fonte = codigo.split(".", 1)
        criar_fonte(ident, fonte, f"Fonte de teste {codigo}", vigencia,
                    vinculada='L' if vinculada == 'livre' else 'V')


@given(parsers.parse('um qualificador folha de despesa "{num}"'))
def qualificador_despesa(app, num):
    garantir_qualificador(num)


@given(parsers.parse('uma liberação confirmada de {valor} em "{dat}" no órgão "{cod:d}", qualificador "{num}" e fonte "{codigo}" da vigência {vigencia:d}'),
       target_fixture="liberacao_atual")
def liberacao_confirmada(app, valor, dat, cod, num, codigo, vigencia):
    from fluxocaixa.services.liberacao_service import confirmar_liberacao, criar_liberacao

    q = garantir_qualificador(num)
    fonte = _fonte(codigo, vigencia)
    liberacao = criar_liberacao(
        dat_liberacao=date.fromisoformat(dat), cod_orgao=cod,
        seq_qualificador=q.seq_qualificador,
        seq_fonte_recurso=fonte.seq_fonte_recurso,
        val_liberacao=Decimal(valor))
    return confirmar_liberacao(liberacao.seq_liberacao)


def _criar_pagamento(valor, dat, cod, num):
    from fluxocaixa.domain import PagamentoCreate
    from fluxocaixa.models import Pagamento
    from fluxocaixa.services.pagamento_service import create_pagamento

    q = garantir_qualificador(num)
    out = create_pagamento(PagamentoCreate(
        dat_pagamento=date.fromisoformat(dat), cod_orgao=cod,
        seq_qualificador=q.seq_qualificador, val_pagamento=Decimal(valor)))
    return Pagamento.query.get(out.seq_pagamento)


@given(parsers.parse('um pagamento de {valor} em "{dat}" no órgão "{cod:d}" e qualificador "{num}" apropriado nessa liberação'))
def pagamento_apropriado(app, liberacao_atual, valor, dat, cod, num):
    from fluxocaixa.models import PagamentoLiberacao
    from fluxocaixa.models.base import db

    pagamento = _criar_pagamento(valor, dat, cod, num)
    # apropriação com dat_evento = dia do pagamento (a visão usa dat_evento)
    db.session.add(PagamentoLiberacao(
        seq_pagamento=pagamento.seq_pagamento,
        seq_liberacao=liberacao_atual.seq_liberacao,
        cod_tipo_evento='A', val_apropriado=Decimal(valor),
        dat_evento=date.fromisoformat(dat)))
    db.session.commit()


@given(parsers.parse('um pagamento de {valor} em "{dat}" no órgão "{cod:d}" e qualificador "{num}"'))
def pagamento_solto(app, valor, dat, cod, num):
    _criar_pagamento(valor, dat, cod, num)


@given(parsers.parse('uma saída bancária de {valor} em "{dat}" no qualificador "{num}"'))
def saida_bancaria(app, valor, dat, num):
    from fluxocaixa.models import Lancamento, OrigemLancamento
    from fluxocaixa.models.base import db

    q = garantir_qualificador(num)
    origem = OrigemLancamento.query.filter_by(dsc_origem_lancamento='Manual').first()
    db.session.add(Lancamento(
        dat_lancamento=date.fromisoformat(dat), seq_qualificador=q.seq_qualificador,
        val_lancamento=Decimal(valor), cod_tipo_lancamento='D',
        cod_origem_lancamento=origem.cod_origem_lancamento,
        cod_pessoa_inclusao=1, ind_status='A'))
    db.session.commit()


@given(parsers.parse('uma transferência interna de {valor} em "{dat}"'))
def transferencia_interna(app, valor, dat):
    from fluxocaixa.models import ContaBancaria
    from fluxocaixa.models.base import db
    from fluxocaixa.services.transferencia_service import criar_transferencia

    contas = []
    for sufixo in ('CF-1', 'CF-2'):
        conta = ContaBancaria.query.filter_by(
            cod_banco='001', num_agencia='0001', num_conta=sufixo).first()
        if conta is None:
            conta = ContaBancaria(cod_banco='001', num_agencia='0001',
                                  num_conta=sufixo, dsc_conta=f'Conta {sufixo}')
            db.session.add(conta)
            db.session.commit()
        contas.append(conta)
    criar_transferencia(date.fromisoformat(dat), contas[0].seq_conta,
                        contas[1].seq_conta, Decimal(valor))


@given(parsers.parse('o apurado externo de liberações de "{dat}" informado como {valor}'))
@when(parsers.parse('o apurado externo de liberações de "{dat}" é alterado para {valor}'))
def apurado_informado(app, dat, valor):
    from fluxocaixa.services.conferencia_desembolso_service import informar_apurado

    informar_apurado(date.fromisoformat(dat), val_liberacoes=Decimal(valor))


@when(parsers.parse('consulto o controle de "{inicio}" a "{fim}"'))
def consulta_controle(app, contexto, inicio, fim):
    from fluxocaixa.services.conferencia_desembolso_service import visao_controle

    _db().session.expire_all()
    contexto["controle"] = {
        l['dia']: l for l in visao_controle(
            date.fromisoformat(inicio), date.fromisoformat(fim))
    }


@when(parsers.parse('consulto a conciliação de "{inicio}" a "{fim}"'))
def consulta_conciliacao(app, contexto, inicio, fim):
    from fluxocaixa.services.conferencia_desembolso_service import visao_conciliacao

    _db().session.expire_all()
    contexto["conciliacao"] = {
        l['dia']: l for l in visao_conciliacao(
            date.fromisoformat(inicio), date.fromisoformat(fim))
    }


@then(parsers.parse('o movimento do controle de "{dat}" é {valor}'))
def movimento_do_dia(contexto, dat, valor):
    """Delta do dia (final − anterior) — imune ao pendente global de outras
    ilhas de teste, que entra no 'anterior' de todos."""
    linha = contexto["controle"][date.fromisoformat(dat)]
    movimento = linha['pendente_final'] - linha['pendente_anterior']
    assert movimento == Decimal(valor).quantize(Decimal("0.01")), linha


@then(parsers.parse('o dia "{dat}" aparece no controle com liberações {valor}'))
def dia_com_zeros(contexto, dat, valor):
    linha = contexto["controle"][date.fromisoformat(dat)]
    assert linha['liberacoes'] == Decimal(valor).quantize(Decimal("0.01"))


@then(parsers.parse('a parcela neutra de "{dat}" é {valor}'))
def parcela_neutra(contexto, dat, valor):
    linha = contexto["conciliacao"][date.fromisoformat(dat)]
    assert linha['transferencia_neutra'] == Decimal(valor).quantize(Decimal("0.01")), linha


@then(parsers.parse('o valor a investigar de "{dat}" é {valor}'))
def a_investigar(contexto, dat, valor):
    linha = contexto["conciliacao"][date.fromisoformat(dat)]
    assert linha['a_investigar'] == Decimal(valor).quantize(Decimal("0.01")), linha


@then(parsers.parse('a situação do apurado de "{dat}" é "{situacao}"'))
def situacao_apurado(contexto, dat, situacao):
    linha = contexto["controle"][date.fromisoformat(dat)]
    assert linha['situacao_apurado'] == situacao, linha
