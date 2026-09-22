"""Método por qualificador (docs/previsao-metodo-por-qualificador.md, RN01–RN17).

Um cenário pode misturar, na mesma árvore, métodos diferentes por rubrica:
valor fixo, percentual, fórmula, modelo, LOA, proposta de setor ou "sem
projeção" declarada. A marcação fica em QUALQUER nó (`flc_cenario_metodo`) e
as folhas herdam — **a marcação mais próxima vence**, o mesmo desempate da
categoria fiscal.

⚠️ **Origem única** (RN03): `marcacao_resolvida` é a ÚNICA resposta para
"qual método projeta esta folha?" — mesmo estatuto de `is_folha()`,
`valor_com_sinal` e `periodo_resolver`. O método resolvido nunca é persistido:
reapontar um pai o mudaria para a subárvore inteira.

⚠️ **Saída sempre por folha** (RN14): todo método entrega linhas
`(data, seq_qualificador folha, valor_projetado, cod_metodo,
seq_qualificador_calculo)` em MAGNITUDE — o sinal vem da perna (R6). Métodos
calculados num bloco (modelo treinado no total, valor fixo do bloco) são
DISTRIBUÍDOS às folhas pela participação no realizado do ano anterior
(RN05); a soma distribuída é exatamente o total do nó (RN13).

⚠️ **Nó de cálculo exclui subárvore com marcação própria** (RN06): se o bloco
está em SARIMA e uma folha dele tem proposta setorial, a folha sai do treino
e da distribuição do bloco — senão seria projetada duas vezes.

⚠️ **Falha nunca é silenciosa**: histórico insuficiente, folha sem fórmula,
proposta inválida viram STATUS da folha (lacuna com a nota), não zero com cara
de dado apurado — a cobertura (RN11) os exibe.

Compatibilidade: cenário SEM marcação não passa por aqui — `executar_simulacao`
segue idêntico (a configuração da perna é o "método padrão").
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date

from ..auth.contexto import cod_pessoa_atual
from . import periodo_resolver
from .validacao import RegraNegocioError

VALOR_FIXO = 'VALOR_FIXO'
PERCENTUAL = 'PERCENTUAL'
FORMULA = 'FORMULA'
MODELO = 'MODELO'
LOA = 'LOA'
PROPOSTA_SETORIAL = 'PROPOSTA_SETORIAL'
SEM_PROJECAO = 'SEM_PROJECAO'

METODOS = {
    VALOR_FIXO: 'Valor fixo',
    PERCENTUAL: 'Percentual sobre o realizado',
    FORMULA: 'Fórmula',
    MODELO: 'Modelo',
    LOA: 'LOA',
    PROPOSTA_SETORIAL: 'Proposta setorial',
    SEM_PROJECAO: 'Sem projeção (declarado)',
}

# Modelos oferecidos na marcação → (janela de treino em anos, mínimo de
# pontos). Os dois de crescimento não treinam série: leem acumulados.
MODELOS_DE_SERIE = {
    'HOLT_WINTERS': (3, 12),
    'ARIMA': (3, 12),
    'SARIMA': (4, 12),
    'XGBOOST': (3, 13),
    'LIGHTGBM': (3, 13),
    'MEDIA_HISTORICA': (3, 1),
    'CRESCIMENTO_ANO': None,
    'MEDIA_CRESCIMENTO': None,
}
ROTULO_MODELO = {
    'HOLT_WINTERS': 'Holt-Winters',
    'ARIMA': 'ARIMA',
    'SARIMA': 'SARIMA',
    'XGBOOST': 'XGBoost',
    'LIGHTGBM': 'LightGBM',
    'MEDIA_HISTORICA': 'Média histórica',
    'CRESCIMENTO_ANO': 'Crescimento sobre o ano anterior',
    'MEDIA_CRESCIMENTO': 'Média de crescimento dos anos',
}

# Status de uma folha na cobertura (RN11)
STATUS_PROJETADA = 'PROJETADA'
STATUS_LACUNA = 'LACUNA'
STATUS_DECLARADA = 'DECLARADA'
STATUS_SEM_PARTICIPACAO = 'SEM_PARTICIPACAO'
STATUS_FORA_DO_RECORTE = 'FORA_DO_RECORTE'


# ---------------------------------------------------------------------------
# Catálogo e validação
# ---------------------------------------------------------------------------

def perna_do_qualificador(qualificador) -> str | None:
    """'C' receita / 'D' despesa, pela raiz da árvore (`tipo_fluxo`)."""
    return {'receita': 'C', 'despesa': 'D'}.get(qualificador.tipo_fluxo)


def pernas_do_metodo(cod_metodo: str, config: dict | None) -> tuple:
    """Pernas em que o método se aplica (RN04). Tupla vazia = inexistente.

    MODELO usa o catálogo do simulador (`CATALOGO_MODELOS`): os
    econométricos só em receita — com uma exceção, média histórica nas duas
    pernas (ver abaixo).
    """
    from ..models.simulador_cenario import pernas_do_modelo

    if cod_metodo == LOA:
        return ('D',)
    if cod_metodo == MODELO:
        modelo = (config or {}).get('modelo')
        if modelo not in MODELOS_DE_SERIE:
            return ()
        if modelo == 'MEDIA_HISTORICA':
            # Na marcação vale para as DUAS pernas: o backtest avalia e
            # recomenda média histórica para receita, e a recomendação
            # sumia em silêncio de "Aplicar recomendações". A restrição
            # "só despesa" do `CATALOGO_MODELOS` é da configuração da perna
            # (legado das tabelas separadas, spec R2) e continua lá.
            return ('C', 'D')
        return pernas_do_modelo(modelo)
    if cod_metodo in METODOS:
        return ('C', 'D')
    return ()


def rotulo(cod_metodo: str | None, config: dict | None = None) -> str:
    """Descrição curta para tela ("Modelo · SARIMA", "Valor fixo · 170,00")."""
    config = config or {}
    if not cod_metodo:
        return 'Sem método'
    if cod_metodo == MODELO:
        return f"Modelo · {ROTULO_MODELO.get(config.get('modelo'), config.get('modelo'))}"
    if cod_metodo == VALOR_FIXO and config.get('valor_anual') is not None:
        valor = f"{float(config['valor_anual']):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        return f"Valor fixo · {valor}/ano"
    if cod_metodo == VALOR_FIXO:
        return 'Valor fixo · mensal'
    if cod_metodo == PERCENTUAL:
        pct = float(config.get('percentual', 0))
        return f"Percentual · {pct:+.2f}%".replace('.', ',')
    if cod_metodo == PROPOSTA_SETORIAL:
        return f"Proposta setorial · versão {config.get('seq_projecao_versao')}"
    return METODOS.get(cod_metodo, cod_metodo)


def _numero(valor, campo: str) -> float:
    try:
        return float(str(valor).replace(',', '.'))
    except (TypeError, ValueError):
        raise RegraNegocioError(f"Informe um número válido em {campo}")


def normalizar_config(cod_metodo: str, config: dict | None) -> dict:
    """Valida e normaliza a configuração do método (RN04, RN07, RN08).

    Devolve só as chaves que o método usa — configuração com lixo de outro
    método (troca de método na tela) não é gravada.
    """
    config = dict(config or {})
    if cod_metodo == VALOR_FIXO:
        if config.get('valores_mensais'):
            mensais = {}
            for mes, valor in dict(config['valores_mensais']).items():
                mes = int(mes)
                if not 1 <= mes <= 12:
                    raise RegraNegocioError("Mês inválido nos valores mensais")
                v = _numero(valor, f"valor do mês {mes}")
                if v < 0:
                    raise RegraNegocioError(
                        "Valor projetado é magnitude — informe valor positivo "
                        "(o sinal vem da receita/despesa)")
                mensais[str(mes)] = v
            return {'valores_mensais': mensais}
        if config.get('valor_anual') in (None, ''):
            raise RegraNegocioError("Informe o valor anual do valor fixo")
        valor = _numero(config['valor_anual'], 'valor anual')
        if valor < 0:
            raise RegraNegocioError(
                "Valor projetado é magnitude — informe valor positivo "
                "(o sinal vem da receita/despesa)")
        return {'valor_anual': valor}
    if cod_metodo == PERCENTUAL:
        pct = _numero(config.get('percentual', 0), 'percentual')
        anos = int(config.get('anos_base') or 1)
        if not 1 <= anos <= 10:
            raise RegraNegocioError("A base do percentual usa de 1 a 10 anos")
        return {'percentual': pct, 'anos_base': anos}
    if cod_metodo == MODELO:
        modelo = config.get('modelo')
        if modelo not in MODELOS_DE_SERIE:
            raise RegraNegocioError(f"Modelo '{modelo}' não disponível para marcação")
        saida = {'modelo': modelo,
                 'por_folha': str(config.get('por_folha', '')).lower() in ('1', 'true', 'on', 's')}
        if modelo in ('CRESCIMENTO_ANO', 'MEDIA_CRESCIMENTO'):
            saida['mes_referencia'] = int(config.get('mes_referencia') or 6)
            anos = config.get('anos_referencia') or []
            saida['anos_referencia'] = [int(a) for a in anos]
        return saida
    if cod_metodo == SEM_PROJECAO:
        motivo = (config.get('motivo') or '').strip()
        if not motivo:
            raise RegraNegocioError(
                "Informe o motivo: projeção zero declarada precisa de justificativa")
        return {'motivo': motivo[:200]}
    if cod_metodo == PROPOSTA_SETORIAL:
        try:
            return {'seq_projecao_versao': int(config.get('seq_projecao_versao'))}
        except (TypeError, ValueError):
            raise RegraNegocioError("Escolha a versão da proposta do setor")
    if cod_metodo in (FORMULA, LOA):
        return {}
    raise RegraNegocioError(f"Método '{cod_metodo}' não existe")


# ---------------------------------------------------------------------------
# Leitura e resolução (origem única)
# ---------------------------------------------------------------------------

def carregar_marcacoes(seq_simulador_cenario: int) -> dict:
    """{seq_qualificador: CenarioMetodo} do cenário."""
    from ..models import CenarioMetodo

    return {
        m.seq_qualificador: m
        for m in CenarioMetodo.query.filter_by(
            seq_simulador_cenario=seq_simulador_cenario).all()
    }


def config_da_marcacao(marcacao) -> dict:
    if marcacao is None or not marcacao.json_configuracao:
        return {}
    try:
        return json.loads(marcacao.json_configuracao)
    except (json.JSONDecodeError, TypeError):
        return {}


def marcacao_resolvida(qualificador, marcacoes: dict, memo: dict | None = None):
    """(marcação efetiva, é_própria) do qualificador — ou (None, False).

    Sobe pela cadeia de pais com conjunto de VISITADOS separado do memo (a
    lição da `categoria_resolvida`: sem ele a subida numa árvore ciclada não
    terminava). O memo guarda o caminho inteiro, para os irmãos reusarem.
    """
    if qualificador is None:
        return None, False
    if memo is None:
        memo = {}
    caminho = []
    vistos = set()
    no = qualificador
    resolvida = None
    while no is not None:
        if no.seq_qualificador in memo:
            resolvida = memo[no.seq_qualificador]
            break
        if no.seq_qualificador in vistos:
            raise no._erro_ciclo()
        vistos.add(no.seq_qualificador)
        caminho.append(no)
        if no.seq_qualificador in marcacoes:
            resolvida = marcacoes[no.seq_qualificador]
            break
        no = no.pai
    for visitado in caminho:
        memo[visitado.seq_qualificador] = resolvida
    propria = resolvida is not None and resolvida.seq_qualificador == qualificador.seq_qualificador
    return resolvida, propria


def exercicio_do_cenario(simulador) -> int | None:
    from .qualificador_service import resolver_exercicio_do_plano

    return resolver_exercicio_do_plano(simulador.ano_base)


def folhas_da_perna(perna: str, exercicio: int | None) -> list:
    from ..repositories import qualificador_repository as repo

    if perna == 'C':
        return repo.get_receita_qualificadores_folha(exercicio)
    return repo.get_despesa_qualificadores_folha(exercicio)


def folhas_sob(qualificador) -> list:
    """Folhas ativas da subárvore (o próprio nó, se for folha)."""
    if qualificador.is_folha():
        return [qualificador]
    return [q for q in qualificador.get_todos_filhos() if q.is_folha()]


# ---------------------------------------------------------------------------
# Escrita de marcações
# ---------------------------------------------------------------------------

def definir_marcacao(seq_simulador_cenario: int, seq_qualificador: int,
                     cod_metodo: str, config: dict | None = None,
                     user_id: int | None = None, commit: bool = True):
    """Grava (insere ou substitui) a marcação do nó (RN02, RN04, RN09, RN24).

    Validações: cenário ativo; qualificador ativo do plano do exercício do
    cenário; método aplicável à perna; configuração válida; em cenário
    SETORIAL, nó dentro do recorte do setor; proposta setorial válida e sem
    sobreposição com outra proposta na mesma linhagem da árvore (RN28).
    """
    from ..models import CenarioMetodo, Qualificador, SimuladorCenario
    from ..models.base import db

    simulador = SimuladorCenario.query.get(seq_simulador_cenario)
    if simulador is None or simulador.ind_status != 'A':
        raise RegraNegocioError("Cenário inexistente ou inativo")
    qualificador = Qualificador.query.get(seq_qualificador)
    if qualificador is None or qualificador.ind_status != 'A':
        raise RegraNegocioError("Qualificador inexistente ou inativo")

    exercicio = exercicio_do_cenario(simulador)
    if exercicio is not None and qualificador.num_ano_exercicio != exercicio:
        raise RegraNegocioError(
            f"O qualificador {qualificador.num_qualificador} é do exercício "
            f"{qualificador.num_ano_exercicio}; o cenário de {simulador.ano_base} "
            f"usa o plano de {exercicio}")

    perna = perna_do_qualificador(qualificador)
    if perna is None:
        raise RegraNegocioError(
            f"O qualificador {qualificador.num_qualificador} não é de receita nem de despesa")

    config = normalizar_config(cod_metodo, config)
    pernas = pernas_do_metodo(cod_metodo, config)
    if perna not in pernas:
        nome_perna = 'receita' if perna == 'C' else 'despesa'
        raise RegraNegocioError(
            f"{rotulo(cod_metodo, config)} não se aplica a {nome_perna}")

    if simulador.seq_setor_previsao is not None:
        from .setor_previsao_service import no_no_recorte

        if not no_no_recorte(qualificador, simulador.seq_setor_previsao):
            raise RegraNegocioError(
                f"O qualificador {qualificador.num_qualificador} está fora do "
                "recorte do setor deste cenário")

    if cod_metodo == PROPOSTA_SETORIAL:
        _validar_proposta(simulador, qualificador, config['seq_projecao_versao'])
        _validar_sem_sobreposicao_de_propostas(seq_simulador_cenario, qualificador)

    marcacao = CenarioMetodo.query.filter_by(
        seq_simulador_cenario=seq_simulador_cenario,
        seq_qualificador=seq_qualificador).first()
    autor = user_id or cod_pessoa_atual()
    if marcacao is None:
        marcacao = CenarioMetodo(
            seq_simulador_cenario=seq_simulador_cenario,
            seq_qualificador=seq_qualificador,
            cod_pessoa_inclusao=autor)
        db.session.add(marcacao)
    else:
        marcacao.dat_alteracao = date.today()
        marcacao.cod_pessoa_alteracao = autor
    marcacao.cod_metodo = cod_metodo
    marcacao.json_configuracao = json.dumps(config)
    # `commit=False`: o chamador é dono da transação (criar/atualizar cenário
    # com as marcações do formulário — tudo ou nada, previsao R13).
    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return marcacao


def remover_marcacao(seq_simulador_cenario: int, seq_qualificador: int,
                     commit: bool = True) -> bool:
    """Remove a marcação própria — o nó volta a herdar."""
    from ..models import CenarioMetodo
    from ..models.base import db

    marcacao = CenarioMetodo.query.filter_by(
        seq_simulador_cenario=seq_simulador_cenario,
        seq_qualificador=seq_qualificador).first()
    if marcacao is None:
        return False
    db.session.delete(marcacao)
    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return True


# ---------------------------------------------------------------------------
# Marcações vindas do FORMULÁRIO do cenário (modo "por qualificador")
# ---------------------------------------------------------------------------

MANTER = '__MANTER__'  # linha com método que o formulário não edita (proposta, mensal)


def opcoes_do_formulario(perna: str) -> list[tuple[str, str]]:
    """(valor, rótulo) do seletor de método de uma linha da árvore no
    formulário do cenário. Modelo vai achatado como `MODELO:<tipo>`."""
    opcoes = [(VALOR_FIXO, 'Valor fixo (anual)'), (PERCENTUAL, 'Percentual sobre o ano anterior'),
              (FORMULA, 'Fórmula')]
    if perna in pernas_do_metodo(LOA, {}):
        opcoes.append((LOA, 'LOA'))
    for modelo, nome in ROTULO_MODELO.items():
        if perna in pernas_do_metodo(MODELO, {'modelo': modelo}):
            opcoes.append((f'{MODELO}:{modelo}', f'Modelo · {nome}'))
    opcoes.append((SEM_PROJECAO, 'Sem projeção (informe o motivo)'))
    return opcoes


def valor_do_formulario(marcacao) -> tuple[str, str]:
    """(valor do seletor, parâmetro) de uma marcação existente, para o
    formulário. Métodos que o formulário não edita voltam como MANTER."""
    if marcacao is None:
        return '', ''
    config = config_da_marcacao(marcacao)
    metodo = marcacao.cod_metodo
    if metodo == VALOR_FIXO and config.get('valor_anual') is not None:
        return VALOR_FIXO, f"{float(config['valor_anual']):.2f}"
    if metodo == PERCENTUAL and not int(config.get('anos_base') or 1) > 1:
        return PERCENTUAL, f"{float(config.get('percentual', 0)):g}"
    if metodo == MODELO:
        modelo = config.get('modelo')
        # o formulário só expressa o modelo com os defaults; ajuste fino
        # (treino por folha, mês/anos de referência) fica na tela de métodos
        editavel = not config.get('por_folha') and (
            modelo not in ('CRESCIMENTO_ANO', 'MEDIA_CRESCIMENTO')
            or (not config.get('anos_referencia')
                and int(config.get('mes_referencia') or 6) == 6))
        return (f"{MODELO}:{modelo}", '') if editavel else (MANTER, '')
    if metodo in (FORMULA, LOA):
        return metodo, ''
    if metodo == SEM_PROJECAO:
        return SEM_PROJECAO, config.get('motivo', '')
    return MANTER, ''


def marcacoes_do_formulario(form) -> dict:
    """{seq_qualificador: (cod_metodo | '' | MANTER, config)} lidas do
    formulário (`metodo_<seq>` + `param_<seq>`). '' = herdar (sem marcação)."""
    saida = {}
    for chave in form.keys():
        if not chave.startswith('metodo_'):
            continue
        try:
            seq = int(chave[len('metodo_'):])
        except ValueError:
            continue
        valor = (form.get(chave) or '').strip()
        param = (form.get(f'param_{seq}') or '').strip()
        if valor in ('', MANTER):
            saida[seq] = (valor, {})
        elif valor.startswith(f'{MODELO}:'):
            saida[seq] = (MODELO, {'modelo': valor.split(':', 1)[1]})
        elif valor == VALOR_FIXO:
            saida[seq] = (VALOR_FIXO, {'valor_anual': param})
        elif valor == PERCENTUAL:
            saida[seq] = (PERCENTUAL, {'percentual': param or '0'})
        elif valor == SEM_PROJECAO:
            saida[seq] = (SEM_PROJECAO, {'motivo': param})
        else:
            saida[seq] = (valor, {})
    return saida


def aplicar_marcacoes_do_formulario(seq_simulador_cenario: int, marcacoes: dict,
                                    user_id: int | None = None) -> int:
    """Sincroniza as marcações do cenário com o formulário SEM commit (o
    serviço do cenário é o dono da transação). Linha '' remove a marcação
    própria; MANTER preserva a existente. Devolve quantas ficaram gravadas.

    Erro de negócio cita a rubrica — a mensagem sozinha ("informe o valor
    anual") não diria qual das quarenta linhas corrigir.
    """
    from ..models import Qualificador

    gravadas = 0
    for seq, (cod_metodo, config) in marcacoes.items():
        if cod_metodo == MANTER:
            gravadas += 1
            continue
        if not cod_metodo:
            remover_marcacao(seq_simulador_cenario, seq, commit=False)
            continue
        try:
            definir_marcacao(seq_simulador_cenario, seq, cod_metodo, config,
                             user_id, commit=False)
        except RegraNegocioError as exc:
            q = Qualificador.query.get(seq)
            rotulo_q = f"{q.num_qualificador} {q.dsc_qualificador}" if q else str(seq)
            raise RegraNegocioError(f"{rotulo_q}: {exc.mensagem}")
        gravadas += 1
    return gravadas


def nos_do_plano(exercicio: int | None) -> list[dict]:
    """Árvore do plano em profundidade (para o formulário do cenário)."""
    from ..repositories import qualificador_repository as repo

    linhas: list[dict] = []

    def visitar(q, nivel, vistos):
        if q.seq_qualificador in vistos:
            raise q._erro_ciclo()
        vistos = vistos | {q.seq_qualificador}
        filhos = sorted((f for f in q.filhos if f.ind_status == 'A'),
                        key=lambda f: f.num_qualificador)
        linhas.append({'q': q, 'nivel': nivel, 'folha': not filhos,
                       'perna': perna_do_qualificador(q)})
        for filho in filhos:
            visitar(filho, nivel + 1, vistos)

    for raiz in repo.get_root_qualificadores(exercicio):
        visitar(raiz, 0, frozenset())
    return linhas


def _validar_proposta(simulador, qualificador, seq_projecao_versao: int) -> None:
    """RN27/RN29: versão publicada de cenário setorial, não devolvida,
    homogênea (ano-base e periodicidade) e cujo setor cobre o nó marcado."""
    from ..models import ProjecaoVersao, SimuladorCenario
    from .setor_previsao_service import no_no_recorte

    versao = ProjecaoVersao.query.get(seq_projecao_versao)
    if versao is None or versao.ind_publicado != 'S':
        raise RegraNegocioError("A proposta precisa ser uma versão publicada")
    origem = SimuladorCenario.query.get(versao.seq_simulador_cenario)
    if origem is None or origem.seq_setor_previsao is None:
        raise RegraNegocioError("A versão escolhida não é de um cenário setorial")
    if origem.seq_simulador_cenario == simulador.seq_simulador_cenario:
        raise RegraNegocioError("Um cenário não pode usar a própria versão como proposta")
    if versao.cod_situacao_proposta == 'D':
        raise RegraNegocioError(
            "Esta versão foi devolvida ao setor — escolha outra versão")
    if (origem.ano_base != simulador.ano_base
            or periodo_resolver.normalizar(origem.cod_periodicidade)
            != periodo_resolver.normalizar(simulador.cod_periodicidade)):
        raise RegraNegocioError(
            "A proposta tem ano-base ou periodicidade diferente deste cenário "
            f"({origem.ano_base}/{origem.cod_periodicidade} × "
            f"{simulador.ano_base}/{simulador.cod_periodicidade})")
    if not no_no_recorte(qualificador, origem.seq_setor_previsao):
        raise RegraNegocioError(
            f"O qualificador {qualificador.num_qualificador} está fora do "
            f"recorte do setor {origem.setor.sgl_setor if origem.setor else ''}")


def _validar_sem_sobreposicao_de_propostas(seq_simulador_cenario: int,
                                           qualificador) -> None:
    """RN28 — conflito é erro: duas propostas não podem cobrir a mesma folha.

    Com herança, proposta num ancestral e outra num descendente fariam a mais
    próxima vencer em SILÊNCIO; a regra recusa a sobreposição na gravação.
    """
    marcacoes = carregar_marcacoes(seq_simulador_cenario)
    propostas = {seq for seq, m in marcacoes.items()
                 if m.cod_metodo == PROPOSTA_SETORIAL
                 and seq != qualificador.seq_qualificador}
    if not propostas:
        return
    ancestrais = set()
    no = qualificador.pai
    while no is not None and no.seq_qualificador not in ancestrais:
        ancestrais.add(no.seq_qualificador)
        no = no.pai
    descendentes = {q.seq_qualificador for q in qualificador.get_todos_filhos()}
    conflito = propostas & (ancestrais | descendentes)
    if conflito:
        from ..models import Qualificador

        outro = Qualificador.query.get(next(iter(conflito)))
        raise RegraNegocioError(
            f"Conflito de propostas: {outro.num_qualificador} já recebe proposta "
            f"setorial e cobre as mesmas folhas de {qualificador.num_qualificador}")


# ---------------------------------------------------------------------------
# Realizado (bases de participação, perfil e percentual)
# ---------------------------------------------------------------------------

class _Realizado:
    """Realizado mensal por folha, em MAGNITUDE, costurado por raiz.

    Memoizado por (folha, ano) numa execução — a mesma folha é consultada para
    participação, perfil e percentual.
    """

    def __init__(self):
        self._cache: dict = {}

    def mensal(self, seq_folha: int, ano: int) -> dict[int, float]:
        chave = (seq_folha, ano)
        if chave in self._cache:
            return self._cache[chave]
        from sqlalchemy import extract, func

        from ..models import Lancamento
        from ..models.base import db
        from .serie_historica import seqs_da_rubrica

        mes_col = extract('month', Lancamento.dat_lancamento)
        linhas = (
            db.session.query(mes_col.label('mes'),
                             func.sum(Lancamento.valor_com_sinal))
            .filter(
                Lancamento.seq_qualificador.in_(seqs_da_rubrica(seq_folha)),
                Lancamento.ind_status == 'A',
                Lancamento.dat_lancamento >= date(ano, 1, 1),
                Lancamento.dat_lancamento <= date(ano, 12, 31),
            )
            .group_by(mes_col)
            .all()
        )
        valores = {int(mes): abs(float(total or 0)) for mes, total in linhas}
        self._cache[chave] = valores
        return valores

    def anual(self, seq_folha: int, ano: int) -> float:
        return sum(self.mensal(seq_folha, ano).values())

    def perfil(self, seq_folhas: list[int], ano: int) -> dict[int, float]:
        """Fração de cada mês no realizado do ano; sem realizado, 1/12."""
        soma = Counter()
        for seq in seq_folhas:
            soma.update(self.mensal(seq, ano))
        total = sum(soma.values())
        if total <= 0:
            return {m: 1 / 12 for m in range(1, 13)}
        return {m: soma.get(m, 0.0) / total for m in range(1, 13)}


# ---------------------------------------------------------------------------
# Motor
# ---------------------------------------------------------------------------

class _Execucao:
    """Estado de uma execução das marcações de um cenário."""

    def __init__(self, simulador, marcacoes: dict):
        self.simulador = simulador
        self.marcacoes = marcacoes
        self.ano = simulador.ano_base
        self.periodicidade = periodo_resolver.normalizar(
            simulador.cod_periodicidade or periodo_resolver.MENSAL)
        self.datas = periodo_resolver.serie_de_datas(
            self.periodicidade, self.ano, simulador.num_periodos or 12)
        self.quota = Counter((d.year, d.month) for d in self.datas)
        self.realizado = _Realizado()
        self.linhas: dict[str, list] = {'C': [], 'D': []}
        self.status: dict[int, dict] = {}
        self.cobertas: dict[str, set] = {'C': set(), 'D': set()}
        self.avisos: list[str] = []
        self._parametros = None

    # -- emissão ----------------------------------------------------------
    def emitir_mensal(self, perna, seq_folha, valores_mes: dict[int, float],
                      cod_metodo, seq_calculo):
        """Emite a série na periodicidade do cenário a partir de valores por
        MÊS. ANUAL soma os meses; quinzenal/semanal rateiam o mês pela quota
        de períodos que ele tem na série (mecanismo do R15)."""
        if self.periodicidade == periodo_resolver.ANUAL:
            total = sum(valores_mes.get(m, 0.0) for m in range(1, 13))
            for d in self.datas:
                self._linha(perna, d, seq_folha, total, cod_metodo, seq_calculo)
            return
        for d in self.datas:
            quota = self.quota[(d.year, d.month)] or 1
            valor = valores_mes.get(d.month, 0.0) / quota
            self._linha(perna, d, seq_folha, valor, cod_metodo, seq_calculo)

    def _linha(self, perna, data, seq_folha, valor, cod_metodo, seq_calculo):
        self.linhas[perna].append({
            'data': data,
            'seq_qualificador': seq_folha,
            'valor_projetado': abs(float(valor or 0)),
            'cod_metodo': cod_metodo,
            'seq_qualificador_calculo': seq_calculo,
        })

    def marcar(self, seq_folha, status, nota='', metodo=None, seq_no=None):
        self.status[seq_folha] = {'status': status, 'nota': nota,
                                  'cod_metodo': metodo, 'seq_no': seq_no}

    # -- participação -----------------------------------------------------
    def participacao(self, folhas: list) -> dict[int, float]:
        """Peso de cada folha no realizado do ano anterior ao ano-base.

        Sem realizado no ano anterior em NENHUMA folha, usa a média dos três
        anos anteriores; persistindo zero, pesos zero (folha sem participação,
        visível na cobertura — nunca rateio igual inventado).
        """
        pesos = {q.seq_qualificador: self.realizado.anual(q.seq_qualificador, self.ano - 1)
                 for q in folhas}
        if sum(pesos.values()) <= 0:
            pesos = {q.seq_qualificador: sum(
                self.realizado.anual(q.seq_qualificador, self.ano - k) for k in (1, 2, 3))
                for q in folhas}
        total = sum(pesos.values())
        if total <= 0:
            return {seq: 0.0 for seq in pesos}
        return {seq: peso / total for seq, peso in pesos.items()}

    def parametros(self) -> dict:
        if self._parametros is None:
            from ..repositories import formula_repository as f_repo

            self._parametros = {
                v.nom_parametro: float(v.val_parametro)
                for v in f_repo.get_valores_cenario(self.simulador.seq_simulador_cenario)}
        return self._parametros


def projetar(simulador, marcacoes: dict | None = None) -> dict:
    """Executa as marcações do cenário.

    Devolve `{'linhas': {'C': [...], 'D': [...]}, 'cobertas': {'C': set, 'D': set},
    'status': {seq_folha: {...}}, 'avisos': [...]}` — `cobertas` são as folhas
    cujo método vem de uma marcação (a configuração da perna não as projeta).
    """
    if marcacoes is None:
        marcacoes = carregar_marcacoes(simulador.seq_simulador_cenario)
    ex = _Execucao(simulador, marcacoes)
    if not marcacoes:
        return _saida(ex)

    exercicio = exercicio_do_cenario(simulador)
    setor = simulador.seq_setor_previsao
    if setor is not None:
        from .setor_previsao_service import no_no_recorte
    memo: dict = {}
    memo_setor: dict = {}
    grupos: dict[int, list] = {}
    for perna in ('C', 'D'):
        for folha in folhas_da_perna(perna, exercicio):
            # Cenário setorial só projeta o recorte do setor (RN24) — um bloco
            # marcado pode conter folha de outro setor (marcação própria).
            if setor is not None and not no_no_recorte(folha, setor, memo_setor):
                continue
            marcacao, _propria = marcacao_resolvida(folha, marcacoes, memo)
            if marcacao is None:
                continue
            ex.cobertas[perna].add(folha.seq_qualificador)
            grupos.setdefault(marcacao.seq_qualificador, []).append(folha)

    for seq_no, folhas in grupos.items():
        marcacao = marcacoes[seq_no]
        perna = perna_do_qualificador(folhas[0])
        config = config_da_marcacao(marcacao)
        try:
            _projetar_grupo(ex, perna, marcacao, config, folhas)
        except RegraNegocioError as exc:
            for folha in folhas:
                ex.marcar(folha.seq_qualificador, STATUS_LACUNA, str(exc),
                          marcacao.cod_metodo, seq_no)
    return _saida(ex)


def _saida(ex: _Execucao) -> dict:
    return {'linhas': ex.linhas, 'cobertas': ex.cobertas,
            'status': ex.status, 'avisos': ex.avisos}


def _projetar_grupo(ex: _Execucao, perna: str, marcacao, config: dict, folhas: list):
    metodo = marcacao.cod_metodo
    seq_no = marcacao.seq_qualificador
    no_folha = len(folhas) == 1 and folhas[0].seq_qualificador == seq_no
    calc = None if no_folha else seq_no

    if metodo == SEM_PROJECAO:
        for folha in folhas:
            ex.emitir_mensal(perna, folha.seq_qualificador, {}, metodo, calc)
            ex.marcar(folha.seq_qualificador, STATUS_DECLARADA,
                      config.get('motivo', ''), metodo, seq_no)
        return

    if metodo == PERCENTUAL:
        fator = 1 + float(config.get('percentual', 0)) / 100
        anos = int(config.get('anos_base') or 1)
        for folha in folhas:
            base = Counter()
            for k in range(1, anos + 1):
                base.update(ex.realizado.mensal(folha.seq_qualificador, ex.ano - k))
            valores = {m: base.get(m, 0.0) / anos * fator for m in range(1, 13)}
            ex.emitir_mensal(perna, folha.seq_qualificador, valores, metodo, calc)
            _status_por_valor(ex, folha, valores, metodo, seq_no,
                              'Sem realizado na base do percentual')
        return

    if metodo == LOA:
        from ..models import Loa

        for folha in folhas:
            loa = Loa.query.filter_by(seq_qualificador=folha.seq_qualificador,
                                      num_ano=ex.ano, ind_status='A').first()
            if loa is None:
                ex.marcar(folha.seq_qualificador, STATUS_LACUNA,
                          f"Sem LOA {ex.ano} para a rubrica", metodo, seq_no)
                continue
            perfil = ex.realizado.perfil([folha.seq_qualificador], ex.ano - 1)
            valores = {m: float(loa.val_loa) * perfil[m] for m in range(1, 13)}
            ex.emitir_mensal(perna, folha.seq_qualificador, valores, metodo, calc)
            ex.marcar(folha.seq_qualificador, STATUS_PROJETADA, '', metodo, seq_no)
        return

    if metodo == FORMULA:
        _projetar_formula(ex, perna, folhas, metodo, seq_no, calc)
        return

    if metodo == PROPOSTA_SETORIAL:
        _projetar_proposta(ex, perna, config, folhas, seq_no)
        return

    if metodo in (VALOR_FIXO, MODELO):
        if metodo == MODELO and (config.get('por_folha') or no_folha):
            for folha in folhas:
                total_mes = _treinar(ex, perna, config, [folha], seq_no)
                if total_mes is None:
                    continue
                ex.emitir_mensal(perna, folha.seq_qualificador, total_mes, metodo,
                                 None if no_folha else seq_no)
                _status_por_valor(ex, folha, total_mes, metodo, seq_no,
                                  'O modelo projetou zero')
            return
        if metodo == VALOR_FIXO:
            total_mes = _valor_fixo_mensal(ex, config, folhas)
        else:
            total_mes = _treinar(ex, perna, config, folhas, seq_no)
            if total_mes is None:
                return
        _distribuir(ex, perna, folhas, total_mes, metodo, seq_no, calc)
        return

    raise RegraNegocioError(f"Método '{metodo}' não existe")


def _status_por_valor(ex, folha, valores, metodo, seq_no, nota_zero):
    if sum(valores.values()) > 0:
        ex.marcar(folha.seq_qualificador, STATUS_PROJETADA, '', metodo, seq_no)
    else:
        ex.marcar(folha.seq_qualificador, STATUS_LACUNA, nota_zero, metodo, seq_no)


def _valor_fixo_mensal(ex, config, folhas) -> dict[int, float]:
    """Total do NÓ por mês: anual × perfil do realizado do nó (fallback 1/12)
    ou os doze valores informados."""
    if config.get('valores_mensais'):
        return {int(m): float(v) for m, v in config['valores_mensais'].items()}
    perfil = ex.realizado.perfil([q.seq_qualificador for q in folhas], ex.ano - 1)
    return _ratear_em_centavos(float(config.get('valor_anual') or 0), perfil)


def _ratear_em_centavos(total: float, pesos: dict) -> dict:
    """Reparte `total` pelos pesos em CENTAVOS, com o resíduo do
    arredondamento no maior peso — a soma das partes é exatamente o total
    (RN13). Sem isso, R$ 5.000.000,00 distribuídos pelo perfil mensal viravam
    R$ 4.999.999,99 nas folhas."""
    partes = {chave: round(total * peso, 2) for chave, peso in pesos.items()}
    if partes:
        maior = max(pesos, key=pesos.get)
        partes[maior] = round(partes[maior] + round(total, 2) - round(sum(partes.values()), 2), 2)
    return partes


def _distribuir(ex, perna, folhas, total_mes, metodo, seq_no, calc):
    """RN05/RN13: total do nó → folhas pela participação histórica; a folha
    de maior peso absorve o arredondamento (soma de controle exata)."""
    pesos = ex.participacao(folhas)
    if not any(pesos.values()):
        for folha in folhas:
            ex.marcar(folha.seq_qualificador, STATUS_SEM_PARTICIPACAO,
                      'Nenhuma folha do bloco tem realizado para ratear', metodo, seq_no)
        ex.avisos.append(
            f"Bloco {folhas[0].pai.num_qualificador if folhas[0].pai else ''}: "
            "sem realizado para distribuir — o total não foi projetado")
        return
    por_mes = {m: _ratear_em_centavos(v, pesos) for m, v in total_mes.items()}
    for folha in folhas:
        seq = folha.seq_qualificador
        valores = {m: partes[seq] for m, partes in por_mes.items()}
        ex.emitir_mensal(perna, seq, valores, metodo, calc)
        if pesos[seq] <= 0:
            ex.marcar(seq, STATUS_SEM_PARTICIPACAO,
                      'Sem realizado: participação zero no bloco', metodo, seq_no)
        else:
            ex.marcar(seq, STATUS_PROJETADA, '', metodo, seq_no)


def _treinar(ex, perna, config, folhas, seq_no) -> dict[int, float] | None:
    """Treina o modelo na série das folhas (soma costurada por raiz) e devolve
    o total projetado por MÊS do ano-base. Insuficiência vira lacuna com nota
    — nunca projeção zero em silêncio (R12)."""
    from dateutil.relativedelta import relativedelta

    from . import modelos_economicos_service as modelos

    modelo = config.get('modelo')
    seqs = [q.seq_qualificador for q in folhas]

    def _lacuna(nota):
        for folha in folhas:
            ex.marcar(folha.seq_qualificador, STATUS_LACUNA, nota, MODELO, seq_no)
        return None

    if modelo in ('CRESCIMENTO_ANO', 'MEDIA_CRESCIMENTO'):
        from .formula_engine import (
            projetar_crescimento_ultimo_ano,
            projetar_media_crescimento_anos,
        )

        mes_ref = int(config.get('mes_referencia') or 6)
        anos = config.get('anos_referencia') or [ex.ano - 1]
        if modelo == 'CRESCIMENTO_ANO':
            df = projetar_crescimento_ultimo_ano(
                seq_qualificadores=seqs, ano_projecao=ex.ano,
                ano_referencia=max(anos), mes_referencia=mes_ref, num_periodos=12)
        else:
            df = projetar_media_crescimento_anos(
                seq_qualificadores=seqs, ano_projecao=ex.ano,
                anos_referencia=anos, mes_referencia=mes_ref, num_periodos=12)
        return _df_por_mes(df, ex.ano)

    janela, minimo = MODELOS_DE_SERIE[modelo]
    fim = date(ex.ano - 1, 12, 31)
    inicio = fim - relativedelta(years=janela)
    if len(seqs) > 1:
        historico = modelos.obter_dados_historicos_agregados(seqs, inicio, fim)
    else:
        historico = modelos.obter_dados_historicos(seqs[0], inicio, fim)
    if len(historico) < minimo:
        return _lacuna(
            f"Histórico insuficiente para {ROTULO_MODELO[modelo]}: "
            f"{len(historico)} meses, mínimo {minimo}")
    historico = historico.copy()
    historico['valor'] = historico['valor'].abs()
    motor = {
        'HOLT_WINTERS': modelos.projetar_holt_winters,
        'ARIMA': modelos.projetar_arima,
        'SARIMA': modelos.projetar_sarima,
        'XGBOOST': modelos.projetar_xgboost,
        'LIGHTGBM': modelos.projetar_lightgbm,
        'MEDIA_HISTORICA': modelos.projetar_media_historica,
    }[modelo]
    try:
        df = motor(historico, 12, config.get('parametros') or {}, ex.ano)
    except RegraNegocioError:
        raise
    except Exception as exc:  # lib opcional ausente (libomp etc.)
        return _lacuna(f"{ROTULO_MODELO[modelo]} indisponível ({type(exc).__name__})")
    degradacao = getattr(df, 'attrs', {}).get('degradacao')
    if degradacao:
        ex.avisos.append(f"{ROTULO_MODELO[modelo]}: {degradacao}")
    return _df_por_mes(df, ex.ano)


def _df_por_mes(df, ano: int) -> dict[int, float]:
    import pandas as pd

    if df is None or len(df) == 0:
        return {}
    saida = Counter()
    for _, linha in df.iterrows():
        data = pd.Timestamp(linha['data'])
        if data.year != ano:
            continue
        saida[data.month] += abs(float(linha.get('valor_projetado', 0) or 0))
    return dict(saida)


def formula_da_folha(seq_simulador_cenario: int, seq_qualificador: int):
    """(expressão, origem) — própria do cenário vence a da biblioteca (RN18).
    `(None, None)` quando a folha não tem fórmula nenhuma."""
    from ..models import CenarioFormula, RubricaFormula

    propria = CenarioFormula.query.filter_by(
        seq_simulador_cenario=seq_simulador_cenario,
        seq_qualificador=seq_qualificador).first()
    if propria is not None:
        return propria.dsc_formula_expressao, 'CENARIO'
    biblioteca = RubricaFormula.query.filter_by(
        seq_qualificador=seq_qualificador, ind_status='A').first()
    if biblioteca is not None:
        return biblioteca.dsc_formula_expressao, 'BIBLIOTECA'
    return None, None


def _projetar_formula(ex, perna, folhas, metodo, seq_no, calc):
    from .formula_engine import avaliar_formula, calcular_base, calcular_base_anual

    simulador = ex.simulador
    config_base = {}
    if simulador.json_config_base:
        try:
            config_base = json.loads(simulador.json_config_base)
        except (json.JSONDecodeError, TypeError):
            config_base = {}
    metodo_base = simulador.cod_metodo_base or 'MEDIA_SIMPLES'
    for folha in folhas:
        seq = folha.seq_qualificador
        expressao, _origem = formula_da_folha(simulador.seq_simulador_cenario, seq)
        if expressao is None:
            ex.marcar(seq, STATUS_LACUNA,
                      'Folha sem fórmula (nem própria do cenário, nem na biblioteca)',
                      metodo, seq_no)
            continue
        try:
            if ex.periodicidade == periodo_resolver.ANUAL:
                base = calcular_base_anual(seq, metodo_base, config_base)
                total = avaliar_formula(expressao, {**ex.parametros(), 'base': base})
                valores = {1: total}  # ANUAL: emitir_mensal soma os meses
            else:
                valores = {}
                for mes in range(1, 13):
                    base = calcular_base(seq, mes, metodo_base, config_base)
                    valores[mes] = avaliar_formula(
                        expressao, {**ex.parametros(), 'base': base})
        except ValueError as exc:
            ex.marcar(seq, STATUS_LACUNA,
                      f"Fórmula não pôde ser avaliada: {exc}", metodo, seq_no)
            continue
        ex.emitir_mensal(perna, seq, valores, metodo, calc)
        _status_por_valor(ex, folha, valores, metodo, seq_no, 'A fórmula resultou em zero')


def _projetar_proposta(ex, perna, config, folhas, seq_no):
    """Copia da versão fixada as linhas das folhas do nó marcado (RN27/RN28)."""
    from ..models import ProjecaoValor, ProjecaoVersao, SimuladorCenario

    seq_versao = config.get('seq_projecao_versao')
    versao = ProjecaoVersao.query.get(seq_versao) if seq_versao else None
    origem = SimuladorCenario.query.get(versao.seq_simulador_cenario) if versao else None
    problema = None
    if versao is None or origem is None:
        problema = 'A versão da proposta não existe mais'
    elif versao.cod_situacao_proposta == 'D':
        problema = 'A versão fixada foi devolvida ao setor'
    elif (origem.ano_base != ex.ano or periodo_resolver.normalizar(origem.cod_periodicidade)
          != ex.periodicidade):
        problema = 'Proposta com ano-base ou periodicidade diferente do cenário'
    if problema:
        for folha in folhas:
            ex.marcar(folha.seq_qualificador, STATUS_LACUNA, problema,
                      PROPOSTA_SETORIAL, seq_no)
        return

    alvo = {q.seq_qualificador for q in folhas}
    recebidas = set()
    ignoradas = set()
    for linha in ProjecaoValor.query.filter_by(
            seq_projecao_versao=seq_versao, cod_tipo=perna).all():
        if linha.seq_qualificador not in alvo:
            ignoradas.add(linha.seq_qualificador)
            continue
        recebidas.add(linha.seq_qualificador)
        data = periodo_resolver.data_inicial_do_periodo(
            ex.periodicidade, linha.ano, linha.num_periodo)
        ex._linha(perna, data, linha.seq_qualificador, linha.val_projetado,
                  PROPOSTA_SETORIAL, seq_no)
    for folha in folhas:
        if folha.seq_qualificador in recebidas:
            ex.marcar(folha.seq_qualificador, STATUS_PROJETADA,
                      f"Versão {seq_versao} de {origem.nom_cenario}",
                      PROPOSTA_SETORIAL, seq_no)
        else:
            ex.marcar(folha.seq_qualificador, STATUS_LACUNA,
                      'A proposta fixada não traz valor para esta folha',
                      PROPOSTA_SETORIAL, seq_no)
    ignoradas.discard(None)
    if ignoradas:
        ex.avisos.append(
            f"Proposta {seq_versao}: {len(ignoradas)} rubrica(s) fora do nó "
            "marcado foram ignoradas")


# ---------------------------------------------------------------------------
# Saída por folha dos modelos agregados da configuração da perna (RN05/RN14)
# ---------------------------------------------------------------------------

def distribuir_projecao_agregada(projecao, seq_qualificadores, ano_base: int):
    """Distribui uma projeção AGREGADA (sem qualificador) entre os
    qualificadores do modelo, pela participação no realizado do ano anterior
    (fallback: três anos). O total por período é preservado.

    Devolve `None` quando não há por onde ratear (vários qualificadores e
    nenhum realizado): a projeção segue agregada, como antes — nunca um
    rateio igual inventado.
    """
    import pandas as pd

    if projecao is None or len(projecao) == 0:
        return None
    if 'seq_qualificador' in projecao.columns:
        return projecao.copy()
    seqs = [int(s) for s in (seq_qualificadores or [])]
    if not seqs:
        return None
    if len(seqs) == 1:
        pesos = {seqs[0]: 1.0}
    else:
        realizado = _Realizado()
        pesos = {s: realizado.anual(s, ano_base - 1) for s in seqs}
        if sum(pesos.values()) <= 0:
            pesos = {s: sum(realizado.anual(s, ano_base - k) for k in (1, 2, 3))
                     for s in seqs}
        total = sum(pesos.values())
        if total <= 0:
            return None
        pesos = {s: p / total for s, p in pesos.items()}
    linhas = []
    for _, linha in projecao.iterrows():
        valor = float(linha['valor_projetado'] or 0)
        for seq, peso in pesos.items():
            linhas.append({'data': linha['data'], 'seq_qualificador': seq,
                           'valor_projetado': valor * peso})
    detalhe = pd.DataFrame(linhas, columns=['data', 'seq_qualificador', 'valor_projetado'])
    detalhe.attrs = dict(getattr(projecao, 'attrs', {}))
    return detalhe


# ---------------------------------------------------------------------------
# Combinação com a configuração da perna
# ---------------------------------------------------------------------------

COLUNAS = ['data', 'seq_qualificador', 'valor_projetado', 'cod_metodo',
           'seq_qualificador_calculo']


def combinar(pernas: dict, simulador, marcacoes: dict) -> tuple[dict, dict]:
    """Junta a saída da configuração da perna (padrão) com a das marcações.

    Linhas do padrão para folhas cobertas por marcação saem (a marcação vence);
    linhas das marcações entram. Devolve `(pernas, execucao)` — o mesmo shape
    `{chave: (projecao, detalhada)}` que `executar_simulacao` já monta.
    """
    import pandas as pd

    execucao = projetar(simulador, marcacoes)
    saida = {}
    for chave, perna in (('receita', 'C'), ('despesa', 'D')):
        projecao, detalhada = pernas[chave]
        base = detalhada if detalhada is not None and len(detalhada) else projecao
        cobertas = execucao['cobertas'][perna]
        partes = []
        if base is not None and len(base):
            base = base.copy()
            if 'seq_qualificador' not in base.columns:
                base['seq_qualificador'] = None
                if cobertas:
                    execucao['avisos'].append(
                        f"O padrão da {chave} não é distribuído por qualificador "
                        "e foi mantido inteiro — confira se não duplica as marcações")
            else:
                base = base[~base['seq_qualificador'].isin(cobertas)]
            partes.append(base)
        novas = pd.DataFrame(execucao['linhas'][perna], columns=COLUNAS)
        if len(novas):
            partes.append(novas)
        partes = [p for p in partes if len(p)]
        if partes:
            detalhe = pd.concat(partes, ignore_index=True)
            detalhe['data'] = pd.to_datetime(detalhe['data'])
            total = (detalhe.groupby('data', as_index=False)['valor_projetado'].sum()
                     .sort_values('data').reset_index(drop=True))
        else:
            detalhe = pd.DataFrame(columns=COLUNAS)
            total = pd.DataFrame({'data': [], 'valor_projetado': []})
        saida[chave] = (total, detalhe)
    return saida, execucao


# ---------------------------------------------------------------------------
# Cobertura (RN11–RN13)
# ---------------------------------------------------------------------------

def cobertura(simulador, resultado: dict) -> dict:
    """Situação de cada folha relevante da perna após a execução.

    Folha relevante = folha ativa do plano do exercício do cenário (e, em
    cenário setorial, do recorte do setor) com movimento nos três anos
    anteriores ao ano-base OU com método declarado. Lacuna = relevante e sem
    projeção — "não projetei" nunca se confunde com "projetei zero".
    """
    status_marcacoes = (resultado.get('execucao_marcacoes') or {}).get('status', {})
    exercicio = exercicio_do_cenario(simulador)
    realizado = _Realizado()
    projetadas = {'C': set(), 'D': set()}
    agregado = []
    for chave, perna in (('receita', 'C'), ('despesa', 'D')):
        df = resultado.get(f'projecao_{chave}_detalhada')
        if df is None or not len(df):
            df = resultado.get(f'projecao_{chave}')
        if df is None or not len(df):
            continue
        positivos = df[df['valor_projetado'].astype(float).abs() > 0]
        if 'seq_qualificador' not in df.columns:
            if len(positivos):
                agregado.append(chave)
            continue
        if positivos['seq_qualificador'].isna().any():
            agregado.append(chave)
        projetadas[perna] = {int(s) for s in positivos['seq_qualificador'].dropna()}

    setor = simulador.seq_setor_previsao
    memo_setor: dict = {}
    if setor is not None:
        from .setor_previsao_service import no_no_recorte

    saida = {'C': [], 'D': [], 'lacunas': 0, 'avisos': list(
        (resultado.get('execucao_marcacoes') or {}).get('avisos', []))}
    for chave in agregado:
        saida['avisos'].append(
            f"Parte da projeção da {chave} vem de um modelo sem qualificador "
            "(LOA/regressão da configuração da perna): o total existe, mas não "
            "chega às rubricas — elas aparecem como lacuna. Use o método por "
            "qualificador para distribuí-lo.")
    for perna in ('C', 'D'):
        for folha in folhas_da_perna(perna, exercicio):
            seq = folha.seq_qualificador
            if setor is not None and not no_no_recorte(folha, setor, memo_setor):
                continue
            historico = sum(realizado.anual(seq, simulador.ano_base - k) for k in (1, 2, 3))
            info = status_marcacoes.get(seq)
            if info:
                status, nota = info['status'], info['nota']
            elif seq in projetadas[perna]:
                status, nota = STATUS_PROJETADA, ''
            elif historico > 0:
                status, nota = STATUS_LACUNA, 'Sem método: nenhuma marcação e o padrão da perna não a projeta'
            else:
                continue  # sem histórico e sem método: não é lacuna (RN11)
            item = {
                'seq_qualificador': seq,
                'num_qualificador': folha.num_qualificador,
                'dsc_qualificador': folha.dsc_qualificador,
                'status': status,
                'nota': nota,
                'historico': round(historico, 2),
                'cod_metodo': info['cod_metodo'] if info else None,
            }
            saida[perna].append(item)
            if status == STATUS_LACUNA:
                saida['lacunas'] += 1
    return saida


def resumo_cobertura(cob: dict) -> dict:
    """Forma curta gravada no `json_resumo` da versão (RN12)."""
    lacunas = [i['num_qualificador'] for p in ('C', 'D') for i in cob[p]
               if i['status'] == STATUS_LACUNA]
    return {'lacunas': len(lacunas), 'rubricas_sem_projecao': lacunas[:50]}


# ---------------------------------------------------------------------------
# Árvore para a tela (método resolvido por nó, próprio × herdado)
# ---------------------------------------------------------------------------

ROTULO_PADRAO = {
    'MANUAL': 'Manual (ajustes)',
    'FORMULA': 'Fórmula',
    'LOA': 'LOA',
    'REGRESSAO': 'Regressão',
    **ROTULO_MODELO,
}


def arvore(simulador, status: dict | None = None) -> list[dict]:
    """Linhas da árvore do plano do cenário, em profundidade, com o método
    RESOLVIDO de cada nó e de onde ele vem (próprio, herdado de um ancestral,
    padrão da perna ou nenhum). `status` é o da execução, por folha.

    A tela mostra a herança — "por que esta rubrica está em SARIMA?" não pode
    ser pergunta que só o código responde (lição da categoria fiscal).
    """
    from ..models import CenarioConfig
    from ..repositories import qualificador_repository as repo

    seq = simulador.seq_simulador_cenario
    marcacoes = carregar_marcacoes(seq)
    padroes = {c.cod_tipo_lancamento: c for c in CenarioConfig.query.filter_by(
        seq_simulador_cenario=seq).all()}
    exercicio = exercicio_do_cenario(simulador)
    setor = simulador.seq_setor_previsao
    if setor is not None:
        from .setor_previsao_service import no_no_recorte
    memo: dict = {}
    memo_setor: dict = {}
    status = status or {}
    linhas: list[dict] = []

    def visitar(q, nivel, vistos):
        if q.seq_qualificador in vistos:
            raise q._erro_ciclo()
        vistos = vistos | {q.seq_qualificador}
        filhos = sorted((f for f in q.filhos if f.ind_status == 'A'),
                        key=lambda f: f.num_qualificador)
        perna = perna_do_qualificador(q)
        marcacao, propria = marcacao_resolvida(q, marcacoes, memo)
        if marcacao is not None:
            config = config_da_marcacao(marcacao)
            metodo, rot = marcacao.cod_metodo, rotulo(marcacao.cod_metodo, config)
            origem = 'PROPRIA' if propria else 'HERDADA'
            de = marcacao.qualificador
        else:
            padrao = padroes.get(perna)
            config = {}
            metodo = None
            de = None
            if padrao is not None:
                rot = f"Padrão da perna · {ROTULO_PADRAO.get(padrao.cod_tipo_modelo, padrao.cod_tipo_modelo)}"
                origem = 'PADRAO'
            else:
                rot, origem = 'Sem método', 'NENHUM'
        linhas.append({
            'q': q,
            'nivel': nivel,
            'folha': not filhos,
            'perna': perna,
            'cod_metodo': metodo,
            'config': config,
            'rotulo': rot,
            'origem': origem,
            'de': de,
            'marcacao_propria': marcacoes.get(q.seq_qualificador),
            'fora_do_recorte': setor is not None and not no_no_recorte(q, setor, memo_setor),
            'status': status.get(q.seq_qualificador),
        })
        for filho in filhos:
            visitar(filho, nivel + 1, vistos)

    for raiz in repo.get_root_qualificadores(exercicio):
        visitar(raiz, 0, frozenset())
    return linhas


# ---------------------------------------------------------------------------
# Recomendações do backtest (RN10)
# ---------------------------------------------------------------------------

def recomendacoes_aplicaveis(simulador) -> list[dict]:
    """Recomendações gravadas pelo backtest que viram marcação MODELO.

    Só entram modelos do catálogo de marcação e aplicáveis à perna da folha.
    É SUGESTÃO — gravar é ação explícita do usuário (padrão da repartição).
    """
    from ..models import BacktestRecomendacao, Qualificador

    exercicio = exercicio_do_cenario(simulador)
    saida = []
    for rec in BacktestRecomendacao.query.order_by(BacktestRecomendacao.val_mape).all():
        modelo = (rec.cod_modelo or '').upper()
        if modelo not in MODELOS_DE_SERIE:
            continue
        q = Qualificador.query.get(rec.seq_qualificador)
        if q is None or q.ind_status != 'A':
            continue
        if exercicio is not None and q.num_ano_exercicio != exercicio:
            continue
        perna = perna_do_qualificador(q)
        if perna not in pernas_do_metodo(MODELO, {'modelo': modelo}):
            continue
        if any(r['seq_qualificador'] == q.seq_qualificador for r in saida):
            continue
        saida.append({
            'seq_qualificador': q.seq_qualificador,
            'num_qualificador': q.num_qualificador,
            'dsc_qualificador': q.dsc_qualificador,
            'modelo': modelo,
            'rotulo_modelo': ROTULO_MODELO[modelo],
            'erro': float(rec.val_mape) if rec.val_mape is not None else None,
        })
    return saida


def aplicar_recomendacoes(seq_simulador_cenario: int, seq_qualificadores: list[int],
                          user_id: int | None = None) -> int:
    """Grava as recomendações escolhidas como marcação PRÓPRIA da folha."""
    from ..models import SimuladorCenario

    simulador = SimuladorCenario.query.get(seq_simulador_cenario)
    if simulador is None:
        raise RegraNegocioError("Cenário inexistente")
    escolhidas = set(seq_qualificadores)
    n = 0
    for rec in recomendacoes_aplicaveis(simulador):
        if rec['seq_qualificador'] in escolhidas:
            definir_marcacao(seq_simulador_cenario, rec['seq_qualificador'],
                             MODELO, {'modelo': rec['modelo']}, user_id)
            n += 1
    return n
