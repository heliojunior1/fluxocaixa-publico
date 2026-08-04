from ..models import Qualificador, db


def get_all_qualificadores():
    return Qualificador.query.order_by(Qualificador.num_qualificador).all()

def get_active_qualificadores():
    return Qualificador.query.filter_by(ind_status='A').order_by(Qualificador.num_qualificador).all()

def get_root_qualificadores():
    return Qualificador.query.filter_by(ind_status='A', cod_qualificador_pai=None).order_by(Qualificador.num_qualificador).all()

def get_qualificador_by_id(qualificador_id: int):
    return Qualificador.query.get(qualificador_id)

def get_qualificadores_by_ids(ids: list[int]):
    return Qualificador.query.filter(
        Qualificador.seq_qualificador.in_(ids)
    ).all()

def get_qualificador_by_name(name: str):
    from sqlalchemy import func
    return Qualificador.query.filter(func.lower(Qualificador.dsc_qualificador) == name.lower()).first()

def get_receita_qualificadores():
    return Qualificador.query.filter(
        Qualificador.num_qualificador.startswith('1'),
        Qualificador.ind_status == 'A',
    ).order_by(Qualificador.num_qualificador).all()

def get_despesa_qualificadores():
    return Qualificador.query.filter(
        Qualificador.num_qualificador.startswith('2'),
        Qualificador.ind_status == 'A',
    ).order_by(Qualificador.num_qualificador).all()

def _folhas(raiz: str):
    """Folhas ativas sob uma raiz, pela ORIGEM ÚNICA `Qualificador.is_folha()`.

    ⚠️ Antes (F6.4) cada uma destas listas recalculava folha por conta própria,
    montando o conjunto de pais A PARTIR DO RECORTE por prefixo do código:

        todos    = filter(num_qualificador.startswith('1'), ...)
        ids_pais = {q.cod_qualificador_pai for q in todos}
        folhas   = [q for q in todos if q.seq not in ids_pais]

    Um filho cujo código não casa com o prefixo do pai — dado legado, ou o
    resultado de reapontar o pai numa edição, que não revalida a subárvore —
    nunca entrava em `ids_pais`. O pai era listado como folha aqui e recusado
    pela validação de lançamento: a mesma pergunta com duas respostas. Mesmo
    padrão que a F6.1 resolveu com `valor_com_sinal` e a F6.3 com
    `periodo_resolver`.

    O custo é o N+1 de `is_folha()` (toca `filhos`), já pago hoje em
    `web/relatorios.py`, `web/base.py` e `web/loa.py`. Um `NOT EXISTS` em SQL
    seria uma TERCEIRA definição de folha — exatamente o que se está
    eliminando.
    """
    todos = Qualificador.query.filter(
        Qualificador.num_qualificador.startswith(raiz),
        Qualificador.ind_status == 'A',
    ).order_by(Qualificador.num_qualificador).all()
    return [q for q in todos if q.is_folha()]


def get_receita_qualificadores_folha():
    """Qualificadores de receita que são folha (sem filhos ativos)."""
    return _folhas('1')

def get_despesa_qualificadores_folha():
    """Qualificadores de despesa que são folha (sem filhos ativos)."""
    return _folhas('2')

def create_qualificador(qualificador: Qualificador):
    db.session.add(qualificador)
    db.session.commit()
    return qualificador

def update_qualificador(qualificador: Qualificador):
    db.session.commit()
    return qualificador

def delete_qualificador_logical(qualificador_id: int):
    qualificador = get_qualificador_by_id(qualificador_id)
    if qualificador:
        qualificador.ind_status = 'I'
        db.session.commit()
    return qualificador

def count_qualificadores():
    return Qualificador.query.count()

def get_qualificadores_limit(limit: int):
    return Qualificador.query.limit(limit).all()
