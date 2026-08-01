"""Resolução de termos de negócio → campo da staging (spec R7).

A implementação de referência faz `re.sub(r'\\b<termo>\\b', coluna)` sobre o
texto inteiro, com os termos ordenados por comprimento decrescente. A ordenação
existe por um motivo real: sem ela, o termo "Unidade Gestora" comeria o prefixo
de "Unidade Gestora Emitente".

Aqui a **semântica é a mesma** (fronteira de palavra + mais longo vence), mas o
casamento acontece durante a tokenização, não num passe textual antes dela.
Motivo: `re.sub` cego também substitui termo dentro de literal — em
`Natureza = 'Unidade Gestora'` o texto entre aspas seria corrompido. O lexer
consome literais primeiro, então isso não acontece.
"""
from ...models.termo_regra import COLUNAS_PERMITIDAS, ORIGEM_COLUNA, TermoRegra
from .ast import Campo


def carregar_termos() -> list[tuple[str, Campo]]:
    """Termos ATIVOS, ordenados por comprimento DECRESCENTE (mais longo vence)."""
    termos = TermoRegra.query.filter_by(ind_status='A').all()
    pares = [
        (t.nom_termo, Campo(
            nom_termo=t.nom_termo,
            cod_origem_campo=t.cod_origem_campo,
            nom_campo=t.nom_campo,
            cod_tipo=t.cod_tipo,
        ))
        for t in termos
        # Defesa em profundidade: um termo COLUNA fora da whitelist (gravado
        # antes de a whitelist existir, ou por caminho não validado) é ignorado
        # em vez de virar acesso a coluna de controle.
        if t.cod_origem_campo != ORIGEM_COLUNA or t.nom_campo in COLUNAS_PERMITIDAS
    ]
    pares.sort(key=lambda par: len(par[0]), reverse=True)
    return pares


def _eh_caractere_de_palavra(ch: str) -> bool:
    return ch.isalnum() or ch == '_'


def casar_termo(texto: str, pos: int, termos: list[tuple[str, Campo]]):
    """Tenta casar um termo em `texto[pos:]`, respeitando fronteira de palavra.

    Devolve `(Campo, pos_final)` ou `None`. Como `termos` vem ordenado por
    comprimento decrescente, o primeiro que casar é o mais longo possível.
    """
    for nom_termo, campo in termos:
        fim = pos + len(nom_termo)
        if texto[pos:fim].casefold() != nom_termo.casefold():
            continue
        # fronteira à direita: o termo não pode ser prefixo de uma palavra maior
        if fim < len(texto) and _eh_caractere_de_palavra(texto[fim]):
            continue
        return campo, fim
    return None
