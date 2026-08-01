"""Steps BDD — folha dinâmica em qualquer nível (spec cadastros-nucleo R12–R14).

Ilha de datas 2016 e ramo de qualificador `1.7.*`. O ramo NÃO é arbitrário: as
consultas de folha do repositório recortam por `num_qualificador` começando em
`'1'`, então uma cadeia fora da raiz de receita não passaria por elas — e o
cenário de concordância ficaria verde sem exercitar nada.
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../cadastros-nucleo/qualificador_folha_dinamica.feature")

ANO = 2016
DIA = date(ANO, 5, 12)
RAMO = "1.7"
#: ramo separado para o código longo — 1.7.* não chega a estourar 20 chars
RAMO_LONGO = "1.100"


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    """Remove tudo do ramo 1.7 — filhos antes dos pais, pela FK."""
    from fluxocaixa.models import CenarioAjuste, Lancamento, Qualificador, SimuladorCenario

    db = _db()
    db.session.rollback()
    quals = Qualificador.query.filter(
        Qualificador.num_qualificador.like(f"{RAMO}%")
        | Qualificador.num_qualificador.like(f"{RAMO_LONGO}%")
        | Qualificador.num_qualificador.like("2.7.4%")
    ).all()
    if quals:
        seqs = [q.seq_qualificador for q in quals]
        CenarioAjuste.query.filter(
            CenarioAjuste.seq_qualificador.in_(seqs)
        ).delete(synchronize_session=False)
        Lancamento.query.filter(
            Lancamento.seq_qualificador.in_(seqs)
        ).delete(synchronize_session=False)
        db.session.commit()
        # do mais profundo para o mais raso
        for q in sorted(quals, key=lambda x: -x.num_qualificador.count('.')):
            db.session.delete(q)
        db.session.commit()
    for c in SimuladorCenario.query.filter(
        SimuladorCenario.nom_cenario.like("CEN_FOLHA%")
    ).all():
        db.session.delete(c)
    db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


def _criar(num, dsc=None, pai=None):
    from fluxocaixa.models import Qualificador

    db = _db()
    q = Qualificador(
        num_qualificador=num,
        dsc_qualificador=dsc or f"Rubrica {num}",
        cod_qualificador_pai=pai.seq_qualificador if pai else None,
        ind_status='A',
    )
    db.session.add(q)
    db.session.commit()
    return q


def _cadeia(niveis: int):
    """`niveis` nós encadeados a partir de 1.7 — 1 nível é só "1.7"."""
    nos = []
    pai = None
    for i in range(niveis):
        num = RAMO if i == 0 else f"{nos[-1].num_qualificador}.1"
        pai = _criar(num, pai=pai)
        nos.append(pai)
    return nos


def _lancar(qualificador, valor="100.00"):
    """Grava direto no model — usado onde o lançamento é MASSA, não o alvo."""
    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.lancamento import TIPO_CREDITO
    from fluxocaixa.services.dominio_lancamento import resolver_origem

    db = _db()
    db.session.add(Lancamento(
        dat_lancamento=DIA, seq_qualificador=qualificador.seq_qualificador,
        val_lancamento=Decimal(valor), cod_tipo_lancamento=TIPO_CREDITO,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        cod_pessoa_inclusao=1, ind_status='A',
    ))
    db.session.commit()


def _criar_lancamento_pelo_servico(seq_qualificador, valor="100.00"):
    """Passa pelo serviço — é ele que carrega a validação de folha."""
    from fluxocaixa.domain.lancamento import LancamentoCreate
    from fluxocaixa.models.lancamento import TIPO_CREDITO
    from fluxocaixa.services.dominio_lancamento import resolver_origem
    from fluxocaixa.services.lancamento_service import create_lancamento

    return create_lancamento(LancamentoCreate(
        dat_lancamento=DIA,
        seq_qualificador=seq_qualificador,
        val_lancamento=Decimal(valor),
        cod_tipo_lancamento=TIPO_CREDITO,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
    ))


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given(parsers.parse('uma cadeia de qualificadores com {niveis:d} níveis a partir de "{ramo}"'))
def dado_cadeia(app, contexto, niveis, ramo):
    contexto["cadeia"] = _cadeia(niveis)


@given(parsers.parse('um qualificador "{num}" chamado "{dsc}" com o filho "{filho}"'))
def dado_qual_com_filho(app, contexto, num, dsc, filho):
    pai = _criar(num, dsc)
    _criar(filho, pai=pai)


@given(parsers.parse('uma folha "{num}" chamada "{dsc}" com lançamentos ativos'))
def dado_folha_com_lancamentos(app, contexto, num, dsc):
    folha = _criar(num, dsc)
    _lancar(folha)
    contexto["folha"] = folha


@given(parsers.parse('uma folha "{num}" chamada "{dsc}" sem lançamentos'))
def dado_folha_vazia(app, contexto, num, dsc):
    contexto["folha"] = _criar(num, dsc)


@given(parsers.parse('um qualificador "{num}" chamado "{dsc}"'))
def dado_qual_simples(app, contexto, num, dsc):
    contexto["pai_fora_prefixo"] = _criar(num, dsc)


@given(parsers.parse('um filho legado "{filho}" apontado para "{pai_num}"'))
def dado_filho_legado(app, contexto, filho, pai_num):
    """Escreve direto no model: o R3 recusaria este código, mas dado legado o
    tem — e reapontar o pai numa edição produz o mesmo estado sem revalidar a
    subárvore."""
    from fluxocaixa.models import Qualificador

    pai = Qualificador.query.filter_by(num_qualificador=pai_num).first()
    _criar(filho, pai=pai)


@given(parsers.parse('um qualificador "{num}" chamado "{dsc}" sem pai definido'))
def dado_qual_solto(app, contexto, num, dsc):
    contexto["solto"] = _criar(num, dsc)


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

def _tentar(contexto, acao):
    from fluxocaixa.services.validacao import RegraNegocioError

    contexto.pop("erro", None)
    try:
        contexto["resultado"] = acao()
    except RegraNegocioError as erro:
        contexto["erro"] = erro
        _db().session.rollback()


@when("crio um lançamento na ponta da cadeia")
def quando_lanco_na_ponta(contexto):
    ponta = contexto["cadeia"][-1]
    _tentar(contexto,
            lambda: _criar_lancamento_pelo_servico(ponta.seq_qualificador))


@when("crio um lançamento no penúltimo nó da cadeia")
def quando_lanco_no_penultimo(contexto):
    no = contexto["cadeia"][-2]
    _tentar(contexto,
            lambda: _criar_lancamento_pelo_servico(no.seq_qualificador))


@when("inativo a ponta da cadeia")
def quando_inativo_a_ponta(contexto):
    ponta = contexto["cadeia"][-1]
    ponta.ind_status = 'I'
    _db().session.commit()


@when("confronto as folhas listadas com a validação de lançamento")
def quando_confronto(contexto):
    from fluxocaixa.models import Qualificador
    from fluxocaixa.services.qualificador_service import (
        list_despesa_qualificadores_folha, list_receita_qualificadores_folha,
    )

    listadas = {q.seq_qualificador for q in list_receita_qualificadores_folha()}
    listadas |= {q.seq_qualificador for q in list_despesa_qualificadores_folha()}
    ativos = Qualificador.query.filter_by(ind_status='A').all()
    contexto["listadas"] = listadas
    contexto["ativos"] = ativos


@when(parsers.parse('cadastro a cadeia até o código "{codigo}"'))
def quando_cadastro_codigo_longo(app, contexto, codigo):
    from fluxocaixa.services.qualificador_service import create_qualificador

    from fluxocaixa.models import Qualificador

    partes = codigo.split('.')
    # a raiz "1" vem do seed de domínio; recriá-la bateria na unicidade
    raiz = Qualificador.query.filter_by(num_qualificador=partes[0]).first()
    pai_seq = raiz.seq_qualificador if raiz else None
    inicio = 1 if raiz else 0
    for i in range(inicio, len(partes)):
        num = '.'.join(partes[:i + 1])
        criado = create_qualificador(num, f"Rubrica longa {num}", pai_seq)
        pai_seq = criado.seq_qualificador
    contexto["ultimo_codigo"] = num


@when(parsers.parse('cadastro o filho "{filho}" sob ela sem confirmar'))
def quando_cadastro_filho_sem_confirmar(contexto, filho):
    from fluxocaixa.services.qualificador_service import create_qualificador

    pai = contexto["folha"]
    _tentar(contexto, lambda: create_qualificador(
        filho, f"Filho {filho}", pai.seq_qualificador))


@when(parsers.parse('cadastro o filho "{filho}" sob ela confirmando'))
def quando_cadastro_filho_confirmando(contexto, filho):
    from fluxocaixa.services.qualificador_service import create_qualificador

    pai = contexto["folha"]
    _tentar(contexto, lambda: create_qualificador(
        filho, f"Filho {filho}", pai.seq_qualificador, confirmado=True))


@when(parsers.parse('cadastro o filho "{filho}" sob o primeiro nó da cadeia sem confirmar'))
def quando_cadastro_filho_no_primeiro(contexto, filho):
    from fluxocaixa.services.qualificador_service import create_qualificador

    pai = contexto["cadeia"][0]
    _tentar(contexto, lambda: create_qualificador(
        filho, f"Filho {filho}", pai.seq_qualificador))


@when(parsers.parse('reaponto "{num}" para ser filho de "{pai_num}" sem confirmar'))
def quando_reaponto(contexto, num, pai_num):
    from fluxocaixa.models import Qualificador
    from fluxocaixa.services.qualificador_service import update_qualificador

    alvo = Qualificador.query.filter_by(num_qualificador=num).first()
    pai = Qualificador.query.filter_by(num_qualificador=pai_num).first()
    novo_num = f"{pai.num_qualificador}.7"
    _tentar(contexto, lambda: update_qualificador(
        alvo.seq_qualificador, novo_num, alvo.dsc_qualificador,
        pai.seq_qualificador))


def _salvar_cenario_com_ajuste(nome, seq_qualificador):
    from fluxocaixa.services.simulador_cenario_service import criar_simulador_cenario

    return criar_simulador_cenario(
        nom_cenario=nome, dsc_cenario="R14", ano_base=ANO, num_periodos=12,
        tipo_cenario_receita="MANUAL",
        config_receita={"seq_qualificadores": [seq_qualificador]},
        tipo_cenario_despesa=None, config_despesa={},
        ajustes_receita={
            f"val_ajuste_1_{seq_qualificador}": 100,
            f"cod_tipo_ajuste_1_{seq_qualificador}": "V",
        },
        user_id=1,
    )


@when("salvo um cenário com ajuste manual no primeiro nó da cadeia")
def quando_cenario_ajuste_no_pai(contexto):
    no = contexto["cadeia"][0]
    contexto["seq_ajuste"] = no.seq_qualificador
    _tentar(contexto,
            lambda: _salvar_cenario_com_ajuste("CEN_FOLHA_PAI", no.seq_qualificador))


@when("salvo um cenário com ajuste manual na ponta da cadeia")
def quando_cenario_ajuste_na_folha(contexto):
    no = contexto["cadeia"][-1]
    contexto["seq_ajuste"] = no.seq_qualificador
    _tentar(contexto,
            lambda: _salvar_cenario_com_ajuste("CEN_FOLHA_OK", no.seq_qualificador))


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then("o lançamento é aceito")
def entao_lancamento_aceito(contexto):
    assert "erro" not in contexto, str(contexto.get("erro"))
    assert contexto["resultado"] is not None


@then(parsers.parse('vejo o erro "{trecho}"'))
def entao_vejo_erro(contexto, trecho):
    assert "erro" in contexto, "esperava RegraNegocioError, nada foi levantado"
    assert trecho.lower() in str(contexto["erro"]).lower(), str(contexto["erro"])


@then("toda folha listada é aceita pela validação")
def entao_folhas_listadas_aceitas(contexto):
    from fluxocaixa.models import Qualificador

    for seq in contexto["listadas"]:
        q = Qualificador.query.get(seq)
        assert q.is_folha(), \
            f"{q.num_qualificador} listado como folha, mas is_folha() é False"


@then("todo qualificador não listado é recusado por ela")
def entao_nao_listados_recusados(contexto):
    nao_listados = [
        q for q in contexto["ativos"]
        if q.seq_qualificador not in contexto["listadas"]
        and q.num_qualificador.startswith(('1', '2'))
    ]
    vazando = [q.num_qualificador for q in nao_listados if q.is_folha()]
    assert not vazando, f"folhas fora da listagem: {vazando}"


@then(parsers.parse('a coluna do código comporta "{codigo}"'))
def entao_coluna_comporta(contexto, codigo):
    from fluxocaixa.models import Qualificador

    declarado = Qualificador.__table__.c.num_qualificador.type.length
    assert declarado >= len(codigo), (
        f"num_qualificador é String({declarado}) e o código tem {len(codigo)} "
        "caracteres — SQLite aceita calado, PostgreSQL recusa"
    )


@then(parsers.parse('o código gravado é "{codigo}"'))
def entao_codigo_gravado(contexto, codigo):
    from fluxocaixa.models import Qualificador

    _db().session.expire_all()
    q = Qualificador.query.filter_by(num_qualificador=codigo).first()
    assert q is not None, f"código {codigo} não encontrado — truncado?"
    assert q.num_qualificador == codigo


@then(parsers.parse('o qualificador "{num}" não existe'))
def entao_nao_existe(contexto, num):
    from fluxocaixa.models import Qualificador

    assert Qualificador.query.filter_by(num_qualificador=num).first() is None


@then(parsers.parse('o qualificador "{num}" existe'))
def entao_existe(contexto, num):
    from fluxocaixa.models import Qualificador

    assert "erro" not in contexto, str(contexto.get("erro"))
    assert Qualificador.query.filter_by(num_qualificador=num).first() is not None


@then(parsers.parse('o qualificador "{num}" continua sendo folha'))
def entao_continua_folha(contexto, num):
    from fluxocaixa.models import Qualificador

    _db().session.expire_all()
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    assert q.is_folha(), f"{num} deixou de ser folha"


@then(parsers.parse('o qualificador "{num}" deixa de ser folha'))
def entao_deixa_de_ser_folha(contexto, num):
    from fluxocaixa.models import Qualificador

    _db().session.expire_all()
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    assert not q.is_folha(), f"{num} continua folha"


@then("nenhum ajuste foi gravado")
def entao_sem_ajuste(contexto):
    from fluxocaixa.models import CenarioAjuste

    assert CenarioAjuste.query.filter_by(
        seq_qualificador=contexto["seq_ajuste"]).count() == 0


@then("o ajuste foi gravado")
def entao_com_ajuste(contexto):
    from fluxocaixa.models import CenarioAjuste

    assert "erro" not in contexto, str(contexto.get("erro"))
    assert CenarioAjuste.query.filter_by(
        seq_qualificador=contexto["seq_ajuste"]).count() >= 1
