"""Unitários — qualificador por exercício (cadastros-nucleo R25–R26, F10.1).

Imports de app sempre tardios (isolamento de banco da suíte — ver nota em
CLAUDE.md sobre `DATABASE_URL` e o engine).
"""
import pytest

RAMO = "8.2"
ANO_A, ANO_B = 2073, 2074


@pytest.fixture(autouse=True)
def _ilha(client):
    """`client` garante app + banco migrado; limpeza antes e depois."""
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


def _criar(num, dsc, ano, **kw):
    from fluxocaixa.services import qualificador_service

    return qualificador_service.create_qualificador(
        num, dsc, num_ano_exercicio=ano, **kw)


def test_default_de_ano_e_o_corrente():
    from datetime import date

    from fluxocaixa.services import qualificador_service

    q = qualificador_service.create_qualificador(RAMO, "Bloco Default")
    assert q.num_ano_exercicio == date.today().year


def test_raiz_nasce_como_o_proprio_seq_na_criacao_direta():
    """O evento after_insert vale também para quem cria pelo ORM direto —
    seeds e testes, não só o serviço."""
    from fluxocaixa.models import Qualificador
    from fluxocaixa.models.base import db

    q = Qualificador(num_qualificador=RAMO, dsc_qualificador="Bloco Direto",
                     num_ano_exercicio=ANO_A)
    db.session.add(q)
    db.session.commit()
    assert q.cod_rubrica_raiz == q.seq_qualificador


def test_raiz_explicita_e_preservada():
    """A cópia de exercício (F10.3) passa a raiz herdada — o evento não pode
    sobrescrevê-la."""
    origem = _criar(RAMO, "Bloco Origem", ANO_A)
    espelho = _criar(RAMO, "Bloco Espelho", ANO_B,
                     cod_rubrica_raiz=origem.cod_rubrica_raiz)
    assert espelho.cod_rubrica_raiz == origem.cod_rubrica_raiz != espelho.seq_qualificador


def test_codigo_duplicado_no_mesmo_exercicio_e_recusado():
    from fluxocaixa.services.validacao import RegraNegocioError

    _criar(RAMO, "Bloco Unico", ANO_A)
    with pytest.raises(RegraNegocioError, match="exercício"):
        _criar(RAMO, "Bloco Duplicado", ANO_A)


def test_codigo_inativo_nao_bloqueia_novo_ativo_no_mesmo_exercicio():
    """Unicidade é ENTRE ATIVOS (padrão fonte-recurso/LOA): inativa convive."""
    from fluxocaixa.models.base import db
    from fluxocaixa.services import qualificador_service

    q = _criar(RAMO, "Bloco Que Sai", ANO_A)
    qualificador_service.delete_qualificador(q.seq_qualificador, confirmado=True)
    db.session.commit()
    novo = _criar(RAMO, "Bloco Que Volta", ANO_A)
    assert novo.seq_qualificador != q.seq_qualificador


def test_descricao_duplicada_so_conta_dentro_do_exercicio():
    _criar(RAMO, "Mesma Descricao", ANO_A)
    q = _criar(RAMO, "Mesma Descricao", ANO_B)
    assert q.num_ano_exercicio == ANO_B


def test_pai_de_outro_exercicio_e_recusado():
    from fluxocaixa.services.validacao import RegraNegocioError

    pai = _criar(RAMO, "Bloco Pai", ANO_A)
    with pytest.raises(RegraNegocioError, match="mesmo exercício"):
        _criar(f"{RAMO}.1", "Filho Fora", ANO_B,
               cod_qualificador_pai=pai.seq_qualificador)


def test_transicao_sem_plano_no_ano_aceita():
    from fluxocaixa.services.qualificador_service import (
        validar_qualificador_do_exercicio,
    )

    q = _criar(RAMO, "Bloco Transicao", ANO_A)
    # 2099: nenhum plano — não levanta
    validar_qualificador_do_exercicio(q, 2099)


def test_transicao_com_plano_no_ano_recusa():
    from fluxocaixa.services.qualificador_service import (
        validar_qualificador_do_exercicio,
    )
    from fluxocaixa.services.validacao import RegraNegocioError

    q_a = _criar(RAMO, "Bloco A", ANO_A)
    _criar(RAMO, "Bloco B", ANO_B)
    with pytest.raises(RegraNegocioError, match=str(ANO_B)):
        validar_qualificador_do_exercicio(q_a, ANO_B)
