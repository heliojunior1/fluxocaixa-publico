"""Introspecção do schema do conector para o formulário dinâmico (spec R12).

Converte o `schema_config` (Pydantic) de um conector em uma descrição de
formulário — lista de campos com nome, rótulo, tipo HTML, obrigatoriedade e
marcação de segredo — que o template itera sem conhecer conector algum.
Campos cujo tipo não tem mapeamento simples marcam `fallback_json`: a tela
oferece um textarea JSON, validado no envio pelo próprio schema.
"""
from dataclasses import dataclass

from pydantic import BaseModel

from .credenciais import campos_secretos

# Tipos JSON Schema → input HTML
_TIPO_HTML = {
    "string": "text",
    "integer": "number",
    "number": "number",
    "boolean": "checkbox",
}


@dataclass
class CampoFormulario:
    nome: str
    rotulo: str
    tipo_html: str
    obrigatorio: bool
    secreto: bool
    ajuda: str = ""


@dataclass
class DescricaoFormulario:
    campos: list[CampoFormulario]
    fallback_json: bool  # há campo sem mapeamento simples → oferecer textarea JSON


# Prioridade ao colapsar `anyOf` com múltiplos tipos (ex.: Decimal vira
# number+string; opcionais viram <tipo>+null). String vence — é a entrada
# mais geral e preserva precisão de valores monetários.
_PRIORIDADE_TIPO = ("string", "number", "integer", "boolean")


def _tipo_do_campo(spec: dict) -> str | None:
    """Resolve o tipo base, tolerando nulláveis e uniões (`anyOf`)."""
    if "type" in spec:
        return spec["type"]
    for chave in ("anyOf", "oneOf"):
        if chave in spec:
            tipos = {s.get("type") for s in spec[chave] if s.get("type") != "null"}
            for candidato in _PRIORIDADE_TIPO:
                if candidato in tipos:
                    return candidato
    return None


def descrever_formulario(conector) -> DescricaoFormulario:
    schema: type[BaseModel] = conector.schema_config
    json_schema = schema.model_json_schema()
    obrigatorios = set(json_schema.get("required", []))
    secretos = campos_secretos(schema)

    campos: list[CampoFormulario] = []
    fallback = False
    for nome, spec in json_schema.get("properties", {}).items():
        tipo = _tipo_do_campo(spec)
        tipo_html = _TIPO_HTML.get(tipo)
        if tipo_html is None:
            # object/array/sem tipo → não há input simples; usa o textarea JSON
            fallback = True
            continue
        eh_secreto = nome in secretos
        campos.append(
            CampoFormulario(
                nome=nome,
                rotulo=spec.get("title") or nome,
                tipo_html="password" if eh_secreto else tipo_html,
                obrigatorio=nome in obrigatorios,
                secreto=eh_secreto,
                ajuda=spec.get("description", ""),
            )
        )
    return DescricaoFormulario(campos=campos, fallback_json=fallback)
