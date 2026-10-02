"""Steps BDD — lançamento automático por exercício (automacao-lancamentos
R19–R21, extracao-configuravel R24–R25)."""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from . import apoio_exercicio as apoio

scenarios("../automacao-lancamentos/lancamento_por_exercicio.feature")


@pytest.fixture()
def contexto():
    return {}


@pytest.fixture(autouse=True)
def _ilha(app):
    apoio.limpar()
    yield
    apoio.limpar()


class ConectorPorExercicio:
    """Fake que declara filtrar pelo exercício (como a consulta SQL com
    `:ano`) e registra o exercício de cada chamada."""

    tipo = "FAKE_ANO"

    def __init__(self):
        from ..conftest_extracao import ConfigFake

        self.schema_config = ConfigFake
        self.exercicios = []

    def usa_exercicio(self, config):
        return True

    def testar_conexao(self, config):
        from fluxocaixa.extracao.conector import ResultadoTeste

        return ResultadoTeste(ok=True, mensagem="ok")

    def extrair(self, config, layout, janela):
        self.exercicios.append(janela.num_ano_exercicio)
        return []


_POR_EXERCICIO = None


def _fake_por_exercicio():
    global _POR_EXERCICIO
    from fluxocaixa.extracao import registry

    if _POR_EXERCICIO is None:
        _POR_EXERCICIO = ConectorPorExercicio()
    if "FAKE_ANO" not in registry.tipos_disponiveis():
        registry.registrar(_POR_EXERCICIO)
    _POR_EXERCICIO.exercicios = []
    return _POR_EXERCICIO


@given(parsers.parse('os planos de {a:d} e {b:d} com a rubrica "{codigo}"'))
def planos(a, b, codigo):
    qa = apoio.rubrica(codigo, a)
    apoio.rubrica(codigo, b, raiz=qa.cod_rubrica_raiz)


@given(parsers.parse('os mapeamentos de {a:d} e {b:d} do sistema "{sigla}" com o item '
                     '"{regra}" em "{codigo}"'))
def mapeamentos(a, b, sigla, regra, codigo):
    apoio.mapeamento(a, sigla, regra, codigo)
    apoio.mapeamento(b, sigla, regra, codigo)


@given(parsers.parse("o exercício {ano:d} fechado"))
def exercicio_fechado(ano):
    apoio.fechar(ano)


def _linha(dia, valor, natureza):
    from fluxocaixa.extracao.conector import LinhaExtraida

    return LinhaExtraida(cod_banco="", num_agencia="", num_conta="", cod_fundo="",
                         dsc_fundo="", val_saldo=Decimal(valor),
                         dat_saldo=date.fromisoformat(dia),
                         json_atributos={"natureza": natureza})


@given(parsers.parse('a fonte "{nome}" do sistema "{sigla}" com linhas de natureza "{natureza}" '
                     'em {d1} de {v1} e em {d2} de {v2}'))
def fonte_com_linhas(nome, sigla, natureza, d1, v1, d2, v2):
    from ..conftest_extracao import garantir_conector_fake

    fake = garantir_conector_fake()
    apoio.fonte_lancamento(nome, sigla)
    fake.linhas = [_linha(d1, v1, natureza), _linha(d2, v2, natureza)]


@given(parsers.parse('a fonte por exercício "{nome}" do sistema "{sigla}"'))
def fonte_por_exercicio(nome, sigla):
    _fake_por_exercicio()
    apoio.fonte_lancamento(nome, sigla, tipo="FAKE_ANO")


def _executar(nome, d1, d2):
    from fluxocaixa.extracao.conector import Janela
    from fluxocaixa.services.extracao_service import executar_fonte

    from ..conftest_extracao import fonte_por_nome

    return executar_fonte(fonte_por_nome(nome).seq_fonte_extracao,
                          janela=Janela(date.fromisoformat(d1), date.fromisoformat(d2)),
                          disparo="MANUAL")


@given(parsers.parse('a fonte "{nome}" executada na janela de {d1} a {d2}'))
def fonte_executada(nome, d1, d2):
    _executar(nome, d1, d2)


@given(parsers.parse('uma linha pendente na staging de {ano:d} com natureza "{natureza}"'))
def linha_pendente(ano, natureza):
    apoio.linha_pendente(ano, natureza)


@given(parsers.parse('uma linha pendente na staging de {ano:d} com natureza "{natureza}" '
                     'incluída há {dias:d} dias'))
def linha_pendente_antiga(ano, natureza, dias):
    apoio.linha_pendente(ano, natureza, dias_atras=dias)


@when(parsers.parse('crio o mapeamento de {ano:d} do sistema "{sigla}" com item em "{codigo}" '
                    'de {ano_rubrica:d}'))
def cria_mapeamento_outro_ano(contexto, ano, sigla, codigo, ano_rubrica):
    apoio.capturar(contexto, apoio.mapeamento, ano, sigla, "Natureza = 'A84'", codigo,
                   ano_rubrica)


@when(parsers.parse('executo a fonte "{nome}" na janela de {d1} a {d2}'))
def executa(contexto, nome, d1, d2):
    contexto["execucao"] = _executar(nome, d1, d2)


@when(parsers.parse('processo o sistema "{sigla}"'))
def processa(sigla):
    from fluxocaixa.services.processamento_service import processar_sistema_origem

    processar_sistema_origem(apoio.sistema(sigla).seq_sistema_origem)


@when("consulto as pendências da staging")
def consulta_pendencias(contexto):
    from fluxocaixa.services.staging_service import pendencias

    contexto["pendencias"] = pendencias(dias=7)


@then(parsers.parse('recebo erro de negócio citando "{trecho}"'))
def erro_cita(contexto, trecho):
    assert contexto.get("erro") is not None, "esperava erro de negócio"
    assert trecho in contexto["erro"].mensagem, contexto["erro"].mensagem


def _staging(nome="Fonte BDD84"):
    from fluxocaixa.models import EtlStaging

    from ..conftest_extracao import fonte_por_nome

    apoio.db().session.expire_all()
    return EtlStaging.query.filter_by(
        seq_fonte_extracao=fonte_por_nome(nome).seq_fonte_extracao).all()


@then(parsers.parse("a linha de {dia} está na staging no exercício {ano:d}"))
def linha_no_exercicio(dia, ano):
    linhas = [l for l in _staging() if l.dat_referencia == date.fromisoformat(dia)]
    assert [l.num_ano_exercicio for l in linhas] == [ano], linhas


@then(parsers.parse('a linha de {dia} virou lançamento na rubrica "{codigo}" de {ano:d}'))
def virou_lancamento(dia, codigo, ano):
    from fluxocaixa.models import Lancamento

    linha = next(l for l in _staging() if l.dat_referencia == date.fromisoformat(dia))
    lancs = Lancamento.query.filter_by(seq_etl_staging=linha.seq_etl_staging,
                                       ind_status='A').all()
    assert len(lancs) == 1, lancs
    assert lancs[0].seq_qualificador == apoio.rubrica(codigo, ano).seq_qualificador
    assert lancs[0].dat_lancamento == date.fromisoformat(dia)


@then(parsers.parse('a staging da fonte "{nome}" tem {n:d} linha'))
@then(parsers.parse('a staging da fonte "{nome}" tem {n:d} linhas'))
def staging_tem(nome, n):
    assert len(_staging(nome)) == n, _staging(nome)


@then(parsers.parse('a última execução da fonte "{nome}" cita "{trecho}"'))
def execucao_cita(contexto, nome, trecho):
    assert trecho in (contexto["execucao"].txt_detalhe_erros or ""), \
        contexto["execucao"].txt_detalhe_erros


@then(parsers.parse('nenhum lançamento foi gerado na rubrica "{codigo}" de {ano:d}'))
def nenhum_lancamento(codigo, ano):
    from fluxocaixa.models import Lancamento

    assert Lancamento.query.filter_by(
        seq_qualificador=apoio.rubrica(codigo, ano).seq_qualificador).count() == 0


@then(parsers.parse("a consulta rodou para os exercícios {a:d} e {b:d}"))
def rodou_para(a, b):
    assert sorted(_POR_EXERCICIO.exercicios) == [a, b], _POR_EXERCICIO.exercicios


@then(parsers.parse('cada linha da fonte "{nome}" tem um único lançamento'))
def lancamento_unico(nome):
    from fluxocaixa.models import Lancamento

    for linha in _staging(nome):
        assert Lancamento.query.filter_by(seq_etl_staging=linha.seq_etl_staging,
                                          ind_status='A').count() == 1, linha.seq_etl_staging


@then(parsers.parse('o exercício {ano:d} aparece com {n:d} linha pendente do sistema "{sigla}"'))
def aparece_pendente(contexto, ano, n, sigla):
    itens = [p for p in contexto["pendencias"]
             if p["ano"] == ano and p["sistema"] == sigla]
    assert itens and itens[0]["quantidade"] == n, contexto["pendencias"]
