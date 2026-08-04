"""Catálogo de permissões FC_<VERBO>_<RECURSO> e matriz default de perfis.

Modelo verbo+recurso (padrão corporativo de controle de acesso). O catálogo
cresce a cada feature que criar novos recursos (ex.: FC_APROVAR_FUNDO na
F2.2). A matriz é o DEFAULT de fábrica — customizações por instalação são
feitas via banco e preservadas pelo seed (ver seed_dominio).
"""

# (cod, descrição)
PERMISSOES = [
    # Dashboard
    ("FC_EXI_DASHBOARD", "Exibir o dashboard inicial"),
    # Lançamentos
    ("FC_CONS_LANCAMENTO", "Consultar lançamentos"),
    ("FC_INS_LANCAMENTO", "Incluir lançamento"),
    ("FC_ALT_LANCAMENTO", "Alterar lançamento"),
    ("FC_DEL_LANCAMENTO", "Excluir lançamento"),
    ("FC_IMP_LANCAMENTO", "Importar lançamentos (CSV/XLSX)"),
    # Saldos bancários
    ("FC_CONS_SALDO_BANCARIO", "Consultar saldos bancários"),
    ("FC_INS_SALDO_BANCARIO", "Incluir saldo bancário"),
    ("FC_ALT_SALDO_BANCARIO", "Alterar saldo bancário"),
    ("FC_DEL_SALDO_BANCARIO", "Excluir saldo bancário"),
    ("FC_IMP_SALDO_BANCARIO", "Importar saldos bancários (CSV/XLSX)"),
    # Contas bancárias
    ("FC_CONS_CONTA", "Consultar contas bancárias"),
    ("FC_INS_CONTA", "Incluir conta bancária"),
    ("FC_ALT_CONTA", "Alterar conta bancária"),
    ("FC_DEL_CONTA", "Inativar conta bancária"),
    ("FC_ATIVAR_CONTA", "Reativar conta bancária inativa"),
    # Qualificadores
    ("FC_CONS_QUALIFICADOR", "Consultar qualificadores"),
    ("FC_INS_QUALIFICADOR", "Incluir qualificador"),
    ("FC_ALT_QUALIFICADOR", "Alterar qualificador"),
    ("FC_DEL_QUALIFICADOR", "Excluir qualificador"),
    # F10.3 (R29): abrir exercício é ato distinto de manter qualificadores —
    # como confirmar liberação é distinto de mantê-la.
    ("FC_ABRIR_EXERCICIO", "Abrir exercício (copiar o plano de qualificadores)"),
    # Mapeamentos
    ("FC_CONS_MAPEAMENTO", "Consultar mapeamentos"),
    ("FC_INS_MAPEAMENTO", "Incluir mapeamento"),
    ("FC_ALT_MAPEAMENTO", "Alterar mapeamento"),
    ("FC_DEL_MAPEAMENTO", "Excluir mapeamento"),
    # Dicionário de termos de regra (motor de classificação)
    ("FC_CONS_TERMO_REGRA", "Consultar termos de regra"),
    ("FC_MANT_TERMO_REGRA", "Cadastrar/alterar/inativar termo de regra"),
    # Processamento da automação de lançamentos
    ("FC_CONS_EXECUCAO_MAPEAMENTO", "Consultar execuções de processamento de mapeamento"),
    ("FC_EXEC_MAPEAMENTO", "Processar mapeamento (gerar lançamentos automáticos)"),
    # LOA
    ("FC_CONS_LOA", "Consultar LOA"),
    ("FC_INS_LOA", "Incluir/atualizar LOA"),
    ("FC_DEL_LOA", "Excluir LOA"),
    ("FC_IMP_LOA", "Importar LOA (CSV/XLSX)"),
    # Alertas
    ("FC_CONS_ALERTA", "Consultar alertas"),
    ("FC_INS_ALERTA", "Incluir alerta"),
    ("FC_ALT_ALERTA", "Alterar alerta / marcar lido ou resolvido"),
    ("FC_DEL_ALERTA", "Excluir alerta"),
    # Fórmulas e parâmetros globais
    ("FC_CONS_FORMULA", "Consultar fórmulas e parâmetros globais"),
    ("FC_INS_FORMULA", "Incluir fórmula ou parâmetro global"),
    ("FC_ALT_FORMULA", "Alterar fórmula ou parâmetro global"),
    ("FC_DEL_FORMULA", "Excluir fórmula ou parâmetro global"),
    # Previsão (simulador de cenários)
    ("FC_CONS_PREVISAO", "Consultar/executar cenários de previsão"),
    ("FC_INS_PREVISAO", "Criar cenário / salvar versão de projeção"),
    ("FC_ALT_PREVISAO", "Alterar cenário / publicar versão"),
    ("FC_DEL_PREVISAO", "Excluir cenário ou versão"),
    # Repartição da projeção por fonte (percentuais-fallback)
    ("FC_CONS_REPARTICAO_FONTE", "Consultar repartição de qualificadores por fonte"),
    ("FC_MANT_REPARTICAO_FONTE", "Definir repartição de qualificadores por fonte"),
    # Fontes de recurso (catálogo STN + classificação de fundos)
    ("FC_CONS_FONTE_RECURSO", "Consultar fontes de recurso e disponibilidade por grupo"),
    ("FC_MANT_FONTE_RECURSO", "Cadastrar/alterar/inativar fonte de recurso e classificar fundos"),
    ("FC_IMP_FONTE_RECURSO", "Importar tabela oficial de fontes (CSV/XLSX)"),
    # Fundos de investimento
    ("FC_CONS_FUNDO", "Consultar fundos"),
    ("FC_INS_FUNDO", "Cadastrar fundo"),
    ("FC_ALT_FUNDO", "Alterar descrição de fundo"),
    ("FC_DEL_FUNDO", "Inativar fundo"),
    ("FC_APROVAR_FUNDO", "Aprovar fundo auto-cadastrado"),
    ("FC_IMP_SALDO_FUNDO", "Importar saldos por fundo em lote (API/extração)"),
    # Extração embutida
    ("FC_CONS_FONTE_EXTRACAO", "Consultar fontes de extração"),
    ("FC_MANT_FONTE_EXTRACAO", "Cadastrar/alterar/inativar fonte de extração"),
    ("FC_EXEC_EXTRACAO", "Executar fonte de extração manualmente"),
    ("FC_CONS_EXECUCAO_EXTRACAO", "Consultar histórico de execuções de extração"),
    # Pagamentos e conferência
    ("FC_CONS_PAGAMENTO", "Consultar pagamentos"),
    ("FC_INS_PAGAMENTO", "Incluir pagamento"),
    ("FC_ALT_PAGAMENTO", "Alterar pagamento"),
    ("FC_DEL_PAGAMENTO", "Excluir (inativar) pagamento"),
    ("FC_APROPRIAR_PAGAMENTO", "Apropriar/estornar pagamento em liberações"),
    ("FC_CONS_CONFERENCIA", "Consultar conferência de caixa"),
    ("FC_MANT_CONFERENCIA", "Informar apurado externo da conferência"),
    # Simulação de disponibilidade do desembolso
    ("FC_EXEC_SIMULACAO_DESEMBOLSO", "Executar a simulação de disponibilidade"),
    ("FC_MANT_PARAM_DESEMBOLSO", "Definir parâmetros do desembolso (colchão mínimo)"),
    # Liberações do desembolso
    ("FC_CONS_LIBERACAO", "Consultar liberações do desembolso"),
    ("FC_MANT_LIBERACAO", "Criar/cancelar liberação (rascunho)"),
    ("FC_CONF_LIBERACAO", "Confirmar liberação (ato distinto de manter)"),
    # Transferências internas (registro de controle)
    ("FC_CONS_TRANSFERENCIA", "Consultar transferências internas"),
    ("FC_MANT_TRANSFERENCIA", "Registrar/inativar transferência interna"),
    # Reservas financeiras e bloqueios judiciais
    ("FC_CONS_RESERVA", "Consultar reservas financeiras e bloqueios"),
    ("FC_MANT_RESERVA", "Constituir/movimentar reserva financeira ou bloqueio"),
    # Programação de desembolso (cotas do decreto)
    ("FC_CONS_PROGRAMACAO", "Consultar programação de desembolso"),
    ("FC_MANT_PROGRAMACAO", "Registrar cotas da programação de desembolso"),
    ("FC_IMP_PROGRAMACAO", "Importar programação de desembolso (CSV/XLSX)"),
    ("FC_CONS_DOTACAO", "Consultar dotações e créditos adicionais"),
    ("FC_MANT_DOTACAO", "Manter dotações e registrar créditos adicionais"),
    ("FC_IMP_DOTACAO", "Importar dotação inicial (CSV/XLSX)"),
    ("FC_CONS_EXECUCAO_ORCAMENTARIA", "Consultar execução orçamentária (E/L/P)"),
    ("FC_IMP_EXECUCAO_ORCAMENTARIA", "Importar execução orçamentária (CSV/XLSX)"),
    ("FC_REL_FUNIL", "Relatório do funil LOA→caixa e conciliação orçamento × financeiro"),
    ("FC_REL_CONCILIACAO_FONTE", "Conciliação da disponibilidade operacional × contábil por fonte"),
    ("FC_REL_ANALITICO_DESEMBOLSO", "Painel analítico do desembolso (liberado × pago × pendente)"),
    ("FC_IMP_DISPONIBILIDADE_CONTABIL", "Importar disponibilidade contábil por fonte (CSV/XLSX)"),
    # Órgãos (dimensão do desembolso)
    ("FC_CONS_ORGAO", "Consultar órgãos"),
    ("FC_MANT_ORGAO", "Cadastrar/alterar/inativar órgão"),
    # Backtest
    ("FC_REL_BACKTEST", "Visualizar/executar backtest de modelos"),
    ("FC_INS_BACKTEST", "Salvar recomendações do backtest"),
    # Relatórios (um evento por relatório)
    ("FC_REL_RESUMO", "Relatório resumo de fluxo de caixa"),
    ("FC_REL_INDICADORES", "Relatório de indicadores"),
    ("FC_REL_ANALISE_COMPARATIVA", "Relatório de análise comparativa"),
    ("FC_REL_SALDOS_DIARIOS", "Relatório de saldos diários"),
    ("FC_REL_DFC", "Demonstração do Fluxo de Caixa (DFC)"),
    ("FC_REL_PREVISAO_RECEITA", "Relatório de previsão de receita"),
    ("FC_REL_CONTROLE_DESPESA", "Relatório de controle de despesa"),
    ("FC_REL_LDO_ORCAMENTO", "Relatório LDO & Orçamento"),
    ("FC_REL_PREVISAO_REALIZADO", "Relatório previsão × realizado"),
    ("FC_REL_KPIS", "Relatório de KPIs (dashboard gerencial)"),
    ("FC_REL_EXECUCAO_DESEMBOLSO", "Relatório de execução do desembolso (previsto × liberado × pago)"),
    # Administração
    ("FC_ADMIN_BANCO", "Inicializar/recriar o banco de dados (/init-db, /recreate-db)"),
]

_TODAS = {cod for cod, _ in PERMISSOES}
_CONS = {cod for cod in _TODAS if cod.startswith("FC_CONS_")}
_REL = {cod for cod in _TODAS if cod.startswith("FC_REL_")}
# Módulo de extração é operacional — fora do perfil somente-leitura (spec
# extracao-configuravel R8); OPERADOR mantém as consultas via _CONS.
_CONS_EXTRACAO = {"FC_CONS_FONTE_EXTRACAO", "FC_CONS_EXECUCAO_EXTRACAO"}

# Matriz default: perfil -> permissões
MATRIZ_PERFIS = {
    "ADMINISTRADOR": _TODAS,
    "GESTOR_FINANCEIRO": _TODAS - {"FC_ADMIN_BANCO"},
    "OPERADOR": (
        {"FC_EXI_DASHBOARD"}
        | _CONS
        | _REL
        | {
            "FC_INS_LANCAMENTO", "FC_ALT_LANCAMENTO", "FC_IMP_LANCAMENTO",
            "FC_INS_SALDO_BANCARIO", "FC_ALT_SALDO_BANCARIO", "FC_IMP_SALDO_BANCARIO",
            "FC_INS_PAGAMENTO", "FC_ALT_PAGAMENTO", "FC_APROPRIAR_PAGAMENTO",
            "FC_MANT_LIBERACAO",
            "FC_INS_LOA", "FC_IMP_LOA",
        }
    ),
    "CONSULTA": {"FC_EXI_DASHBOARD"} | (_CONS - _CONS_EXTRACAO) | _REL,
    "EXTRACAO": {
        "FC_IMP_LANCAMENTO",
        "FC_IMP_SALDO_BANCARIO",
        "FC_IMP_SALDO_FUNDO",
        "FC_CONS_LANCAMENTO",
        "FC_CONS_SALDO_BANCARIO",
        "FC_CONS_FUNDO",
        "FC_CONS_CONTA",
        "FC_EXEC_EXTRACAO",
        "FC_CONS_FONTE_EXTRACAO",
        "FC_CONS_EXECUCAO_EXTRACAO",
    },
}

DESCRICAO_PERFIS = {
    "ADMINISTRADOR": "Acesso total, incluindo administração do banco de dados",
    "GESTOR_FINANCEIRO": "Acesso total ao negócio, sem administração do banco",
    "OPERADOR": "Operação diária: lançamentos, saldos, pagamentos, LOA e relatórios",
    "CONSULTA": "Somente leitura e relatórios",
    "EXTRACAO": "Conta de serviço para importações automatizadas",
}
