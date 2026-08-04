"""Service layer for Simulador de Cenários."""
import json
from datetime import date

from ..auth.contexto import cod_pessoa_atual
from ..models import (
    CenarioAjuste,
    CenarioConfig,
    ModeloEconomicoParametro,
    SimuladorCenario,
    SimuladorCenarioHistorico,
)
from ..repositories import simulador_cenario_repository as repo
from ..repositories.simulador_cenario_historico_repository import (
    SimuladorCenarioHistoricoRepository,
)
from . import periodo_resolver

# ==================== CRUD Operations ====================

def list_simuladores() -> list[SimuladorCenario]:
    """Lista todos os cenários simuladores."""
    return repo.get_all_simuladores()


def list_active_simuladores() -> list[SimuladorCenario]:
    """Lista apenas cenários ativos."""
    return repo.get_active_simuladores()


def get_simulador(seq_simulador_cenario: int) -> SimuladorCenario | None:
    """Busca um cenário simulador por ID."""
    return repo.get_simulador_by_id(seq_simulador_cenario)


def delete_simulador(seq_simulador_cenario: int, user_id: int | None = None) -> SimuladorCenario | None:
    """Inativa logicamente um cenário simulador."""
    return repo.delete_simulador_logical(seq_simulador_cenario, user_id or cod_pessoa_atual())


# ==================== Criar Cenário Completo ====================

def criar_simulador_cenario(
    nom_cenario: str,
    dsc_cenario: str,
    ano_base: int,
    num_periodos: int,
    tipo_cenario_receita: str,
    config_receita: dict,
    tipo_cenario_despesa: str,
    config_despesa: dict,
    ajustes_receita: dict | None = None,
    ajustes_despesa: dict | None = None,
    user_id: int | None = None,
    cod_periodicidade: str = 'MENSAL',
    cod_metodo_base: str = 'MEDIA_SIMPLES',
    json_config_base: str | None = None,
) -> SimuladorCenario:
    """
    Cria um cenário simulador completo com receita e despesa.
    
    Args:
        nom_cenario: Nome do cenário
        dsc_cenario: Descrição
        ano_base: Ano base para projeção
        num_periodos: Número de meses a projetar
        tipo_cenario_receita: 'MANUAL', 'HOLT_WINTERS', 'ARIMA', 'SARIMA', 'REGRESSAO'
        config_receita: Dicionário com configuração específica do modelo
        ajustes_receita: Ajustes mensais para cenário manual (dict)
        tipo_cenario_despesa: 'MANUAL', 'LOA', 'MEDIA_HISTORICA'
        config_despesa: Dicionário com configuração específica
        ajustes_despesa: Ajustes mensais para cenário manual (dict)
        user_id: ID do usuário criando o cenário
        cod_periodicidade: 'ANUAL', 'MENSAL', 'QUINZENAL', 'SEMANAL'
        cod_metodo_base: 'MEDIA_SIMPLES', 'MEDIA_PONDERADA', 'VALOR_FIXO'
        json_config_base: JSON com config da base histórica
    
    Returns:
        SimuladorCenario criado
    """
    # TRANSAÇÃO ÚNICA (previsao R13): cabeçalho + configs + ajustes comitam
    # juntos — antes o cabeçalho já estava commitado quando a config falhava
    # (modelo não aplicável à perna) e sobrava um cenário órfão.
    from ..models.base import db
    from ..models.lancamento import TIPO_CREDITO, TIPO_DEBITO

    try:
        simulador = SimuladorCenario(
            nom_cenario=nom_cenario,
            dsc_cenario=dsc_cenario,
            ano_base=ano_base,
            num_periodos=num_periodos,
            cod_periodicidade=cod_periodicidade,
            cod_metodo_base=cod_metodo_base,
            json_config_base=json_config_base,
            ind_status='A',
            cod_pessoa_inclusao=user_id or cod_pessoa_atual(),
        )
        repo.create_simulador(simulador, commit=False)

        for perna, modelo, cfg, ajustes, prefixo in (
            (TIPO_CREDITO, tipo_cenario_receita, config_receita, ajustes_receita, ''),
            (TIPO_DEBITO, tipo_cenario_despesa, config_despesa, ajustes_despesa, 'desp_'),
        ):
            if not modelo:
                continue
            config = criar_config(
                simulador.seq_simulador_cenario, perna, modelo, cfg or {},
                commit=False)
            if modelo == 'MANUAL' and ajustes:
                _criar_ajustes(config.seq_cenario_config, ajustes, ano_base,
                               prefixo, commit=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return simulador


def _validar_modelo_na_perna(cod_tipo_modelo: str, cod_tipo_lancamento: str) -> None:
    """Catálogo: o modelo serve a esta perna? (R2)"""
    from ..models.simulador_cenario import pernas_do_modelo
    from .validacao import RegraNegocioError

    pernas = pernas_do_modelo(cod_tipo_modelo)
    if not pernas:
        raise RegraNegocioError(
            f"Tipo de modelo '{cod_tipo_modelo}' não está disponível")
    if cod_tipo_lancamento not in pernas:
        raise RegraNegocioError(
            f"O modelo '{cod_tipo_modelo}' não se aplica a essa perna "
            f"({cod_tipo_lancamento}) — aceita apenas {', '.join(pernas)}")


def criar_config(seq_simulador_cenario: int, cod_tipo_lancamento: str,
                 cod_tipo_modelo: str, configuracao: dict,
                 commit: bool = True) -> CenarioConfig:
    """Cria a configuração de UMA perna, validando catálogo e unicidade (R1/R2)."""
    from .validacao import RegraNegocioError

    _validar_modelo_na_perna(cod_tipo_modelo, cod_tipo_lancamento)
    if repo.get_config_by_perna(seq_simulador_cenario, cod_tipo_lancamento):
        raise RegraNegocioError(
            f"A perna {cod_tipo_lancamento} já está configurada neste cenário")

    return repo.create_config(CenarioConfig(
        seq_simulador_cenario=seq_simulador_cenario,
        cod_tipo_lancamento=cod_tipo_lancamento,
        cod_tipo_modelo=cod_tipo_modelo,
        json_configuracao=json.dumps(configuracao or {}),
    ), commit=commit)


def _validar_qualificador_folha(seq_qualificador: int) -> None:
    """Ajuste só aponta para folha (spec cadastros-nucleo R14).

    Fecha o terceiro verbo do plano ("lançamento/ajuste/mapeamento só em
    folha"): `lancamento_service` e `mapeamento_service` já validavam, o ajuste
    não. Mesma origem única — `Qualificador.is_folha()`.
    """
    from ..models import Qualificador
    from .validacao import RegraNegocioError

    qualificador = Qualificador.query.get(seq_qualificador)
    if qualificador is None or qualificador.ind_status != 'A':
        raise RegraNegocioError("Qualificador do ajuste inexistente ou inativo")
    if not qualificador.is_folha():
        raise RegraNegocioError(
            f"Ajustes só podem apontar para qualificadores folha — "
            f"{qualificador.num_qualificador} possui filhos ativos"
        )


def _criar_ajustes(seq_cenario_config: int, ajustes_data: dict, ano_base: int,
                   prefixo: str = '', commit: bool = True):
    """Ajustes de UMA perna. `prefixo='desp_'` para débito — o formato achatado
    do form web separa as pernas pelo prefixo da chave."""
    marca = f'val_ajuste_{prefixo}'
    for chave, valor in (ajustes_data or {}).items():
        if not chave.startswith(marca) or not valor:
            continue
        if not prefixo and chave.startswith('val_ajuste_desp_'):
            continue  # chave da outra perna
        try:
            partes = chave[len(marca):].split('_')
            mes, seq_qualificador = int(partes[0]), int(partes[1])
            tipo = ajustes_data.get(
                f'cod_tipo_ajuste_{prefixo}{mes}_{seq_qualificador}', 'P')
            val_ajuste = float(valor)
        except (ValueError, IndexError):
            continue  # chave malformada do form — ignorar é deliberado

        # ⚠️ A validação fica FORA do try acima. Lá dentro, o `except
        # (ValueError, IndexError)` engoliria qualquer coisa que casasse — e a
        # regra de negócio passaria a depender de qual exceção o parser resolve
        # tolerar. `RegraNegocioError` herda de Exception e escaparia hoje, mas
        # essa é a espécie de sutileza que quebra na próxima edição.
        _validar_qualificador_folha(seq_qualificador)
        # F10.1 (R25): ajuste aponta para o qualificador do exercício-alvo —
        # regra de transição, terceira porta ao lado de manual e importação.
        from ..models import Qualificador
        from .qualificador_service import validar_qualificador_do_exercicio

        validar_qualificador_do_exercicio(
            Qualificador.query.get(seq_qualificador), ano_base)

        repo.create_ajuste(CenarioAjuste(
            seq_cenario_config=seq_cenario_config,
            seq_qualificador=seq_qualificador, ano=ano_base, mes=mes,
            cod_tipo_ajuste=tipo, val_ajuste=val_ajuste,
        ), commit=commit)


def _criar_parametros_economicos(seq_cenario_config: int, parametros: list[dict]):
    """Helper para criar parâmetros de modelos econômicos."""
    for param in parametros:
        modelo_param = ModeloEconomicoParametro(
            seq_cenario_config=seq_cenario_config,
            nom_variavel=param['nome'],
            val_coeficiente=param['coeficiente'],
            json_valores_historicos=json.dumps(param.get('valores_historicos', [])),
        )
        repo.create_parametro_economico(modelo_param)


# ==================== Atualizar Cenário ====================

def atualizar_simulador_cenario(
    seq_simulador_cenario: int,
    nom_cenario: str,
    dsc_cenario: str,
    ano_base: int,
    num_periodos: int,
    tipo_cenario_receita: str,
    config_receita: dict,
    tipo_cenario_despesa: str,
    config_despesa: dict,
    ajustes_receita: dict | None = None,
    ajustes_despesa: dict | None = None,
    user_id: int | None = None,
    cod_periodicidade: str = 'MENSAL',
    cod_metodo_base: str = 'MEDIA_SIMPLES',
    json_config_base: str | None = None,
) -> SimuladorCenario | None:
    """Atualiza um cenário simulador existente."""
    simulador = repo.get_simulador_by_id(seq_simulador_cenario)
    if not simulador:
        return None
    
    # Criar snapshot do estado atual ANTES de atualizar
    try:
        criar_snapshot_cenario(seq_simulador_cenario, user_id)
    except Exception as e:
        # Log error but continue with update
        print(f"Erro ao criar snapshot: {e}")
    
    # Atualizar dados principais
    simulador.nom_cenario = nom_cenario
    simulador.dsc_cenario = dsc_cenario
    simulador.ano_base = ano_base
    simulador.num_periodos = num_periodos
    simulador.cod_periodicidade = cod_periodicidade
    simulador.cod_metodo_base = cod_metodo_base
    simulador.json_config_base = json_config_base
    simulador.dat_alteracao = date.today()
    simulador.cod_pessoa_alteracao = user_id or cod_pessoa_atual()
    
    # Atualização por perna — sem os dois blocos espelhados de antes
    from ..models.lancamento import TIPO_CREDITO, TIPO_DEBITO

    # TRANSAÇÃO ÚNICA (previsao R13): a exclusão dos ajustes antigos fica
    # PENDENTE até o commit final — se os novos falharem no meio, o rollback
    # devolve os antigos (antes: exclusão commitada + novos parciais).
    from ..models.base import db

    try:
        for perna, modelo, cfg, ajustes, prefixo in (
            (TIPO_CREDITO, tipo_cenario_receita, config_receita, ajustes_receita, ''),
            (TIPO_DEBITO, tipo_cenario_despesa, config_despesa, ajustes_despesa, 'desp_'),
        ):
            config = repo.get_config_by_perna(seq_simulador_cenario, perna)
            if config is None:
                if modelo:
                    config = criar_config(seq_simulador_cenario, perna, modelo,
                                          cfg or {}, commit=False)
                else:
                    continue
            elif modelo:
                _validar_modelo_na_perna(modelo, perna)
                config.cod_tipo_modelo = modelo
                config.json_configuracao = json.dumps(cfg) if cfg else None

            repo.delete_ajustes_by_config_ano(config.seq_cenario_config,
                                              ano_base, commit=False)
            if ajustes:
                _criar_ajustes(config.seq_cenario_config, ajustes, ano_base,
                               prefixo, commit=False)

            if perna == TIPO_CREDITO and modelo == 'REGRESSAO' and (cfg or {}).get('parametros'):
                repo.delete_parametros_by_config(config.seq_cenario_config,
                                                 commit=False)
                _criar_parametros_economicos(config.seq_cenario_config,
                                             cfg['parametros'])

        repo.commit()
    except Exception:
        db.session.rollback()
        raise
    return simulador


# ==================== Obter Dados Completos ====================

def obter_simulador_completo(seq_simulador_cenario: int) -> dict | None:
    """Cenário com as configs por perna.

    O shape mantém as chaves 'receita'/'despesa' por compatibilidade — quem
    consome (web, snapshot, `executar_simulacao`) fala essa língua. O que
    unificou foi o ARMAZENAMENTO e o despacho; o DTO é fachada.
    """
    from ..models.lancamento import TIPO_CREDITO, TIPO_DEBITO

    simulador = repo.get_simulador_by_id(seq_simulador_cenario)
    if not simulador:
        return None

    resultado = {'simulador': simulador, 'receita': {}, 'despesa': {}}
    for perna, chave in ((TIPO_CREDITO, 'receita'), (TIPO_DEBITO, 'despesa')):
        config = repo.get_config_by_perna(seq_simulador_cenario, perna)
        if config is None:
            continue
        resultado[chave]['config'] = config
        resultado[chave]['ajustes'] = repo.get_ajustes_by_config(config.seq_cenario_config)
        if perna == TIPO_CREDITO:
            resultado[chave]['parametros'] = repo.get_parametros_by_config(
                config.seq_cenario_config)
    return resultado


# ==================== Histórico de Cenários ====================

def criar_snapshot_cenario(seq_simulador_cenario: int, user_id: int | None = None) -> SimuladorCenarioHistorico:
    """
    Cria um snapshot do estado atual do cenário.
    
    Args:
        seq_simulador_cenario: ID do cenário
        user_id: ID do usuário criando o snapshot
    
    Returns:
        SimuladorCenarioHistorico criado
    """
    # Obter estado completo do cenário
    cenario_completo = obter_simulador_completo(seq_simulador_cenario)
    
    if not cenario_completo:
        raise ValueError(f"Cenário {seq_simulador_cenario} não encontrado")
    
    # Serializar para JSON
    snapshot_data = {
        'simulador': {
            'seq_simulador_cenario': cenario_completo['simulador'].seq_simulador_cenario,
            'nom_cenario': cenario_completo['simulador'].nom_cenario,
            'dsc_cenario': cenario_completo['simulador'].dsc_cenario,
            'ano_base': cenario_completo['simulador'].ano_base,
            'num_periodos': cenario_completo['simulador'].num_periodos,
        },
        'receita': {
            'config': {
                'cod_tipo_cenario': cenario_completo['receita']['config'].cod_tipo_modelo if cenario_completo['receita'].get('config') else None,
                'json_configuracao': cenario_completo['receita']['config'].json_configuracao if cenario_completo['receita'].get('config') else None,
            },
            'ajustes': [
                {
                    'seq_qualificador': a.seq_qualificador,
                    'ano': a.ano,
                    'mes': a.mes,
                    'cod_tipo_ajuste': a.cod_tipo_ajuste,
                    'val_ajuste': float(a.val_ajuste) if a.val_ajuste else 0
                }
                for a in cenario_completo['receita'].get('ajustes', [])
            ]
        },
        'despesa': {
            'config': {
                'cod_tipo_cenario': cenario_completo['despesa']['config'].cod_tipo_modelo if cenario_completo['despesa'].get('config') else None,
                'json_configuracao': cenario_completo['despesa']['config'].json_configuracao if cenario_completo['despesa'].get('config') else None,
            },
            'ajustes': [
                {
                    'seq_qualificador': a.seq_qualificador,
                    'ano': a.ano,
                    'mes': a.mes,
                    'cod_tipo_ajuste': a.cod_tipo_ajuste,
                    'val_ajuste': float(a.val_ajuste) if a.val_ajuste else 0
                }
                for a in cenario_completo['despesa'].get('ajustes', [])
            ]
        }
    }
    
    # Criar snapshot
    historico_repo = SimuladorCenarioHistoricoRepository()
    snapshot = SimuladorCenarioHistorico(
        seq_simulador_cenario=seq_simulador_cenario,
        cod_pessoa_snapshot=user_id or cod_pessoa_atual(),
        json_snapshot=json.dumps(snapshot_data)
    )
    
    return historico_repo.create_snapshot(snapshot)


def get_versao_inicial_cenario(seq_simulador_cenario: int, ano: int | None = None) -> dict | None:
    """
    Retorna a primeira versão do cenário (do histórico ou atual).
    
    Args:
        seq_simulador_cenario: ID do cenário
        ano: Ano para filtrar snapshots (opcional)
    
    Returns:
        Dicionário com dados do cenário ou None
    """
    historico_repo = SimuladorCenarioHistoricoRepository()
    primeiro_snapshot = historico_repo.get_primeiro_snapshot(seq_simulador_cenario, ano)
    
    if primeiro_snapshot:
        return json.loads(primeiro_snapshot.json_snapshot)
    
    # Fallback: usar cenário atual
    return obter_simulador_completo(seq_simulador_cenario)


def get_versao_final_cenario(seq_simulador_cenario: int, ano: int | None = None) -> dict | None:
    """
    Retorna a última versão do cenário (do histórico ou atual).
    
    Args:
        seq_simulador_cenario: ID do cenário
        ano: Ano para filtrar snapshots (opcional)
    
    Returns:
        Dicionário com dados do cenário ou None
    """
    historico_repo = SimuladorCenarioHistoricoRepository()
    ultimo_snapshot = historico_repo.get_ultimo_snapshot(seq_simulador_cenario, ano)
    
    if ultimo_snapshot:
        return json.loads(ultimo_snapshot.json_snapshot)
    
    # Fallback: usar cenário atual
    return obter_simulador_completo(seq_simulador_cenario)


# ==================== Executar Simulação ====================

def _projetar_perna(perna: str, config, ajustes, simulador, modelos, pd):
    """Despacha UMA perna para o motor do seu `cod_tipo_modelo`.

    Substitui os dois blocos espelhados de ~200 linhas que existiam aqui: os
    ramos de receita e de despesa eram cópia literal um do outro salvo o nome
    (as duas funções MANUAL diferiam em UMA linha funcional). Devolve
    `(projecao, detalhada)`.

    ⚠️ Convenção de sinal (D7/R6): todo motor devolve MAGNITUDE. O sinal do
    fluxo vem da perna na leitura — a mesma regra que a F6.1b deu ao lançamento.
    """
    from datetime import date

    from dateutil.relativedelta import relativedelta

    from ..models.lancamento import TIPO_CREDITO
    from .formula_engine import (
        projetar_cenario_formula,
        projetar_crescimento_ultimo_ano,
        projetar_media_crescimento_anos,
    )

    vazio = pd.DataFrame({'data': [], 'valor_projetado': []})
    if config is None:
        return vazio, None

    modelo = config.cod_tipo_modelo
    periodicidade = periodo_resolver.normalizar(simulador.cod_periodicidade or 'MENSAL')
    ano_base = simulador.ano_base
    meses = simulador.num_periodos
    cfg = json.loads(config.json_configuracao or '{}')
    tipo_fluxo = 'receita' if perna == TIPO_CREDITO else 'despesa'

    def _historico(anos_atras: int = 3):
        """Série histórica da perna EM MAGNITUDE, no recorte do modelo.

        ⚠️ A magnitude vale para a entrada, não só para a saída (R6). Os
        motores foram escritos assumindo série positiva — `projetar_media_
        historica` aplica um piso `max(valor, 0)` — e com a despesa chegando
        negativa ele projetava ZERO para toda despesa, sempre. Bug anterior a
        esta fase, mascarado por um tempo pelo resíduo da F6.1b. Com uma
        convenção só (valor positivo, sinal na perna) o piso volta a fazer o
        que pretendia: barrar projeção negativa.
        """
        quals = cfg.get('seq_qualificadores', [])
        um = cfg.get('seq_qualificador')
        fim = date(ano_base - 1, 12, 31)
        inicio = fim - relativedelta(years=anos_atras)
        if quals and len(quals) > 1:
            historico = modelos.obter_dados_historicos_agregados(quals, inicio, fim)
        elif um:
            historico = modelos.obter_dados_historicos(um, inicio, fim)
        else:
            return pd.DataFrame(columns=['data', 'valor'])
        if len(historico) > 0:
            historico = historico.copy()
            historico['valor'] = historico['valor'].abs()
        return historico

    def _com_serie_info(projecao, historico):
        """F10.2 (previsao R17): a projeção declara com quanto treinou —
        anexado DEPOIS de `_magnitude` (cópias podem perder attrs)."""
        try:
            projecao.attrs['serie_info'] = {
                'pontos': int(len(historico)),
                'anos': sorted({d.year for d in historico['data']}),
            }
        except Exception:  # cosmético — nunca derruba a projeção
            pass
        return projecao

    if modelo == 'MANUAL':
        projecao = _executar_cenario_manual(ajustes, ano_base, meses, periodicidade)
        return projecao, projecao.copy()

    if modelo in ('HOLT_WINTERS', 'ARIMA', 'SARIMA', 'XGBOOST', 'LIGHTGBM'):
        motor = {
            'HOLT_WINTERS': modelos.projetar_holt_winters,
            'ARIMA': modelos.projetar_arima,
            'SARIMA': modelos.projetar_sarima,
            'XGBOOST': modelos.projetar_xgboost,
            'LIGHTGBM': modelos.projetar_lightgbm,
        }[modelo]
        historico = _historico()
        projecao = motor(historico, meses, cfg, ano_base) if len(historico) >= 12 else vazio
        return _com_serie_info(_magnitude(projecao), historico), None

    if modelo == 'REGRESSAO':
        return _magnitude(modelos.projetar_regressao_multipla(meses, cfg, ano_base)), None

    if modelo == 'LOA':
        return _magnitude(modelos.projetar_loa(meses, cfg)), None

    if modelo == 'MEDIA_HISTORICA':
        historico = _historico()
        projecao = (modelos.projetar_media_historica(historico, meses, cfg, ano_base)
                    if len(historico) > 0 else vazio)
        return _com_serie_info(_magnitude(projecao), historico), None

    if modelo == 'FORMULA':
        config_base = {}
        if simulador.json_config_base:
            try:
                config_base = json.loads(simulador.json_config_base)
            except (json.JSONDecodeError, TypeError):
                pass
        projecao = projetar_cenario_formula(
            seq_simulador_cenario=simulador.seq_simulador_cenario,
            ano_base=ano_base, periodos=meses, tipo_fluxo=tipo_fluxo,
            periodicidade=simulador.cod_periodicidade or 'ANUAL',
            metodo_base=simulador.cod_metodo_base or 'MEDIA_SIMPLES',
            config_base=config_base,
        )
        projecao = _magnitude(projecao)
        return projecao, (projecao.copy() if len(projecao) > 0 else None)

    if modelo in ('CRESCIMENTO_ANO', 'MEDIA_CRESCIMENTO'):
        config_base = json.loads(simulador.json_config_base or '{}')
        anos = config_base.get('anos', [])
        mes_ref = cfg.get('mes_referencia', 6)
        quals = cfg.get('seq_qualificadores', [])
        if modelo == 'CRESCIMENTO_ANO':
            projecao = projetar_crescimento_ultimo_ano(
                seq_qualificadores=quals, ano_projecao=ano_base,
                ano_referencia=max(anos) if anos else ano_base - 1,
                mes_referencia=mes_ref, num_periodos=meses)
        else:
            projecao = projetar_media_crescimento_anos(
                seq_qualificadores=quals, ano_projecao=ano_base,
                anos_referencia=anos, mes_referencia=mes_ref, num_periodos=meses)
        projecao = _magnitude(projecao)
        return projecao, (projecao.copy() if len(projecao) > 0 else None)

    return vazio, None


def _magnitude(projecao):
    """Garante a convenção do R6: valor projetado sempre positivo."""
    if projecao is None or len(projecao) == 0:
        return projecao
    projecao = projecao.copy()
    projecao['valor_projetado'] = projecao['valor_projetado'].abs()
    return projecao


def executar_simulacao(seq_simulador_cenario: int) -> dict | None:
    """Executa a simulação do cenário, uma perna por configuração.

    O shape de retorno é o mesmo de antes da unificação — `projecao_receita`,
    `projecao_despesa`, `_detalhada`, `cenario_total` e `resumo` —, porque
    `projecao_versao_service._montar_linhas_valor` e `dfc_projecao._mapa_ao_vivo`
    dependem dele.
    """
    import pandas as pd

    from ..models.lancamento import TIPO_CREDITO, TIPO_DEBITO
    from . import modelos_economicos_service as modelos

    cenario_completo = obter_simulador_completo(seq_simulador_cenario)
    if not cenario_completo:
        return None

    simulador = cenario_completo['simulador']
    pernas = {}
    for perna, chave in ((TIPO_CREDITO, 'receita'), (TIPO_DEBITO, 'despesa')):
        secao = cenario_completo.get(chave) or {}
        pernas[chave] = _projetar_perna(
            perna, secao.get('config'), secao.get('ajustes', []),
            simulador, modelos, pd)

    projecao_receita, projecao_receita_detalhada = pernas['receita']
    projecao_despesa, projecao_despesa_detalhada = pernas['despesa']

    cenario_total = _calcular_cenario_total(projecao_receita, projecao_despesa)

    # Degradação NUNCA silenciosa (previsao R12): quando um motor caiu para o
    # fallback, a mensagem viaja em attrs['degradacao'] — agregada aqui para
    # qualquer consumidor (padrão `projecao_origem.ao_vivo` da F5.2).
    degradacoes = []
    for chave, (projecao, _detalhada) in pernas.items():
        mensagem = getattr(projecao, 'attrs', {}).get('degradacao')
        if mensagem:
            degradacoes.append({'perna': chave, 'mensagem': mensagem})

    # F10.2 (previsao R17): o resultado declara com quanto cada perna treinou
    # (attrs['serie_info'] dos modelos treináveis). Chave aditiva; a versão
    # publicada reconstruída não a tem — consumidores tratam ausência.
    series_info = {}
    for chave, (projecao, _detalhada) in pernas.items():
        info = getattr(projecao, 'attrs', {}).get('serie_info')
        if info:
            series_info[chave] = info

    resumo = {
        'total_receita': projecao_receita['valor_projetado'].sum() if len(projecao_receita) > 0 else 0,
        'total_despesa': projecao_despesa['valor_projetado'].sum() if len(projecao_despesa) > 0 else 0,
        'saldo_final': 0,
    }
    resumo['saldo_final'] = resumo['total_receita'] - abs(resumo['total_despesa'])

    return {
        'simulador': simulador,
        'projecao_receita': projecao_receita,
        'projecao_despesa': projecao_despesa,
        'projecao_receita_detalhada': projecao_receita_detalhada,
        'projecao_despesa_detalhada': projecao_despesa_detalhada,
        'cenario_total': cenario_total,
        'resumo': resumo,
        'degradacoes': degradacoes,
        'series_info': series_info,
    }


def _executar_cenario_manual(ajustes: list, ano_base: int, num_periodos: int,
                             periodicidade: str = 'MENSAL') -> 'pd.DataFrame':  # noqa: F821 - import tardio de pandas, anotação-string
    """Cenário manual a partir dos ajustes — uma função para as DUAS pernas.

    Antes havia `_receita` e `_despesa`, 69 e 67 linhas, diferindo em UMA linha
    funcional: a de despesa aplicava `abs()`. Com o R6 (todo motor devolve
    magnitude) o `abs()` vale para as duas, e a cópia deixou de ter razão.
    """
    import pandas as pd

    from . import modelos_economicos_service as modelos

    # Criar lista de todos os meses e qualificadores
    records = []
    
    # Agrupar ajustes por (mes, qualificador)
    ajustes_map = {}
    qualificadores = set()
    
    for ajuste in ajustes:
        ajustes_map[(ajuste.mes, ajuste.seq_qualificador)] = {
            'tipo': ajuste.cod_tipo_ajuste,
            'valor': float(ajuste.val_ajuste)
        }
        qualificadores.add(ajuste.seq_qualificador)
        
    # Buscar dados históricos do ano anterior para base de cálculo de porcentagem
    ano_ref = ano_base - 1
    data_inicio_ref = date(ano_ref, 1, 1)
    data_fim_ref = date(ano_ref, 12, 31)
    valores_ref = {} # (seq, mes) -> valor
    
    if qualificadores:
        # Otimização: buscar dados apenas se houver ajustes percentuais?
        # Por simplicidade, buscamos para todos os qualificadores envolvidos
        for seq in qualificadores:
            df_hist = modelos.obter_dados_historicos(seq, data_inicio_ref, data_fim_ref)
            for _, row in df_hist.iterrows():
                valores_ref[(seq, row['data'].month)] = row['valor']
    
    # F6.3 (R9): as datas vêm do resolver, na granularidade da periodicidade.
    # Antes eram sempre `relativedelta(months=i)`, então 52 "semanas" viravam
    # 52 meses. O ajuste continua indexado pelo MÊS da data — é o grão em que o
    # usuário preenche a tela.
    datas = periodo_resolver.serie_de_datas(periodicidade, ano_base, num_periodos)

    # R15 (L8): o ajuste é MENSAL; em quinzenal/semanal o mês tem 2/4-5
    # períodos e emitir o valor cheio em cada um multiplicava o mês
    # (R$ 120 mil viravam R$ 240–600 mil). O valor do mês é RATEADO pela
    # quota de períodos que o mês tem NESTA série — MENSAL/ANUAL têm quota 1,
    # mecanismo único e inerte onde já estava certo.
    from collections import Counter
    periodos_no_mes = Counter((d.year, d.month) for d in datas)

    for i, data_mes in enumerate(datas):
        mes = data_mes.month
        quota = periodos_no_mes[(data_mes.year, data_mes.month)] or 1

        for seq_qualificador in qualificadores:
            ajuste = ajustes_map.get((mes, seq_qualificador))
            
            if not ajuste:
                valor_projetado = 0
            else:
                tipo = ajuste['tipo']
                val_ajuste = ajuste['valor']
                
                if tipo == 'V':
                    # Valor fixo MENSAL rateado pelos períodos do mês
                    valor_projetado = val_ajuste / quota
                else:
                    # Porcentagem sobre o total MENSAL do ano anterior, rateada
                    valor_ref = valores_ref.get((seq_qualificador, mes), 0)
                    valor_projetado = valor_ref * (1 + val_ajuste / 100) / quota
            
            records.append({
                'data': data_mes,
                'seq_qualificador': seq_qualificador,
                'valor_projetado': abs(valor_projetado)
            })
            
    if not records:
        return pd.DataFrame(columns=['data', 'seq_qualificador', 'valor_projetado'])
        
    return pd.DataFrame(records)


def _calcular_cenario_total(projecao_receita: 'pd.DataFrame', projecao_despesa: 'pd.DataFrame') -> 'pd.DataFrame':  # noqa: F821 - import tardio de pandas, anotação-string
    """Combina projeções de receita e despesa em um cenário total."""
    import pandas as pd
    
    # Agregar por data se houver detalhamento por qualificador
    if 'seq_qualificador' in projecao_receita.columns:
        df_receita = projecao_receita.groupby('data')['valor_projetado'].sum().reset_index()
    else:
        df_receita = projecao_receita.copy() if len(projecao_receita) > 0 else pd.DataFrame({'data': [], 'valor_projetado': []})
        
    if 'seq_qualificador' in projecao_despesa.columns:
        df_despesa = projecao_despesa.groupby('data')['valor_projetado'].sum().reset_index()
    else:
        df_despesa = projecao_despesa.copy() if len(projecao_despesa) > 0 else pd.DataFrame({'data': [], 'valor_projetado': []})
    
    # Renomear colunas
    df_receita = df_receita.rename(columns={'valor_projetado': 'receita'})
    df_despesa = df_despesa.rename(columns={'valor_projetado': 'despesa'})
    
    # Merge
    if len(df_receita) == 0 and len(df_despesa) == 0:
        return pd.DataFrame(columns=['data', 'receita', 'despesa', 'saldo'])
        
    cenario_total = pd.merge(df_receita, df_despesa, on='data', how='outer').fillna(0)
    
    # Calcular saldo
    cenario_total['saldo'] = cenario_total['receita'] - cenario_total['despesa']
    
    return cenario_total.sort_values('data')
