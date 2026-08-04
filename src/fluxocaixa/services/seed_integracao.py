"""Massa de demonstração das telas de Integração (F3/F4).

As telas do grupo Integração do menu — Fontes de Extração, Execuções,
Mapeamentos e Termos de Regra — nasciam vazias: o `seed_data` cobre
lançamentos, fundos, saldos e projeção, mas nunca chegou ao pipeline de
automação. Numa instalação de demonstração isso deixa metade do produto
invisível, porque as quatro telas só fazem sentido juntas: a fonte traz o
dado, o mapeamento o classifica usando os termos, a execução conta o que
aconteceu.

Tudo aqui é FICTÍCIO por construção (o repositório é público): hosts
`*.exemplo`, agência `0001`, contas `12345-6`/`98765-4`, naturezas
`1112xxxx`, UGs `999xxx`. Credenciais aparecem só como placeholder `${VAR}`
— é assim que o cadastro real deve ser preenchido, e o seed serve de
exemplo do formato.

Idempotente por chave natural: cada bloco só cria o que ainda não existe.
Diferente do `seed_data`, que limpa e repopula, aqui NADA é apagado —
fonte editada pelo usuário sobrevive ao próximo boot.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from ..models import (
    EtlStaging,
    ExecucaoExtracao,
    FonteExtracao,
    ItemMapeamento,
    Mapeamento,
    Qualificador,
    SistemaOrigem,
    TermoRegra,
)
from ..models.base import db

# Sistemas de origem — cadastro da instalação, não domínio semeado.
SISTEMAS = (
    ("SIS_CONTABIL", "Sistema Contábil (demonstração)"),
    ("SIS_BANCARIO", "Portal Bancário (demonstração)"),
)

# Dicionário de termos: o vocabulário em que as regras são escritas.
# ATRIBUTO = chave do json_atributos da origem; COLUNA = coluna de negócio
# da staging (restrita à whitelist de `models/termo_regra.py`).
TERMOS = (
    ("Natureza", "ATRIBUTO", "natureza", "TEXTO"),
    ("Unidade Gestora", "ATRIBUTO", "ug", "TEXTO"),
    ("Fonte de Recurso", "ATRIBUTO", "fonte_recurso", "TEXTO"),
    ("Elemento de Despesa", "ATRIBUTO", "elemento", "TEXTO"),
    ("Valor", "COLUNA", "val_referencia", "NUMERO"),
    ("Data de Referência", "COLUNA", "dat_referencia", "DATA"),
    ("Ano do Exercício", "COLUNA", "num_ano_exercicio", "NUMERO"),
)

# Sinal contábil na origem (ver CLAUDE.md): a query já entrega o valor
# assinado, o motor de regras nunca vê débito/crédito.
QUERY_DEMO = (
    "SELECT dat_emissao AS data,\n"
    "       CASE WHEN SUBSTR(cod_conta_contabil, 1, 1) IN ('1','3','5','7')\n"
    "            THEN val_debito - val_credito\n"
    "            ELSE val_credito - val_debito END AS valor,\n"
    "       cod_natureza AS natureza,\n"
    "       cod_ug AS ug,\n"
    "       cod_elemento AS elemento,\n"
    "       cod_fonte AS fonte_recurso\n"
    "  FROM fato_lancamento\n"
    " WHERE dat_emissao BETWEEN :data_inicio AND :data_fim"
)


def _sistemas(session):
    mapa = {}
    for sigla, descricao in SISTEMAS:
        sistema = SistemaOrigem.query.filter_by(txt_sigla=sigla).first()
        if sistema is None:
            sistema = SistemaOrigem(txt_sigla=sigla, dsc_sistema_origem=descricao)
            session.add(sistema)
            session.flush()
        mapa[sigla] = sistema
    session.commit()
    return mapa


def _termos(session):
    for nome, origem, campo, tipo in TERMOS:
        if TermoRegra.query.filter_by(nom_termo=nome).first() is None:
            session.add(TermoRegra(
                nom_termo=nome, cod_origem_campo=origem,
                nom_campo=campo, cod_tipo=tipo, ind_status='A',
            ))
    session.commit()


def _fontes(session, sistemas):
    """As três famílias de conector, uma de cada — arquivo, API e banco SQL."""
    definicoes = (
        {
            "nom_fonte": "Extrato bancário diário (arquivo)",
            "cod_tipo_conector": "FTP_ARQUIVO",
            "cod_destino": "SALDO_FUNDO",
            "sistema": "SIS_BANCARIO",
            "txt_cron": "0 6 * * *",
            "ind_status": "A",
            "json_config": {
                "protocolo": "SFTP",
                "host": "sftp.banco-demo.exemplo",
                "porta": 22,
                "usuario": "extrator",
                "senha": "${SENHA_SFTP_BANCO}",
                "diretorio": "/extratos",
                "padrao_nome": "{:%Y%m%d}_0001_EXTRATO.csv",
            },
            "json_layout": {
                "separador": ";",
                "encoding": "utf-8-sig",
                "tem_header": True,
                "formato_data": "%d/%m/%Y",
                "formato_decimal": "PT_BR",
                "colunas": [
                    {"origem": "Banco", "destino": "cod_banco"},
                    {"origem": "Agência", "destino": "num_agencia",
                     "transformacao": "somente_digitos"},
                    {"origem": "Conta", "destino": "num_conta",
                     "transformacao": "somente_digitos"},
                    {"origem": "Data", "destino": "dat_saldo",
                     "transformacao": "data"},
                    {"origem": "Descrição", "destino": "cod_fundo+dsc_fundo",
                     "transformacao": "codigo_antes_hifen"},
                    {"origem": "Saldo", "destino": "val_saldo",
                     "transformacao": "decimal"},
                ],
            },
        },
        {
            "nom_fonte": "Saldos por API do banco",
            "cod_tipo_conector": "API_REST",
            "cod_destino": "SALDO_FUNDO",
            "sistema": "SIS_BANCARIO",
            "txt_cron": "0 7 * * *",
            "ind_status": "A",
            "json_config": {
                "url_base": "https://api.banco-demo.exemplo",
                "path_template": "/contas/{agencia}/{conta}/saldo",
                "cod_banco": "104",
                "autenticacao": "BEARER",
                "token": "${TOKEN_API_BANCO}",
                "timeout": 30,
                "contas": [
                    {"agencia": "0001", "conta": "12345-6"},
                    {"agencia": "0001", "conta": "98765-4"},
                ],
            },
            "json_layout": {
                "lista_path": "dados",
                "campos": [
                    {"caminho": "agencia", "destino": "num_agencia",
                     "transformacao": "somente_digitos"},
                    {"caminho": "conta", "destino": "num_conta",
                     "transformacao": "somente_digitos"},
                    {"caminho": "data", "destino": "dat_saldo"},
                    {"caminho": "saldo", "destino": "val_saldo"},
                    {"caminho": "fundo", "destino": "cod_fundo"},
                ],
            },
        },
        {
            # Destino LANCAMENTO: a carga vai para a staging e é o mapeamento
            # que a classifica. Exige `capturar_atributos` — sem a linha crua
            # as regras não teriam em que campo casar.
            "nom_fonte": "Execução orçamentária (banco SQL)",
            "cod_tipo_conector": "BANCO_SQL",
            "cod_destino": "LANCAMENTO",
            "sistema": "SIS_CONTABIL",
            "txt_cron": "30 5 * * *",
            "ind_status": "A",
            "json_config": {
                "url_conexao": "${URL_ERP_CONTABIL}",
                "query": QUERY_DEMO,
                "cod_banco": "001",
                "batch_size": 5000,
            },
            "json_layout": {
                "campos": [
                    {"caminho": "data", "destino": "dat_saldo"},
                    {"caminho": "valor", "destino": "val_saldo"},
                ],
                "capturar_atributos": True,
            },
        },
        {
            # Fonte inativa: mostra na tela que inativar preserva o histórico
            # de execuções em vez de apagar o cadastro.
            "nom_fonte": "Extrato bancário (FTP legado)",
            "cod_tipo_conector": "FTP_ARQUIVO",
            "cod_destino": "SALDO_FUNDO",
            "sistema": "SIS_BANCARIO",
            "txt_cron": None,
            "ind_status": "I",
            "json_config": {
                "protocolo": "FTP",
                "host": "ftp.legado-demo.exemplo",
                "porta": 21,
                "usuario": "extrator",
                "senha": "${SENHA_FTP_LEGADO}",
                "diretorio": "/saldos",
                "padrao_nome": "SALDO_{:%d%m%Y}.txt",
            },
            "json_layout": {
                "separador": ";",
                "tem_header": False,
                "colunas": [
                    {"origem": 0, "destino": "cod_banco"},
                    {"origem": 1, "destino": "num_agencia"},
                    {"origem": 2, "destino": "num_conta"},
                    {"origem": 3, "destino": "dat_saldo", "transformacao": "data"},
                    {"origem": 4, "destino": "val_saldo", "transformacao": "decimal"},
                ],
            },
        },
    )

    fontes = {}
    for d in definicoes:
        fonte = FonteExtracao.query.filter_by(nom_fonte=d["nom_fonte"]).first()
        if fonte is None:
            fonte = FonteExtracao(
                nom_fonte=d["nom_fonte"],
                cod_tipo_conector=d["cod_tipo_conector"],
                cod_destino=d["cod_destino"],
                seq_sistema_origem=sistemas[d["sistema"]].seq_sistema_origem,
                txt_cron=d["txt_cron"],
                json_config=d["json_config"],
                json_layout=d["json_layout"],
                ind_status=d["ind_status"],
                cod_pessoa_inclusao=1,
            )
            session.add(fonte)
            session.flush()
        fontes[d["nom_fonte"]] = fonte
    session.commit()
    return fontes


def _execucoes(session, fontes):
    """Histórico com os quatro status — é o que dá sentido à tela de log.

    As datas são relativas a hoje para que a última execução fique sempre
    recente: o semáforo de defasagem dos KPIs mede horas desde a última
    execução bem-sucedida, e uma data fixa envelheceria a demonstração.
    """
    agora = datetime.now()
    hoje = date.today()
    definicoes = (
        # (fonte, horas atrás, disparo, status, inseridas, erros, fundos novos,
        #  duração, detalhe)
        ("Extrato bancário diário (arquivo)", 3, "AGENDADO", "SUCESSO",
         128, 0, 0, "4.310", None),
        ("Extrato bancário diário (arquivo)", 27, "AGENDADO", "PARCIAL",
         126, 2, 1, "4.902",
         "linha 43: conta 00000-0 não cadastrada\n"
         "linha 77: saldo vazio"),
        ("Extrato bancário diário (arquivo)", 51, "MANUAL", "SEM_DADOS",
         0, 0, 0, "0.884", "Arquivo do dia não encontrado na origem"),
        ("Saldos por API do banco", 2, "AGENDADO", "SUCESSO",
         2, 0, 0, "1.507", None),
        ("Saldos por API do banco", 26, "AGENDADO", "ERRO",
         0, 0, 0, "30.118",
         "Falha de autenticação (401) após renovação do token"),
        ("Execução orçamentária (banco SQL)", 4, "AGENDADO", "SUCESSO",
         6, 0, 0, "2.664", None),
        ("Extrato bancário (FTP legado)", 24 * 40, "AGENDADO", "SUCESSO",
         95, 0, 0, "6.221", None),
    )

    # A guarda é POR FONTE, não por linha: `dat_inicio_execucao` é relativa a
    # `agora` e nunca repete entre boots, então comparar a data duplicaria o
    # histórico a cada start. Fonte que já tem execução fica como está.
    ja_tem_historico = {
        nome for nome, fonte in fontes.items()
        if ExecucaoExtracao.query.filter_by(
            seq_fonte_extracao=fonte.seq_fonte_extracao).first() is not None
    }

    # Da MAIS ANTIGA para a mais recente: a tela de fontes resolve "última
    # execução" pela PK (`_ultima_execucao` ordena por seq), o que em operação
    # real coincide com a ordem cronológica porque a linha nasce quando a
    # execução roda. Semear fora de ordem quebraria essa coincidência e a tela
    # mostraria a execução errada como última.
    for (nome, atras, disparo, status, inseridas, erros,
         fundos_novos, duracao, detalhe) in sorted(definicoes, key=lambda d: -d[1]):
        if nome in ja_tem_historico:
            continue
        fonte = fontes[nome]
        inicio = agora - timedelta(hours=atras)
        session.add(ExecucaoExtracao(
            seq_fonte_extracao=fonte.seq_fonte_extracao,
            dat_inicio_execucao=inicio,
            num_duracao_segundos=Decimal(duracao),
            cod_disparo=disparo,
            cod_status=status,
            dat_janela_inicio=hoje - timedelta(days=atras // 24),
            dat_janela_fim=hoje - timedelta(days=atras // 24),
            qtd_linhas_inseridas=inseridas,
            qtd_linhas_erro=erros,
            qtd_fundos_auto_cadastrados=fundos_novos,
            txt_detalhe_erros=detalhe,
        ))
    session.commit()


def _staging(session, fontes):
    """Linhas cruas pendentes — é contra elas que o preview da regra roda.

    Sem staging o botão "Testar regra" da tela de mapeamento devolveria
    sempre zero, e a demonstração não mostraria o que a regra faz.
    """
    fonte = fontes["Execução orçamentária (banco SQL)"]
    if EtlStaging.query.filter_by(
            seq_fonte_extracao=fonte.seq_fonte_extracao).first() is not None:
        return

    execucao = (ExecucaoExtracao.query
                .filter_by(seq_fonte_extracao=fonte.seq_fonte_extracao)
                .order_by(ExecucaoExtracao.dat_inicio_execucao.desc())
                .first())
    ano = date.today().year
    referencia = date.today() - timedelta(days=1)

    # (natureza, ug, elemento, fonte de recurso, valor, status, erro)
    linhas = (
        ("11120101", "999001", "000000", "0100", "185420.55", '0', None),
        ("11120102", "999001", "000000", "0100", "97310.20", '0', None),
        ("11210301", "999002", "000000", "0100", "43877.90", '0', None),
        ("11310401", "999002", "000000", "0100", "12045.00", '0', None),
        ("33900101", "999003", "339030", "0500", "-58120.75", '0', None),
        ("31900101", "999003", "319011", "0100", "-214900.00", '0', None),
        ("99999999", "999009", "000000", "0100", "1234.56", '2',
         "Nenhum item de mapeamento casou com a linha"),
    )
    for natureza, ug, elemento, recurso, valor, status, erro in linhas:
        session.add(EtlStaging(
            seq_fonte_extracao=fonte.seq_fonte_extracao,
            seq_execucao_extracao=execucao.seq_execucao_extracao if execucao else None,
            num_ano_exercicio=ano,
            dat_referencia=referencia,
            val_referencia=Decimal(valor),
            json_atributos={
                "natureza": natureza, "ug": ug,
                "elemento": elemento, "fonte_recurso": recurso,
                "valor": valor,
            },
            ind_status_processamento=status,
            dsc_erro=erro,
        ))
    session.commit()


def _mapeamentos(session, sistemas):
    """Um mapeamento por perna, com regras escritas no vocabulário dos termos.

    A unicidade é (ano, sistema de origem) entre ativos — UM mapeamento
    reúne itens de receita e de despesa (a classificação vem do qualificador
    do item; change mapeamento-sem-dimensao-receita-despesa).
    """
    ano = date.today().year
    definicoes = (
        ("Classificação SIS_CONTABIL — demonstração", (
            ('1.0.0', "Natureza começa com '1112'"),
            ('1.0.1', "Natureza começa com '1121'"),
            ('1.5.2', "Natureza começa com '1131'"),
            ('2.0.1', "Elemento de Despesa começa com '3190'"),
            ('2.2.1', "Elemento de Despesa começa com '3390' "
                      "e Unidade Gestora <> '999009'"),
        )),
    )

    sistema = sistemas["SIS_CONTABIL"]
    for descricao, itens in definicoes:
        existe = Mapeamento.query.filter_by(
            num_ano_exercicio=ano,
            seq_sistema_origem=sistema.seq_sistema_origem,
        ).first()
        if existe is not None:
            continue

        mapeamento = Mapeamento(
            num_ano_exercicio=ano,
            seq_sistema_origem=sistema.seq_sistema_origem,
            dsc_mapeamento=descricao, ind_status='A',
            cod_pessoa_inclusao=1,
        )
        for num_qualificador, regra in itens:
            qualificador = Qualificador.query.filter_by(
                num_qualificador=num_qualificador, ind_status='A').first()
            # A árvore vem do seed_data; se alguém a alterar, o item some em
            # vez de derrubar o boot.
            if qualificador is None or not qualificador.is_folha():
                continue
            mapeamento.itens.append(ItemMapeamento(
                seq_qualificador=qualificador.seq_qualificador,
                txt_regra=regra, ind_inversao_sinal='0', ind_status='A',
                cod_pessoa_inclusao=1,
            ))
        if mapeamento.itens:
            session.add(mapeamento)
    session.commit()


def seed_integracao(session=None):
    """Popula as quatro telas de Integração com massa de demonstração."""
    session = session or db.session

    sistemas = _sistemas(session)
    _termos(session)
    fontes = _fontes(session, sistemas)
    _execucoes(session, fontes)
    _staging(session, fontes)
    _mapeamentos(session, sistemas)

    print("Seeded integração data (4 fontes, 7 execuções, 7 termos, 2 mapeamentos)")
