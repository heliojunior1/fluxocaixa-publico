"""Unitários do loa_service (cadastros-nucleo R24).

Import tardio de `fluxocaixa` dentro dos testes (isolamento de banco).
Ilha 2165 — distinta da 2065 do BDD para os asserts não colidirem.
"""
from decimal import Decimal

import pytest

ANO = 2165
QUAL = "1.68.1"


@pytest.fixture()
def qualificador(app):
    from fluxocaixa.models import Loa, Qualificador
    from fluxocaixa.models.base import db

    db.session.rollback()
    q = Qualificador.query.filter_by(num_qualificador=QUAL).first()
    if q is None:
        q = Qualificador(num_qualificador=QUAL,
                         dsc_qualificador="Rubrica Serviço LOA",
                         ind_status='A')
        db.session.add(q)
        db.session.commit()
    Loa.query.filter_by(seq_qualificador=q.seq_qualificador).delete()
    db.session.commit()
    yield q
    Loa.query.filter_by(seq_qualificador=q.seq_qualificador).delete()
    db.session.commit()


def test_upsert_atualiza_o_ativo(qualificador):
    from fluxocaixa.models import Loa
    from fluxocaixa.models.base import db
    from fluxocaixa.services import loa_service

    loa_service.upsert_loa(ANO, qualificador.seq_qualificador, Decimal("100.00"))
    loa_service.upsert_loa(ANO, qualificador.seq_qualificador, Decimal("200.00"))
    db.session.commit()

    ativos = Loa.query.filter_by(
        num_ano=ANO, seq_qualificador=qualificador.seq_qualificador,
        ind_status='A').all()
    assert len(ativos) == 1
    assert ativos[0].val_loa == Decimal("200.00")
    assert ativos[0].dat_alteracao is not None


def test_upsert_carimba_autor_da_inclusao(qualificador):
    from fluxocaixa.models.base import db
    from fluxocaixa.services import loa_service

    registro = loa_service.upsert_loa(
        ANO, qualificador.seq_qualificador, Decimal("100.00"))
    db.session.commit()
    assert registro.cod_pessoa_inclusao is not None


def test_encontrar_qualificador_por_codigo_e_descricao(qualificador):
    from fluxocaixa.services import loa_service

    assert loa_service.encontrar_qualificador(QUAL) is not None
    assert loa_service.encontrar_qualificador("rubrica serviço loa") is not None
    assert loa_service.encontrar_qualificador("inexistente-xyz") is None


def test_inativar_carimba_auditoria(qualificador):
    from fluxocaixa.models.base import db
    from fluxocaixa.services import loa_service

    registro = loa_service.upsert_loa(
        ANO, qualificador.seq_qualificador, Decimal("100.00"))
    db.session.commit()

    inativado = loa_service.inativar(registro.seq_loa)
    assert inativado.ind_status == 'I'
    assert inativado.cod_pessoa_alteracao is not None
