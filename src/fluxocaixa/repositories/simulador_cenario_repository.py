"""Repository for Simulador de Cenários functionality."""



from ..models import (
    CenarioAjuste,
    CenarioConfig,
    ModeloEconomicoParametro,
    SimuladorCenario,
    db,
)

# ==================== SimuladorCenario ====================

def get_all_simuladores() -> list[SimuladorCenario]:
    """Retorna todos os cenários simuladores."""
    return SimuladorCenario.query.order_by(SimuladorCenario.dat_criacao.desc()).all()


def get_active_simuladores() -> list[SimuladorCenario]:
    """Retorna apenas cenários ativos."""
    return (
        SimuladorCenario.query
        .filter_by(ind_status='A')
        .order_by(SimuladorCenario.dat_criacao.desc())
        .all()
    )


def get_simulador_by_id(seq_simulador_cenario: int) -> SimuladorCenario | None:
    """Busca um cenário simulador por ID."""
    return SimuladorCenario.query.get(seq_simulador_cenario)


def create_simulador(simulador: SimuladorCenario,
                     commit: bool = True) -> SimuladorCenario:
    """Cria um novo cenário simulador.

    `commit=False` só faz flush — o serviço é o dono da transação
    (previsao R13): falha depois do cabeçalho não pode deixar órfão.
    """
    db.session.add(simulador)
    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return simulador


def update_simulador(simulador: SimuladorCenario) -> SimuladorCenario:
    """Atualiza um cenário simulador existente."""
    db.session.commit()
    return simulador


def delete_simulador_logical(seq_simulador_cenario: int, user_id: int) -> SimuladorCenario | None:
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

def get_configs_by_simulador(seq_simulador_cenario: int) -> list[CenarioConfig]:
    return (CenarioConfig.query
            .filter_by(seq_simulador_cenario=seq_simulador_cenario)
            .order_by(CenarioConfig.cod_tipo_lancamento)
            .all())


def get_config_by_perna(seq_simulador_cenario: int,
                        cod_tipo_lancamento: str) -> CenarioConfig | None:
    return CenarioConfig.query.filter_by(
        seq_simulador_cenario=seq_simulador_cenario,
        cod_tipo_lancamento=cod_tipo_lancamento,
    ).first()


def create_config(config: CenarioConfig, commit: bool = True) -> CenarioConfig:
    db.session.add(config)
    if commit:
        db.session.commit()
        db.session.refresh(config)
    else:
        db.session.flush()
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


def get_ajustes_by_config(seq_cenario_config: int) -> list[CenarioAjuste]:
    return CenarioAjuste.query.filter_by(seq_cenario_config=seq_cenario_config).all()


def get_ajustes_by_config_and_year(seq_cenario_config: int, ano: int) -> list[CenarioAjuste]:
    return (CenarioAjuste.query
            .filter_by(seq_cenario_config=seq_cenario_config, ano=ano)
            .all())


def create_ajuste(ajuste: CenarioAjuste, commit: bool = True) -> CenarioAjuste:
    db.session.add(ajuste)
    if commit:
        db.session.commit()
        db.session.refresh(ajuste)
    else:
        db.session.flush()
    return ajuste


def delete_ajustes_by_config_ano(seq_cenario_config: int, ano: int,
                                 commit: bool = True) -> None:
    CenarioAjuste.query.filter_by(
        seq_cenario_config=seq_cenario_config, ano=ano
    ).delete(synchronize_session=False)
    if commit:
        db.session.commit()
    # sem commit: a exclusão fica PENDENTE — se os ajustes novos falharem,
    # o rollback do serviço devolve os antigos (previsao R13)


def get_parametros_by_config(seq_cenario_config: int) -> list[ModeloEconomicoParametro]:
    """Retorna parâmetros econômicos de um cenário de receita."""
    return ModeloEconomicoParametro.query.filter_by(seq_cenario_config=seq_cenario_config).all()


def create_parametro_economico(parametro: ModeloEconomicoParametro) -> ModeloEconomicoParametro:
    """Cria um parâmetro econômico."""
    db.session.add(parametro)
    return parametro


def delete_parametros_by_config(seq_cenario_config: int, commit: bool = True):
    """Remove todos os parâmetros de um cenário de receita."""
    ModeloEconomicoParametro.query.filter_by(seq_cenario_config=seq_cenario_config).delete()
    if commit:
        db.session.commit()


# ==================== Commit ====================

def commit():
    """Commit manual para operações em lote."""
    db.session.commit()
