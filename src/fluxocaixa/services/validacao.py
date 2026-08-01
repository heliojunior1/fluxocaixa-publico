"""Erro de regra de negócio (spec cadastros-nucleo R1).

Services levantam `RegraNegocioError` com mensagem pt-BR; o handler global
converte em flash + redirect (HTML) ou 400 JSON (API). Regra de negócio
NUNCA deve virar 500.
"""


class RegraNegocioError(Exception):
    def __init__(self, mensagem: str, destino: str | None = None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        # destino do redirect em HTML; sem ele, usa o Referer da requisição
        self.destino = destino
