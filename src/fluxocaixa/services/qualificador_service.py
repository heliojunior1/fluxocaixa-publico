import re

from ..models import Lancamento, Qualificador
from ..repositories import qualificador_repository
from .validacao import RegraNegocioError

FORMATO_CODIGO = re.compile(r"^[0-9]+(\.[0-9]+)*$")


def _validar_qualificador(num_qualificador, dsc_qualificador, cod_qualificador_pai, seq_atual=None):
    """Regras de negócio de qualificador (spec cadastros-nucleo R3)."""
    num = (num_qualificador or "").strip()
    dsc = (dsc_qualificador or "").strip()

    if not FORMATO_CODIGO.match(num):
        raise RegraNegocioError(
            "Código do qualificador deve conter apenas números separados por pontos"
        )

    duplicado = Qualificador.query.filter_by(num_qualificador=num).first()
    if duplicado and duplicado.seq_qualificador != seq_atual:
        raise RegraNegocioError("Já existe um qualificador com este código")

    for existente in Qualificador.query.filter_by(ind_status='A'):
        if (
            existente.seq_qualificador != seq_atual
            and (existente.dsc_qualificador or "").strip().lower() == dsc.lower()
        ):
            raise RegraNegocioError("Já existe um qualificador com esta descrição")

    if cod_qualificador_pai is not None:
        pai = Qualificador.query.get(cod_qualificador_pai)
        if pai is None or pai.ind_status != 'A':
            raise RegraNegocioError("Qualificador pai inexistente ou inativo")
        prefixo = f"{pai.num_qualificador}."
        if not num.startswith(prefixo):
            raise RegraNegocioError(
                f"O código do filho deve começar com o código do pai ({prefixo})"
            )
    return num, dsc

def _validar_sem_ciclo(seq_qualificador, cod_qualificador_pai) -> None:
    """Recusa apontar um nó para si mesmo ou para um descendente (spec R16).

    Sobe do pai PROPOSTO até a raiz: se o nó editado aparecer no caminho, o
    reapontamento fecharia um ciclo.

    ⚠️ A auto-referência era recusada só POR ACIDENTE do prefixo — `"7.1"` não
    começa com `"7.1."`. Acidente que protege não é guarda: some no dia em que o
    esquema de código mudar.

    ⚠️ A regra do prefixo (R3) valida apenas o nó editado, então renomeá-lo para
    caber sob o próprio descendente passava na validação e criava o ciclo — o
    que a sonda da F6.7 confirmou.
    """
    if cod_qualificador_pai is None or seq_qualificador is None:
        return
    if cod_qualificador_pai == seq_qualificador:
        raise RegraNegocioError(
            "Um qualificador não pode ser pai de si mesmo")

    no = Qualificador.query.get(cod_qualificador_pai)
    vistos = set()
    while no is not None:
        if no.seq_qualificador == seq_qualificador:
            raise RegraNegocioError(
                "A hierarquia não pode ter ciclo: o qualificador escolhido "
                "como pai está abaixo do que está sendo alterado"
            )
        if no.seq_qualificador in vistos:
            # árvore JÁ ciclada — a própria guarda não pode travar
            raise no._erro_ciclo()
        vistos.add(no.seq_qualificador)
        no = no.pai


def _planejar_cascata(qualificador, novo_codigo: str) -> dict:
    """Mapa `seq → código novo` da subárvore, para o R17.

    Reapontar `1.2` (filhos `1.2.1`, `1.2.2`) para debaixo de `3`, renomeando-o
    para `3.5`, deixaria os filhos em `1.2.*` sob um pai `3.*`: o invariante do
    R3 ("o código do filho começa com o do pai") vale só para o nó editado, e a
    subárvore nunca era revisitada.

    Devolve `{}` quando não há o que renomear (folha, ou código inalterado).
    """
    antigo = qualificador.num_qualificador
    if novo_codigo == antigo:
        return {}
    mapa = {}
    for descendente in qualificador.get_todos_filhos():
        sufixo = descendente.num_qualificador[len(antigo):]
        mapa[descendente.seq_qualificador] = f"{novo_codigo}{sufixo}"
    return mapa


def _validar_cascata(mapa: dict, seq_editado: int, novo_codigo: str) -> None:
    """Valida a cascata INTEIRA antes de qualquer gravação.

    ⚠️ Aplicar em ordem e falhar no meio deixaria a árvore pela metade — parte
    dos códigos novos, parte dos antigos, e o invariante quebrado nos dois
    sentidos. Por isso a checagem é do mapa completo, contra o banco E contra
    os próprios códigos gerados.
    """
    if not mapa:
        return
    gerados = list(mapa.values()) + [novo_codigo]
    repetidos = {c for c in gerados if gerados.count(c) > 1}
    if repetidos:
        raise RegraNegocioError(
            f"A renomeação geraria códigos duplicados: {', '.join(sorted(repetidos))}"
        )

    tocados = set(mapa) | {seq_editado}
    colisoes = [
        q.num_qualificador
        for q in Qualificador.query.filter(
            Qualificador.num_qualificador.in_(gerados)
        ).all()
        if q.seq_qualificador not in tocados
    ]
    if colisoes:
        raise RegraNegocioError(
            "Já existe qualificador com o código "
            f"{', '.join(sorted(colisoes))} — a renomeação foi cancelada"
        )


def _confirmar_cascata(mapa: dict, confirmado: bool) -> None:
    """Renomear a subárvore é consequente demais para acontecer sem o usuário
    ver — mesmo padrão de confirmação do R4/R13. Folha não pede nada."""
    if mapa and not confirmado:
        raise RegraNegocioError(
            f"A alteração renomeia {len(mapa)} qualificador(es) abaixo deste — "
            "confirme para continuar"
        )


def _confirmar_folha_vira_pai(cod_qualificador_pai, confirmado: bool,
                              seq_movido=None):
    """Aviso ao transformar folha COM LANÇAMENTOS em pai (spec R13).

    Uma folha morre por DUAS portas — criar filho sob ela, e reapontar um nó
    existente para ela. Guardar só a primeira seria ilusão de guarda: o mesmo
    estado final entra pela segunda sem um aviso sequer.

    O gatilho são os LANÇAMENTOS do futuro pai, não "ele é folha": nó que já é
    pai ganhar mais um filho não muda nada e não pede confirmação.

    ⚠️ O aviso avisa e deixa passar — é o que o plano pede. Depois do "sim" o
    lançamento continua num nó que virou pai, e o DFC segue mostrando
    `próprio + filhos` no realizado contra `só filhos` no projetado para essa
    célula (`dfc_service._recompor_pais`). Limitação conhecida, card próprio.
    """
    if cod_qualificador_pai is None or confirmado:
        return
    pai = Qualificador.query.get(cod_qualificador_pai)
    if pai is None:
        return
    filhos_ativos = [
        f for f in pai.filhos
        if f.ind_status == 'A' and f.seq_qualificador != seq_movido
    ]
    if filhos_ativos:
        return  # já era pai — nada muda
    lancamentos = Lancamento.query.filter_by(
        seq_qualificador=cod_qualificador_pai, ind_status='A'
    ).count()
    if lancamentos:
        raise RegraNegocioError(
            f"O qualificador {pai.num_qualificador} tem {lancamentos} "
            "lançamento(s) e deixará de ser folha, saindo das listas de "
            "seleção — confirme para continuar"
        )


def list_all_qualificadores():
    return qualificador_repository.get_all_qualificadores()

def list_active_qualificadores():
    return qualificador_repository.get_active_qualificadores()

def list_root_qualificadores():
    return qualificador_repository.get_root_qualificadores()

def get_qualificador(qualificador_id: int):
    return qualificador_repository.get_qualificador_by_id(qualificador_id)

def get_qualificador_by_name(name: str):
    return qualificador_repository.get_qualificador_by_name(name)

def list_receita_qualificadores():
    return qualificador_repository.get_receita_qualificadores()

def list_despesa_qualificadores():
    return qualificador_repository.get_despesa_qualificadores()

def list_receita_qualificadores_folha():
    """Retorna apenas qualificadores de receita que não têm filhos."""
    return qualificador_repository.get_receita_qualificadores_folha()

def list_despesa_qualificadores_folha():
    """Retorna apenas qualificadores de despesa que não têm filhos."""
    return qualificador_repository.get_despesa_qualificadores_folha()

def create_qualificador(num_qualificador: str, dsc_qualificador: str,
                        cod_qualificador_pai: int = None,
                        confirmado: bool = False,
                        cod_categoria_fiscal: int = None):
    num_qualificador, dsc_qualificador = _validar_qualificador(
        num_qualificador, dsc_qualificador, cod_qualificador_pai
    )
    _confirmar_folha_vira_pai(cod_qualificador_pai, confirmado)
    qualificador = Qualificador(
        num_qualificador=num_qualificador,
        dsc_qualificador=dsc_qualificador,
        cod_qualificador_pai=cod_qualificador_pai,
        # ⚠️ Marcação NÃO exige folha, ao contrário de lançamento/ajuste/
        # mapeamento (R12–R14): marcar o BLOCO e as folhas herdarem é o
        # propósito da regra (R15). Exceção deliberada, não descuido.
        cod_categoria_fiscal=cod_categoria_fiscal,
    )
    return qualificador_repository.create_qualificador(qualificador)

def update_qualificador(seq_qualificador: int, num_qualificador: str,
                        dsc_qualificador: str, cod_qualificador_pai: int = None,
                        confirmado: bool = False,
                        cod_categoria_fiscal: int = None):
    qualificador = qualificador_repository.get_qualificador_by_id(seq_qualificador)
    if not qualificador:
        return None

    _validar_sem_ciclo(seq_qualificador, cod_qualificador_pai)
    num_qualificador, dsc_qualificador = _validar_qualificador(
        num_qualificador, dsc_qualificador, cod_qualificador_pai, seq_atual=seq_qualificador
    )

    # R17: a subárvore acompanha o novo código. Planeja → confirma → valida →
    # só então grava.
    cascata = _planejar_cascata(qualificador, num_qualificador)
    _confirmar_cascata(cascata, confirmado)
    _validar_cascata(cascata, seq_qualificador, num_qualificador)
    # `seq_movido` fora da contagem: se o nó JÁ era filho deste pai, ele não
    # está transformando folha em pai — está só sendo editado no lugar.
    if cod_qualificador_pai != qualificador.cod_qualificador_pai:
        _confirmar_folha_vira_pai(cod_qualificador_pai, confirmado,
                                  seq_movido=seq_qualificador)
    qualificador.num_qualificador = num_qualificador
    qualificador.dsc_qualificador = dsc_qualificador
    qualificador.cod_qualificador_pai = cod_qualificador_pai
    qualificador.cod_categoria_fiscal = cod_categoria_fiscal

    if cascata:
        for descendente in qualificador.get_todos_filhos():
            novo = cascata.get(descendente.seq_qualificador)
            if novo:
                descendente.num_qualificador = novo

    return qualificador_repository.update_qualificador(qualificador)

def delete_qualificador(seq_qualificador: int, confirmado: bool = False):
    """Inativação com guardas (spec cadastros-nucleo R3/R4)."""
    qualificador = qualificador_repository.get_qualificador_by_id(seq_qualificador)
    if qualificador is None:
        raise RegraNegocioError("Qualificador inexistente")

    filhos_ativos = Qualificador.query.filter_by(
        cod_qualificador_pai=seq_qualificador, ind_status='A'
    ).count()
    if filhos_ativos:
        raise RegraNegocioError("Qualificador possui filhos ativos")

    lancamentos = Lancamento.query.filter_by(
        seq_qualificador=seq_qualificador, ind_status='A'
    ).count()
    if lancamentos and not confirmado:
        raise RegraNegocioError(
            "Qualificador possui lançamentos vinculados — confirme a exclusão"
        )

    return qualificador_repository.delete_qualificador_logical(seq_qualificador)
