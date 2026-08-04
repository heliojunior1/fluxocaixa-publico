"""Resolvedor de mapeamento JSON pontilhado (spec R20).

Dirige a conversão de uma resposta JSON de API em `LinhaExtraida` a partir do
`json_layout` do conector `API_REST`: `lista_path` (caminho pontilhado até o
array de itens; ausente ⇒ a resposta é 1 item) e `campos` (cada um: `caminho`
pontilhado relativo ao item → `destino` de `LinhaExtraida`, com transformação
opcional). Dep-free — navega `a.b.c` em dicts/listas. JSONPath completo fica
como evolução.
"""
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, field_validator

from .conector import ErroLinha, LinhaExtraida
from .parser_arquivo import _DESTINO_COMPOSTO, _DESTINOS_SIMPLES, TRANSFORMACOES

_MONETARIOS = {"val_saldo", "val_aplicacoes", "val_resgates"}
# Transformações aplicáveis a valor de API (as que não dependem de layout de arquivo)
_TRANSF_API = {"somente_digitos", "codigo_antes_hifen"}


class _CaminhoAusente(Exception):
    pass


class CampoMapa(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caminho: str
    destino: str
    transformacao: str | None = None

    @field_validator("destino")
    @classmethod
    def _destino_valido(cls, v: str) -> str:
        if v != _DESTINO_COMPOSTO and v not in _DESTINOS_SIMPLES:
            raise ValueError(f"destino inválido: '{v}'")
        return v

    @field_validator("transformacao")
    @classmethod
    def _transf_valida(cls, v):
        if v is not None and v not in _TRANSF_API:
            raise ValueError(
                f"transformação '{v}' não aplicável ao mapeamento de API "
                f"(disponíveis: {', '.join(sorted(_TRANSF_API))})"
            )
        return v


class LayoutApiRest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lista_path: str | None = None
    campos: list[CampoMapa]
    # Destino LANCAMENTO (F4.1): guarda a linha crua em LinhaExtraida.json_atributos
    capturar_atributos: bool = False


def navegar(obj, caminho: str):
    """Segue `a.b.c` em dicts/listas (segmento numérico = índice de lista)."""
    atual = obj
    for seg in caminho.split("."):
        if isinstance(atual, dict):
            if seg not in atual:
                raise _CaminhoAusente(caminho)
            atual = atual[seg]
        elif isinstance(atual, list) and seg.isdigit():
            idx = int(seg)
            if idx >= len(atual):
                raise _CaminhoAusente(caminho)
            atual = atual[idx]
        else:
            raise _CaminhoAusente(caminho)
    return atual


def itens(resposta, lista_path: str | None):
    """Array em `lista_path`, ou `[resposta]` se `lista_path` é None."""
    if lista_path is None:
        return [resposta]
    try:
        arr = navegar(resposta, lista_path)
    except _CaminhoAusente:
        return []
    return arr if isinstance(arr, list) else [arr]


def _coagir(destino: str, valor):
    if destino in _MONETARIOS:
        try:
            return Decimal(str(valor)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            raise ValueError(f"valor monetário inválido para {destino}: {valor!r}")
    if destino == "dat_saldo":
        from datetime import date, datetime

        if isinstance(valor, date) and not isinstance(valor, datetime):
            return valor
        if isinstance(valor, datetime):
            return valor.date()
        try:
            return date.fromisoformat(str(valor)[:10])
        except ValueError:
            raise ValueError(f"data inválida para dat_saldo: {valor!r}")
    return str(valor)


def mapear_item(item, layout, *, cod_banco: str, agencia: str, conta: str):
    """Um item da resposta → `LinhaExtraida` ou `ErroLinha` (pontual).

    `cod_banco` vem do config; `num_agencia`/`num_conta` vêm da conta
    consultada (não da resposta).
    """
    cfg = layout if isinstance(layout, LayoutApiRest) else LayoutApiRest.model_validate(layout)
    destino_vals: dict = {}
    try:
        for campo in cfg.campos:
            bruto = navegar(item, campo.caminho)
            if campo.transformacao:
                resultado = TRANSFORMACOES[campo.transformacao](str(bruto), None)
            else:
                resultado = bruto
            if campo.destino == _DESTINO_COMPOSTO:
                destino_vals["cod_fundo"], destino_vals["dsc_fundo"] = resultado
            else:
                destino_vals[campo.destino] = _coagir(campo.destino, resultado)
    except _CaminhoAusente as exc:
        return ErroLinha(numero=0, arquivo=f"conta {conta}",
                         mensagem=f"campo ausente na resposta: {exc}")
    except (ValueError, TypeError) as exc:
        return ErroLinha(numero=0, arquivo=f"conta {conta}", mensagem=str(exc))

    return LinhaExtraida(
        cod_banco=cod_banco,
        # agência/conta podem vir de colunas mapeadas (SQL) ou do parâmetro
        # (API, onde a conta consultada é conhecida) — o mapeado tem prioridade
        num_agencia=destino_vals.get("num_agencia", agencia),
        num_conta=destino_vals.get("num_conta", conta),
        cod_fundo=destino_vals.get("cod_fundo", ""),
        dsc_fundo=destino_vals.get("dsc_fundo", ""),
        val_saldo=destino_vals.get("val_saldo", Decimal(0)),
        val_aplicacoes=destino_vals.get("val_aplicacoes", Decimal(0)),
        val_resgates=destino_vals.get("val_resgates", Decimal(0)),
        dat_saldo=destino_vals.get("dat_saldo"),
        # Linha crua para a staging (F4.1) — só quando o layout pede
        json_atributos=dict(item) if getattr(cfg, "capturar_atributos", False)
        and isinstance(item, dict) else None,
    )
