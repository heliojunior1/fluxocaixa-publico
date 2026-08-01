"""Registro dos conectores disponíveis na instalação (spec R13).

Chamado no import do pacote `extracao`. Hoje só o conector de demonstração,
gated por `EXTRACAO_DEMO_CONNECTOR` — produção fica sem conector até a F3.2
introduzir o primeiro conector real (FTP/arquivo). Idempotente: seguro
chamar mais de uma vez (recarga de módulos em testes).
"""
from ...bootstrap_db import env_flag
from .. import registry


def registrar_conectores_disponiveis() -> None:
    # Conector de arquivo — real, sempre disponível (FTP/SFTP/pasta local).
    from .ftp_arquivo import ConectorFtpArquivo

    if "FTP_ARQUIVO" not in registry.tipos_disponiveis():
        registry.registrar(ConectorFtpArquivo())

    # Conector de API REST — real, sempre disponível.
    from .api_rest import ConectorApiRest

    if "API_REST" not in registry.tipos_disponiveis():
        registry.registrar(ConectorApiRest())

    # Conector de banco SQL externo — real, sempre disponível.
    from .banco_sql import ConectorBancoSql

    if "BANCO_SQL" not in registry.tipos_disponiveis():
        registry.registrar(ConectorBancoSql())

    # Conector de demonstração — só com a flag (andaime de E2E/demo).
    if env_flag("EXTRACAO_DEMO_CONNECTOR", False):
        from .demo import ConectorDemoManual

        if "DEMO_MANUAL" not in registry.tipos_disponiveis():
            registry.registrar(ConectorDemoManual())
