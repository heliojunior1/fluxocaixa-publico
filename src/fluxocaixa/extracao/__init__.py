"""Extração embutida e configurável (spec extracao-configuravel).

Chassi criado no change infra-extracao-agendador: contrato de conector
(`conector.py`), registry de plugins (`registry.py`), credenciais por
referência de ambiente (`credenciais.py`) e agendador APScheduler
(`scheduler.py`). Conectores de produção: F3.2 (FTP/arquivo), F3.3
(API REST) e F3.4 (banco SQL).
"""
from . import registry  # noqa: F401
from .conector import Conector, Janela, LinhaExtraida, ResultadoTeste  # noqa: F401
from .conectores import registrar_conectores_disponiveis

# Registra os conectores disponíveis na instalação (hoje só o demo, gated por
# EXTRACAO_DEMO_CONNECTOR) no import — o registry precisa estar populado antes
# da primeira requisição (a tela de nova fonte lista os tipos).
registrar_conectores_disponiveis()
