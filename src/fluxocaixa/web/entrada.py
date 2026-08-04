"""Conversão VALIDADA de entrada do usuário (infraestrutura-banco R15).

Change: validacao-de-entrada-na-web. `int(page_str)` cru fazia `?page=abc`
virar 500 — erro de servidor para o que é erro do USUÁRIO, sem mensagem que
explicasse o campo. Aqui o parse inválido vira `RegraNegocioError` citando o
campo; o handler global converte em flash+redirect (HTML) ou 400 (JSON).
Generaliza o `_param_data` que já era o padrão certo em `relatorios.py`.
"""
from datetime import date

from ..services.validacao import RegraNegocioError


def inteiro(raw, nome: str, default: int | None = None,
            obrigatorio: bool = False) -> int | None:
    """Converte para int; vazio/None vira `default` (ou erro se obrigatório)."""
    if raw is None or str(raw).strip() == "":
        if obrigatorio:
            raise RegraNegocioError(f"Informe o parâmetro '{nome}'.")
        return default
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        raise RegraNegocioError(f"Valor inválido para '{nome}'.")


def data_iso(raw, nome: str, default: date | None = None,
             obrigatorio: bool = False) -> date | None:
    """Converte ISO (AAAA-MM-DD); vazio vira `default` (ou erro se obrigatório)."""
    if raw is None or str(raw).strip() == "":
        if obrigatorio:
            raise RegraNegocioError(f"Informe a data '{nome}'.")
        return default
    try:
        return date.fromisoformat(str(raw).strip())
    except (TypeError, ValueError):
        raise RegraNegocioError(f"Data inválida no campo '{nome}'.")


def lista_de_inteiros(raw, nome: str) -> list[int]:
    """Converte 'a,b,c' em lista de ints; vazio vira lista vazia."""
    if not raw:
        return []
    try:
        return [int(parte) for parte in str(raw).split(",") if parte.strip()]
    except (TypeError, ValueError):
        raise RegraNegocioError(f"Valores inválidos para '{nome}'.")


def texto_obrigatorio(form, nome: str) -> str:
    """Campo de form obrigatório — ausência é erro de negócio, nunca KeyError."""
    valor = form.get(nome)
    if valor is None or str(valor).strip() == "":
        raise RegraNegocioError(f"O campo '{nome}' é obrigatório.")
    return str(valor)
