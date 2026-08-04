"""Steps BDD — relatório de KPIs (spec relatorios R1–R8).

Ataque via TestClient no par página + `/relatorios/kpis/data` (JSON). Os
cenários usam ilhas de datas 2031–2033 (o seed demo grava em 2022–2026) e
contas/qualificadores fictícios próprios, então as agregações globais dos
KPIs não sofrem interferência do restante da suíte.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../relatorios/kpis.feature")


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


# --------------------------------------------------------------------------
# Helpers de massa de teste
# --------------------------------------------------------------------------

def _conta(ident: str):
    from fluxocaixa.models import ContaBancaria

    db = _db()
    db.session.rollback()
    banco, agencia, num = ident.split("/")
    existente = ContaBancaria.query.filter_by(
        cod_banco=banco, num_agencia=agencia, num_conta=num
    ).first()
    if existente:
        return existente
    conta = ContaBancaria(
        cod_banco=banco, num_agencia=agencia, num_conta=num,
        dsc_conta=f"Conta KPI {ident}",
    )
    db.session.add(conta)
    db.session.commit()
    return conta


def _fundo_kpi():
    from fluxocaixa.models import Fundo, TipoOrigemSaldo

    db = _db()
    fundo = Fundo.query.filter_by(cod_fundo="9901").first()
    if fundo:
        return fundo
    tipo = TipoOrigemSaldo.query.filter_by(txt_sigla="MANUAL").first()
    fundo = Fundo(cod_fundo="9901", dsc_fundo="Fundo KPI",
                  seq_tipo_origem=tipo.seq_tipo_origem_saldo)
    db.session.add(fundo)
    db.session.commit()
    return fundo


def _gravar_saldo(conta, dat: str, valor: str):
    from fluxocaixa.services.saldo_fundo_service import gravar_saldo

    gravar_saldo(
        seq_conta=conta.seq_conta,
        seq_fundo=_fundo_kpi().seq_fundo,
        dat_saldo=date.fromisoformat(dat),
        val_saldo=Decimal(valor),
        val_aplicacoes=Decimal(0),
        val_resgates=Decimal(0),
        sigla_tipo_origem="MANUAL",
        sigla_sistema_origem=None,
    )


def _qualificador(num: str):
    """Cria (ou reusa) o qualificador `num`, garantindo a cadeia de pais."""
    from fluxocaixa.models import Qualificador

    db = _db()
    existente = Qualificador.query.filter_by(num_qualificador=num).first()
    if existente:
        return existente
    partes = num.split(".")
    pai = _qualificador(".".join(partes[:-1])) if len(partes) > 1 else None
    qualificador = Qualificador(
        num_qualificador=num,
        dsc_qualificador=f"Qualificador KPI {num}",
        cod_qualificador_pai=pai.seq_qualificador if pai else None,
    )
    db.session.add(qualificador)
    db.session.commit()
    return qualificador


def _lancamento(tipo_desc: str, valor: str, dat: str,
                qual_num: str | None = None, origem_desc: str = "Manual",
                seq_conta: int | None = None):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.services.dominio_lancamento import resolver_origem, resolver_tipo

    db = _db()
    db.session.rollback()
    # Folha padrão por tipo, fora das ilhas dos cenários de composição
    if qual_num is None:
        qual_num = "1.90.1" if tipo_desc == "Entrada" else "2.90.9"
    lancamento = Lancamento(
        dat_lancamento=date.fromisoformat(dat),
        seq_qualificador=_qualificador(qual_num).seq_qualificador,
        val_lancamento=Decimal(valor),
        cod_tipo_lancamento=resolver_tipo(tipo_desc).cod_tipo_lancamento,
        cod_origem_lancamento=resolver_origem(origem_desc).cod_origem_lancamento,
        seq_conta=seq_conta,
        cod_pessoa_inclusao=1,
        ind_status='A',
    )
    db.session.add(lancamento)
    db.session.commit()
    return lancamento


def _sistema_kpi():
    from fluxocaixa.models import SistemaOrigem

    db = _db()
    sistema = SistemaOrigem.query.filter_by(txt_sigla="KPI_TESTE").first()
    if sistema is None:
        sistema = SistemaOrigem(txt_sigla="KPI_TESTE",
                                dsc_sistema_origem="Sistema KPI de teste")
        db.session.add(sistema)
        db.session.commit()
    return sistema


def _fonte(destino: str):
    from fluxocaixa.models.extracao import FonteExtracao

    db = _db()
    fonte = FonteExtracao(
        nom_fonte=f"Fonte KPI {destino}",
        cod_tipo_conector="FAKE_KPI",
        cod_destino=destino,
        seq_sistema_origem=_sistema_kpi().seq_sistema_origem,
        json_config={},
        ind_status='A',
    )
    db.session.add(fonte)
    db.session.commit()
    return fonte


def _execucao(fonte, status: str, horas_atras: int):
    from fluxocaixa.models.extracao import ExecucaoExtracao

    db = _db()
    hoje = date.today()
    db.session.add(ExecucaoExtracao(
        seq_fonte_extracao=fonte.seq_fonte_extracao,
        dat_inicio_execucao=datetime.now() - timedelta(hours=horas_atras),
        cod_disparo='MANUAL',
        cod_status=status,
        dat_janela_inicio=hoje,
        dat_janela_fim=hoje,
    ))
    db.session.commit()


def _get_kpis(client, contexto, **params):
    contexto["resp"] = client.get("/relatorios/kpis/data", params=params)
    return contexto["resp"]


def _dados(contexto) -> dict:
    resp = contexto["resp"]
    assert resp.status_code == 200, f"esperava 200, veio {resp.status_code}: {resp.text[:300]}"
    return resp.json()


def _linha_conta(contexto, ident: str) -> dict:
    banco, agencia, num = ident.split("/")
    linhas = [
        linha for linha in _dados(contexto)["saldo_por_conta"]
        if linha["cod_banco"] == banco
        and linha["num_agencia"] == agencia
        and linha["num_conta"] == num
    ]
    assert linhas, f"conta {ident} não está no bloco saldo por conta"
    return linhas[0]


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given(parsers.parse('um usuário autenticado com perfil "{perfil}"'),
       target_fixture="client_perfil")
def usuario_com_perfil(app, perfil):
    from fastapi.testclient import TestClient

    from ..conftest_permissoes import criar_usuario_com_perfil

    login, senha, _ = criar_usuario_com_perfil(perfil)
    tc = TestClient(app)
    resp = tc.post("/login", data={"usuario": login, "senha": senha},
                   follow_redirects=False)
    assert resp.status_code in (302, 303)
    return tc


@given(parsers.parse('uma conta KPI "{ident}" com saldo de "{valor}" em "{dat}"'))
@given(parsers.parse('a conta KPI "{ident}" com saldo de "{valor}" em "{dat}"'))
def conta_com_saldo(client, ident, valor, dat):
    _gravar_saldo(_conta(ident), dat, valor)


@given(parsers.parse('um lançamento de "{tipo}" de "{valor}" em "{dat}"'))
def lancamento_simples(client, tipo, valor, dat):
    _lancamento(tipo, valor, dat)


@given(parsers.parse('um lançamento de "{tipo}" de "{valor}" no qualificador folha "{qual}" em "{dat}"'))
def lancamento_no_qualificador(client, tipo, valor, qual, dat):
    _lancamento(tipo, valor, dat, qual_num=qual)


@given(parsers.parse('lançamentos de entrada nos qualificadores "{quals}" com valores "{valores}" em "{dat}"'))
def lancamentos_por_qualificador(client, quals, valores, dat):
    for qual, valor in zip(quals.split(","), valores.split(",")):
        _lancamento("Entrada", valor, dat, qual_num=qual.strip())


@given(parsers.parse('um lançamento automático sem conta de "{valor}" em "{dat}"'))
def lancamento_automatico_sem_conta(client, valor, dat):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.services.dominio_lancamento import resolver_origem

    origem = resolver_origem("Automático")
    existente = Lancamento.query.filter_by(
        dat_lancamento=date.fromisoformat(dat),
        cod_origem_lancamento=origem.cod_origem_lancamento,
        val_lancamento=Decimal(valor),
    ).first()
    if existente is None:
        _lancamento("Entrada", valor, dat, origem_desc="Automático")


@given("nenhuma fonte ou execução de extração remanescente")
def limpar_extracao(client):
    from fluxocaixa.models.extracao import ExecucaoExtracao, FonteExtracao

    db = _db()
    db.session.rollback()
    db.session.query(ExecucaoExtracao).delete()
    for fonte in FonteExtracao.query.all():
        fonte.ind_status = 'I'
    db.session.commit()


@given(parsers.parse('uma fonte ativa de destino "{destino}" com execução "{status}" há "{horas}" horas'),
       target_fixture="fonte_kpi")
def fonte_com_execucao(client, destino, status, horas):
    fonte = _fonte(destino)
    _execucao(fonte, status, int(horas))
    return fonte


@given(parsers.parse('a mesma fonte com execução "{status}" há "{horas}" horas'))
def mesma_fonte_execucao(fonte_kpi, status, horas):
    _execucao(fonte_kpi, status, int(horas))


@given(parsers.parse('uma fonte ativa de destino "{destino}" sem execuções'),
       target_fixture="fonte_kpi")
def fonte_sem_execucao(client, destino):
    return _fonte(destino)


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when("acesso a página do relatório de KPIs")
def acessa_pagina(client, contexto):
    contexto["resp_pagina"] = client.get("/relatorios/kpis")


@when("esse usuário acessa a página do relatório de KPIs")
def acessa_pagina_perfil(client_perfil, contexto):
    contexto["resp_pagina"] = client_perfil.get("/relatorios/kpis")


@when(parsers.parse('solicito os dados de KPIs com início "{inicio}" e fim "{fim}"'))
def solicita_periodo_invalido(client, contexto, inicio, fim):
    _get_kpis(client, contexto, data_inicio=inicio, data_fim=fim)


@when(parsers.parse('solicito os KPIs com data de referência "{ref}"'))
def solicita_por_referencia(client, contexto, ref):
    _get_kpis(client, contexto, data_referencia=ref)


@when(parsers.parse('solicito os KPIs com data de referência "{ref}" e período de "{inicio}" a "{fim}"'))
def solicita_referencia_e_periodo(client, contexto, ref, inicio, fim):
    _get_kpis(client, contexto, data_referencia=ref,
              data_inicio=inicio, data_fim=fim)


@when(parsers.parse('solicito os KPIs do período "{inicio}" a "{fim}"'))
def solicita_por_periodo(client, contexto, inicio, fim):
    _get_kpis(client, contexto, data_inicio=inicio, data_fim=fim)


@when(parsers.parse('solicito os KPIs do período "{inicio}" a "{fim}" filtrando pelo banco "{banco}"'))
def solicita_periodo_banco(client, contexto, inicio, fim, banco):
    _get_kpis(client, contexto, data_inicio=inicio, data_fim=fim,
              cod_banco=banco)


@when("solicito os KPIs")
def solicita_sem_parametros(client, contexto):
    _get_kpis(client, contexto)


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then("a página de KPIs responde com sucesso")
def pagina_ok(contexto):
    resp = contexto["resp_pagina"]
    assert resp.status_code == 200, f"esperava 200, veio {resp.status_code}"


@then("o acesso aos KPIs é negado")
def acesso_negado(contexto):
    assert contexto["resp_pagina"].status_code == 403


@then(parsers.parse('recebo erro de negócio nos KPIs mencionando "{trecho}"'))
def erro_de_negocio(contexto, trecho):
    resp = contexto["resp"]
    assert resp.status_code == 400, f"esperava 400, veio {resp.status_code}"
    assert trecho.lower() in resp.json()["detail"].lower()


@then(parsers.parse('o saldo consolidado é "{valor}"'))
def saldo_consolidado(contexto, valor):
    assert _dados(contexto)["saldos"]["consolidado"] == valor


@then(parsers.parse('a quebra por banco lista "{banco}" com "{valor}"'))
def quebra_por_banco(contexto, banco, valor):
    por_banco = {
        item["cod_banco"]: item["valor"]
        for item in _dados(contexto)["saldos"]["por_banco"]
    }
    assert por_banco.get(banco) == valor, f"por_banco={por_banco}"


@then(parsers.parse('a variação do consolidado vs D-1 é "{valor}"'))
def variacao_consolidado(contexto, valor):
    assert _dados(contexto)["saldos"]["variacao_d1"] == valor


@then("a variação do consolidado vs D-1 é nula")
def variacao_consolidado_nula(contexto):
    assert _dados(contexto)["saldos"]["variacao_d1"] is None


@then(parsers.parse('o rendimento do período é "{valor}"'))
def rendimento_periodo(contexto, valor):
    assert _dados(contexto)["saldos"]["rendimento"] == valor


@then(parsers.parse('a receita do período é "{valor}"'))
def receita_periodo(contexto, valor):
    assert _dados(contexto)["receita_despesa"]["receita"] == valor


@then(parsers.parse('a despesa do período é "{valor}"'))
def despesa_periodo(contexto, valor):
    assert _dados(contexto)["receita_despesa"]["despesa"] == valor


@then(parsers.parse('o resultado do período é "{valor}"'))
def resultado_periodo(contexto, valor):
    assert _dados(contexto)["receita_despesa"]["resultado"] == valor


@then(parsers.parse('o percentual despesa sobre receita é "{valor}"'))
def percentual_periodo(contexto, valor):
    assert _dados(contexto)["receita_despesa"]["percentual"] == valor


@then("o percentual despesa sobre receita é nulo")
def percentual_nulo(contexto):
    assert _dados(contexto)["receita_despesa"]["percentual"] is None


@then(parsers.parse('a evolução tem {qtd:d} pontos de "{inicio}" a "{fim}"'))
def evolucao_pontos(contexto, qtd, inicio, fim):
    evolucao = _dados(contexto)["evolucao"]
    assert len(evolucao) == qtd, f"esperava {qtd} pontos, vieram {len(evolucao)}"
    chave = lambda p: f"{p['ano']}-{p['mes']:02d}"
    assert chave(evolucao[0]) == inicio
    assert chave(evolucao[-1]) == fim


@then(parsers.parse('apenas o ponto "{mes}" está marcado como parcial'))
def evolucao_parcial(contexto, mes):
    parciais = [
        f"{p['ano']}-{p['mes']:02d}"
        for p in _dados(contexto)["evolucao"] if p["parcial"]
    ]
    assert parciais == [mes], f"parciais={parciais}"


@then(parsers.parse('o ponto da evolução "{mes}" tem receita "{valor}"'))
def evolucao_receita(contexto, mes, valor):
    ponto = _ponto_evolucao(contexto, mes)
    assert ponto["receita"] == valor, f"ponto={ponto}"


@then(parsers.parse('o ponto da evolução "{mes}" tem despesa "{valor}"'))
def evolucao_despesa(contexto, mes, valor):
    ponto = _ponto_evolucao(contexto, mes)
    assert ponto["despesa"] == valor, f"ponto={ponto}"


def _ponto_evolucao(contexto, mes: str) -> dict:
    pontos = [
        p for p in _dados(contexto)["evolucao"]
        if f"{p['ano']}-{p['mes']:02d}" == mes
    ]
    assert pontos, f"ponto {mes} ausente da evolução"
    return pontos[0]


@then(parsers.parse('a linha da conta "{ident}" mostra delta "{valor}"'))
def linha_conta_delta(contexto, ident, valor):
    assert _linha_conta(contexto, ident)["delta"] == valor


@then(parsers.parse('a linha da conta "{ident}" mostra delta nulo'))
def linha_conta_delta_nulo(contexto, ident):
    assert _linha_conta(contexto, ident)["delta"] is None


@then(parsers.parse('a linha da conta "{ident}" mostra percentual "{valor}"'))
def linha_conta_percentual(contexto, ident, valor):
    assert _linha_conta(contexto, ident)["percentual"] == valor


@then(parsers.parse('o top de receitas tem {qtd:d} itens'))
def top_receitas_qtd(contexto, qtd):
    assert len(_dados(contexto)["composicao"]["top_receitas"]) == qtd


@then(parsers.parse('o top de despesas tem {qtd:d} itens'))
def top_despesas_qtd(contexto, qtd):
    assert len(_dados(contexto)["composicao"]["top_despesas"]) == qtd


@then(parsers.parse('o primeiro item do top de receitas vale "{valor}"'))
def top_receitas_primeiro(contexto, valor):
    assert _dados(contexto)["composicao"]["top_receitas"][0]["valor"] == valor


@then(parsers.parse('as outras receitas somam "{valor}"'))
def outras_receitas(contexto, valor):
    assert _dados(contexto)["composicao"]["outras_receitas"] == valor


@then(parsers.parse('as outras despesas somam "{valor}"'))
def outras_despesas(contexto, valor):
    assert _dados(contexto)["composicao"]["outras_despesas"] == valor


@then(parsers.parse('o item do top de receitas do qualificador "{qual}" tem pai "{pai}"'))
def item_com_pai(contexto, qual, pai):
    itens = [
        item for item in _dados(contexto)["composicao"]["top_receitas"]
        if item["num_qualificador"] == qual
    ]
    assert itens, f"qualificador {qual} ausente do top de receitas"
    assert itens[0]["num_qualificador_pai"] == pai


@then(parsers.parse('o semáforo de defasagem de saldo é "{estado}"'))
def semaforo_saldo(contexto, estado):
    assert _dados(contexto)["defasagem"]["saldo"]["estado"] == estado


@then(parsers.parse('o semáforo de defasagem de lançamento é "{estado}"'))
def semaforo_lancamento(contexto, estado):
    assert _dados(contexto)["defasagem"]["lancamento"]["estado"] == estado


@then("o recorte sem conta está sinalizado")
def recorte_sinalizado(contexto):
    assert _dados(contexto)["filtros"]["recorte_sem_conta"] is True


@then("o recorte sem conta não está sinalizado")
def recorte_nao_sinalizado(contexto):
    assert _dados(contexto)["filtros"]["recorte_sem_conta"] is False
