"""Steps BDD — catálogo de fontes de recurso e disponibilidade por grupo
(specs fonte-recurso R1–R6 e saldo-por-fundo R21).

Feature majoritariamente de service (fonte_recurso_service, fundo_service,
saldo_fundo_repository); os cenários de tela/permissão usam TestClient.
Ilha de datas 2034 e códigos fictícios (fundos 9xxx, fontes 5xx/6xx de teste)
para não colidir com o seed demo nem com as demais features.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_permissoes import criar_usuario_com_perfil

scenarios("../fonte-recurso/catalogo.feature")
scenarios("../fonte-recurso/disponibilidade_grupo.feature")
scenarios("../saldo-por-fundo/classificacao_fonte.feature")

USUARIO_SESSAO = 12345


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _partes(codigo: str) -> tuple[str, str]:
    ident, fonte = codigo.split(".", 1)
    return ident, fonte


def _fonte(codigo: str, vigencia: int):
    from fluxocaixa.models import FonteRecurso

    ident, fonte = _partes(codigo)
    return FonteRecurso.query.filter_by(
        cod_identificador_exercicio=ident,
        cod_fonte_stn=fonte,
        num_exercicio_vigencia=vigencia,
        ind_status='A',
    ).first()


def _fundo(cod):
    from fluxocaixa.models import Fundo

    return Fundo.query.filter_by(cod_fundo=cod).first()


def _executar(contexto, fn):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        contexto["resultado"] = fn()
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


def _criar_fonte(codigo: str, vigencia: int, vinculada: str):
    from fluxocaixa.services.fonte_recurso_service import criar_fonte

    ident, fonte = _partes(codigo)
    return criar_fonte(ident, fonte, f"Fonte de teste {codigo}", vigencia,
                       vinculada='L' if vinculada == 'livre' else 'V')


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(USUARIO_SESSAO)


@given(parsers.parse('a fonte "{codigo}" cadastrada na vigência {vigencia:d} como "{vinculada}"'))
def fonte_cadastrada(app, contexto, codigo, vigencia, vinculada):
    _db().session.rollback()
    if _fonte(codigo, vigencia) is None:
        _criar_fonte(codigo, vigencia, vinculada)


@given(parsers.parse('a fonte do seed "{codigo}" do exercício corrente'), target_fixture="fonte_seed")
def fonte_do_seed(app, codigo):
    fonte = _fonte(codigo, date.today().year)
    assert fonte is not None, f"seed não criou a fonte {codigo}"
    return fonte.seq_fonte_recurso


@given(parsers.parse('uma planilha da tabela STN da vigência {vigencia:d} com uma linha sem código de fonte'))
def planilha_invalida(app, contexto, vigencia):
    contexto["vigencia_import"] = vigencia
    contexto["csv"] = (
        b"identificador;fonte;detalhamento;descricao;vinculada;grupo\n"
        b"1;;;Fonte sem codigo;L;\n"
    )


@given(parsers.parse('uma planilha válida da tabela STN da vigência {vigencia:d} com a fonte "{fonte}"'))
def planilha_valida(app, contexto, vigencia, fonte):
    contexto["vigencia_import"] = vigencia
    contexto["csv"] = (
        "identificador;fonte;detalhamento;descricao;vinculada;grupo\n"
        f"1;{fonte};;Fonte importada {fonte};V;Teste\n"
    ).encode()


@given(parsers.parse('uma conta de disponibilidade "{ident}"'), target_fixture="conta")
def conta_disponibilidade(app, ident):
    from fluxocaixa.models import ContaBancaria

    db = _db()
    db.session.rollback()
    banco, agencia, num = ident.split("/")
    existente = ContaBancaria.query.filter_by(
        cod_banco=banco, num_agencia=agencia, num_conta=num).first()
    if existente:
        return existente
    conta = ContaBancaria(cod_banco=banco, num_agencia=agencia, num_conta=num,
                          dsc_conta=f"Conta {ident}")
    db.session.add(conta)
    db.session.commit()
    return conta


@given(parsers.parse('um fundo "{cod}" sem fonte de recursos'))
def fundo_sem_fonte(app, cod):
    from fluxocaixa.services.fundo_service import classificar_fundo, criar_fundo

    _db().session.rollback()
    if _fundo(cod) is None:
        criar_fundo(cod, f"Fundo de teste {cod}")
    elif _fundo(cod).seq_fonte_recurso is not None:
        classificar_fundo(_fundo(cod).seq_fundo, None)


@given(parsers.parse('um fundo "{cod}" classificado na fonte "{codigo}" da vigência {vigencia:d}'))
def fundo_classificado(app, cod, codigo, vigencia):
    from fluxocaixa.services.fundo_service import classificar_fundo, criar_fundo

    _db().session.rollback()
    if _fundo(cod) is None:
        criar_fundo(cod, f"Fundo de teste {cod}")
    fonte = _fonte(codigo, vigencia)
    assert fonte is not None
    classificar_fundo(_fundo(cod).seq_fundo, fonte.seq_fonte_recurso)


@given(parsers.parse('um saldo de {valor} do fundo "{cod}" nessa conta em "{dat}"'))
def saldo_do_fundo(app, conta, valor, cod, dat):
    from fluxocaixa.services.saldo_fundo_service import gravar_saldo

    gravar_saldo(
        seq_conta=conta.seq_conta,
        seq_fundo=_fundo(cod).seq_fundo,
        dat_saldo=date.fromisoformat(dat),
        val_saldo=Decimal(valor),
    )


@given(parsers.parse('a fonte "{codigo}" da vigência {vigencia:d} foi inativada'))
def fonte_inativada(app, codigo, vigencia):
    from fluxocaixa.services.fonte_recurso_service import inativar_fonte

    fonte = _fonte(codigo, vigencia)
    if fonte is not None:
        # guarda o seq antes de inativar (a busca só encontra ativas)
        inativar_fonte(fonte.seq_fonte_recurso)


@given(parsers.parse('um usuário de fontes autenticado com o perfil "{perfil}"'), target_fixture="navegador")
def usuario_com_perfil(app, perfil):
    login, senha, seq = criar_usuario_com_perfil(perfil)
    tc = TestClient(app, follow_redirects=False, headers={"Accept": "text/html"})
    resp = tc.post("/login", data={"usuario": login, "senha": senha})
    assert resp.status_code in (302, 303)
    return tc


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

@when(parsers.parse('cadastro a fonte "{codigo}" na vigência {vigencia:d} como "{vinculada}"'))
def cadastra_fonte(app, contexto, codigo, vigencia, vinculada):
    _executar(contexto, lambda: _criar_fonte(codigo, vigencia, vinculada))


@when(parsers.parse('altero a vinculação dessa fonte para "{vinculada}"'))
def altera_vinculacao(app, contexto, fonte_seed, vinculada):
    from fluxocaixa.services.fonte_recurso_service import alterar_fonte

    _executar(contexto, lambda: alterar_fonte(
        fonte_seed, vinculada='L' if vinculada == 'livre' else 'V'))


@when("o seed de domínio roda novamente")
def seed_roda(app):
    from fluxocaixa.services.seed_dominio import seed_dominio

    seed_dominio()


@when("envio a planilha para preview")
def envia_preview(app, contexto):
    from fluxocaixa.services.preprocessamento_adapters import _AdapterFontesRecurso

    # contexto viaja como parâmetro (importacao-arquivos R7) — nada de
    # atributo de classe compartilhado
    adapter = _AdapterFontesRecurso()
    contexto["adapter"] = adapter
    contexto["ctx_import"] = {"exercicio": contexto["vigencia_import"]}
    contexto["preview"] = adapter.parse_validar(
        contexto["csv"], "tabela_stn.csv", contexto["ctx_import"])


@when("confirmo a importação da planilha")
def confirma_importacao(app, contexto):
    preview = contexto["preview"]
    contexto["resultado_import"] = contexto["adapter"].gravar(
        preview.graváveis, contexto["ctx_import"])


@when(parsers.parse('uma carga referencia a fonte desconhecida "{codigo}" na vigência {vigencia:d}'))
def carga_fonte_desconhecida(app, contexto, codigo, vigencia):
    from fluxocaixa.services.fonte_recurso_service import obter_ou_criar_pendente

    _executar(contexto, lambda: obter_ou_criar_pendente(codigo, vigencia))


@when(parsers.parse('reclassifico o fundo "{cod}" para a fonte "{codigo}" da vigência {vigencia:d}'))
def reclassifica_fundo(app, contexto, cod, codigo, vigencia):
    from fluxocaixa.services.fundo_service import classificar_fundo

    fonte = _fonte(codigo, vigencia)
    seq_fonte = fonte.seq_fonte_recurso if fonte is not None else -1
    _executar(contexto, lambda: classificar_fundo(_fundo(cod).seq_fundo, seq_fonte))


@when(parsers.parse('removo a classificação do fundo "{cod}"'))
def remove_classificacao(app, contexto, cod):
    from fluxocaixa.services.fundo_service import classificar_fundo

    _executar(contexto, lambda: classificar_fundo(_fundo(cod).seq_fundo, None))


@when(parsers.parse('inativo a fonte "{codigo}" da vigência {vigencia:d}'))
def inativa_fonte(app, contexto, codigo, vigencia):
    from fluxocaixa.services.fonte_recurso_service import inativar_fonte

    fonte = _fonte(codigo, vigencia)
    _executar(contexto, lambda: inativar_fonte(fonte.seq_fonte_recurso))


@when("esse usuário acessa a tela do catálogo de fontes")
def usuario_acessa_tela(navegador, contexto):
    contexto["resp"] = navegador.get("/fontes-recurso")


@when("acesso a tela do catálogo de fontes como administrador")
def admin_acessa_tela(client, contexto):
    contexto["resp"] = client.get("/fontes-recurso")


@when("acesso a tela de fundos como administrador")
def admin_acessa_fundos(client, contexto):
    contexto["resp"] = client.get("/fundos")


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then(parsers.parse('existem {qtd:d} fontes ativas com o código "{codigo}"'))
def qtd_fontes(qtd, codigo):
    from fluxocaixa.models import FonteRecurso

    _db().session.expire_all()
    ident, fonte = _partes(codigo)
    total = FonteRecurso.query.filter_by(
        cod_identificador_exercicio=ident, cod_fonte_stn=fonte, ind_status='A').count()
    assert total == qtd, f"esperava {qtd}, veio {total}"


@then(parsers.parse('a operação de fonte é rejeitada com a mensagem "{mensagem}"'))
def fonte_rejeitada(contexto, mensagem):
    assert contexto["erro"] == mensagem, f"esperava {mensagem!r}, veio {contexto['erro']!r}"


@then(parsers.parse('o código exibido da fonte "{codigo}" na vigência {vigencia:d} é "{esperado}"'))
def codigo_exibido(codigo, vigencia, esperado):
    _db().session.expire_all()
    assert _fonte(codigo, vigencia).codigo_completo == esperado


@then(parsers.parse('a fonte "{codigo}" da vigência {vigencia:d} pertence ao grupo "{grupo}"'))
def fonte_pertence_grupo(codigo, vigencia, grupo):
    _db().session.expire_all()
    assert _fonte(codigo, vigencia).grupo == grupo


@then(parsers.parse('a vinculação dessa fonte permanece "{vinculada}"'))
def vinculacao_permanece(fonte_seed, vinculada):
    from fluxocaixa.models import FonteRecurso

    _db().session.expire_all()
    fonte = FonteRecurso.query.get(fonte_seed)
    esperado = 'L' if vinculada == 'livre' else 'V'
    assert fonte.ind_vinculada == esperado


@then("a linha inválida é apontada como erro")
def linha_erro(contexto):
    assert contexto["preview"].total_erro >= 1


@then(parsers.parse('nenhuma fonte da vigência {vigencia:d} foi gravada'))
def nada_gravado(vigencia):
    from fluxocaixa.models import FonteRecurso

    _db().session.expire_all()
    assert FonteRecurso.query.filter_by(num_exercicio_vigencia=vigencia).count() == 0


@then(parsers.parse('a fonte "{codigo}" existe ativa na vigência {vigencia:d}'))
def fonte_existe_na_vigencia(codigo, vigencia):
    _db().session.expire_all()
    assert _fonte(codigo, vigencia) is not None


@then(parsers.parse('a fonte "{codigo}" da vigência {vigencia:d} permanece intacta'))
def fonte_intacta(codigo, vigencia):
    _db().session.expire_all()
    fonte = _fonte(codigo, vigencia)
    assert fonte is not None and fonte.dat_alteracao is None


@then("a linha aparece como aviso de já existente")
def linha_aviso(contexto):
    assert contexto["preview"].total_aviso >= 1


@then(parsers.parse('a fonte "{codigo}" da vigência {vigencia:d} existe vinculada e pendente de revisão'))
def fonte_pendente_vinculada(codigo, vigencia):
    _db().session.expire_all()
    fonte = _fonte(codigo, vigencia)
    assert fonte is not None
    assert fonte.ind_vinculada == 'V' and fonte.ind_pendente_revisao == 'S'


@then(parsers.parse('o grupo "{grupo}" em "{dat}" soma {valor}'))
def grupo_soma(grupo, dat, valor):
    from fluxocaixa.repositories.saldo_fundo_repository import saldo_bruto_por_grupo

    _db().session.expire_all()
    grupos = saldo_bruto_por_grupo(date.fromisoformat(dat))
    assert grupos[grupo]["total"] == Decimal(valor).quantize(Decimal("0.01")), \
        f"grupo {grupo}: esperava {valor}, veio {grupos[grupo]['total']}"


@then(parsers.parse('a soma dos grupos em "{dat}" é igual ao agregado da conta em "{dat2}"'))
def soma_fecha_com_agregado(conta, dat, dat2):
    from fluxocaixa.repositories.saldo_fundo_repository import (
        agregado_por_conta,
        saldo_bruto_por_grupo,
    )

    _db().session.expire_all()
    ref = date.fromisoformat(dat)
    grupos = saldo_bruto_por_grupo(ref)
    agregado = agregado_por_conta(ref, ref, seq_conta=conta.seq_conta)
    total_agregado = sum((l["val_saldo"] for l in agregado), Decimal("0.00"))
    assert grupos["total"]["total"] == total_agregado, \
        f"grupos {grupos['total']['total']} != agregado {total_agregado}"


@then(parsers.parse('a fonte "{codigo}" da vigência {vigencia:d} permanece ativa'))
def fonte_permanece_ativa(codigo, vigencia):
    _db().session.expire_all()
    assert _fonte(codigo, vigencia) is not None


@then("o acesso à tela de fontes é negado")
def acesso_negado(contexto):
    assert contexto["resp"].status_code == 403


@then("a tela exibe a decomposição da disponibilidade operacional")
def tela_decomposicao(contexto):
    corpo = contexto["resp"].text
    assert contexto["resp"].status_code == 200
    assert 'data-testid="disponibilidade-operacional"' in corpo
    assert "não é a disponibilidade fiscal do RGF" in corpo


@then(parsers.parse('o fundo "{cod}" aparece destacado como pendente de classificação'))
def fundo_destacado_pendente(contexto, cod):
    corpo = contexto["resp"].text
    assert contexto["resp"].status_code == 200
    assert (f'aviso-sem-fonte-{cod}' in corpo) or (f'badge-sem-fonte-{cod}' in corpo)
