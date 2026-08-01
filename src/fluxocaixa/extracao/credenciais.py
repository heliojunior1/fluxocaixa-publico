"""Resolução de credenciais por referência de ambiente (spec R7, design D6).

Campos marcados como secretos no `schema_config` do conector
(`json_schema_extra={"secreto": True}`) aceitam o placeholder
`${NOME_DA_VARIAVEL}`. A resolução acontece numa CÓPIA do config, apenas no
momento da execução/teste de conexão — o valor resolvido nunca é persistido,
logado ou retornado por API. Mensagens de erro citam somente o NOME da
variável, nunca valores.
"""
import os
import re

from pydantic import BaseModel

from ..services.validacao import RegraNegocioError

_PLACEHOLDER = re.compile(r"^\$\{([A-Z][A-Z0-9_]*)\}$")


def campos_secretos(schema: type[BaseModel]) -> set[str]:
    """Nomes dos campos marcados com `json_schema_extra={"secreto": True}`."""
    secretos = set()
    for nome, campo in schema.model_fields.items():
        extra = campo.json_schema_extra
        if isinstance(extra, dict) and extra.get("secreto"):
            secretos.add(nome)
    return secretos


def resolver_config(config: dict, schema: type[BaseModel]) -> dict:
    """Devolve uma cópia do config com os `${VAR}` dos campos secretos resolvidos."""
    resolvido = dict(config)
    for campo in campos_secretos(schema):
        valor = resolvido.get(campo)
        if not isinstance(valor, str):
            continue
        m = _PLACEHOLDER.match(valor.strip())
        if not m:
            continue  # valor literal (ex.: ambiente de teste) — segue como está
        nome_var = m.group(1)
        valor_env = os.environ.get(nome_var)
        if valor_env is None:
            raise RegraNegocioError(
                f"Variável de ambiente '{nome_var}' não definida "
                f"(referenciada no campo '{campo}' da fonte)"
            )
        resolvido[campo] = valor_env
    return resolvido
