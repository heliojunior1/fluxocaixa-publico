"""Steps BDD — registro e disparo do processamento (spec R15)."""
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import garantir_sistema_origem
from .conftest_processamento import (
    LINHAS_PADRAO,
    lancamentos_do_qualificador,
    limpar_estado_processamento,
    semear_staging,
    ultima_execucao_mapeamento,
)
from .conftest_regra import (
    criar_mapeamento,
    garantir_qualificador,
    garantir_termos_padrao,
    sistema_por_sigla,
)

scenarios("../automacao-lancamentos/execucao_mapeamento.feature")


@pytest.fixture()
def contexto():
    return {}


@pytest.fixture(autouse=True)
def _limpo(app):
    limpar_estado_processamento()


@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(777)


@given(parsers.parse('um sistema de origem "{sigla}" cadastrado'))
def sistema_cadastrado(app, contexto, sigla):
    garantir_sistema_origem(sigla)
    contexto["sigla"] = sigla


@given("os termos de regra padrão cadastrados")
def termos_padrao(app):
    garantir_termos_padrao()


@given(parsers.parse('um qualificador folha "{num}"'))
def qualificador_folha(app, num):
    garantir_qualificador(num)


@given(parsers.parse('linhas na staging de "{sigla}" no ano {ano:d}'))
def staging(app, sigla, ano):
    semear_staging(sigla, f"Fonte {sigla}", LINHAS_PADRAO, ano=ano)


@given(parsers.parse('o mapeamento 2026 de "{sigla}" com o item "{num}" e regra "{regra}"'))
def mapeamento_um_item(app, contexto, sigla, num, regra):
    q = garantir_qualificador(num)
    mapeamento = criar_mapeamento(2026, "1", sigla, [
        {"seq_qualificador": q.seq_qualificador, "txt_regra": regra},
    ])
    contexto["seq_mapeamento"] = mapeamento.seq_mapeamento


@given(parsers.parse('o mapeamento 2026 de "{sigla}" com dois itens que casam '
                     'com a mesma linha'))
def mapeamento_conflito(app, contexto, sigla):
    q1, q2 = garantir_qualificador("1.1.1"), garantir_qualificador("1.1.2")
    # 11120000 → casa com os DOIS itens  → erro
    # 11120001 → casa só com o item A    → 1 lançamento
    # 22220000 → não casa com ninguém    → segue pendente
    mapeamento = criar_mapeamento(2026, "1", sigla, [
        {"seq_qualificador": q1.seq_qualificador,
         "txt_regra": "Natureza começa com '1112'"},
        {"seq_qualificador": q2.seq_qualificador,
         "txt_regra": "Natureza = '11120000'"},
    ])
    contexto["seq_mapeamento"] = mapeamento.seq_mapeamento


@given(parsers.parse('uma fonte de lançamento de "{sigla}" que traz linhas que casam'))
def fonte_lancamento(app, contexto, sigla):
    """Conector fake de destino LANCAMENTO: emite linhas com json_atributos."""
    from decimal import Decimal

    from fluxocaixa.extracao import registry
    from fluxocaixa.extracao.conector import LinhaExtraida
    from fluxocaixa.services.extracao_service import criar_fonte
    from pydantic import BaseModel

    class _ConfigLanc(BaseModel):
        pass

    class _LayoutLanc(BaseModel):
        capturar_atributos: bool = True
        campos: list = []

    class ConectorLancFake:
        tipo = "LANC_FAKE"
        schema_config = _ConfigLanc
        layout_kind = "MAPEAMENTO"

        def testar_conexao(self, config):  # pragma: no cover
            from fluxocaixa.extracao.conector import ResultadoTeste
            return ResultadoTeste(ok=True, mensagem="ok")

        def extrair(self, config, layout, janela):
            from datetime import date
            for linha in LINHAS_PADRAO:
                yield LinhaExtraida(
                    cod_banco="001", num_agencia="0001", num_conta="12345-6",
                    cod_fundo="", dsc_fundo="",
                    val_saldo=Decimal(linha["valor"]),
                    dat_saldo=date(2026, 7, 10),
                    json_atributos=dict(linha),
                )

    if "LANC_FAKE" not in registry.tipos_disponiveis():
        registry.registrar(ConectorLancFake())

    from ..conftest_extracao import fonte_por_nome

    existente = fonte_por_nome(f"Fonte Carga {sigla}")
    if existente is not None:
        contexto["seq_fonte"] = existente.seq_fonte_extracao
        return

    fonte = criar_fonte(
        nom_fonte=f"Fonte Carga {sigla}", cod_tipo_conector="LANC_FAKE",
        sigla_sistema=sigla, json_config={},
        json_layout={"capturar_atributos": True, "campos": [
            {"caminho": "data", "destino": "dat_saldo"},
            {"caminho": "valor", "destino": "val_saldo"},
        ]},
        cod_destino="LANCAMENTO",
    )
    contexto["seq_fonte"] = fonte.seq_fonte_extracao


@given("que o processamento vai falhar")
def processamento_falha(app, contexto, monkeypatch):
    from fluxocaixa.services import processamento_service

    def _explode(*a, **kw):
        raise RuntimeError("falha simulada no processamento")

    monkeypatch.setattr(processamento_service, "_classificar_linhas", _explode)


@given("que já processei o mapeamento")
def ja_processei(app, contexto):
    from fluxocaixa.services.processamento_service import processar_mapeamento

    processar_mapeamento(contexto["seq_mapeamento"], disparo="MANUAL")


@when("processo o mapeamento")
@when("processo o mapeamento manualmente")
def processa(app, contexto):
    from fluxocaixa.services.processamento_service import processar_mapeamento

    contexto["execucao"] = processar_mapeamento(
        contexto["seq_mapeamento"], disparo="MANUAL")


@when(parsers.parse('altero a regra do item "{num}" para "{regra}" e processo'))
def altera_e_processa(app, contexto, num, regra):
    from fluxocaixa.models import Mapeamento
    from fluxocaixa.services.mapeamento_service import alterar_mapeamento
    from fluxocaixa.services.processamento_service import processar_mapeamento

    mapeamento = Mapeamento.query.get(contexto["seq_mapeamento"])
    itens = [{
        "seq_item_mapeamento": i.seq_item_mapeamento,
        "seq_qualificador": i.seq_qualificador,
        "txt_regra": regra if i.qualificador.num_qualificador == num else i.txt_regra,
        "ind_inversao_sinal": i.ind_inversao_sinal,
    } for i in mapeamento.itens]
    alterar_mapeamento(
        contexto["seq_mapeamento"], 2026, "1",
        sistema_por_sigla(contexto["sigla"]).seq_sistema_origem,
        mapeamento.dsc_mapeamento, itens,
    )
    contexto["execucao"] = processar_mapeamento(
        contexto["seq_mapeamento"], disparo="MANUAL")


@when("executo a fonte de lançamento")
def executa_fonte(app, contexto):
    from datetime import date

    from fluxocaixa.extracao.conector import Janela
    from fluxocaixa.services.extracao_service import executar_fonte

    contexto["execucao_extracao"] = executar_fonte(
        contexto["seq_fonte"], janela=Janela(date(2026, 7, 10), date(2026, 7, 10)))


@then(parsers.parse('a execução de mapeamento registra {ok:d} lançamento gerado '
                    'e {erro:d} linha com erro'))
def execucao_contadores(app, contexto, ok, erro):
    execucao = ultima_execucao_mapeamento(contexto["seq_mapeamento"])
    assert execucao is not None, "nenhuma execução de mapeamento registrada"
    assert (execucao.qtd_lancamentos_gerados, execucao.qtd_linhas_erro) == (ok, erro), (
        f"gerados={execucao.qtd_lancamentos_gerados}, erros={execucao.qtd_linhas_erro}"
    )


@then(parsers.parse('a situação da execução de mapeamento é "{status}"'))
def execucao_status(app, contexto, status):
    execucao = ultima_execucao_mapeamento(contexto.get("seq_mapeamento"))
    assert execucao is not None, "nenhuma execução de mapeamento registrada"
    assert execucao.cod_status == status, (
        f"esperava {status}, veio {execucao.cod_status} "
        f"(detalhe: {execucao.txt_detalhe_erros!r})"
    )


@then(parsers.parse('a execução de mapeamento registra {n:d} lançamentos removidos'))
def execucao_removidos(app, contexto, n):
    execucao = ultima_execucao_mapeamento(contexto["seq_mapeamento"])
    assert execucao.qtd_lancamentos_removidos == n, execucao.qtd_lancamentos_removidos


@then(parsers.parse('a execução de mapeamento tem disparo "{disparo}"'))
def execucao_disparo(app, contexto, disparo):
    execucao = ultima_execucao_mapeamento()
    assert execucao is not None, "nenhuma execução de mapeamento registrada"
    assert execucao.cod_disparo == disparo, execucao.cod_disparo


@then(parsers.parse('foram criados {n:d} lançamentos no qualificador "{num}"'))
def n_lancamentos(app, n, num):
    assert len(lancamentos_do_qualificador(num)) == n


@then(parsers.parse('a execução da extração mantém a situação "{status}"'))
def extracao_status(app, contexto, status):
    from fluxocaixa.models.base import db

    db.session.expire_all()
    assert contexto["execucao_extracao"].cod_status == status, (
        "falha no processamento reclassificou a extração — são operações distintas"
    )
