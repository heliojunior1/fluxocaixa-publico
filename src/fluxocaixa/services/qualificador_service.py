import re

from ..models import Lancamento, Qualificador
from ..repositories import qualificador_repository
from .validacao import RegraNegocioError

FORMATO_CODIGO = re.compile(r"^[0-9]+(\.[0-9]+)*$")


def _validar_qualificador(num_qualificador, dsc_qualificador, cod_qualificador_pai,
                          num_ano_exercicio, seq_atual=None):
    """Regras de negócio de qualificador (spec cadastros-nucleo R3 + R25).

    F10.1: unicidade de código e de descrição são POR EXERCÍCIO, entre
    ativos — a mesma rubrica em anos diferentes são linhas diferentes. Pai e
    filho vivem no mesmo exercício (nas duas portas: quem chama passa o ano do
    nó validado).
    """
    num = (num_qualificador or "").strip()
    dsc = (dsc_qualificador or "").strip()

    if not FORMATO_CODIGO.match(num):
        raise RegraNegocioError(
            "Código do qualificador deve conter apenas números separados por pontos"
        )

    duplicado = Qualificador.query.filter_by(
        num_qualificador=num, num_ano_exercicio=num_ano_exercicio,
        ind_status='A',
    ).first()
    if duplicado and duplicado.seq_qualificador != seq_atual:
        raise RegraNegocioError(
            "Já existe um qualificador com este código no exercício "
            f"{num_ano_exercicio}"
        )

    for existente in Qualificador.query.filter_by(
            ind_status='A', num_ano_exercicio=num_ano_exercicio):
        if (
            existente.seq_qualificador != seq_atual
            and (existente.dsc_qualificador or "").strip().lower() == dsc.lower()
        ):
            raise RegraNegocioError("Já existe um qualificador com esta descrição")

    if cod_qualificador_pai is not None:
        pai = Qualificador.query.get(cod_qualificador_pai)
        if pai is None or pai.ind_status != 'A':
            raise RegraNegocioError("Qualificador pai inexistente ou inativo")
        if pai.num_ano_exercicio != num_ano_exercicio:
            raise RegraNegocioError(
                "Pai e filho devem pertencer ao mesmo exercício — o pai "
                f"{pai.num_qualificador} é do exercício {pai.num_ano_exercicio}"
            )
        prefixo = f"{pai.num_qualificador}."
        if not num.startswith(prefixo):
            raise RegraNegocioError(
                f"O código do filho deve começar com o código do pai ({prefixo})"
            )
    return num, dsc


def validar_qualificador_do_exercicio(qualificador, num_ano_exercicio) -> None:
    """Regra de transição da F10.1 (spec R25, decisão D5 do design).

    Invariante-alvo: registro aponta para o qualificador do seu exercício.
    Enquanto não existir plano no exercício do registro (instalação que nunca
    abriu exercício — o estado de TODA instalação até a F10.3), a escrita segue
    como sempre foi. Quando o plano do ano existir, a validação morde.

    Origem única para as três portas (lançamento manual, importação e ajuste
    de cenário) — três cópias divergiriam.
    """
    if qualificador is None or num_ano_exercicio is None:
        return
    if qualificador.num_ano_exercicio == num_ano_exercicio:
        return
    existe_plano = Qualificador.query.filter_by(
        num_ano_exercicio=num_ano_exercicio, ind_status='A'
    ).first() is not None
    if existe_plano:
        raise RegraNegocioError(
            f"O qualificador {qualificador.num_qualificador} é do exercício "
            f"{qualificador.num_ano_exercicio}, mas o registro é do exercício "
            f"{num_ano_exercicio} — use o plano de {num_ano_exercicio}"
        )

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

    # F10.1: a colisão que importa é DENTRO do exercício do nó editado — o
    # mesmo código em outro exercício é convivência legítima (R25).
    editado = Qualificador.query.get(seq_editado)
    tocados = set(mapa) | {seq_editado}
    colisoes = [
        q.num_qualificador
        for q in Qualificador.query.filter(
            Qualificador.num_qualificador.in_(gerados),
            Qualificador.num_ano_exercicio == editado.num_ano_exercicio,
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


def exercicios_com_plano() -> list[int]:
    """Exercícios com pelo menos um qualificador ativo, mais recente primeiro
    (F10.4, R28)."""
    from ..models import db

    linhas = (
        db.session.query(Qualificador.num_ano_exercicio)
        .filter(Qualificador.ind_status == 'A')
        .distinct()
        .all()
    )
    return sorted((ano for (ano,) in linhas), reverse=True)


def resolver_exercicio_do_plano(ano: int) -> int | None:
    """ORIGEM ÚNICA de "qual plano vale para o ano X" (F10.4, R28/D1).

    Plano do próprio ano quando existir; senão o mais recente ANTERIOR; senão
    o mais antigo posterior. Racional: registros de ano sem plano próprio
    apontam para o plano base (decisão D1 da F10.1) — um relatório de 2024
    numa base cujo único plano é 2026 tem de usar o plano de 2026, que é onde
    os lançamentos de 2024 apontam. `None` só quando não há plano algum.
    """
    anos = exercicios_com_plano()
    if not anos:
        return None
    if ano in anos:
        return ano
    anteriores = [a for a in anos if a < ano]
    if anteriores:
        return max(anteriores)
    return min(a for a in anos if a > ano)


def exercicio_corrente() -> int | None:
    """Exercício resolvido para o ano do relógio — o default de toda tela sem
    contexto de ano próprio (F10.4, R28)."""
    from datetime import date

    return resolver_exercicio_do_plano(date.today().year)


def list_all_qualificadores(num_ano_exercicio: int | None = None):
    return qualificador_repository.get_all_qualificadores(num_ano_exercicio)

def list_active_qualificadores(num_ano_exercicio: int | None = None):
    return qualificador_repository.get_active_qualificadores(num_ano_exercicio)

def list_root_qualificadores(num_ano_exercicio: int | None = None):
    return qualificador_repository.get_root_qualificadores(num_ano_exercicio)

def get_qualificador(qualificador_id: int):
    return qualificador_repository.get_qualificador_by_id(qualificador_id)

def get_qualificador_by_name(name: str):
    return qualificador_repository.get_qualificador_by_name(name)

def list_receita_qualificadores(num_ano_exercicio: int | None = None):
    return qualificador_repository.get_receita_qualificadores(num_ano_exercicio)

def list_despesa_qualificadores(num_ano_exercicio: int | None = None):
    return qualificador_repository.get_despesa_qualificadores(num_ano_exercicio)

def list_receita_qualificadores_folha(num_ano_exercicio: int | None = None):
    """Retorna apenas qualificadores de receita que não têm filhos."""
    return qualificador_repository.get_receita_qualificadores_folha(num_ano_exercicio)

def list_despesa_qualificadores_folha(num_ano_exercicio: int | None = None):
    """Retorna apenas qualificadores de despesa que não têm filhos."""
    return qualificador_repository.get_despesa_qualificadores_folha(num_ano_exercicio)

def create_qualificador(num_qualificador: str, dsc_qualificador: str,
                        cod_qualificador_pai: int = None,
                        confirmado: bool = False,
                        cod_categoria_fiscal: int = None,
                        num_ano_exercicio: int = None,
                        cod_rubrica_raiz: int = None):
    from datetime import date

    # F10.1 (R25): sem ano informado (telas até a F10.4), o plano corrente.
    if num_ano_exercicio is None:
        num_ano_exercicio = date.today().year
    num_qualificador, dsc_qualificador = _validar_qualificador(
        num_qualificador, dsc_qualificador, cod_qualificador_pai,
        num_ano_exercicio,
    )
    # F10.5 (R30): raiz herdada é decisão humana validada — existir e não
    # estar em uso por ativo do mesmo exercício.
    if cod_rubrica_raiz is not None:
        _validar_raiz_herdada(cod_rubrica_raiz, num_ano_exercicio)
    _confirmar_folha_vira_pai(cod_qualificador_pai, confirmado)
    qualificador = Qualificador(
        num_qualificador=num_qualificador,
        dsc_qualificador=dsc_qualificador,
        cod_qualificador_pai=cod_qualificador_pai,
        # ⚠️ Marcação NÃO exige folha, ao contrário de lançamento/ajuste/
        # mapeamento (R12–R14): marcar o BLOCO e as folhas herdarem é o
        # propósito da regra (R15). Exceção deliberada, não descuido.
        cod_categoria_fiscal=cod_categoria_fiscal,
        num_ano_exercicio=num_ano_exercicio,
        # R26: nula ⇒ o evento after_insert grava o próprio seq; a cópia de
        # exercício (F10.3) e a herança (F10.5) passam a raiz explicitamente.
        cod_rubrica_raiz=cod_rubrica_raiz,
        cod_pessoa_inclusao=_autor(),
    )
    return qualificador_repository.create_qualificador(qualificador)


def _autor() -> int:
    from ..auth.contexto import cod_pessoa_atual

    return cod_pessoa_atual()


def _validar_raiz_herdada(cod_rubrica_raiz: int, num_ano_exercicio: int) -> None:
    """Herança da identidade estável (spec R30 — C3/C4/C7 da concepção).

    A raiz herdada tem de EXISTIR (apontar série de alguém) e NÃO pode estar
    em uso por qualificador ATIVO do mesmo exercício — duas rubricas ativas do
    mesmo ano com a mesma raiz somariam a série em dobro. Inativa do mesmo ano
    não bloqueia: herdar dela é exatamente a reativação (C7).
    """
    existe = Qualificador.query.filter_by(
        cod_rubrica_raiz=cod_rubrica_raiz).first()
    if existe is None:
        raise RegraNegocioError(
            "A raiz de rubrica informada para herança não existe"
        )
    em_uso = Qualificador.query.filter_by(
        cod_rubrica_raiz=cod_rubrica_raiz,
        num_ano_exercicio=num_ano_exercicio,
        ind_status='A',
    ).first()
    if em_uso is not None:
        raise RegraNegocioError(
            f"A raiz de rubrica já está em uso por "
            f"{em_uso.num_qualificador} — {em_uso.dsc_qualificador} no "
            f"exercício {num_ano_exercicio}; duas rubricas ativas com a mesma "
            "raiz somariam a série histórica em dobro"
        )


def candidatas_para_heranca(ano_tela: int) -> list[Qualificador]:
    """Rubricas cuja raiz pode ser herdada por uma criação em `ano_tela`
    (spec R30/D3): ativas do exercício ANTERIOR resolvido + inativas do
    próprio exercício (reativação C7), excluindo raízes já em uso por ativos
    de `ano_tela`."""
    raizes_em_uso = {
        q.cod_rubrica_raiz
        for q in Qualificador.query.filter_by(
            num_ano_exercicio=ano_tela, ind_status='A').all()
    }
    candidatas: list[Qualificador] = []
    ano_anterior = resolver_exercicio_do_plano(ano_tela - 1)
    if ano_anterior is not None and ano_anterior != ano_tela:
        candidatas.extend(Qualificador.query.filter_by(
            num_ano_exercicio=ano_anterior, ind_status='A'
        ).order_by(Qualificador.num_qualificador).all())
    candidatas.extend(Qualificador.query.filter_by(
        num_ano_exercicio=ano_tela, ind_status='I'
    ).order_by(Qualificador.num_qualificador).all())
    return [c for c in candidatas
            if c.cod_rubrica_raiz not in raizes_em_uso]


def abrir_exercicio(ano_origem: int, ano_novo: int,
                    confirmado: bool = False) -> int:
    """Abre o exercício `ano_novo` como CÓPIA por valor do plano de
    `ano_origem` (spec cadastros-nucleo R29 — decisão D-A da concepção).

    Só ATIVOS entram (A.2); a cópia carrega hierarquia (pai remapeado para o
    espelho), marcação PRÓPRIA de categoria fiscal e `cod_rubrica_raiz` (A.3
    — a cópia é o veículo da identidade estável; NUNCA a categoria resolvida,
    que congelaria a herança). LOA/dotação/programação ficam onde estão —
    estrutura, nunca saldo (A.4). Abrir para ano que já tem plano ativo é
    recusado (A.5 — abertura, não sincronização: uma "segunda cópia"
    sobrescreveria meses de edição do ciclo do PLOA).

    Transação ÚNICA: falha no meio não deixa exercício pela metade (padrão
    `confirmar_lote` da F7.2). Devolve o número de qualificadores criados.
    """
    from ..models import db

    origem = Qualificador.query.filter_by(
        num_ano_exercicio=ano_origem, ind_status='A'
    ).order_by(Qualificador.num_qualificador).all()
    if not origem:
        raise RegraNegocioError(
            f"O exercício {ano_origem} não tem plano ativo — não há o que copiar"
        )
    existente = Qualificador.query.filter_by(
        num_ano_exercicio=ano_novo, ind_status='A').first()
    if existente is not None:
        raise RegraNegocioError(
            f"O exercício {ano_novo} já possui plano — a abertura é uma "
            "cópia única, não uma sincronização"
        )
    if not confirmado:
        raise RegraNegocioError(
            f"A abertura copia {len(origem)} qualificador(es) de "
            f"{ano_origem} para {ano_novo} — confirme para continuar"
        )

    autor = _autor()
    try:
        # Passada 1: cria as linhas SEM pai, montando o mapa origem → espelho.
        # O remapeamento por mapa (e não por código) resiste a dado legado cujo
        # código não deriva do pai — caso real da F6.4.
        espelhos: dict[int, Qualificador] = {}
        for q in origem:
            espelho = Qualificador(
                num_qualificador=q.num_qualificador,
                dsc_qualificador=q.dsc_qualificador,
                cod_categoria_fiscal=q.cod_categoria_fiscal,
                num_ano_exercicio=ano_novo,
                cod_rubrica_raiz=q.cod_rubrica_raiz,
                cod_pessoa_inclusao=autor,
                ind_status='A',
            )
            db.session.add(espelho)
            espelhos[q.seq_qualificador] = espelho
        db.session.flush()

        # Passada 2: pais remapeados pelo mapa. Pai inativo (não copiado —
        # A.2) deixa o filho como raiz no ano novo, visível em tela.
        for q in origem:
            if q.cod_qualificador_pai is not None:
                espelho_pai = espelhos.get(q.cod_qualificador_pai)
                if espelho_pai is not None:
                    espelhos[q.seq_qualificador].cod_qualificador_pai = (
                        espelho_pai.seq_qualificador)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return len(espelhos)

def update_qualificador(seq_qualificador: int, num_qualificador: str,
                        dsc_qualificador: str, cod_qualificador_pai: int = None,
                        confirmado: bool = False,
                        cod_categoria_fiscal: int = None):
    qualificador = qualificador_repository.get_qualificador_by_id(seq_qualificador)
    if not qualificador:
        return None

    _validar_sem_ciclo(seq_qualificador, cod_qualificador_pai)
    # F10.1: o exercício é IMUTÁVEL na edição (mover um nó de ano seria
    # reescrever história) — valida-se contra o ano que o nó já tem. A raiz
    # (R26) tampouco é exposta aqui: renome/renumeração/reapontamento nunca a
    # tocam.
    num_qualificador, dsc_qualificador = _validar_qualificador(
        num_qualificador, dsc_qualificador, cod_qualificador_pai,
        qualificador.num_ano_exercicio, seq_atual=seq_qualificador
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
