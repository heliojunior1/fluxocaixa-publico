"""Validação de configuração no boot (spec infraestrutura-banco R10).

Change: hardening-configuracao-producao.

Função PURA sobre um mapa de variáveis — assim a matriz de combinações cabe em
teste unitário, sem subir aplicação.
"""

SECRET_KEY_TAMANHO_MINIMO = 32

# Placeholders que já circularam no repositório ou em exemplos. Recusados por
# nome além do comprimento: alguém pode "corrigir" alongando o texto sem trocar
# o valor.
_PLACEHOLDERS = {
    "your-secret-key-here",
    "changeme",
    "secret",
    "sua-chave-secreta",
}


class ConfiguracaoInseguraError(RuntimeError):
    """Combinação de configuração sem uso legítimo — aborta o boot."""


def _ligado(valor: str | None, default: bool) -> bool:
    if valor is None:
        return default
    return valor.strip().lower() not in {"false", "0", "no", "off", "n"}


def validar_configuracao(env: dict) -> None:
    """Recusa combinações sem uso legítimo. Silencioso quando está tudo bem.

    Chamada no `create_app`, e NÃO em `modo_demo()` — a leitura por chamada
    existe para os testes alternarem o valor, e levantar exceção ali quebraria
    isso.
    """
    ambiente = (env.get("APP_ENV") or "").strip().lower()
    demo = _ligado(env.get("DEMO_MODE"), False)
    dados_demo = _ligado(env.get("SEED_DEMO_DATA"), True)
    chave = env.get("SECRET_KEY") or ""

    # "Modo de demonstração sobre dados que NÃO são de demonstração" — é o
    # estado de quem forkou, desligou os dados de exemplo para carregar os
    # próprios, e esqueceu a outra flag. Ligar a demo ali expõe admin/admin na
    # tela de login E impede a correção (a troca de senha passa a ser recusada).
    if demo and not dados_demo:
        raise ConfiguracaoInseguraError(
            "DEMO_MODE está ligado com SEED_DEMO_DATA desligado: modo de "
            "demonstração sobre dados que não são de demonstração. Desligue "
            "DEMO_MODE numa instalação com dados reais."
        )

    if demo and ambiente == "prod":
        raise ConfiguracaoInseguraError(
            "DEMO_MODE está ligado com APP_ENV=prod. A demonstração pública "
            "expõe as credenciais na tela de login e recusa a troca de senha."
        )

    if ambiente == "prod":
        # Sem chave fixa, as sessões morrem a cada deploy e a autenticação
        # quebra EM SILÊNCIO sob mais de um worker (válida num, inválida no
        # outro). Advertir não basta: o log de boot raramente é lido no minuto
        # em que importa.
        if not chave:
            raise ConfiguracaoInseguraError(
                "SECRET_KEY é obrigatória com APP_ENV=prod. Gere uma com: "
                'python -c "import secrets; print(secrets.token_hex(32))"'
            )
        if chave.strip().lower() in _PLACEHOLDERS or \
                len(chave) < SECRET_KEY_TAMANHO_MINIMO:
            raise ConfiguracaoInseguraError(
                f"SECRET_KEY inválida: use ao menos {SECRET_KEY_TAMANHO_MINIMO} "
                "caracteres e nunca um valor de exemplo (o placeholder do "
                ".env.example é público). Gere uma com: "
                'python -c "import secrets; print(secrets.token_hex(32))"'
            )


__all__ = [
    "validar_configuracao",
    "ConfiguracaoInseguraError",
    "SECRET_KEY_TAMANHO_MINIMO",
]
