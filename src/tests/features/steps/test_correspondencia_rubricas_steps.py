"""Steps BDD — correspondência de rubricas entre exercícios (previsao R30–R33).

Ilhas 2082–2084, ramos "1.82"/"2.82", ato fictício "BDD82" (a limpeza apaga
por ele). Import tardio de `fluxocaixa`.
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../previsao/correspondencia_rubricas.feature")

ANOS = (2082, 2083, 2084)
ATO = "Portaria fictícia BDD82"
FONTE = "Fonte BDD82"


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


# --------------------------------------------------------------- limpeza

def _limpar():
    from sqlalchemy import or_

    from fluxocaixa.models import (
        CorrespondenciaDestino,
        CorrespondenciaEvento,
        CorrespondenciaOrigem,
        CorrespondenciaRateio,
        CorrespondenciaRubrica,
        EtlStaging,
        FonteExtracao,
        Lancamento,
        ProjecaoValor,
        ProjecaoVersao,
        Qualificador,
        SimuladorCenario,
    )

    db = _db()
    db.session.rollback()
    for c in SimuladorCenario.query.filter(SimuladorCenario.nom_cenario.like("CEN_CR%")).all():
        for v in ProjecaoVersao.query.filter_by(seq_simulador_cenario=c.seq_simulador_cenario).all():
            db.session.delete(v)
        db.session.flush()
        db.session.delete(c)
        db.session.flush()
    for corr in CorrespondenciaRubrica.query.filter_by(dsc_referencia_ato=ATO).all():
        seq = corr.seq_correspondencia_rubrica
        ProjecaoValor.query.filter_by(seq_correspondencia_rubrica=seq).delete()
        eventos = [e.seq_correspondencia_evento for e in CorrespondenciaEvento.query.filter_by(
            seq_correspondencia_rubrica=seq).all()]
        if eventos:
            CorrespondenciaRateio.query.filter(
                CorrespondenciaRateio.seq_correspondencia_evento.in_(eventos)).delete(
                    synchronize_session=False)
        CorrespondenciaEvento.query.filter_by(seq_correspondencia_rubrica=seq).delete()
        CorrespondenciaOrigem.query.filter_by(seq_correspondencia_rubrica=seq).delete()
        CorrespondenciaDestino.query.filter_by(seq_correspondencia_rubrica=seq).delete()
        db.session.delete(corr)
    db.session.flush()
    quals = Qualificador.query.filter(
        Qualificador.num_ano_exercicio.in_(ANOS),
        or_(Qualificador.num_qualificador.like("1.82%"),
            Qualificador.num_qualificador.like("2.82%"))).all()
    seqs = [q.seq_qualificador for q in quals]
    if seqs:
        Lancamento.query.filter(Lancamento.seq_qualificador.in_(seqs)).delete(
            synchronize_session=False)
        db.session.flush()
        for q in sorted(quals, key=lambda q: -len(q.num_qualificador)):
            db.session.delete(q)
            db.session.flush()
    fonte = FonteExtracao.query.filter_by(nom_fonte=FONTE).first()
    if fonte is not None:
        EtlStaging.query.filter_by(seq_fonte_extracao=fonte.seq_fonte_extracao).delete()
    db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


# ----------------------------------------------------------------- massa

def _q(codigo, ano=None):
    from fluxocaixa.models import Qualificador

    consulta = Qualificador.query.filter(
        Qualificador.num_qualificador == codigo,
        Qualificador.num_ano_exercicio.in_([ano] if ano else ANOS))
    return consulta.order_by(Qualificador.num_ano_exercicio.desc()).first()


def _q_antes(codigo, ano):
    """Linha mais recente da rubrica ANTES do exercício `ano` (a origem)."""
    from fluxocaixa.models import Qualificador

    return (Qualificador.query
            .filter(Qualificador.num_qualificador == codigo,
                    Qualificador.num_ano_exercicio.in_([a for a in ANOS if a < ano]))
            .order_by(Qualificador.num_ano_exercicio.desc()).first())


def _rubrica(codigo, ano, raiz=None, pai=None):
    from fluxocaixa.models import Qualificador

    existente = _q(codigo, ano)
    if existente is not None:
        if pai is not None and existente.cod_qualificador_pai != pai.seq_qualificador:
            existente.cod_qualificador_pai = pai.seq_qualificador
            _db().session.commit()
        return existente
    q = Qualificador(num_qualificador=codigo, dsc_qualificador=f"BDD82 {codigo}",
                     num_ano_exercicio=ano, ind_status='A', cod_rubrica_raiz=raiz,
                     cod_qualificador_pai=pai.seq_qualificador if pai else None)
    _db().session.add(q)
    _db().session.commit()
    return q


def _lancar(q, dia, valor, origem="Manual", seq_staging=None):
    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.lancamento import TIPO_CREDITO, TIPO_DEBITO
    from fluxocaixa.services.dominio_lancamento import resolver_origem

    _db().session.add(Lancamento(
        dat_lancamento=dia, seq_qualificador=q.seq_qualificador,
        val_lancamento=Decimal(str(valor)),
        cod_tipo_lancamento=TIPO_CREDITO if q.num_qualificador.startswith("1") else TIPO_DEBITO,
        cod_origem_lancamento=resolver_origem(origem).cod_origem_lancamento,
        seq_etl_staging=seq_staging, cod_pessoa_inclusao=1, ind_status='A'))


@given(parsers.re(r'as rubricas "(?P<a>[\d.]+)" e "(?P<b>[\d.]+)" no plano de '
                  r'(?P<ano_a>\d+) e "(?P<c>[\d.]+)" no plano de (?P<ano_c>\d+)$'),
       converters={"ano_a": int, "ano_c": int})
def rubricas_dois_planos(contexto, a, b, ano_a, c, ano_c):
    from fluxocaixa.services.correspondencia_rubrica_service import versao_atual

    _rubrica(a, ano_a)
    _rubrica(b, ano_a)
    _rubrica(c, ano_c)
    contexto["versao_inicial"] = versao_atual()


@given(parsers.re(r'as rubricas "(?P<a>[\d.]+)" e "(?P<b>[\d.]+)" no plano de (?P<ano>\d+)$'),
       converters={"ano": int})
def rubricas_um_plano(a, b, ano):
    _rubrica(a, ano)
    _rubrica(b, ano)


@given(parsers.parse('a rubrica "{codigo}" também no plano de {ano:d} com a mesma identidade'))
def rubrica_continua(codigo, ano):
    origem = _q(codigo)
    _rubrica(codigo, ano, raiz=origem.cod_rubrica_raiz)


@given(parsers.parse('a rubrica "{codigo}" no plano de {ano:d} herdando a identidade de '
                     '"{origem}"'))
def rubrica_herdeira(codigo, ano, origem):
    _rubrica(codigo, ano, raiz=_q(origem).cod_rubrica_raiz)


@given(parsers.parse('a rubrica "{codigo}" no plano de {ano:d}'))
def rubrica_simples(codigo, ano):
    _rubrica(codigo, ano)


@given(parsers.re(r'"(?P<codigo>[\d.]+)" de (?P<ano>\d+) com (?P<valor>[\d.]+) por mês em '
                  r'(?P<ano_lanc>\d+)$'), converters={"ano": int, "ano_lanc": int})
def realizado_mensal(codigo, ano, valor, ano_lanc):
    q = _rubrica(codigo, ano)
    for mes in range(1, 13):
        _lancar(q, date(ano_lanc, mes, 15), valor)
    _db().session.commit()


@given(parsers.re(r'"(?P<codigo>[\d.]+)" com (?P<valor>[\d.]+) por mês em (?P<ano_lanc>\d+)$'),
       converters={"ano_lanc": int})
def realizado_mensal_existente(codigo, valor, ano_lanc):
    q = _q(codigo)
    for mes in range(1, 13):
        _lancar(q, date(ano_lanc, mes, 15), valor)
    _db().session.commit()


@given(parsers.parse('"{codigo}" de {ano:d} com lançamentos automáticos de {v1} com natureza '
                     '"{n1}" e {v2} com natureza "{n2}" por mês em {ano_lanc:d}'))
def realizado_automatico(app, codigo, ano, v1, n1, v2, n2, ano_lanc):
    from fluxocaixa.models import EtlStaging, ExecucaoExtracao

    from ..conftest_extracao import criar_fonte_fake, fonte_por_nome, garantir_conector_fake
    from .conftest_regra import garantir_termos_padrao, sistema_por_sigla

    garantir_termos_padrao()
    sistema_por_sigla("SIS82")
    garantir_conector_fake()
    fonte = fonte_por_nome(FONTE) or criar_fonte_fake(FONTE, sigla_sistema="SIS82")
    db = _db()
    execucao = ExecucaoExtracao(
        seq_fonte_extracao=fonte.seq_fonte_extracao, dat_inicio_execucao=date(ano_lanc, 12, 31),
        cod_disparo="MANUAL", cod_status="SUCESSO",
        dat_janela_inicio=date(ano_lanc, 1, 1), dat_janela_fim=date(ano_lanc, 12, 31))
    db.session.add(execucao)
    db.session.flush()
    q = _rubrica(codigo, ano)
    for mes in range(1, 13):
        for valor, natureza in ((v1, n1), (v2, n2)):
            linha = EtlStaging(
                seq_fonte_extracao=fonte.seq_fonte_extracao,
                seq_execucao_extracao=execucao.seq_execucao_extracao,
                num_ano_exercicio=ano_lanc, dat_referencia=date(ano_lanc, mes, 10),
                val_referencia=Decimal(valor), json_atributos={"natureza": natureza},
                ind_status_processamento='1')
            db.session.add(linha)
            db.session.flush()
            _lancar(q, date(ano_lanc, mes, 10), valor, origem="Automático",
                    seq_staging=linha.seq_etl_staging)
    db.session.commit()


@given(parsers.parse('um lançamento manual de {valor} em "{codigo}" de {ano:d} em março de '
                     '{ano_lanc:d}'))
def lancamento_manual(codigo, ano, valor, ano_lanc):
    _lancar(_q(codigo, ano), date(ano_lanc, 3, 20), valor)
    _db().session.commit()


def _desdobrar(contexto, origem, ano_origem, d1, d2, vigencia, regras=None):
    from fluxocaixa.services.correspondencia_rubrica_service import criar_correspondencia

    o = _rubrica(origem, ano_origem)
    pai = _q(origem.rsplit(".", 1)[0], vigencia)
    q1 = _rubrica(d1, vigencia, pai=pai)
    q2 = _rubrica(d2, vigencia, pai=pai)
    corr = criar_correspondencia(
        'D', vigencia, [o.seq_qualificador], [q1.seq_qualificador, q2.seq_qualificador],
        ATO, "Desdobramento da rubrica no exercício (BDD)",
        regras={q1.seq_qualificador: regras[0], q2.seq_qualificador: regras[1]} if regras else None,
        user_id=1)
    contexto["corr"] = corr.seq_correspondencia_rubrica
    contexto["destinos"] = (d1, d2)
    return corr


@given(parsers.parse('o desdobramento de "{origem}" de {ano_origem:d} em "{d1}" e "{d2}" '
                     'vigente em {vigencia:d}'))
def desdobramento(contexto, origem, ano_origem, d1, d2, vigencia):
    _desdobrar(contexto, origem, ano_origem, d1, d2, vigencia)


@given(parsers.parse('o desdobramento de "{origem}" de {ano_origem:d} em "{d1}" e "{d2}" '
                     'vigente em {vigencia:d} com as regras "{r1}" e "{r2}"'))
def desdobramento_com_regras(contexto, origem, ano_origem, d1, d2, vigencia, r1, r2):
    _desdobrar(contexto, origem, ano_origem, d1, d2, vigencia, regras=(r1, r2))


def _fundir(contexto, a, b, destino, vigencia):
    from fluxocaixa.services.correspondencia_rubrica_service import criar_correspondencia

    qa, qb = _q_antes(a, vigencia), _q_antes(b, vigencia)
    corr = criar_correspondencia(
        'F', vigencia, [qa.seq_qualificador, qb.seq_qualificador], [_q(destino, vigencia).seq_qualificador],
        ATO, "Fusão das rubricas no exercício (BDD)", user_id=1)
    contexto["corr"] = corr.seq_correspondencia_rubrica
    return corr


@given(parsers.parse('a fusão de "{a}" e "{b}" em "{destino}" vigente em {vigencia:d}'))
def fusao(contexto, a, b, destino, vigencia):
    _fundir(contexto, a, b, destino, vigencia)


def _rateio(contexto, p1, p2):
    from fluxocaixa.services.correspondencia_rubrica_service import definir_rateio

    d1, d2 = contexto["destinos"]
    definir_rateio(contexto["corr"], {_q(d1).seq_qualificador: p1, _q(d2).seq_qualificador: p2},
                   "Proporção estimada pela tesouraria (BDD)", user_id=1)


@given(parsers.parse('o rateio "{p1}" e "{p2}" registrado'))
def rateio_registrado(contexto, p1, p2):
    from fluxocaixa.services.correspondencia_rubrica_service import versao_atual

    _rateio(contexto, p1, p2)
    contexto["versao_registrada"] = versao_atual()


@given(parsers.parse('o bloco "{bloco}" de {ano:d} com as folhas "{f1}" e "{f2}"'))
def bloco_com_folhas(bloco, ano, f1, f2):
    pai = _rubrica(bloco, ano)
    _rubrica(f1, ano, pai=pai)
    _rubrica(f2, ano, pai=pai)


def _cenario(contexto, ano, codigo):
    from fluxocaixa.services.metodo_qualificador_service import definir_marcacao
    from fluxocaixa.services.simulador_cenario_service import criar_simulador_cenario

    cenario = criar_simulador_cenario(
        nom_cenario="CEN_CR BDD82", dsc_cenario="bdd", ano_base=ano, num_periodos=12,
        tipo_cenario_receita='', config_receita={}, tipo_cenario_despesa='',
        config_despesa={}, user_id=1)
    definir_marcacao(cenario.seq_simulador_cenario, _q(codigo, ano).seq_qualificador,
                     'MODELO', {'modelo': 'MEDIA_HISTORICA'}, user_id=1)
    contexto["cenario"] = cenario.seq_simulador_cenario


@given(parsers.parse('um cenário de {ano:d} com o bloco "{codigo}" marcado com média histórica'))
def cenario_bloco(contexto, ano, codigo):
    _cenario(contexto, ano, codigo)


@given(parsers.parse('um cenário de {ano:d} com a folha "{codigo}" marcada com média histórica'))
def cenario_folha(contexto, ano, codigo):
    _cenario(contexto, ano, codigo)


# ----------------------------------------------------------------- ações

def _capturar(contexto, funcao, *args, **kwargs):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        contexto["retorno"] = funcao(*args, **kwargs)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        _db().session.rollback()
        contexto["erro"] = exc


@when(parsers.parse('cadastro a fusão de "{a}" e "{b}" em "{destino}" vigente em {vigencia:d}'))
def cadastra_fusao(contexto, a, b, destino, vigencia):
    _capturar(contexto, _fundir, contexto, a, b, destino, vigencia)


@when(parsers.parse('defino o rateio "{p1}" e "{p2}"'))
def define_rateio(contexto, p1, p2):
    _capturar(contexto, _rateio, contexto, p1, p2)


def _serie(contexto, codigos, ano):
    from fluxocaixa.services.serie_historica import serie_mensal

    contexto["serie"] = serie_mensal([_q(c).seq_qualificador for c in codigos],
                                     date(ano, 1, 1), date(ano, 12, 31))
    contexto["ano_serie"] = ano


@when(parsers.parse('obtenho a série de {ano:d} de "{codigo}"'))
def obtem_serie(contexto, ano, codigo):
    _serie(contexto, [codigo], ano)


@when(parsers.parse('obtenho a série conjunta de {ano:d} de "{a}" e "{b}"'))
def obtem_serie_conjunta(contexto, ano, a, b):
    _serie(contexto, [a, b], ano)


@when("executo a simulação do cenário")
def executa(contexto):
    from fluxocaixa.services.simulador_cenario_service import executar_simulacao

    contexto["resultado"] = executar_simulacao(contexto["cenario"])


@when("publico uma versão do cenário sem confirmar")
def publica_sem_confirmar(contexto):
    from fluxocaixa.services.projecao_versao_service import salvar_projecao_como_versao

    _capturar(contexto, salvar_projecao_como_versao, contexto["cenario"], "v BDD82",
              user_id=1, publicar=True, confirmado=False)


@when("salvo uma versão do cenário")
def salva_versao(contexto):
    from fluxocaixa.services.correspondencia_rubrica_service import versao_atual
    from fluxocaixa.services.projecao_versao_service import salvar_projecao_como_versao

    versao = salvar_projecao_como_versao(contexto["cenario"], "v BDD82", user_id=1,
                                         publicar=False)
    contexto["versao_salva"] = versao.seq_projecao_versao
    contexto["versao_de_para"] = versao_atual()


@when("peço a sugestão de rateio")
def pede_sugestao(contexto):
    from fluxocaixa.services.correspondencia_rubrica_service import sugestao_rateio

    contexto["sugestao"] = sugestao_rateio(contexto["corr"])


# ---------------------------------------------------------- verificações

def _estado(contexto, versao=None):
    from fluxocaixa.services.correspondencia_rubrica_service import correspondencias

    return next((e for e in correspondencias(versao=versao)
                 if e.seq == contexto["corr"]), None)


@then(parsers.parse('recebo erro de negócio citando "{trecho}"'))
def erro_cita(contexto, trecho):
    assert contexto.get("erro") is not None, "esperava erro de negócio"
    assert trecho in contexto["erro"].mensagem, contexto["erro"].mensagem


@then("a correspondência fica ativa")
def correspondencia_ativa(contexto):
    assert contexto.get("erro") is None, contexto.get("erro")
    assert _estado(contexto) is not None


@then("a versão do De/Para avança")
def versao_avanca(contexto):
    from fluxocaixa.services.correspondencia_rubrica_service import versao_atual

    assert versao_atual() > contexto["versao_inicial"]


def _rateio_por_codigo(contexto, estado):
    d1, d2 = contexto["destinos"]
    rateio = estado.rateio or {}
    return (rateio.get(_q(d1).cod_rubrica_raiz), rateio.get(_q(d2).cod_rubrica_raiz))


@then(parsers.parse('o De/Para na versão registrada mostra o rateio "{p1}" e "{p2}"'))
def rateio_na_versao(contexto, p1, p2):
    estado = _estado(contexto, contexto["versao_registrada"])
    assert _rateio_por_codigo(contexto, estado) == (Decimal(p1), Decimal(p2))


@then(parsers.parse('o De/Para atual mostra o rateio "{p1}" e "{p2}"'))
def rateio_atual(contexto, p1, p2):
    assert _rateio_por_codigo(contexto, _estado(contexto)) == (Decimal(p1), Decimal(p2))


@then("o desdobramento continua sem rateio")
def sem_rateio(contexto):
    assert _estado(contexto).rateio is None


def _valores(contexto):
    ano = contexto["ano_serie"]
    return {m: round(contexto["serie"].valores.get((ano, m), 0.0), 2) for m in range(1, 13)}


@then(parsers.parse("cada mês da série vale {valor}"))
def cada_mes(contexto, valor):
    assert set(_valores(contexto).values()) == {float(valor)}, _valores(contexto)


@then(parsers.parse("o mês {mes:d} da série vale {valor}"))
def um_mes(contexto, mes, valor):
    assert _valores(contexto)[mes] == float(valor), _valores(contexto)


@then("nenhum mês da série é estimado")
def nenhum_estimado(contexto):
    assert not contexto["serie"].estimados


@then("todos os meses da série são estimados")
def todos_estimados(contexto):
    ano = contexto["ano_serie"]
    assert {(ano, m) for m in range(1, 13)} <= contexto["serie"].estimados


@then("a série é vazia")
def serie_vazia(contexto):
    assert not any(_valores(contexto).values()), _valores(contexto)


@then("a pendência da série é declarada")
def pendencia_declarada(contexto):
    assert contexto["serie"].pendencias


def _linhas_receita(contexto):
    return contexto["resultado"]["projecao_receita_detalhada"]


@then(parsers.parse("a receita tem uma linha de grupo de {valor} por mês sem rubrica"))
def linha_de_grupo(contexto, valor):
    import pandas as pd

    df = _linhas_receita(contexto)
    grupo = df[df["seq_correspondencia_rubrica"] == contexto["corr"]]
    assert len(grupo) == 12, df
    assert grupo["seq_qualificador"].map(lambda v: v is None or pd.isna(v)).all()
    assert {round(float(v), 2) for v in grupo["valor_projetado"]} == {float(valor)}


def _status(contexto, codigo):
    status = contexto["resultado"]["execucao_marcacoes"]["status"]
    return status[_q(codigo).seq_qualificador]


@then(parsers.parse('"{a}" e "{b}" ficam com distribuição pendente'))
def distribuicao_pendente(contexto, a, b):
    for codigo in (a, b):
        assert _status(contexto, codigo)["status"] == "DISTRIBUICAO_PENDENTE"


@then(parsers.parse('"{codigo}" fica em lacuna citando "{outro}"'))
def lacuna_citando(contexto, codigo, outro):
    info = _status(contexto, codigo)
    assert info["status"] == "LACUNA" and outro in info["nota"], info


@then(parsers.parse('a sugestão é "{p1}" para "{d1}" e "{p2}" para "{d2}"'))
def sugestao(contexto, p1, d1, p2, d2):
    sug = contexto["sugestao"]
    assert sug[_q(d1).cod_rubrica_raiz] == Decimal(p1)
    assert sug[_q(d2).cod_rubrica_raiz] == Decimal(p2)


def _resumo(contexto):
    import json

    from fluxocaixa.models import ProjecaoVersao

    _db().session.expire_all()
    versao = ProjecaoVersao.query.get(contexto["versao_salva"])
    return json.loads(versao.json_resumo)


@then("o resumo da versão salva registra a versão atual do De/Para")
def resumo_registra(contexto):
    assert _resumo(contexto)["versao_de_para"] == contexto["versao_de_para"]


@then("o resumo da versão salva continua com a versão anterior do De/Para")
def resumo_continua(contexto):
    from fluxocaixa.services.correspondencia_rubrica_service import versao_atual

    assert _resumo(contexto)["versao_de_para"] == contexto["versao_de_para"]
    assert versao_atual() > contexto["versao_de_para"]
