"""AST → expressão SQLAlchemy (spec automacao-lancamentos R7).

Único ponto que fala com o banco. Produz **objetos de expressão**, nunca texto
SQL — é isso que torna a injeção impossível por construção, independentemente do
que o usuário digitou na regra.

Portabilidade: `json_atributos[chave].as_string()` compila para `json_extract`
no SQLite e `->>` no PostgreSQL — o SQLAlchemy resolve o dialeto.
"""
import sqlalchemy as sa

from ...models.etl_staging import EtlStaging
from ...models.termo_regra import COLUNAS_PERMITIDAS, ORIGEM_COLUNA
from ..validacao import RegraNegocioError
from .ast import (
    OP_COMECA_COM,
    OP_DIFERENTE,
    OP_EM,
    OP_IGUAL,
    OP_MAIOR,
    OP_MAIOR_IGUAL,
    OP_MENOR,
    OP_MENOR_IGUAL,
    Campo,
    Comparacao,
    E,
    Nao,
    Ou,
)


def _coluna(campo: Campo):
    """Resolve o campo para uma coluna/expressão da staging."""
    if campo.cod_origem_campo == ORIGEM_COLUNA:
        # Whitelist: sem ela, um termo alcançaria coluna de controle da staging
        # ou um atributo qualquer do model.
        if campo.nom_campo not in COLUNAS_PERMITIDAS:
            raise RegraNegocioError(
                f"O termo '{campo.nom_termo}' aponta para um campo que não é permitido"
            )
        return getattr(EtlStaging, campo.nom_campo)
    # ATRIBUTO: chave do JSON, parametrizada pelo SQLAlchemy
    return EtlStaging.json_atributos[campo.nom_campo].as_string()


def _comparar(no: Comparacao):
    coluna = _coluna(no.campo)
    op, valor = no.operador, no.valor

    if op == OP_COMECA_COM:
        # `começa com` é textual: LIKE 'prefixo%'
        return coluna.like(f"{valor}%")
    if op == OP_EM:
        return coluna.in_([_valor(no.campo, v) for v in valor])

    alvo = _valor(no.campo, valor)
    if op == OP_IGUAL:
        return coluna == alvo
    if op == OP_DIFERENTE:
        return coluna != alvo
    if op == OP_MAIOR:
        return coluna > alvo
    if op == OP_MENOR:
        return coluna < alvo
    if op == OP_MAIOR_IGUAL:
        return coluna >= alvo
    if op == OP_MENOR_IGUAL:
        return coluna <= alvo
    raise RegraNegocioError(f"Operador não suportado: {op}")  # pragma: no cover


def _valor(campo: Campo, valor):
    """Coage o literal ao tipo do campo.

    `json_atributos` guarda a linha CRUA da origem, cujos valores são texto —
    por isso ATRIBUTO compara sempre como string (`.as_string()` do lado da
    coluna). Colunas da whitelist são tipadas de verdade e recebem o literal
    como veio.
    """
    if campo.cod_origem_campo != ORIGEM_COLUNA:
        return str(valor)
    return valor


def renderizar(no):
    """AST → expressão SQLAlchemy booleana."""
    if isinstance(no, Comparacao):
        return _comparar(no)
    if isinstance(no, E):
        return sa.and_(renderizar(no.esquerda), renderizar(no.direita))
    if isinstance(no, Ou):
        return sa.or_(renderizar(no.esquerda), renderizar(no.direita))
    if isinstance(no, Nao):
        return sa.not_(renderizar(no.operando))
    raise RegraNegocioError(f"Nó de regra desconhecido: {no!r}")  # pragma: no cover
