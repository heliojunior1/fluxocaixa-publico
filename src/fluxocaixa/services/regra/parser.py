"""Parser da regra de classificação (spec automacao-lancamentos R7).

Descida recursiva dep-free, no espírito de `extracao/mapeamento_json.py`.
Gramática (precedência: `ou` < `e` < `não` < comparação):

    expressao  := termo_ou
    termo_ou   := termo_e ( 'ou' termo_e )*
    termo_e    := fator ( 'e' fator )*
    fator      := 'não' fator | '(' expressao ')' | comparacao
    comparacao := CAMPO operador valor
    operador   := '=' | '<>' | 'começa com' | '>' | '<' | '>=' | '<=' | 'em'
    valor      := literal | '(' literal ( ',' literal )* ')'    -- lista só p/ 'em'
    literal    := 'texto entre aspas simples' | numero

Qualquer trecho não reconhecido vira erro de parse EXPLÍCITO — nada
não-reconhecido chega ao banco. A referência não tem parser: o `txt_regra` é
SQL cru e um erro só aparece no banco, em execução.
"""
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
    OPS_POR_TIPO,
    ROTULO_OP,
    Campo,
    Comparacao,
    E,
    Nao,
    Ou,
)
from .substituicao import carregar_termos, casar_termo

# Operadores textuais e simbólicos. Os textuais são casados com fronteira de
# palavra; os simbólicos, do mais longo para o mais curto ('>=' antes de '>').
_OPS_TEXTO = [('começa com', OP_COMECA_COM), ('em', OP_EM)]
_OPS_SIMBOLO = [('>=', OP_MAIOR_IGUAL), ('<=', OP_MENOR_IGUAL), ('<>', OP_DIFERENTE),
                ('=', OP_IGUAL), ('>', OP_MAIOR), ('<', OP_MENOR)]

_CONECTIVOS = [('ou', 'OU'), ('e', 'E'), ('não', 'NAO'), ('nao', 'NAO')]


class _Token:
    def __init__(self, tipo, valor, pos):
        self.tipo = tipo    # CAMPO | OP | CONECTIVO | ABRE | FECHA | VIRGULA | LITERAL
        self.valor = valor
        self.pos = pos

    def __repr__(self):  # pragma: no cover - debug
        return f"<{self.tipo}:{self.valor!r}>"


def _erro(mensagem: str):
    raise RegraNegocioError(f"Regra inválida: {mensagem}")


def _tokenizar(texto: str, termos) -> list[_Token]:
    tokens: list[_Token] = []
    i, n = 0, len(texto)
    while i < n:
        ch = texto[i]
        if ch.isspace():
            i += 1
            continue

        # Literal de texto primeiro: protege termos/operadores dentro de aspas
        if ch == "'":
            fim = texto.find("'", i + 1)
            if fim == -1:
                _erro("aspas simples não fechadas")
            tokens.append(_Token('LITERAL', texto[i + 1:fim], i))
            i = fim + 1
            continue

        if ch == '(':
            tokens.append(_Token('ABRE', '(', i)); i += 1; continue
        if ch == ')':
            tokens.append(_Token('FECHA', ')', i)); i += 1; continue
        if ch == ',':
            tokens.append(_Token('VIRGULA', ',', i)); i += 1; continue

        simbolo = next((par for par in _OPS_SIMBOLO if texto.startswith(par[0], i)), None)
        if simbolo:
            tokens.append(_Token('OP', simbolo[1], i))
            i += len(simbolo[0])
            continue

        # Número (inteiro ou decimal com ponto)
        if ch.isdigit() or (ch == '-' and i + 1 < n and texto[i + 1].isdigit()):
            j = i + 1
            while j < n and (texto[j].isdigit() or texto[j] == '.'):
                j += 1
            bruto = texto[i:j]
            try:
                tokens.append(_Token('LITERAL', float(bruto) if '.' in bruto else int(bruto), i))
            except ValueError:
                _erro(f"número inválido: '{bruto}'")
            i = j
            continue

        # Termo do dicionário (mais longo vence — ver substituicao.py)
        casado = casar_termo(texto, i, termos)
        if casado:
            campo, fim = casado
            tokens.append(_Token('CAMPO', campo, i))
            i = fim
            continue

        # Operador/conectivo textual (fronteira de palavra)
        palavra = _proxima_palavra(texto, i)
        if palavra:
            chave = palavra.casefold()
            op = next((par[1] for par in _OPS_TEXTO if par[0] == chave), None)
            if chave == 'começa' and _proxima_palavra(texto, i + len(palavra) + 1) == 'com':
                tokens.append(_Token('OP', OP_COMECA_COM, i))
                i += len('começa com') + 1
                continue
            if op:
                tokens.append(_Token('OP', op, i)); i += len(palavra); continue
            conectivo = next((par[1] for par in _CONECTIVOS if par[0] == chave), None)
            if conectivo:
                tokens.append(_Token('CONECTIVO', conectivo, i)); i += len(palavra); continue
            # Termos são multi-palavra ("Unidade Gestora Emitente"): citar só a
            # primeira palavra não ajudaria quem escreveu a regra.
            _erro(f"termo não reconhecido: '{_frase_nao_reconhecida(texto, i)}'")

        _erro(f"trecho não reconhecido a partir de '{texto[i:i + 20]}'")
    return tokens


def _frase_nao_reconhecida(texto: str, i: int) -> str:
    """Acumula as palavras seguidas que não são operador/conectivo.

    Um termo desconhecido é indistinguível de lixo, mas como os termos do
    dicionário são multi-palavra, devolver a frase toda ('Coisa Inexistente')
    aponta o problema melhor do que a primeira palavra ('Coisa').
    """
    reservadas = {par[0] for par in _OPS_TEXTO} | {par[0] for par in _CONECTIVOS} | {'começa'}
    palavras: list[str] = []
    j = i
    n = len(texto)
    while j < n:
        while j < n and texto[j] == ' ':
            j += 1
        palavra = _proxima_palavra(texto, j)
        if not palavra or palavra.casefold() in reservadas:
            break
        palavras.append(palavra)
        j += len(palavra)
    return ' '.join(palavras) or texto[i:i + 20]


def _proxima_palavra(texto: str, i: int) -> str:
    n = len(texto)
    j = i
    while j < n and (texto[j].isalnum() or texto[j] in '_çÇáàâãéêíóôõúÁÀÂÃÉÊÍÓÔÕÚ'):
        j += 1
    return texto[i:j]


class _Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.i = 0

    def _atual(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def _consumir(self, tipo, valor=None):
        tok = self._atual()
        if tok is None or tok.tipo != tipo or (valor is not None and tok.valor != valor):
            esperado = valor or tipo
            achado = 'fim da regra' if tok is None else repr(tok.valor)
            _erro(f"esperava {esperado}, encontrei {achado}")
        self.i += 1
        return tok

    def parse(self):
        no = self._expressao()
        if self._atual() is not None:
            _erro(f"trecho sobrando a partir de {self._atual().valor!r}")
        return no

    def _expressao(self):
        no = self._termo_e()
        while (tok := self._atual()) and tok.tipo == 'CONECTIVO' and tok.valor == 'OU':
            self.i += 1
            no = Ou(no, self._termo_e())
        return no

    def _termo_e(self):
        no = self._fator()
        while (tok := self._atual()) and tok.tipo == 'CONECTIVO' and tok.valor == 'E':
            self.i += 1
            no = E(no, self._fator())
        return no

    def _fator(self):
        tok = self._atual()
        if tok is None:
            _erro("regra incompleta")
        if tok.tipo == 'CONECTIVO' and tok.valor == 'NAO':
            self.i += 1
            return Nao(self._fator())
        if tok.tipo == 'ABRE':
            self.i += 1
            no = self._expressao()
            self._consumir('FECHA')
            return no
        return self._comparacao()

    def _comparacao(self):
        campo: Campo = self._consumir('CAMPO').valor
        operador = self._consumir('OP').valor

        permitidos = OPS_POR_TIPO.get(campo.cod_tipo, set())
        if operador not in permitidos:
            _erro(
                f"o operador '{ROTULO_OP[operador]}' não se aplica ao termo "
                f"'{campo.nom_termo}' (tipo {campo.cod_tipo})"
            )

        if operador == OP_EM:
            self._consumir('ABRE')
            valores = [self._consumir('LITERAL').valor]
            while (tok := self._atual()) and tok.tipo == 'VIRGULA':
                self.i += 1
                valores.append(self._consumir('LITERAL').valor)
            self._consumir('FECHA')
            return Comparacao(campo, operador, valores)

        return Comparacao(campo, operador, self._consumir('LITERAL').valor)


def parsear(txt_regra: str):
    """Texto pt-BR → AST validada. Levanta `RegraNegocioError` no primeiro erro."""
    if not txt_regra or not txt_regra.strip():
        _erro("regra vazia")
    tokens = _tokenizar(txt_regra, carregar_termos())
    if not tokens:
        _erro("regra vazia")
    return _Parser(tokens).parse()
