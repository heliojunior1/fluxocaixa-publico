"""Unitários — herança da rubrica raiz (cadastros-nucleo R30, F10.5).

Imports de app sempre tardios (isolamento de banco da suíte).
"""
import pytest

RAMO = "8.6"
ANO_A, ANO_B = 2092, 2093


@pytest.fixture(autouse=True)
def _ilha(client):
    _limpar()
    yield
    _limpar()


def _limpar():
    from fluxocaixa.models import Qualificador
    from fluxocaixa.models.base import db

    db.session.rollback()
    for q in Qualificador.query.filter(
            Qualificador.num_qualificador.like(f"{RAMO}%")).all():
        db.session.delete(q)
    db.session.commit()


def _criar(num, dsc, ano, raiz=None, status='A'):
    from fluxocaixa.models.base import db
    from fluxocaixa.services import qualificador_service as svc

    q = svc.create_qualificador(num, dsc, num_ano_exercicio=ano,
                                cod_rubrica_raiz=raiz)
    if status != 'A':
        q.ind_status = status
        db.session.commit()
    return q


def test_candidatas_incluem_exercicio_anterior_com_raiz_livre():
    from fluxocaixa.services.qualificador_service import candidatas_para_heranca

    origem = _criar(RAMO, "Origem Livre", ANO_A)
    seqs = {c.seq_qualificador for c in candidatas_para_heranca(ANO_B)}
    assert origem.seq_qualificador in seqs


def test_candidatas_excluem_raiz_ja_em_uso_no_exercicio():
    from fluxocaixa.services.qualificador_service import candidatas_para_heranca

    origem = _criar(RAMO, "Origem Usada", ANO_A)
    _criar(RAMO, "Herdeira", ANO_B, raiz=origem.cod_rubrica_raiz)
    seqs = {c.seq_qualificador for c in candidatas_para_heranca(ANO_B)}
    assert origem.seq_qualificador not in seqs


def test_candidatas_incluem_inativa_do_proprio_exercicio():
    from fluxocaixa.services.qualificador_service import candidatas_para_heranca

    extinta = _criar(RAMO, "Extinta Local", ANO_B, status='I')
    seqs = {c.seq_qualificador for c in candidatas_para_heranca(ANO_B)}
    assert extinta.seq_qualificador in seqs


def test_heranca_de_inativa_do_mesmo_ano_e_aceita():
    extinta = _criar(RAMO, "Extinta Retomada", ANO_A, status='I')
    nova = _criar(f"{RAMO}.1", "Retomada", ANO_A,
                  raiz=extinta.cod_rubrica_raiz)
    assert nova.cod_rubrica_raiz == extinta.cod_rubrica_raiz


def test_heranca_duplicada_no_mesmo_ano_e_recusada():
    from fluxocaixa.services.validacao import RegraNegocioError

    origem = _criar(RAMO, "Origem Dupla", ANO_A)
    _criar(RAMO, "Primeira Herdeira", ANO_B, raiz=origem.cod_rubrica_raiz)
    with pytest.raises(RegraNegocioError, match="em dobro"):
        _criar(f"{RAMO}.1", "Segunda Herdeira", ANO_B,
               raiz=origem.cod_rubrica_raiz)
