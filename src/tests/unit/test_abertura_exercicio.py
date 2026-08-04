"""Unitários — abertura de exercício (cadastros-nucleo R29, F10.3).

Imports de app sempre tardios (isolamento de banco da suíte).
"""
import pytest

RAMO = "8.5"
ANO_A, ANO_B = 2088, 2089


@pytest.fixture(autouse=True)
def _ilha(client):
    _limpar()
    yield
    _limpar()


def _limpar():
    from fluxocaixa.models import Qualificador
    from fluxocaixa.models.base import db

    db.session.rollback()
    quals = Qualificador.query.filter(
        Qualificador.num_ano_exercicio.in_((ANO_A, ANO_B))).all()
    for q in sorted(quals, key=lambda x: -x.num_qualificador.count('.')):
        db.session.delete(q)
    db.session.commit()


def _criar(num, dsc, ano, pai=None):
    from fluxocaixa.services import qualificador_service

    return qualificador_service.create_qualificador(
        num, dsc, num_ano_exercicio=ano,
        cod_qualificador_pai=pai.seq_qualificador if pai else None)


def test_criacao_carimba_autor():
    """O autor é sempre carimbado (R29). O VALOR depende do contexto — fora
    de request é o fallback 1, mas o contexto de usuário do processo de teste
    varia com a ordem da suíte; o invariante é não-nulo."""
    q = _criar(RAMO, "Bloco Autor", ANO_A)
    assert q.cod_pessoa_inclusao is not None


def test_filho_de_pai_inativo_vira_raiz_no_ano_novo():
    from fluxocaixa.models.base import db
    from fluxocaixa.services import qualificador_service
    from fluxocaixa.services.qualificador_service import abrir_exercicio

    pai = _criar(RAMO, "Pai Que Sai", ANO_A)
    filho = _criar(f"{RAMO}.1", "Filho Orfao", ANO_A, pai=pai)
    # inativa o pai por fora do serviço (delete_qualificador recusaria com
    # filho ativo) — o estado é o que a cópia precisa tolerar
    pai.ind_status = 'I'
    db.session.commit()
    del filho, qualificador_service

    abrir_exercicio(ANO_A, ANO_B, confirmado=True)

    from fluxocaixa.models import Qualificador

    copiado = Qualificador.query.filter_by(
        num_ano_exercicio=ANO_B, num_qualificador=f"{RAMO}.1").first()
    assert copiado is not None
    assert copiado.cod_qualificador_pai is None  # pai não copiado (A.2)


def test_falha_no_meio_nao_deixa_exercicio_pela_metade(monkeypatch):
    from fluxocaixa.models import Qualificador
    from fluxocaixa.models.base import db
    from fluxocaixa.services.qualificador_service import abrir_exercicio

    _criar(RAMO, "Bloco Atomico", ANO_A)

    def _explode():
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(db.session, "flush", _explode)
    with pytest.raises(RuntimeError):
        abrir_exercicio(ANO_A, ANO_B, confirmado=True)
    monkeypatch.undo()
    db.session.rollback()

    assert Qualificador.query.filter_by(num_ano_exercicio=ANO_B).count() == 0


def test_origem_sem_plano_e_recusada():
    from fluxocaixa.services.qualificador_service import abrir_exercicio
    from fluxocaixa.services.validacao import RegraNegocioError

    with pytest.raises(RegraNegocioError, match="não tem plano"):
        abrir_exercicio(2199, 2200, confirmado=True)
