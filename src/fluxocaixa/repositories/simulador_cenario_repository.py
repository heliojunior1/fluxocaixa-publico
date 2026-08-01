"""Repository for Simulador de Cenários functionality."""

from typing import List, Optional
from sqlalchemy import and_

from ..models import (
    db,
    SimuladorCenario,
    CenarioConfig,
    CenarioAjuste,
    ModeloEconomicoParametro,
)


# ==================== SimuladorCenario ====================

def get_all_simuladores() -> List[SimuladorCenario]:
    """Retorna todos os cenários simuladores."""
    return SimuladorCenario.query.order_by(SimuladorCenario.dat_criacao.desc()).all()


def get_active_simuladores() -> List[SimuladorCenario]:
    """Retorna apenas cenários ativos."""
    return (
        SimuladorCenario.query
        .filter_by(ind_status='A')
        .order_by(SimuladorCenario.dat_criacao.desc())
        .all()
    )


def get_simulador_by_id(seq_simulador_cenario: int) -> Optional[SimuladorCenario]:
    """Busca um cenário simulador por ID."""
    return SimuladorCenario.query.get(seq_simulador_cenario)


def create_simulador(simulador: SimuladorCenario) -> SimuladorCenario:
    """Cria um novo cenário simulador."""
    db.session.add(simulador)
    db.session.commit()
    return simulador


def update_simulador(simulador: SimuladorCenario) -> SimuladorCenario:
    """Atualiza um cenário simulador existente."""
    db.session.commit()
    return simulador


def delete_simulador_logical(seq_simulador_cenario: int, user_id: int = 1) -> Optional[SimuladorCenario]:
    """Inativa logicamente um cenário simulador."""
    from datetime import date
    
    simulador = get_simulador_by_id(seq_simulador_cenario)
    if simulador:
        simulador.ind_status = 'I'
        simulador.cod_pessoa_alteracao = user_id
        simulador.dat_alteracao = date.today()
        db.session.commit()
    return simulador



# ==================== Configuração por perna (F6.2) ====================
# Uma função por operação, com a perna como PARÂMETRO — antes havia um par
# espelhado (receita/despesa) para cada uma delas.

def get_configs_by_simulador(seq_simulador_cenario: int) -> List[CenarioConfig]:
    return (CenarioConfig.query
            .filter_by(seq_simulador_cenario=seq_simulador_cenario)
            .order_by(CenarioConfig.cod_tipo_lancamento)
            .all())


def get_config_by_perna(seq_simulador_cenario: int,
                        cod_tipo_lancamento: str) -> Optional[CenarioConfig]:
    return CenarioConfig.query.filter_by(
        seq_simulador_cenario=seq_simulador_cenario,
        cod_tipo_lancamento=cod_tipo_lancamento,
    ).first()


def create_config(config: CenarioConfig) -> CenarioConfig:
    db.session.add(config)
    db.session.commit()
    db.session.refresh(config)
    return config


def update_config(config: CenarioConfig) -> CenarioConfig:
    db.session.commit()
    db.session.refresh(config)
    return config


def delete_config(seq_cenario_config: int) -> None:
    config = CenarioConfig.query.get(seq_cenario_config)
    if config is not None:
        db.session.delete(config)   # cascade leva os ajustes junto
        db.session.commit()


def get_ajustes_by_config(seq_cenario_config: int) -> List[CenarioAjuste]:
    return CenarioAjuste.query.filter_by(seq_cenario_config=seq_cenario_config).all()


def get_ajustes_by_config_and_year(seq_cenario_config: int, ano: int) -> List[CenarioAjuste]:
    return (CenarioAjuste.query
            .filter_by(seq_cenario_config=seq_cenario_config, ano=ano)
            .all())


def create_ajuste(ajuste: CenarioAjuste) -> CenarioAjuste:
    db.session.add(ajuste)
    db.session.commit()
    db.session.refresh(ajuste)
    return ajuste


def delete_ajustes_by_config_ano(seq_cenario_config: int, ano: int) -> None:
    CenarioAjuste.query.filter_by(
        seq_cenario_config=seq_cenario_config, ano=ano
    ).delete(synchronize_session=False)
    db.session.commit()


def get_parametros_by_config(seq_cenario_config: int) -> List[ModeloEconomicoParametro]:
    """Retorna parâmetros econômicos de um cenário de receita."""
    return ModeloEconomicoParametro.query.filter_by(seq_cenario_config=seq_cenario_config).all()


def create_parametro_economico(parametro: ModeloEconomicoParametro) -> ModeloEconomicoParametro:
    """Cria um parâmetro econômico."""
    db.session.add(parametro)
    return parametro


def delete_parametros_by_config(seq_cenario_config: int):
    """Remove todos os parâmetros de um cenário de receita."""
    ModeloEconomicoParametro.query.filter_by(seq_cenario_config=seq_cenario_config).delete()
    db.session.commit()


# ==================== Commit ====================

def commit():
    """Commit manual para operações em lote."""
    db.session.commit()
