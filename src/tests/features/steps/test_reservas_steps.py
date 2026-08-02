"""Steps BDD — reservas e bloqueios (spec desembolso R19–R20). Ilha 2044.

⚠️ Vigências no FUTURO (2044) nos cenários de aritmética/regras — reserva
vigente HOJE do grupo 'V' abateria a simulação dos outros BDDs; o único
cenário com vigência atual LIBERA a reserva no próprio cenário.
"""
from datetime import date
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../desembolso/reservas.feature")


@pytest.fixture()
def contexto():
    return {}


def _db():
    from fluxocaixa.models.base import db

    return db


def _fonte(codigo: str, vigencia: int):
    from fluxocaixa.models import FonteRecurso

    ident, fonte = codigo.split(".", 1)
    return FonteRecurso.query.filter_by(
        cod_identificador_exercicio=ident, cod_fonte_stn=fonte,
        num_exercicio_vigencia=vigencia, ind_status='A').first()


def _executar(contexto, fn):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        contexto["resultado"] = fn()
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc.mensagem


@given("que estou autenticado como administrador")
def autenticado_admin(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(12345)


@given(parsers.parse('a fonte "{codigo}" cadastrada na vigência {vigencia:d} como "{vinculada}"'))
def fonte_cadastrada(app, codigo, vigencia, vinculada):
    from fluxocaixa.services.fonte_recurso_service import criar_fonte

    _db().session.rollback()
    if _fonte(codigo, vigencia) is None:
        ident, fonte = codigo.split(".", 1)
        criar_fonte(ident, fonte, f"Fonte de teste {codigo}", vigencia,
                    vinculada='L' if vinculada == 'livre' else 'V')


def _constituir(tipo, valor, codigo, vigencia, inicio, processo=None, confirmado=False):
    from fluxocaixa.services.reserva_service import constituir_reserva

    return constituir_reserva(
        cod_tipo_reserva=tipo,
        seq_fonte_recurso=_fonte(codigo, vigencia).seq_fonte_recurso,
        val_reserva=Decimal(valor),
        dsc_motivo="Reserva de teste BDD",
        dat_inicio_vigencia=date.fromisoformat(inicio),
        dsc_referencia_processo=processo,
        confirmado=confirmado)


@given(parsers.parse('uma reserva administrativa de {valor} na fonte "{codigo}" da vigência {vigencia:d} vigente desde "{inicio}"'),
       target_fixture="reserva_atual")
def reserva_administrativa(app, valor, codigo, vigencia, inicio):
    return _constituir('A', valor, codigo, vigencia, inicio, confirmado=True)['reserva']


@given(parsers.parse('um bloqueio judicial de {valor} na fonte "{codigo}" da vigência {vigencia:d} vigente desde "{inicio}" com processo "{processo}"'),
       target_fixture="reserva_atual")
def bloqueio_judicial(app, valor, codigo, vigencia, inicio, processo):
    return _constituir('J', valor, codigo, vigencia, inicio, processo=processo)['reserva']


@when(parsers.parse('constituo uma reserva administrativa de {valor} na fonte "{codigo}" da vigência {vigencia:d} vigente desde "{inicio}" sem confirmação'))
def constitui_adm_sem(app, contexto, valor, codigo, vigencia, inicio):
    _executar(contexto, lambda: _constituir('A', valor, codigo, vigencia, inicio))


@when(parsers.parse('constituo um bloqueio judicial de {valor} na fonte "{codigo}" da vigência {vigencia:d} vigente desde "{inicio}" com processo "{processo}"'))
def constitui_judicial(app, contexto, valor, codigo, vigencia, inicio, processo):
    _executar(contexto, lambda: _constituir('J', valor, codigo, vigencia, inicio,
                                            processo=processo))


@when(parsers.parse('constituo um bloqueio judicial de {valor} na fonte "{codigo}" da vigência {vigencia:d} vigente desde "{inicio}" sem processo'))
def constitui_judicial_sem_processo(app, contexto, valor, codigo, vigencia, inicio):
    _executar(contexto, lambda: _constituir('J', valor, codigo, vigencia, inicio))


@when(parsers.parse('reforço essa reserva em {valor}'))
def reforca(app, contexto, reserva_atual, valor):
    from fluxocaixa.services.reserva_service import reforcar_reserva

    _executar(contexto, lambda: reforcar_reserva(reserva_atual.seq_reserva, Decimal(valor)))


@when(parsers.parse('reduzo essa reserva em {valor}'))
def reduz(app, contexto, reserva_atual, valor):
    from fluxocaixa.services.reserva_service import reduzir_reserva

    _executar(contexto, lambda: reduzir_reserva(reserva_atual.seq_reserva, Decimal(valor)))


@when("libero essa reserva")
def libera_reserva(app, contexto, reserva_atual):
    from fluxocaixa.services.reserva_service import liberar_reserva

    _executar(contexto, lambda: liberar_reserva(reserva_atual.seq_reserva))


@when("libero esse bloqueio sem referência")
def libera_sem_referencia(app, contexto, reserva_atual):
    from fluxocaixa.services.reserva_service import liberar_reserva

    _executar(contexto, lambda: liberar_reserva(reserva_atual.seq_reserva))


@then(parsers.parse('libero esse bloqueio com a ordem "{ordem}"'))
def libera_com_ordem(app, contexto, ordem, request):
    """Limpeza dentro do cenário (bloqueios gigantes não podem vazar) —
    usa a reserva criada no When (contexto) ou a fixture do Given."""
    from fluxocaixa.services.reserva_service import liberar_reserva, valor_corrente

    reserva = None
    if isinstance(contexto.get("resultado"), dict):
        reserva = contexto["resultado"].get('reserva')
    if reserva is None:
        try:
            reserva = request.getfixturevalue('reserva_atual')
        except Exception:
            pytest.fail("sem reserva no contexto")
    if valor_corrente(reserva.seq_reserva) > 0:
        liberar_reserva(reserva.seq_reserva, referencia=ordem)


@then(parsers.parse('o valor corrente dessa reserva é {valor}'))
def corrente_e(reserva_atual, valor):
    from fluxocaixa.services.reserva_service import valor_corrente

    _db().session.expire_all()
    assert valor_corrente(reserva_atual.seq_reserva) == Decimal(valor).quantize(Decimal("0.01"))


@then(parsers.parse('a operação de reserva é rejeitada com a mensagem "{mensagem}"'))
def reserva_rejeitada(contexto, mensagem):
    assert contexto["erro"] == mensagem, f"esperava {mensagem!r}, veio {contexto['erro']!r}"


@then("o bloqueio é registrado com alerta de grupo insuficiente")
def bloqueio_com_alerta(contexto):
    assert contexto["erro"] is None, contexto["erro"]
    assert contexto["resultado"]["alerta"] == "Grupo fica insuficiente com este bloqueio"


@then(parsers.parse('as reservas vigentes do grupo "{grupo}" hoje incluem {valor}'))
def vigentes_incluem(contexto, grupo, valor):
    from fluxocaixa.services.reserva_service import reservas_vigentes_do_grupo

    contexto["vigentes_antes"] = reservas_vigentes_do_grupo(grupo, date.today())
    assert contexto["vigentes_antes"] >= Decimal(valor)


@then(parsers.parse('as reservas vigentes do grupo "{grupo}" hoje não incluem mais os {valor}'))
def vigentes_nao_incluem(contexto, grupo, valor):
    from fluxocaixa.services.reserva_service import reservas_vigentes_do_grupo

    _db().session.expire_all()
    depois = reservas_vigentes_do_grupo(grupo, date.today())
    assert depois == contexto["vigentes_antes"] - Decimal(valor)
