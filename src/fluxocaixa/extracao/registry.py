"""Registry de conectores de extração (spec extracao-configuravel R2).

Registro por dicionário de módulo, com registro dinâmico: conectores de
produção se registram no import do pacote; plugins/testes chamam
`registrar()` diretamente. Evolução documentada no design D3: descoberta
por entry-points de pacote, se a comunidade precisar distribuir conectores
como bibliotecas.
"""
from .conector import Conector

_REGISTRO: dict[str, Conector] = {}


def registrar(conector: Conector) -> None:
    """Registra um conector; tipo duplicado é erro explícito (R2)."""
    tipo = conector.tipo
    if tipo in _REGISTRO:
        raise ValueError(f"Conector de tipo '{tipo}' já registrado")
    _REGISTRO[tipo] = conector


def remover(tipo: str) -> None:
    """Remove um conector do registry (uso em testes/plugins)."""
    _REGISTRO.pop(tipo, None)


def obter(tipo: str) -> Conector | None:
    return _REGISTRO.get(tipo)


def tipos_disponiveis() -> list[str]:
    return sorted(_REGISTRO)
