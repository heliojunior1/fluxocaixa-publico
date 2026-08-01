"""Steps BDD — pré-processamento de importações (spec importacao-arquivos R1–R5)."""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../importacao-arquivos/preprocessamento.feature")

D2 = lambda v: Decimal(str(v)).quantize(Decimal("0.01"))  # noqa: E731


@pytest.fixture()
def contexto():
    return {"sessao": {}}


def _db():
    from fluxocaixa.models.base import db

    return db


def _conta(ident):
    from fluxocaixa.models import ContaBancaria

    banco, ag, num = ident.split("/")
    c = ContaBancaria.query.filter_by(cod_banco=banco, num_agencia=ag, num_conta=num).first()
    if c is None:
        c = ContaBancaria(cod_banco=banco, num_agencia=ag, num_conta=num, dsc_conta=f"PP {ident}")
        _db().session.add(c); _db().session.commit()
    return c


def _fundo(cod):
    from fluxocaixa.models import Fundo

    return Fundo.query.filter_by(cod_fundo=cod).first()


def _saldos(ident, cod, dat=None):
    from fluxocaixa.models import SaldoContaFundo

    _db().session.expire_all()
    q = SaldoContaFundo.query.filter_by(
        seq_conta=_conta(ident).seq_conta, seq_fundo=_fundo(cod).seq_fundo, ind_status='A')
    if dat:
        q = q.filter_by(dat_saldo=date.fromisoformat(dat))
    return q.all()


@given("que estou autenticado como administrador")
def admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(4242)


@given(parsers.parse('uma conta de importação "{ident}"'))
def conta_import(app, ident):
    _db().session.rollback()
    _conta(ident)


@given(parsers.parse('um fundo de importação "{cod}"'))
def fundo_import(app, cod):
    from fluxocaixa.services.fundo_service import criar_fundo

    if _fundo(cod) is None:
        criar_fundo(cod, f"Fundo PP {cod}")


@given(parsers.parse('um saldo ativo de "{valor}" na conta "{ident}" fundo "{cod}" em "{dat}"'))
def saldo_ativo(app, valor, ident, cod, dat):
    from fluxocaixa.services.fundo_service import garantir_fundo_geral
    from fluxocaixa.services.saldo_fundo_service import gravar_saldo

    garantir_fundo_geral()
    gravar_saldo(seq_conta=_conta(ident).seq_conta, seq_fundo=_fundo(cod).seq_fundo,
                 dat_saldo=date.fromisoformat(dat), val_saldo=Decimal(valor))


def _conteudo(datatable) -> bytes:
    # datatable: [[cabeçalho], [linha], ...] — reconstrói o CSV
    return "\n".join(linha[0] for linha in datatable).encode("utf-8")


@when("gero um preview de saldos com o conteúdo:")
def gera_preview_tabela(app, contexto, datatable):
    from fluxocaixa.services.preprocessamento import criar_preview
    from fluxocaixa.services.validacao import RegraNegocioError

    conteudo = _conteudo(datatable)
    try:
        token, preview = criar_preview("saldos", conteudo, "saldos.csv", contexto["sessao"])
        contexto["token"] = token
        contexto["preview"] = preview
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@when("confirmo o preview")
def confirma(app, contexto):
    from fluxocaixa.services.preprocessamento import confirmar

    contexto["resultado"] = confirmar(contexto["token"], contexto["sessao"])


@when("cancelo o preview")
def cancela(app, contexto):
    from fluxocaixa.services.preprocessamento import descartar

    descartar(contexto["token"], contexto["sessao"])


@then(parsers.parse("o preview tem {ok:d} linha ok e {erro:d} com erro"))
def preview_contadores(contexto, ok, erro):
    p = contexto["preview"]
    n_ok = sum(1 for l in p.linhas if l.status == 'ok')
    n_erro = sum(1 for l in p.linhas if l.status == 'erro')
    assert (n_ok, n_erro) == (ok, erro), f"ok={n_ok} erro={n_erro}: {[(l.status, l.mensagem) for l in p.linhas]}"


@then("nenhum saldo por fundo foi gravado")
def nada_gravado(contexto):
    # sem confirmação, nenhuma das DATAS deste preview foi gravada (escopo do
    # cenário — a conta PP-1 é compartilhada entre cenários)
    from fluxocaixa.models import Fundo

    geral = Fundo.query.filter_by(cod_fundo='GERAL').first()
    if geral is None:
        return
    datas = {l.dados.get("dat_saldo") for l in contexto["preview"].linhas if l.dados.get("dat_saldo")}
    for d in datas:
        assert len(_saldos("104/0001/PP-1", "GERAL", d)) == 0, f"data {d} não deveria ter saldo"


@then(parsers.parse("o resultado informa {n:d} inserida"))
def resultado_inserida(contexto, n):
    assert contexto["resultado"].linhas_inseridas == n


@then(parsers.parse('existe {n:d} saldo ativo na conta "{ident}" no fundo "{cod}"'))
def existe_saldo(contexto, n, ident, cod):
    assert len(_saldos(ident, cod)) == n


@then(parsers.parse('existe {n:d} saldo ativo na conta "{ident}" no fundo "{cod}" com aplicacoes "{apl}"'))
def existe_saldo_apl(contexto, n, ident, cod, apl):
    saldos = _saldos(ident, cod)
    assert len(saldos) == n
    assert D2(saldos[0].val_aplicacoes) == D2(apl)


@then("confirmar o mesmo preview é rejeitado por expiração")
def confirmar_expirado(contexto):
    from fluxocaixa.services.preprocessamento import confirmar
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        confirmar(contexto["token"], contexto["sessao"])
        assert False, "deveria rejeitar"
    except RegraNegocioError as exc:
        msg = exc.mensagem.lower()
        assert "expirada" in msg or "inválida" in msg or "invalida" in msg


@then("confirmar o preview em outra sessão é rejeitado")
def confirmar_outra_sessao(contexto):
    from fluxocaixa.services.preprocessamento import confirmar
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        confirmar(contexto["token"], {})  # sessão vazia = outra sessão
        assert False, "deveria rejeitar"
    except RegraNegocioError:
        pass


@then("o preview do arquivo é rejeitado com layout inválido")
def rejeitado_layout(contexto):
    assert contexto["erro"] is not None and "layout" in contexto["erro"].lower()


@then("o preview tem 1 linha com aviso de substituição")
def aviso_substituicao(contexto):
    avisos = [l for l in contexto["preview"].linhas if l.status == 'aviso' and 'substitu' in (l.mensagem or '').lower()]
    assert len(avisos) == 1, [(l.status, l.mensagem) for l in contexto["preview"].linhas]


@then("o preview tem 1 linha com aviso de auto-cadastro")
def aviso_auto(contexto):
    avisos = [l for l in contexto["preview"].linhas if l.status == 'aviso' and 'auto-cadastr' in (l.mensagem or '').lower()]
    assert len(avisos) == 1, [(l.status, l.mensagem) for l in contexto["preview"].linhas]


@then(parsers.parse('o fundo "{cod}" existe pendente de revisão'))
def fundo_pendente(cod):
    _db().session.expire_all()
    f = _fundo(cod)
    assert f is not None and f.ind_pendente_revisao == 'S'


# ---- Lançamentos e LOA (R5) ------------------------------------------------

@when("gero um preview de lançamentos com o conteúdo:")
def gera_preview_lanc(app, contexto, datatable):
    from fluxocaixa.services.preprocessamento import criar_preview

    token, preview = criar_preview("lancamentos", _conteudo(datatable), "lanc.csv", contexto["sessao"])
    contexto["token"] = token
    contexto["preview"] = preview


@then(parsers.parse("o preview de lançamentos tem {ok:d} linha ok e {erro:d} com erro"))
def preview_lanc_contadores(contexto, ok, erro):
    p = contexto["preview"]
    assert (p.total_ok, p.total_erro) == (ok, erro), [(l.status, l.mensagem) for l in p.linhas]


@given(parsers.parse('uma LOA de "{valor}" para o ano {ano:d} e qualificador folha "{num}"'))
def loa_existente(app, valor, ano, num):
    from decimal import Decimal as _D

    from fluxocaixa.models import Loa, Qualificador
    from fluxocaixa.models.base import db

    db.session.rollback()
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    if q is None:
        q = Qualificador(num_qualificador=num, dsc_qualificador=f"Rubrica LOA {num}", ind_status='A')
        db.session.add(q); db.session.commit()
    if not Loa.query.filter_by(num_ano=ano, seq_qualificador=q.seq_qualificador).first():
        db.session.add(Loa(num_ano=ano, seq_qualificador=q.seq_qualificador, val_loa=_D(valor)))
        db.session.commit()


@when(parsers.parse("gero um preview de LOA para o ano {ano:d} com o conteúdo:"))
def gera_preview_loa(app, contexto, ano, datatable):
    from fluxocaixa.services.preprocessamento import criar_preview
    from fluxocaixa.services.preprocessamento_adapters import _AdapterLoa

    _AdapterLoa._ano = ano  # a rota real informa o ano; no teste fixamos
    token, preview = criar_preview("loa", _conteudo(datatable), "loa.csv", contexto["sessao"])
    contexto["token"] = token
    contexto["preview"] = preview


@then("o preview de LOA tem 1 linha com aviso de atualização")
def preview_loa_aviso(contexto):
    avisos = [l for l in contexto["preview"].linhas if l.status == 'aviso' and 'atualiz' in (l.mensagem or '').lower()]
    assert len(avisos) == 1, [(l.status, l.mensagem) for l in contexto["preview"].linhas]


@then(parsers.parse('a LOA de {ano:d} para "{num}" vale "{valor}"'))
def loa_valor(ano, num, valor):
    from decimal import Decimal as _D

    from fluxocaixa.models import Loa, Qualificador

    _db().session.expire_all()
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    loa = Loa.query.filter_by(num_ano=ano, seq_qualificador=q.seq_qualificador).first()
    assert loa is not None and _D(str(loa.val_loa)) == _D(valor)
