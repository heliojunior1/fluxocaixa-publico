"""Unitários — abertura de exercício (cadastros-nucleo R29, F10.3).

Imports de app sempre tardios (isolamento de banco da suíte).
"""
import pytest

RAMO = "8.5"
ANO_A, ANO_B = 2088, 2089
PREFIXO_CENARIO = "CEN_UT_AB_"


@pytest.fixture(autouse=True)
def _ilha(client):
    _limpar()
    yield
    _limpar()


def _limpar():
    from fluxocaixa.models import Qualificador, SimuladorCenario
    from fluxocaixa.models.base import db

    db.session.rollback()
    for c in SimuladorCenario.query.filter(
            SimuladorCenario.nom_cenario.like(f"{PREFIXO_CENARIO}%")).all():
        db.session.delete(c)
    db.session.flush()
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


def _cenario_com_marcacao(folha):
    """Cenário de ANO_B montado quando só existe o plano de ANO_A, com valor
    fixo na folha — o caso que a abertura de ANO_B tem de re-apontar."""
    from fluxocaixa.services.metodo_qualificador_service import definir_marcacao
    from fluxocaixa.services.simulador_cenario_service import criar_simulador_cenario

    cenario = criar_simulador_cenario(
        nom_cenario=f"{PREFIXO_CENARIO}{folha.seq_qualificador}", dsc_cenario="ut",
        ano_base=ANO_B, num_periodos=12, tipo_cenario_receita='', config_receita={},
        tipo_cenario_despesa='', config_despesa={}, user_id=1)
    definir_marcacao(cenario.seq_simulador_cenario, folha.seq_qualificador,
                     'VALOR_FIXO', {'valor_anual': '1200.00'}, user_id=1)
    return cenario


def test_referencia_sem_correspondente_no_ano_novo_permanece():
    """previsao R21: marcação em qualificador que a abertura não copia
    (inativo na origem) fica onde está — nada é apagado."""
    from fluxocaixa.models import CenarioMetodo
    from fluxocaixa.models.base import db
    from fluxocaixa.services.qualificador_service import abrir_exercicio

    bloco = _criar("1.85", "Bloco Receita UT", ANO_A)
    folha = _criar("1.85.1", "Folha Que Sai", ANO_A, pai=bloco)
    _criar("1.85.2", "Folha Que Fica", ANO_A, pai=bloco)
    cenario = _cenario_com_marcacao(folha)
    folha.ind_status = 'I'
    db.session.commit()

    abrir_exercicio(ANO_A, ANO_B, confirmado=True)

    marcacoes = CenarioMetodo.query.filter_by(
        seq_simulador_cenario=cenario.seq_simulador_cenario).all()
    assert [m.seq_qualificador for m in marcacoes] == [folha.seq_qualificador]


def test_falha_no_reapontamento_desfaz_a_abertura_inteira(monkeypatch):
    from fluxocaixa.models import Qualificador
    from fluxocaixa.services import metodo_qualificador_service
    from fluxocaixa.services.qualificador_service import abrir_exercicio

    bloco = _criar("1.85", "Bloco Receita UT", ANO_A)
    _cenario_com_marcacao(_criar("1.85.1", "Folha UT", ANO_A, pai=bloco))

    def _explode(*_args, **_kwargs):
        raise RuntimeError("falha simulada no re-apontamento")

    monkeypatch.setattr(metodo_qualificador_service,
                        "reapontar_cenarios_para_exercicio", _explode)
    with pytest.raises(RuntimeError):
        abrir_exercicio(ANO_A, ANO_B, confirmado=True)

    assert Qualificador.query.filter_by(num_ano_exercicio=ANO_B).count() == 0
