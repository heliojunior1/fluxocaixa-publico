"""Steps BDD — painel analítico do desembolso (spec desembolso R26).

Ilha 2059 (órgão 70014, qualificador 2.9.95, fontes 1.503/1.653) — o painel
varre as liberações confirmadas do ANO inteiro.
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .conftest_regra import garantir_qualificador

scenarios("../desembolso/analitico.feature")


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


def _liberacao_do_dia(dat):
    from fluxocaixa.models import Liberacao

    return Liberacao.query.filter_by(
        dat_liberacao=date.fromisoformat(dat), ind_status='A').first()


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


@given(parsers.parse('um qualificador folha de despesa "{num}"'))
def qualificador_simples(app, num):
    garantir_qualificador(num)


@given(parsers.parse('a fonte "{codigo}" cadastrada na vigência {vigencia:d} como "{vinculada}"'))
def fonte_cadastrada(app, codigo, vigencia, vinculada):
    from fluxocaixa.services.fonte_recurso_service import criar_fonte

    _db().session.rollback()
    if _fonte(codigo, vigencia) is None:
        ident, fonte = codigo.split(".", 1)
        criar_fonte(ident, fonte, f"Fonte de teste {codigo}", vigencia,
                    vinculada='L' if vinculada == 'livre' else 'V')


def _confirmada(dat, cod, num, codigo, vigencia, valor, natureza='D'):
    from fluxocaixa.services.liberacao_service import (
        confirmar_liberacao,
        criar_liberacao,
    )

    if _liberacao_do_dia(dat) is not None:
        return
    q = garantir_qualificador(num)
    fonte = _fonte(codigo, vigencia)
    liberacao = criar_liberacao(
        dat_liberacao=date.fromisoformat(dat), cod_orgao=cod,
        seq_qualificador=q.seq_qualificador,
        seq_fonte_recurso=fonte.seq_fonte_recurso,
        val_liberacao=Decimal(valor), cod_natureza_obrigacao=natureza)
    confirmar_liberacao(liberacao.seq_liberacao, confirmado=True)


@given(parsers.parse('uma liberação confirmada de {valor} em "{dat}" no órgão "{cod:d}", qualificador "{num}" e fonte "{codigo}" da vigência {vigencia:d}'))
def liberacao_confirmada(app, valor, dat, cod, num, codigo, vigencia):
    _confirmada(dat, cod, num, codigo, vigencia, valor)


@given(parsers.parse('uma liberação confirmada de {valor} em "{dat}" no órgão "{cod:d}", qualificador "{num}", fonte "{codigo}" da vigência {vigencia:d} e natureza "{natureza}"'))
def liberacao_confirmada_natureza(app, valor, dat, cod, num, codigo, vigencia, natureza):
    _confirmada(dat, cod, num, codigo, vigencia, valor, natureza)


@given(parsers.parse('uma apropriação de {valor} sobre essa liberação em "{dat}"'))
def apropriacao_datada(app, valor, dat):
    # posiciona o EVENTO no mês desejado — o serviço estampa sempre "hoje",
    # então a massa de teste insere a linha-evento direto (deriva igual)
    from fluxocaixa.models import PagamentoLiberacao

    liberacao = _liberacao_do_dia("2059-03-10")
    if PagamentoLiberacao.query.filter_by(
            seq_liberacao=liberacao.seq_liberacao).first() is not None:
        return
    from fluxocaixa.models import Pagamento

    pagamento = Pagamento(
        dat_pagamento=date.fromisoformat(dat), cod_orgao=liberacao.cod_orgao,
        seq_qualificador=liberacao.seq_qualificador,
        seq_fonte_recurso=liberacao.seq_fonte_recurso,
        val_pagamento=Decimal(valor), cod_origem='M', ind_status='A',
        cod_pessoa_inclusao=1)
    _db().session.add(pagamento)
    _db().session.flush()
    _db().session.add(PagamentoLiberacao(
        seq_pagamento=pagamento.seq_pagamento,
        seq_liberacao=liberacao.seq_liberacao, cod_tipo_evento='A',
        val_apropriado=Decimal(valor), dat_evento=date.fromisoformat(dat),
        cod_pessoa_evento=1))
    _db().session.commit()


@when(parsers.parse('abro o painel analítico de {ano:d}'))
def abre_painel(app, contexto, ano):
    from fluxocaixa.services.relatorio.analitico_desembolso_service import dados_analitico

    contexto["dados"] = dados_analitico(ano)


@then(parsers.parse('a linha analítica do órgão "{cod:d}" mostra liberado {liberado}, pago {pago} e pendente {pendente}'))
def linha_do_orgao(contexto, cod, liberado, pago, pendente):
    linha = contexto["dados"]["por_orgao"].get(cod)
    assert linha is not None, contexto["dados"]["por_orgao"]
    q2 = lambda v: Decimal(v).quantize(Decimal("0.01"))  # noqa: E731
    assert linha["liberado"] == q2(liberado), linha
    assert linha["pago"] == q2(pago), linha
    assert linha["pendente"] == q2(pendente), linha


@then(parsers.parse('a composição por natureza mostra "{n1}" com {p1}% e "{n2}" com {p2}%'))
def composicao_natureza(contexto, n1, p1, n2, p2):
    composicao = contexto["dados"]["por_natureza"]
    assert composicao[n1]["pct"] == Decimal(p1).quantize(Decimal("0.01")), composicao
    assert composicao[n2]["pct"] == Decimal(p2).quantize(Decimal("0.01")), composicao


@then(parsers.parse('a composição por grupo de fonte mostra "{g1}" com {p1}% e "{g2}" com {p2}%'))
def composicao_grupo(contexto, g1, p1, g2, p2):
    composicao = contexto["dados"]["por_grupo_fonte"]
    assert composicao[g1]["pct"] == Decimal(p1).quantize(Decimal("0.01")), composicao
    assert composicao[g2]["pct"] == Decimal(p2).quantize(Decimal("0.01")), composicao


@then(parsers.parse('o pendente acumulado do mês {mes:d} de {ano:d} é {valor}'))
def pendente_do_mes(contexto, mes, ano, valor):
    evolucao = contexto["dados"]["evolucao_pendente"]
    assert evolucao[mes] == Decimal(valor).quantize(Decimal("0.01")), evolucao
