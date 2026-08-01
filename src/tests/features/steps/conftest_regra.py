"""Helpers compartilhados dos steps do motor de mapeamentos (F4.2).

Import tardio de `fluxocaixa` em todas as funções — a fixture `client` do
conftest raiz precisa forçar o DATABASE_URL antes do primeiro import.
"""

# Termos usados pelas features. Espelham o vocabulário da referência (rótulo de
# negócio → campo), com valores fictícios: nada de UG/natureza reais.
TERMOS_PADRAO = [
    ("Natureza", "ATRIBUTO", "natureza", "TEXTO"),
    ("Unidade Gestora", "ATRIBUTO", "ug", "TEXTO"),
    ("Fonte Detalhada", "ATRIBUTO", "fonte_detalhada", "TEXTO"),
    ("Valor", "COLUNA", "val_referencia", "NUMERO"),
    ("Ano de Exercício", "COLUNA", "num_ano_exercicio", "NUMERO"),
    ("Data", "COLUNA", "dat_referencia", "DATA"),
]


def criar_termo(nom_termo, cod_origem_campo, nom_campo, cod_tipo="TEXTO"):
    from fluxocaixa.services.termo_regra_service import criar_termo as _criar

    return _criar(
        nom_termo=nom_termo,
        cod_origem_campo=cod_origem_campo,
        nom_campo=nom_campo,
        cod_tipo=cod_tipo,
    )


def termo_por_nome(nom_termo):
    from fluxocaixa.models import TermoRegra

    return TermoRegra.query.filter_by(nom_termo=nom_termo).first()


def garantir_termos_padrao():
    for nom, origem, campo, tipo in TERMOS_PADRAO:
        if termo_por_nome(nom) is None:
            criar_termo(nom, origem, campo, tipo)


def garantir_qualificador(num, dsc=None, pai=None):
    """Cria (ou devolve) um qualificador ativo pelo número."""
    from fluxocaixa.models import Qualificador
    from fluxocaixa.models.base import db

    q = Qualificador.query.filter_by(num_qualificador=num).first()
    if q is None:
        q = Qualificador(
            num_qualificador=num,
            dsc_qualificador=dsc or f"Qualificador {num}",
            cod_qualificador_pai=pai.seq_qualificador if pai is not None else None,
            ind_status='A',
        )
        db.session.add(q)
        db.session.commit()
    return q


def sistema_por_sigla(sigla):
    """`garantir_sistema_origem` do conftest cria mas não devolve a entidade."""
    from fluxocaixa.models import SistemaOrigem

    from ..conftest_extracao import garantir_sistema_origem

    garantir_sistema_origem(sigla)
    return SistemaOrigem.query.filter_by(txt_sigla=sigla).first()


def criar_mapeamento(ano, ind_tipo, sigla_origem, itens):
    """`itens`: lista de dicts {seq_qualificador, txt_regra, ind_inversao_sinal?}."""
    from fluxocaixa.services.mapeamento_service import criar_mapeamento as _criar

    sistema = sistema_por_sigla(sigla_origem)
    return _criar(
        num_ano_exercicio=ano,
        ind_tipo=ind_tipo,
        seq_sistema_origem=sistema.seq_sistema_origem,
        dsc_mapeamento=f"Mapeamento {ano}/{ind_tipo}/{sigla_origem}",
        itens=itens,
    )


def mapeamento_por_chave(ano, ind_tipo, sigla_origem):
    from fluxocaixa.models import Mapeamento, SistemaOrigem
    from fluxocaixa.models.base import db

    db.session.expire_all()
    sistema = SistemaOrigem.query.filter_by(txt_sigla=sigla_origem).first()
    if sistema is None:
        return None
    return Mapeamento.query.filter_by(
        num_ano_exercicio=ano,
        ind_tipo=ind_tipo,
        seq_sistema_origem=sistema.seq_sistema_origem,
        ind_status='A',
    ).first()
