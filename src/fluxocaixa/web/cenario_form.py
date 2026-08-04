"""Parse compartilhado da configuração de base histórica (previsao R14).

Change: despacho-de-modelos-no-servico (achado A5). Havia DUAS cópias
divergentes de `_parse_config_base_from_form` — simulador (retorna JSON,
campos com sufixo `_cenario`) e fórmulas (retorna dict, sem sufixo). Mesma
semântica, dois contratos: a próxima correção seria feita numa e esquecida
na outra. Uma implementação, dois chamadores.
"""
import json


def parse_config_base(form, cod_metodo_base: str, sufixo: str = "") -> dict:
    """`sufixo`: "_cenario" no formulário do simulador; "" no de fórmulas.

    Os pesos usam o padrão `peso{sufixo}_{ano}` — no simulador o campo é
    `peso_cenario_<ano>`, nas fórmulas `peso_<ano>`.
    """
    config: dict = {}

    if cod_metodo_base == 'VALOR_FIXO':
        try:
            config['valor'] = float(form.get(f'valor_fixo{sufixo}', 0) or 0)
        except (ValueError, TypeError):
            config['valor'] = 0.0
        return config

    anos_str = form.get(f'anos_selecionados{sufixo}', '') or ''
    try:
        config['anos'] = [int(a) for a in json.loads(anos_str)] if anos_str else []
    except (json.JSONDecodeError, ValueError, TypeError):
        config['anos'] = []

    if cod_metodo_base == 'MEDIA_PONDERADA':
        pesos = {}
        for ano in config.get('anos', []):
            try:
                pesos[str(ano)] = float(form.get(f'peso{sufixo}_{ano}', 1) or 1)
            except (ValueError, TypeError):
                pesos[str(ano)] = 1.0
        config['pesos'] = pesos

    return config
