"""Ida e volta entre o builder de linhas e o texto da regra (spec R10).

O **texto é a verdade** (`txt_regra`): o builder só gera texto, e o servidor
valida com o mesmo `validar_regra` de sempre — uma única definição de "regra
válida".

A volta (texto → linhas) reusa o `parsear` que já existe: a regra é
representável no builder quando é uma comparação, ou uma cadeia de UM único
conectivo apenas entre comparações. `não`, parênteses aninhados e conectivos
misturados abrem no modo avançado, sem perda.
"""
from .ast import (
    OP_COMECA_COM,
    OP_EM,
    ROTULO_OP,
    Comparacao,
    E,
    Nao,
    Ou,
)
from ..validacao import RegraNegocioError
from .parser import parsear

# Rótulo pt-BR de cada operador, para os selects do builder
ROTULOS_OPERADOR = [
    {'valor': chave, 'rotulo': rotulo} for chave, rotulo in ROTULO_OP.items()
]

_POR_ROTULO = {rotulo: chave for chave, rotulo in ROTULO_OP.items()}


def _literal(valor: str) -> str:
    """Valor → literal da gramática.

    A gramática não define escape de aspas simples (`texto.find("'", ...)`), então
    um valor com apóstrofo geraria texto inparseável. Recusamos explicitamente em
    vez de deixar o parser reclamar de "aspas não fechadas" — o usuário nunca
    digitou aspas. Limitação conhecida e documentada.
    """
    texto = str(valor).strip()
    if "'" in texto:
        raise RegraNegocioError(
            "O valor não pode conter apóstrofo — a regra não suporta esse caractere"
        )
    if not texto:
        raise RegraNegocioError("Informe o valor da comparação")
    # número entra sem aspas; o resto vira literal de texto
    if _eh_numero(texto):
        return texto
    return f"'{texto}'"


def _eh_numero(texto: str) -> bool:
    try:
        float(texto)
        return True
    except ValueError:
        return False


def montar_regra(linhas: list[dict], conectivo: str) -> str:
    """Linhas do builder → `txt_regra`.

    `linhas`: [{nom_termo, operador (chave da AST), valor}]. Para `em`, o valor
    é uma lista separada por vírgula.
    """
    if not linhas:
        raise RegraNegocioError("Informe ao menos uma condição")
    if conectivo not in ('e', 'ou'):
        raise RegraNegocioError(f"Conectivo inválido: '{conectivo}'")

    partes = []
    for linha in linhas:
        termo = (linha.get('nom_termo') or '').strip()
        operador = linha.get('operador')
        if not termo:
            raise RegraNegocioError("Informe o termo da condição")
        if operador not in ROTULO_OP:
            raise RegraNegocioError(f"Operador inválido: '{operador}'")

        rotulo = ROTULO_OP[operador]
        if operador == OP_EM:
            valores = [v for v in str(linha.get('valor', '')).split(',') if v.strip()]
            if not valores:
                raise RegraNegocioError("Informe ao menos um valor para 'em'")
            lista = ', '.join(_literal(v) for v in valores)
            partes.append(f"{termo} em ({lista})")
        else:
            partes.append(f"{termo} {rotulo} {_literal(linha.get('valor', ''))}")

    return f" {conectivo} ".join(partes)


def regra_para_builder(txt_regra: str | None) -> dict:
    """`txt_regra` → estado da tela: `{modo, conectivo, linhas}`.

    Modo `builder` quando representável em linhas; senão `avancado`.
    """
    vazio = {'modo': 'builder', 'conectivo': 'e', 'linhas': []}
    if not txt_regra or not txt_regra.strip():
        return vazio

    try:
        no = parsear(txt_regra)
    except RegraNegocioError:
        # regra que não parseia (termo inativado depois, por ex.): o usuário
        # precisa ver e consertar o texto original
        return {'modo': 'avancado', 'conectivo': 'e', 'linhas': []}

    plano = _achatar(no)
    if plano is None:
        return {'modo': 'avancado', 'conectivo': 'e', 'linhas': []}
    conectivo, comparacoes = plano
    return {
        'modo': 'builder',
        'conectivo': conectivo,
        'linhas': [_linha(c) for c in comparacoes],
    }


def _achatar(no):
    """AST → (conectivo, [Comparacao]) se for plana; senão None.

    Plana = comparação única, ou cadeia de UM único conectivo só entre
    comparações. Basta um `Nao` ou uma mistura de `e`/`ou` para não ser.
    """
    if isinstance(no, Comparacao):
        return 'e', [no]
    if isinstance(no, Nao):
        return None
    if isinstance(no, (E, Ou)):
        conectivo = 'e' if isinstance(no, E) else 'ou'
        comparacoes = []
        for lado in (no.esquerda, no.direita):
            if isinstance(lado, Comparacao):
                comparacoes.append(lado)
                continue
            sub = _achatar(lado)
            # sub-árvore de outro conectivo (ou com Nao) → não é plana
            if sub is None or sub[0] != conectivo:
                return None
            comparacoes.extend(sub[1])
        return conectivo, comparacoes
    return None


def _linha(comparacao: Comparacao) -> dict:
    valor = comparacao.valor
    if comparacao.operador == OP_EM:
        valor = ', '.join(str(v) for v in valor)
    return {
        'nom_termo': comparacao.campo.nom_termo,
        'operador': comparacao.operador,
        'valor': str(valor),
    }


__all__ = ['montar_regra', 'regra_para_builder', 'ROTULOS_OPERADOR']
