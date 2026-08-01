"""Resolução do domínio de lançamento por descrição (spec R13).

`cod_tipo_lancamento` e `cod_origem_lancamento` são FKs **autoincremento** para
linhas de descrição ("Entrada"/"Saída", "Manual"/"Automático"/"Importado"). A
ordem do seed dá Entrada=1 num banco novo, mas isso é **incidental** — o seed
cria só o que falta, casando pela descrição. Portanto: resolver por descrição,
nunca hardcodar o código.

Implementação única, no espírito de `origem_saldo.py`. Substitui as buscas
ad-hoc que existiam espalhadas (`web/base.py`, `lancamento_service.py`).
"""
from ..models import OrigemLancamento, TipoLancamento
from .validacao import RegraNegocioError

TIPO_ENTRADA = 'Entrada'
TIPO_SAIDA = 'Saída'

ORIGEM_MANUAL = 'Manual'
ORIGEM_AUTOMATICO = 'Automático'
ORIGEM_IMPORTADO = 'Importado'


def resolver_tipo(descricao: str) -> TipoLancamento:
    tipo = TipoLancamento.query.filter_by(dsc_tipo_lancamento=descricao).first()
    if tipo is None:
        raise RegraNegocioError(f"Tipo de lançamento '{descricao}' não encontrado")
    return tipo


def resolver_origem(descricao: str) -> OrigemLancamento:
    origem = OrigemLancamento.query.filter_by(dsc_origem_lancamento=descricao).first()
    if origem is None:
        raise RegraNegocioError(f"Origem de lançamento '{descricao}' não encontrada")
    return origem


__all__ = [
    'resolver_tipo', 'resolver_origem',
    'TIPO_ENTRADA', 'TIPO_SAIDA',
    'ORIGEM_MANUAL', 'ORIGEM_AUTOMATICO', 'ORIGEM_IMPORTADO',
]
