"""Motor de regras de classificação (spec automacao-lancamentos R7/R8).

Pipeline em três estágios, cada um testável isolado:

    txt_regra (pt-BR)
        │  substituicao.py  termos ATIVOS do cadastro, fronteira de palavra,
        │                   mais longo vence (resolvidos no lexer)
        │  parser.py        gramática fechada → AST validada
        ▼
    ast.py (o contrato)
        │  renderer.py      único ponto que fala com o banco
        ▼
    expressão SQLAlchemy   (nunca texto SQL → injeção impossível por construção)

Uso:
    traduzir_regra(txt) -> expressão SQLAlchemy   (levanta RegraNegocioError)
    validar_regra(txt)  -> (ok: bool, erro: str | None)
    preview_regra(txt, seq_fonte, limite) -> {total, amostra}
"""
from ..validacao import RegraNegocioError
from .parser import parsear
from .preview import preview_regra
from .renderer import renderizar


def traduzir_regra(txt_regra: str):
    """Regra em pt-BR → expressão SQLAlchemy sobre `flc_etl_staging`."""
    return renderizar(parsear(txt_regra))


def validar_regra(txt_regra: str) -> tuple[bool, str | None]:
    """`(ok, erro)` — no espírito de `formula_engine.validar_formula`."""
    try:
        traduzir_regra(txt_regra)
        return True, None
    except RegraNegocioError as exc:
        return False, exc.mensagem


__all__ = ['parsear', 'preview_regra', 'renderizar', 'traduzir_regra', 'validar_regra']
