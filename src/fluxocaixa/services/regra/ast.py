"""Nós da AST da regra de classificação (spec automacao-lancamentos R7).

A AST é o **contrato** entre o parser e o renderer: o parser só produz nós
validados e o renderer é o único ponto que fala com o banco. Nenhum estágio
constrói texto SQL — é isso que fecha, por construção, a injeção que a
implementação de referência tem (lá o `txt_regra` é SQL cru concatenado).
"""
from dataclasses import dataclass
from typing import Union

# Operadores de comparação da gramática (rótulo em pt-BR → chave interna)
OP_IGUAL = 'IGUAL'
OP_DIFERENTE = 'DIFERENTE'
OP_COMECA_COM = 'COMECA_COM'
OP_MAIOR = 'MAIOR'
OP_MENOR = 'MENOR'
OP_MAIOR_IGUAL = 'MAIOR_IGUAL'
OP_MENOR_IGUAL = 'MENOR_IGUAL'
OP_EM = 'EM'

# Rótulo pt-BR de cada operador, para mensagens de erro
ROTULO_OP = {
    OP_IGUAL: '=',
    OP_DIFERENTE: '<>',
    OP_COMECA_COM: 'começa com',
    OP_MAIOR: '>',
    OP_MENOR: '<',
    OP_MAIOR_IGUAL: '>=',
    OP_MENOR_IGUAL: '<=',
    OP_EM: 'em',
}

# Operadores aceitos por tipo de termo (TermoRegra.cod_tipo).
# `começa com` é textual; comparadores de ordem não fazem sentido em TEXTO.
OPS_POR_TIPO = {
    'TEXTO': {OP_IGUAL, OP_DIFERENTE, OP_COMECA_COM, OP_EM},
    'NUMERO': {OP_IGUAL, OP_DIFERENTE, OP_MAIOR, OP_MENOR,
               OP_MAIOR_IGUAL, OP_MENOR_IGUAL, OP_EM},
    'DATA': {OP_IGUAL, OP_DIFERENTE, OP_MAIOR, OP_MENOR,
             OP_MAIOR_IGUAL, OP_MENOR_IGUAL},
}


@dataclass(frozen=True)
class Campo:
    """Referência resolvida a um campo da staging (via `flc_termo_regra`)."""

    nom_termo: str        # rótulo original, para mensagens
    cod_origem_campo: str  # COLUNA | ATRIBUTO
    nom_campo: str        # coluna (whitelist) ou chave do json_atributos
    cod_tipo: str         # TEXTO | NUMERO | DATA


@dataclass(frozen=True)
class Comparacao:
    campo: Campo
    operador: str
    valor: str | int | float | list


@dataclass(frozen=True)
class E:
    esquerda: 'No'
    direita: 'No'


@dataclass(frozen=True)
class Ou:
    esquerda: 'No'
    direita: 'No'


@dataclass(frozen=True)
class Nao:
    operando: 'No'


No = Union[Comparacao, E, Ou, Nao]
