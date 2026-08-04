"""Origem única da categoria fiscal de um qualificador (spec cadastros-nucleo R15).

A categoria RESOLVIDA é a marcação do próprio nó ou, na ausência dela, a do
**ancestral marcado mais próximo**. Sem marcação em ancestral algum, o
qualificador não pertence a categoria nenhuma — e não entra em meta nenhuma.

⚠️ **Por que herda**: os lançamentos vivem nas folhas, mas o plano de contas é
pensado por bloco. Marcar folha a folha seria trocar o erro silencioso da
heurística por um erro silencioso manual — esquecer uma folha entre quarenta
subnotifica um piso constitucional, sem aviso.

⚠️ **Por que "mais próximo vence"**: resolve o conflito (folha SAUDE sob bloco
EDUCACAO) sem regra nova, e é o mesmo desempate que a F4.2 usa em
`regra/substituicao.py` ("mais longo vence").

⚠️ **Por que nada disso é persistido**: a categoria resolvida é função da
marcação MAIS da posição na árvore. A F6.4 liberou o reapontamento de pai, que
muda a resposta para a subárvore inteira — uma coluna gravada exigiria
repropagar a cada edição e ficaria errada no primeiro esquecimento. Mesmo
princípio do saldo agregado (F2.1) e do mês da projeção (F6.3).
"""

from ..models import CategoriaFiscal


def categoria_resolvida(qualificador, memo: dict | None = None):
    """`CategoriaFiscal` efetiva do qualificador, ou `None`.

    `memo` é um dicionário `{seq_qualificador: CategoriaFiscal | None}` opcional
    para uso em laços. ⚠️ Ele NÃO é opcional na prática quando se percorre a
    árvore inteira: cada subida toca `pai` (lazy load), então sem memória o
    relatório faz N × profundidade de round-trips. Veja `criar_memo`.
    """
    if qualificador is None:
        return None
    if memo is None:
        memo = {}

    # ⚠️ `vistos` é separado do `memo`: o memo só é gravado DEPOIS do laço, e
    # sem esta marca a subida numa árvore ciclada NÃO TERMINAVA — `caminho`
    # crescia sem limite, consumindo memória junto. Foi um defeito introduzido
    # com esta função na F6.5 e medido na sonda da F6.7.
    caminho = []
    vistos = set()
    no = qualificador
    while no is not None:
        if no.seq_qualificador in memo:
            resolvida = memo[no.seq_qualificador]
            break
        if no.seq_qualificador in vistos:
            raise no._erro_ciclo()
        vistos.add(no.seq_qualificador)
        caminho.append(no)
        if no.cod_categoria_fiscal is not None:
            resolvida = no.categoria_fiscal
            break
        no = no.pai
    else:
        resolvida = None

    # memoiza o caminho inteiro, não só a ponta: os irmãos vão reusá-lo
    for visitado in caminho:
        memo[visitado.seq_qualificador] = resolvida
    return resolvida


def criar_memo() -> dict:
    """Memória para uma passada de relatório. Não sobrevive à requisição."""
    return {}


def siglas_ativas() -> list:
    """Categorias ativas, na ordem de exibição do relatório."""
    return (
        CategoriaFiscal.query.filter_by(ind_status='A')
        .order_by(CategoriaFiscal.seq_categoria_fiscal)
        .all()
    )
