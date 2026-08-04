"""Steps BDD — processamento atômico e resync no escopo do mapeamento.

Spec automacao-lancamentos R12/R14 (change processamento-idempotente-resync-cirurgico).
Ilha de datas 2061/2062 — ver conftest_processamento.semear_staging.
"""
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import garantir_sistema_origem
from .conftest_processamento import (
    LINHAS_PADRAO,
    lancamentos_do_qualificador,
    limpar_estado_processamento,
    linha_por_natureza,
    semear_staging,
    ultima_execucao_mapeamento,
)
from .conftest_regra import (
    criar_mapeamento,
    garantir_qualificador,
    garantir_termos_padrao,
)

scenarios("../automacao-lancamentos/processamento_atomico.feature")


@pytest.fixture()
def contexto():
    return {}


@pytest.fixture(autouse=True)
def _limpo(app):
    limpar_estado_processamento()


def _lancamentos_automaticos():
    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.base import db
    from fluxocaixa.services.dominio_lancamento import (
        ORIGEM_AUTOMATICO,
        resolver_origem,
    )

    db.session.expire_all()
    cod = resolver_origem(ORIGEM_AUTOMATICO).cod_origem_lancamento
    return Lancamento.query.filter_by(cod_origem_lancamento=cod).all()


def _seqs_por_recorte(sigla=None, ano=None):
    """seq_lancamento dos automáticos cujo rastro (staging→fonte) casa o recorte."""
    from fluxocaixa.models import EtlStaging, FonteExtracao, Lancamento
    from fluxocaixa.models.base import db
    from fluxocaixa.services.dominio_lancamento import (
        ORIGEM_AUTOMATICO,
        resolver_origem,
    )

    db.session.expire_all()
    cod = resolver_origem(ORIGEM_AUTOMATICO).cod_origem_lancamento
    consulta = (db.session.query(Lancamento.seq_lancamento)
                .join(EtlStaging,
                      EtlStaging.seq_etl_staging == Lancamento.seq_etl_staging)
                .join(FonteExtracao,
                      FonteExtracao.seq_fonte_extracao == EtlStaging.seq_fonte_extracao)
                .filter(Lancamento.cod_origem_lancamento == cod))
    if ano is not None:
        consulta = consulta.filter(EtlStaging.num_ano_exercicio == ano)
    if sigla is not None:
        from fluxocaixa.models import SistemaOrigem

        sistema = SistemaOrigem.query.filter_by(txt_sigla=sigla).first()
        consulta = consulta.filter(
            FonteExtracao.seq_sistema_origem == sistema.seq_sistema_origem)
    return {seq for (seq,) in consulta.all()}


@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(777)


@given(parsers.parse('um sistema de origem "{sigla}" cadastrado'))
def sistema_cadastrado(app, sigla):
    garantir_sistema_origem(sigla)


@given("os termos de regra padrão cadastrados")
def termos_padrao(app):
    garantir_termos_padrao()


@given(parsers.parse('um qualificador folha "{num}"'))
def qualificador_folha(app, num):
    garantir_qualificador(num)


@given(parsers.parse('linhas na staging de "{sigla}" no ano {ano:d}'))
def staging(app, sigla, ano):
    semear_staging(sigla, f"Fonte {sigla} {ano}", LINHAS_PADRAO, ano=ano)


@given(parsers.parse('o mapeamento {ano:d} tipo "{tipo}" de "{sigla}" com o item '
                     '"{num}" e regra "{regra}"'))
def mapeamento_do_ano(app, contexto, ano, tipo, sigla, num, regra):
    q = garantir_qualificador(num)
    mapeamento = criar_mapeamento(ano, tipo, sigla, [
        {"seq_qualificador": q.seq_qualificador, "txt_regra": regra},
    ])
    contexto.setdefault("mapeamentos", {})[(ano, sigla)] = mapeamento.seq_mapeamento
    contexto["seq_mapeamento"] = mapeamento.seq_mapeamento


@given("que a marcação de status das linhas falhará nesta execução")
def marcacao_falha(app, contexto, monkeypatch):
    from fluxocaixa.services import staging_service

    def _explode(*args, **kwargs):
        raise RuntimeError("falha simulada ao marcar status das linhas")

    monkeypatch.setattr(staging_service, "marcar_ok_lote", _explode)


@given("que já processei o mapeamento")
def ja_processei(app, contexto):
    from fluxocaixa.services.processamento_service import processar_mapeamento

    processar_mapeamento(contexto["seq_mapeamento"], disparo="MANUAL")


@given("que já processei os dois mapeamentos")
def ja_processei_dois(app, contexto):
    from fluxocaixa.services.processamento_service import processar_mapeamento

    for seq in contexto["mapeamentos"].values():
        processar_mapeamento(seq, disparo="MANUAL")


@given(parsers.parse('a linha de natureza "{natureza}" foi devolvida a pendente '
                     'por fora'))
def linha_devolvida(app, natureza):
    from fluxocaixa.models.base import db

    linha = linha_por_natureza(natureza)
    assert linha is not None
    linha.ind_status_processamento = '0'
    db.session.commit()


def _sujar_item(seq_mapeamento):
    from fluxocaixa.models import Mapeamento
    from fluxocaixa.models.base import db

    mapeamento = Mapeamento.query.get(seq_mapeamento)
    for item in mapeamento.itens:
        item.dat_ultima_execucao = None
    db.session.commit()


@given("o item do mapeamento 2061 ficou sujo")
def item_sujo_2061(app, contexto):
    seq = next(s for (ano, _), s in contexto["mapeamentos"].items() if ano == 2061)
    _sujar_item(seq)


@given(parsers.parse('o item do mapeamento de "{sigla}" ficou sujo'))
def item_sujo_sigla(app, contexto, sigla):
    seq = next(s for (_, sig), s in contexto["mapeamentos"].items() if sig == sigla)
    _sujar_item(seq)


@when("processo o mapeamento")
def processa(app, contexto):
    from fluxocaixa.services.processamento_service import processar_mapeamento

    contexto["execucao"] = processar_mapeamento(
        contexto["seq_mapeamento"], disparo="MANUAL")


@when("processo o mapeamento 2061")
def processa_2061(app, contexto):
    from fluxocaixa.services.processamento_service import processar_mapeamento

    seq = next(s for (ano, _), s in contexto["mapeamentos"].items() if ano == 2061)
    contexto["execucao"] = processar_mapeamento(seq, disparo="MANUAL")


@when(parsers.parse('processo o mapeamento de "{sigla}"'))
def processa_sigla(app, contexto, sigla):
    from fluxocaixa.services.processamento_service import processar_mapeamento

    seq = next(s for (_, sig), s in contexto["mapeamentos"].items() if sig == sigla)
    contexto["execucao"] = processar_mapeamento(seq, disparo="MANUAL")


@then(parsers.parse('nenhum lançamento existe no qualificador "{num}"'))
def nenhum_lancamento(app, num):
    assert lancamentos_do_qualificador(num) == []


@then(parsers.parse('a linha de natureza "{natureza}" continua pendente'))
def linha_pendente(app, natureza):
    linha = linha_por_natureza(natureza)
    assert linha is not None
    assert linha.ind_status_processamento == '0', linha.ind_status_processamento


@then(parsers.parse('a execução registra {n:d} lançamentos gerados e status "{status}"'))
def execucao_registra(app, contexto, n, status):
    execucao = ultima_execucao_mapeamento(contexto["seq_mapeamento"])
    assert execucao is not None
    assert execucao.qtd_lancamentos_gerados == n, execucao.qtd_lancamentos_gerados
    assert execucao.cod_status == status, execucao.cod_status


@then(parsers.parse('de fato não há lançamento automático no banco para o '
                    'exercício {ano:d}'))
def banco_coerente(app, ano):
    assert _seqs_por_recorte(ano=ano) == set()


@then(parsers.parse('o qualificador "{num}" tem {n:d} lançamentos'))
def qualificador_tem_n(app, num, n):
    assert len(lancamentos_do_qualificador(num)) == n


@then(parsers.parse('os lançamentos do exercício {ano:d} permanecem intactos'))
def exercicio_intacto(app, ano):
    seqs = _seqs_por_recorte(ano=ano)
    assert len(seqs) == 2, f"esperava os 2 lançamentos do exercício {ano}: {seqs}"


@then(parsers.parse('os lançamentos originados de "{sigla}" permanecem intactos'))
def sistema_intacto(app, sigla):
    seqs = _seqs_por_recorte(sigla=sigla)
    assert len(seqs) == 2, f"esperava os 2 lançamentos de {sigla}: {seqs}"
