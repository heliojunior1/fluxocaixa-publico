"""Steps BDD — exercício aberto e fechado (cadastros-nucleo R31–R32)."""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from . import apoio_exercicio as apoio

scenarios("../cadastros-nucleo/exercicio_aberto_fechado.feature")


@pytest.fixture()
def contexto():
    return {}


@pytest.fixture(autouse=True)
def _ilha(app):
    apoio.limpar()
    yield
    apoio.limpar()


@given(parsers.parse('o plano de {ano:d} com a rubrica "{codigo}"'))
def plano(ano, codigo):
    apoio.rubrica(codigo, ano)


@given(parsers.parse('uma linha pendente na staging de {ano:d} com natureza "{natureza}"'))
def linha_pendente(ano, natureza):
    apoio.linha_pendente(ano, natureza)


@given(parsers.parse("o exercício {ano:d} fechado"))
def exercicio_fechado(ano):
    apoio.fechar(ano)


@given(parsers.parse('o mapeamento de {ano:d} do sistema "{sigla}" com o item "{regra}" em "{codigo}"'))
def mapeamento(ano, sigla, regra, codigo):
    apoio.mapeamento(ano, sigla, regra, codigo)


@when(parsers.parse('fecho o exercício {ano:d} com motivo "{motivo}" sem confirmar'))
def fecha_sem_confirmar(contexto, ano, motivo):
    from fluxocaixa.services.exercicio_service import fechar_exercicio

    apoio.capturar(contexto, fechar_exercicio, ano, motivo, confirmado=False, user_id=1)


@when(parsers.parse('lanço {valor} em "{codigo}" com data {dia}'))
def lanca(contexto, valor, codigo, dia):
    from fluxocaixa.domain.lancamento import LancamentoCreate
    from fluxocaixa.services.dominio_lancamento import resolver_origem, resolver_tipo
    from fluxocaixa.services.lancamento_service import create_lancamento

    data = date.fromisoformat(dia)
    dados = LancamentoCreate(
        dat_lancamento=data, seq_qualificador=apoio.rubrica(codigo, data.year).seq_qualificador,
        val_lancamento=Decimal(valor),
        cod_tipo_lancamento=resolver_tipo("Entrada").cod_tipo_lancamento,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento)
    apoio.capturar(contexto, create_lancamento, dados)


@when(parsers.parse('altero a descrição de "{codigo}" de {ano:d}'))
def altera_descricao(contexto, codigo, ano):
    from fluxocaixa.services.qualificador_service import update_qualificador

    q = apoio.rubrica(codigo, ano)
    apoio.capturar(contexto, update_qualificador, q.seq_qualificador, q.num_qualificador,
                   "Descrição nova BDD84", q.cod_qualificador_pai)


@when(parsers.parse('reabro o exercício {ano:d} com motivo "{motivo}"'))
def reabre(ano, motivo):
    from fluxocaixa.services.exercicio_service import reabrir_exercicio

    reabrir_exercicio(ano, motivo, user_id=1)


@when(parsers.parse("abro o exercício {novo:d} a partir de {origem:d}"))
def abre(novo, origem):
    from fluxocaixa.services.qualificador_service import abrir_exercicio

    abrir_exercicio(origem, novo, confirmado=True)


@then(parsers.parse('recebo erro de negócio citando "{trecho}"'))
def erro_cita(contexto, trecho):
    assert contexto.get("erro") is not None, "esperava erro de negócio"
    assert trecho in contexto["erro"].mensagem, contexto["erro"].mensagem


@then(parsers.parse("o exercício {ano:d} continua aberto"))
def continua_aberto(ano):
    from fluxocaixa.services.exercicio_service import fechado

    assert not fechado(ano)


@then("o lançamento é aceito")
def lancamento_aceito(contexto):
    assert contexto.get("erro") is None, contexto.get("erro")


@then(parsers.parse('o histórico do exercício {ano:d} tem "{a}" e "{b}"'))
def historico_dois(ano, a, b):
    from fluxocaixa.services.exercicio_service import historico

    rotulos = [e.rotulo for e in historico(ano)]
    assert a in rotulos and b in rotulos, rotulos


@then(parsers.parse('o histórico do exercício {ano:d} tem "{a}"'))
def historico_um(ano, a):
    from fluxocaixa.services.exercicio_service import historico

    assert a in [e.rotulo for e in historico(ano)]


def _mapeamento(ano, sigla):
    from fluxocaixa.models import Mapeamento

    return Mapeamento.query.filter_by(
        num_ano_exercicio=ano, seq_sistema_origem=apoio.sistema(sigla).seq_sistema_origem,
        ind_status='A').first()


@then(parsers.parse('existe o mapeamento de {ano:d} do sistema "{sigla}"'))
def existe_mapeamento(ano, sigla):
    assert _mapeamento(ano, sigla) is not None


@then(parsers.parse('o item do mapeamento de {ano:d} aponta para "{codigo}" do plano de '
                    '{plano:d} com a regra "{regra}"'))
def item_aponta(ano, codigo, plano, regra):
    itens = [i for i in _mapeamento(ano, "SIS84").itens if i.ind_status == 'A']
    assert len(itens) == 1
    assert itens[0].seq_qualificador == apoio.rubrica(codigo, plano).seq_qualificador
    assert itens[0].txt_regra == regra
    assert itens[0].dat_ultima_execucao is None
