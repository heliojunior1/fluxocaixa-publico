"""Steps BDD — ciclo na hierarquia de qualificadores (spec cadastros-nucleo R16).

⚠️ Cada travessia roda sob `signal.alarm`. Sem isso, uma regressão que devolva o
laço infinito **trava a suíte inteira** em vez de falhar — e suíte travada não
diz o que está errado. É a mesma técnica da sonda que mediu o problema.
"""
import signal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../cadastros-nucleo/qualificador_ciclo.feature")

RAMOS = ("7.3", "7.4")
LIMITE_SEGUNDOS = 5


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _limpar():
    from fluxocaixa.models import Qualificador

    db = _db()
    db.session.rollback()
    filtro = Qualificador.num_qualificador.like(f"{RAMOS[0]}%")
    for ramo in RAMOS[1:]:
        filtro = filtro | Qualificador.num_qualificador.like(f"{ramo}%")
    quals = Qualificador.query.filter(filtro).all()
    if quals:
        # ⚠️ desfaz qualquer ciclo ANTES de apagar: com o pai apontando para um
        # nó que também será apagado, a ordem de exclusão não existe.
        for q in quals:
            q.cod_qualificador_pai = None
        db.session.commit()
        for q in quals:
            db.session.delete(q)
        db.session.commit()


@pytest.fixture(autouse=True)
def _ilha(app):
    _limpar()
    yield
    _limpar()


def _no(num, dsc=None, pai_num=None):
    from fluxocaixa.models import Qualificador

    db = _db()
    pai = (Qualificador.query.filter_by(num_qualificador=pai_num).first()
           if pai_num else None)
    q = Qualificador(num_qualificador=num, dsc_qualificador=dsc or f"Rubrica {num}",
                     ind_status='A',
                     cod_qualificador_pai=pai.seq_qualificador if pai else None)
    db.session.add(q)
    db.session.commit()
    return q


def _buscar(num):
    from fluxocaixa.models import Qualificador

    _db().session.expire_all()
    return Qualificador.query.filter_by(num_qualificador=num).first()


def _sob_limite(contexto, acao):
    """Executa com teto de tempo. Travamento vira falha explícita, não hang."""
    from fluxocaixa.services.validacao import RegraNegocioError

    contexto.pop("erro", None)
    contexto.pop("travou", None)

    def _estourou(_s, _f):
        raise TimeoutError()

    anterior = signal.signal(signal.SIGALRM, _estourou)
    signal.alarm(LIMITE_SEGUNDOS)
    try:
        contexto["resultado"] = acao()
    except RegraNegocioError as erro:
        contexto["erro"] = erro
    except TimeoutError:
        contexto["travou"] = True
    except RecursionError:
        contexto["erro"] = None
        contexto["recursao"] = True
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, anterior)


# --------------------------------------------------------------------------
# Dado
# --------------------------------------------------------------------------

@given(parsers.parse('o qualificador "{num}" chamado "{dsc}"'))
def dado_no(app, contexto, num, dsc):
    _no(num, dsc)


@given(parsers.parse('a cadeia "{a}" → "{b}"'))
def dado_cadeia_2(app, contexto, a, b):
    _no(a)
    _no(b, pai_num=a)


@given(parsers.parse('a cadeia "{a}" → "{b}" → "{c}"'))
def dado_cadeia_3(app, contexto, a, b, c):
    _no(a)
    _no(b, pai_num=a)
    _no(c, pai_num=b)


@given(parsers.parse('o qualificador "{num}" chamado "{dsc}" sob "{pai}"'))
def dado_no_sob(app, contexto, num, dsc, pai):
    _no(num, dsc, pai_num=pai)


@given(parsers.parse('uma hierarquia já ciclada no ramo "{ramo}"'))
def dado_ciclado(app, contexto, ramo):
    """Monta o ciclo DIRETO no banco — é o estado que a guarda não alcança."""
    db = _db()
    a = _no(ramo)
    b = _no(f"{ramo}.1", pai_num=ramo)
    a.cod_qualificador_pai = b.seq_qualificador
    db.session.commit()
    contexto["ciclado"] = a.seq_qualificador


# --------------------------------------------------------------------------
# Quando
# --------------------------------------------------------------------------

def _reapontar(contexto, num, pai_num, novo_codigo=None, confirmado=True):
    from fluxocaixa.services.qualificador_service import update_qualificador

    alvo = _buscar(num)
    pai = _buscar(pai_num) if pai_num else None
    contexto["alvo_num"] = num
    _sob_limite(contexto, lambda: update_qualificador(
        alvo.seq_qualificador, novo_codigo or alvo.num_qualificador,
        alvo.dsc_qualificador,
        pai.seq_qualificador if pai else None,
        confirmado=confirmado,
    ))


@when(parsers.parse('reaponto "{num}" para ele próprio'))
def quando_reaponto_para_si(app, contexto, num):
    from fluxocaixa.services.qualificador_service import update_qualificador

    alvo = _buscar(num)
    contexto["alvo_num"] = num
    _sob_limite(contexto, lambda: update_qualificador(
        alvo.seq_qualificador, alvo.num_qualificador, alvo.dsc_qualificador,
        alvo.seq_qualificador, confirmado=True,
    ))


@when(parsers.parse('reaponto "{num}" para o descendente "{desc}"'))
def quando_reaponto_para_descendente(app, contexto, num, desc):
    # o código precisa caber no prefixo do novo pai — foi exatamente assim que
    # a sonda criou o ciclo passando pela validação do R3
    _reapontar(contexto, num, desc, novo_codigo=f"{desc}.9")


@when(parsers.parse('reaponto "{num}" para o ramo "{ramo}" com o código "{codigo}"'))
def quando_reaponto_legitimo(app, contexto, num, ramo, codigo):
    _reapontar(contexto, num, ramo, novo_codigo=codigo, confirmado=False)


@when(parsers.parse('reaponto "{num}" para o ramo "{ramo}" com o código "{codigo}" confirmando'))
def quando_reaponto_confirmando(app, contexto, num, ramo, codigo):
    _reapontar(contexto, num, ramo, novo_codigo=codigo, confirmado=True)


def _no_ciclado(contexto):
    from fluxocaixa.models import Qualificador

    _db().session.expire_all()
    return Qualificador.query.get(contexto["ciclado"])


@when("consulto o nível do nó ciclado")
def quando_nivel(app, contexto):
    _sob_limite(contexto, lambda: _no_ciclado(contexto).nivel)


@when("consulto o caminho completo do nó ciclado")
def quando_caminho(app, contexto):
    _sob_limite(contexto, lambda: _no_ciclado(contexto).path_completo)


@when("consulto a raiz do nó ciclado")
def quando_raiz(app, contexto):
    _sob_limite(contexto, lambda: _no_ciclado(contexto).get_root)


@when("consulto o tipo de fluxo do nó ciclado")
def quando_tipo_fluxo(app, contexto):
    _sob_limite(contexto, lambda: _no_ciclado(contexto).tipo_fluxo)


@when("consulto a categoria fiscal do nó ciclado")
def quando_categoria(app, contexto):
    from fluxocaixa.services.categoria_fiscal_service import categoria_resolvida

    _sob_limite(contexto, lambda: categoria_resolvida(_no_ciclado(contexto)))


@when("consulto os descendentes do nó ciclado")
def quando_descendentes(app, contexto):
    _sob_limite(contexto, lambda: _no_ciclado(contexto).get_todos_filhos())


# --------------------------------------------------------------------------
# Então
# --------------------------------------------------------------------------

@then("recebo erro de ciclo")
def entao_erro_ciclo(contexto):
    assert not contexto.get("travou"), "TRAVOU — laço não terminante"
    assert "erro" in contexto and contexto["erro"] is not None, \
        f"esperava RegraNegocioError, veio {contexto.get('resultado')}"
    assert "ciclo" in str(contexto["erro"]).lower() \
        or "si mesmo" in str(contexto["erro"]).lower(), str(contexto["erro"])


@then("recebo erro de ciclo sem travar")
def entao_erro_sem_travar(contexto):
    assert not contexto.get("travou"), \
        f"TRAVOU: a travessia não terminou em {LIMITE_SEGUNDOS}s"
    assert not contexto.get("recursao"), \
        "RecursionError — erro de negócio virando 500, viola o R1"
    assert contexto.get("erro") is not None, \
        f"esperava RegraNegocioError, veio {contexto.get('resultado')}"


@then(parsers.parse('o qualificador "{num}" continua sem pai'))
def entao_sem_pai(contexto, num):
    assert _buscar(num).cod_qualificador_pai is None


@then("a mudança é aceita")
def entao_aceita(contexto):
    assert not contexto.get("travou")
    assert contexto.get("erro") is None, str(contexto.get("erro"))


@then(parsers.parse('o qualificador "{num}" tem pai "{pai}"'))
def entao_tem_pai(contexto, num, pai):
    q = _buscar(num)
    assert q is not None, f"{num} não encontrado"
    assert q.pai is not None and q.pai.num_qualificador == pai


@then(parsers.parse('o qualificador "{num}" existe'))
def entao_existe(contexto, num):
    assert _buscar(num) is not None, f"{num} não encontrado"


@then(parsers.parse('o qualificador "{num}" ainda existe'))
def entao_ainda_existe(contexto, num):
    assert _buscar(num) is not None, f"{num} sumiu — a cascata gravou parcialmente?"


@then(parsers.parse('não existe mais qualificador começando por "{prefixo}"'))
def entao_sem_prefixo(contexto, prefixo):
    from fluxocaixa.models import Qualificador

    _db().session.expire_all()
    sobrou = Qualificador.query.filter(
        Qualificador.num_qualificador.like(f"{prefixo}%")).all()
    assert not sobrou, [q.num_qualificador for q in sobrou]


@then("recebo erro pedindo confirmação da renomeação")
def entao_erro_confirmacao(contexto):
    assert contexto.get("erro") is not None, contexto.get("resultado")
    assert "confirme" in str(contexto["erro"]).lower(), str(contexto["erro"])


@then("recebo erro de código duplicado")
def entao_erro_duplicado(contexto):
    assert contexto.get("erro") is not None, contexto.get("resultado")
    texto = str(contexto["erro"]).lower()
    assert "duplicad" in texto or "já existe" in texto, str(contexto["erro"])
