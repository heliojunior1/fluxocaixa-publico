"""Fontes de extração: CRUD, execução e teste de conexão (spec extracao-configuravel).

Pipeline de execução (design D5): valida a fonte, resolve credenciais numa
cópia do config, extrai pelo conector, entrega ao `importar_lote` (F2.3) e
persiste `flc_execucao_extracao` com o status derivado do resultado.
Pré-condições de chamada (fonte inativa, janela inválida) levantam
`RegraNegocioError` SEM registrar execução; falhas de runtime (config,
credencial, conexão, extração) viram execução com status ERRO.
"""
import json
import time
from datetime import date, datetime

from pydantic import ValidationError

from ..auth.contexto import cod_pessoa_atual
from ..extracao import registry
from ..extracao.conector import ErroLinha, Janela, LinhaExtraida, ResultadoTeste
from ..extracao.credenciais import resolver_config
from ..models import ExecucaoExtracao, FonteExtracao, SistemaOrigem
from ..models.base import db
from ..models.extracao import (
    DESTINO_LANCAMENTO,
    DESTINO_SALDO_FUNDO,
    DISPARO_AGENDADO,
    DISPARO_MANUAL,
    STATUS_ERRO,
    STATUS_PARCIAL,
    STATUS_SEM_DADOS,
    STATUS_SUCESSO,
)
from . import staging_service
from .importacao_lote_service import LinhaLote, importar_lote
from .validacao import RegraNegocioError

JANELA_MAXIMA_DIAS = 90
_LIMITE_DETALHE_ERROS = 4000


# --------------------------------------------------------------------------
# Validações de cadastro (R1)
# --------------------------------------------------------------------------

def _validar_tipo_conector(cod_tipo_conector: str):
    conector = registry.obter(cod_tipo_conector)
    if conector is None:
        raise RegraNegocioError(
            f"Tipo de conector '{cod_tipo_conector}' não está disponível "
            f"(disponíveis: {', '.join(registry.tipos_disponiveis()) or 'nenhum'})"
        )
    return conector


def _validar_destino(cod_destino: str) -> None:
    if cod_destino in (DESTINO_SALDO_FUNDO, DESTINO_LANCAMENTO):
        return
    raise RegraNegocioError(f"Destino '{cod_destino}' não é suportado")


def _validar_layout_lancamento(json_layout: dict | None) -> None:
    """Fonte de destino LANCAMENTO exige que o layout designe data e valor da
    linha (`dat_saldo`/`val_saldo`) e ligue `capturar_atributos` (para guardar
    a linha crua na staging — spec automacao-lancamentos R2)."""
    layout = json_layout or {}
    destinos = {c.get("destino") for c in layout.get("campos", []) if isinstance(c, dict)}
    faltando = {"dat_saldo", "val_saldo"} - destinos
    if faltando:
        raise RegraNegocioError(
            "Fonte de LANCAMENTO exige o layout mapeando "
            f"{', '.join(sorted(faltando))} (data e valor da linha)"
        )
    if not layout.get("capturar_atributos"):
        raise RegraNegocioError(
            "Fonte de LANCAMENTO exige 'capturar_atributos' no layout "
            "(guarda a linha crua na staging)"
        )


def _validar_config(conector, json_config: dict) -> None:
    try:
        conector.schema_config.model_validate(json_config or {})
    except ValidationError as exc:
        detalhes = "; ".join(
            f"{'.'.join(str(p) for p in erro['loc']) or 'config'}: {erro['msg']}"
            for erro in exc.errors()
        )
        raise RegraNegocioError(
            f"Configuração inválida para o conector '{conector.tipo}': {detalhes}"
        )


def _validar_layout(conector, json_layout: dict | None) -> None:
    """Valida o json_layout contra o schema_layout do conector, se houver.

    Conectores que usam layout (ex.: FTP_ARQUIVO) declaram `schema_layout`
    (Pydantic) — cobre transformação desconhecida, destino inválido e
    traversal via validadores do próprio schema."""
    schema_layout = getattr(conector, "schema_layout", None)
    if schema_layout is None:
        return
    try:
        schema_layout.model_validate(json_layout or {})
    except ValidationError as exc:
        detalhes = "; ".join(
            f"{'.'.join(str(p) for p in erro['loc']) or 'layout'}: {erro['msg']}"
            for erro in exc.errors()
        )
        raise RegraNegocioError(
            f"Layout inválido para o conector '{conector.tipo}': {detalhes}"
        )


def _validar_cron(txt_cron: str | None) -> None:
    if not txt_cron:
        return
    from apscheduler.triggers.cron import CronTrigger

    try:
        CronTrigger.from_crontab(txt_cron)
    except ValueError as exc:
        raise RegraNegocioError(f"Agenda cron inválida ('{txt_cron}'): {exc}")


def _resolver_sistema(sigla_sistema: str) -> SistemaOrigem:
    sistema = SistemaOrigem.query.filter_by(txt_sigla=sigla_sistema, ind_status='A').first()
    if sistema is None:
        raise RegraNegocioError(
            f"Sistema de origem '{sigla_sistema}' não encontrado ou inativo"
        )
    return sistema


def _validar_nome_unico(nom_fonte: str, seq_ignorar: int | None = None) -> None:
    consulta = FonteExtracao.query.filter_by(nom_fonte=nom_fonte, ind_status='A')
    if seq_ignorar is not None:
        consulta = consulta.filter(FonteExtracao.seq_fonte_extracao != seq_ignorar)
    if consulta.first() is not None:
        raise RegraNegocioError(f"Já existe uma fonte ativa com o nome '{nom_fonte}'")


def _obter_fonte(seq_fonte: int) -> FonteExtracao:
    fonte = FonteExtracao.query.get(seq_fonte)
    if fonte is None:
        raise RegraNegocioError("Fonte de extração não encontrada")
    return fonte


def _reagendar(fonte: FonteExtracao) -> None:
    from ..extracao import scheduler

    scheduler.reagendar(fonte)


# --------------------------------------------------------------------------
# CRUD (R1)
# --------------------------------------------------------------------------

def criar_fonte(
    nom_fonte: str,
    cod_tipo_conector: str,
    sigla_sistema: str,
    txt_cron: str | None = None,
    json_config: dict | None = None,
    json_layout: dict | None = None,
    cod_destino: str = DESTINO_SALDO_FUNDO,
) -> FonteExtracao:
    nom_fonte = (nom_fonte or "").strip()
    if not nom_fonte:
        raise RegraNegocioError("Informe o nome da fonte de extração")
    conector = _validar_tipo_conector(cod_tipo_conector)
    _validar_destino(cod_destino)
    sistema = _resolver_sistema(sigla_sistema)
    _validar_nome_unico(nom_fonte)
    _validar_config(conector, json_config or {})
    _validar_layout(conector, json_layout)
    if cod_destino == DESTINO_LANCAMENTO:
        _validar_layout_lancamento(json_layout)
    _validar_cron(txt_cron)

    fonte = FonteExtracao(
        nom_fonte=nom_fonte,
        cod_tipo_conector=cod_tipo_conector,
        cod_destino=cod_destino,
        seq_sistema_origem=sistema.seq_sistema_origem,
        txt_cron=txt_cron,
        json_config=json_config or {},
        json_layout=json_layout,
        cod_pessoa_inclusao=cod_pessoa_atual(),
    )
    db.session.add(fonte)
    db.session.commit()
    _reagendar(fonte)
    return fonte


def alterar_fonte(
    seq_fonte: int,
    *,
    nom_fonte: str | None = None,
    txt_cron: str | None = ...,
    json_config: dict | None = None,
    json_layout: dict | None = ...,
) -> FonteExtracao:
    """Altera campos mutáveis. Tipo de conector, destino e sistema são
    imutáveis após a criação (mesma disciplina de chaves dos demais CRUDs)."""
    fonte = _obter_fonte(seq_fonte)
    conector = _validar_tipo_conector(fonte.cod_tipo_conector)

    if nom_fonte is not None:
        nom_fonte = nom_fonte.strip()
        if not nom_fonte:
            raise RegraNegocioError("Informe o nome da fonte de extração")
        _validar_nome_unico(nom_fonte, seq_ignorar=fonte.seq_fonte_extracao)
        fonte.nom_fonte = nom_fonte
    if json_config is not None:
        _validar_config(conector, json_config)
        fonte.json_config = json_config
    if txt_cron is not ...:
        _validar_cron(txt_cron)
        fonte.txt_cron = txt_cron
    if json_layout is not ...:
        _validar_layout(conector, json_layout)
        if fonte.cod_destino == DESTINO_LANCAMENTO:
            _validar_layout_lancamento(json_layout)
        fonte.json_layout = json_layout

    fonte.dat_alteracao = date.today()
    fonte.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    _reagendar(fonte)
    return fonte


def inativar_fonte(seq_fonte: int) -> FonteExtracao:
    fonte = _obter_fonte(seq_fonte)
    fonte.ind_status = 'I'
    fonte.dat_alteracao = date.today()
    fonte.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    _reagendar(fonte)
    return fonte


# --------------------------------------------------------------------------
# Janela de execução (R6)
# --------------------------------------------------------------------------

def montar_janela(data_inicio: date | None, data_fim: date | None) -> Janela:
    """Sem datas → dia corrente; com datas, valida o par (regra de backfill)."""
    if data_inicio is None and data_fim is None:
        hoje = date.today()
        return Janela(data_inicio=hoje, data_fim=hoje)
    if data_inicio is None or data_fim is None:
        raise RegraNegocioError(
            "Informe data_inicio e data_fim em conjunto para o backfill"
        )
    if data_fim < data_inicio:
        raise RegraNegocioError("data_fim não pode ser anterior à data_inicio")
    dias = (data_fim - data_inicio).days + 1
    if dias > JANELA_MAXIMA_DIAS:
        raise RegraNegocioError(
            f"Janela de backfill limitada a {JANELA_MAXIMA_DIAS} dias por execução "
            f"(informada: {dias} dias)"
        )
    return Janela(data_inicio=data_inicio, data_fim=data_fim)


# --------------------------------------------------------------------------
# Execução (R3/R4) e teste de conexão (R9)
# --------------------------------------------------------------------------

def _linha_lote(linha, dat_default: date) -> LinhaLote:
    return LinhaLote(
        cod_banco=linha.cod_banco,
        num_agencia=linha.num_agencia,
        num_conta=linha.num_conta,
        cod_fundo=linha.cod_fundo,
        dsc_fundo=linha.dsc_fundo,
        val_saldo=linha.val_saldo,
        val_aplicacoes=linha.val_aplicacoes,
        val_resgates=linha.val_resgates,
        dat_saldo=linha.dat_saldo or dat_default,
    )


def _serializar_detalhe(detalhe_erros: list) -> str | None:
    if not detalhe_erros:
        return None
    texto = json.dumps(detalhe_erros, ensure_ascii=False)
    return texto[:_LIMITE_DETALHE_ERROS]


def executar_fonte(
    seq_fonte: int,
    janela: Janela | None = None,
    disparo: str = DISPARO_AGENDADO,
) -> ExecucaoExtracao:
    """Executa a fonte e SEMPRE registra a execução (exceto pré-condições)."""
    fonte = _obter_fonte(seq_fonte)
    if fonte.ind_status != 'A':
        raise RegraNegocioError(f"Fonte '{fonte.nom_fonte}' está inativa")
    if janela is None:
        janela = montar_janela(None, None)

    inicio = datetime.now()
    cronometro = time.monotonic()
    inseridas = erros = fundos_novos = 0
    detalhe: str | None = None

    # A execução é criada e persistida ANTES do trabalho: o destino LANCAMENTO
    # grava na staging referenciando seq_execucao_extracao (FK).
    execucao = ExecucaoExtracao(
        seq_fonte_extracao=fonte.seq_fonte_extracao,
        dat_inicio_execucao=inicio,
        cod_disparo=disparo,
        cod_status=STATUS_ERRO,
        dat_janela_inicio=janela.data_inicio,
        dat_janela_fim=janela.data_fim,
        cod_pessoa_inclusao=cod_pessoa_atual(),
    )
    db.session.add(execucao)
    db.session.flush()  # garante seq_execucao_extracao
    status = STATUS_ERRO

    try:
        conector = _validar_tipo_conector(fonte.cod_tipo_conector)
        _validar_config(conector, fonte.json_config or {})
        config = resolver_config(fonte.json_config or {}, conector.schema_config)
        sistema = SistemaOrigem.query.get(fonte.seq_sistema_origem)

        # O conector emite LinhaExtraida (dado) ou ErroLinha (erro/aviso de linha).
        emitidos = list(conector.extrair(config, fonte.json_layout, janela))
        linhas = [e for e in emitidos if isinstance(e, LinhaExtraida)]
        avisos = [e for e in emitidos if isinstance(e, ErroLinha) and e.aviso]
        erros_linha = [e for e in emitidos if isinstance(e, ErroLinha) and not e.aviso]

        eh_lancamento = fonte.cod_destino == DESTINO_LANCAMENTO

        if not linhas and not erros_linha:
            status = STATUS_SEM_DADOS
            if eh_lancamento:
                detalhe = _serializar_detalhe([{
                    "mensagem": "nenhuma linha extraída para staging — carga não efetuada"
                }])
            elif avisos:
                detalhe = _serializar_detalhe(
                    [{"linha": a.numero, "mensagem": f"{a.arquivo}: {a.mensagem}"} for a in avisos]
                )
        else:
            detalhe_erros = [
                {"linha": e.numero, "mensagem": f"{e.arquivo}: {e.mensagem}"}
                for e in (erros_linha + avisos)
            ]
            if eh_lancamento:
                # Destino LANCAMENTO → grava as linhas cruas na staging (F4.1)
                inseridas = staging_service.gravar_lote(
                    fonte.seq_fonte_extracao, execucao.seq_execucao_extracao,
                    janela.data_fim.year, linhas,
                )
                erros = len(erros_linha)
            else:
                if linhas:
                    resultado = importar_lote(
                        [_linha_lote(l, janela.data_fim) for l in linhas],
                        dat_saldo_lote=janela.data_fim,
                        sigla_sistema=sistema.txt_sigla,
                        arquivo_origem=fonte.nom_fonte,
                    )
                    inseridas = resultado.linhas_inseridas
                    fundos_novos = len(resultado.fundos_auto_cadastrados)
                    detalhe_erros = resultado.detalhe_erros + detalhe_erros
                erros = len(erros_linha) + (resultado.linhas_com_erro if linhas else 0)
            detalhe = _serializar_detalhe(detalhe_erros)
            if inseridas == 0 and erros > 0:
                status = STATUS_ERRO
            elif erros > 0:
                status = STATUS_PARCIAL
            else:
                status = STATUS_SUCESSO
    except Exception as exc:  # runtime: config/credencial/conexão/extração
        db.session.rollback()
        db.session.add(execucao)  # rollback descartou a execução em flush
        status = STATUS_ERRO
        inseridas = erros = fundos_novos = 0
        mensagem = getattr(exc, "mensagem", None) or str(exc)
        detalhe = _serializar_detalhe([{"mensagem": mensagem}])

    execucao.num_duracao_segundos = round(time.monotonic() - cronometro, 3)
    execucao.cod_status = status
    execucao.qtd_linhas_inseridas = inseridas
    execucao.qtd_linhas_erro = erros
    execucao.qtd_fundos_auto_cadastrados = fundos_novos
    execucao.txt_detalhe_erros = detalhe
    db.session.commit()

    # Classificação (F4.3) — DEPOIS do commit que fecha a extração, e fora do
    # try dela de propósito: a carga já terminou e deu o que deu; falha de
    # classificação não pode reclassificá-la. Processa por SISTEMA DE ORIGEM
    # (o grão é o mapeamento; um sistema tem N fontes), e cada falha vira uma
    # execução de mapeamento ERRO, registrada lá.
    if fonte.cod_destino == DESTINO_LANCAMENTO:
        # import tardio: processamento_service importa daqui (regra/staging)
        from ..models.execucao_mapeamento import DISPARO_AUTOMATICO
        from .processamento_service import processar_sistema_origem

        processar_sistema_origem(fonte.seq_sistema_origem, disparo=DISPARO_AUTOMATICO)

    return execucao


def testar_conexao_fonte(seq_fonte: int) -> ResultadoTeste:
    """Resolve credenciais como a execução; NÃO registra execução (R9)."""
    fonte = _obter_fonte(seq_fonte)
    conector = _validar_tipo_conector(fonte.cod_tipo_conector)
    _validar_config(conector, fonte.json_config or {})
    config = resolver_config(fonte.json_config or {}, conector.schema_config)
    return conector.testar_conexao(config)


# --------------------------------------------------------------------------
# Leitura para telas (R10/R11/R12)
# --------------------------------------------------------------------------

_MASCARA_SECRETO = ""  # input secreto nunca traz valor; vazio = preserva atual


def _ultima_execucao(seq_fonte: int) -> ExecucaoExtracao | None:
    return (
        ExecucaoExtracao.query
        .filter_by(seq_fonte_extracao=seq_fonte)
        .order_by(ExecucaoExtracao.seq_execucao_extracao.desc())
        .first()
    )


def listar_fontes(nome: str | None = None, tipo: str | None = None,
                  status: str | None = None) -> list[dict]:
    """Fontes para a listagem, com o status da última execução (R10)."""
    consulta = FonteExtracao.query
    if nome:
        consulta = consulta.filter(FonteExtracao.nom_fonte.ilike(f"%{nome}%"))
    if tipo:
        consulta = consulta.filter_by(cod_tipo_conector=tipo)
    if status == "ativo":
        consulta = consulta.filter_by(ind_status="A")
    elif status == "inativo":
        consulta = consulta.filter_by(ind_status="I")

    sistemas = {s.seq_sistema_origem: s.txt_sigla for s in SistemaOrigem.query.all()}
    fontes = []
    for f in consulta.order_by(FonteExtracao.nom_fonte).all():
        ultima = _ultima_execucao(f.seq_fonte_extracao)
        fontes.append({
            "seq_fonte_extracao": f.seq_fonte_extracao,
            "nom_fonte": f.nom_fonte,
            "cod_tipo_conector": f.cod_tipo_conector,
            "sistema_origem": sistemas.get(f.seq_sistema_origem, ""),
            "txt_cron": f.txt_cron or "",
            "ativo": f.ind_status == "A",
            "ultima_status": ultima.cod_status if ultima else None,
            "ultima_em": ultima.dat_inicio_execucao if ultima else None,
        })
    return fontes


def obter_fonte_para_edicao(seq_fonte: int) -> dict:
    """Config com campos secretos mascarados — a tela nunca vê o valor (R12/D2)."""
    fonte = _obter_fonte(seq_fonte)
    conector = _validar_tipo_conector(fonte.cod_tipo_conector)
    secretos = set()
    try:
        from ..extracao.credenciais import campos_secretos
        secretos = campos_secretos(conector.schema_config)
    except Exception:
        pass
    config = dict(fonte.json_config or {})
    for campo in secretos:
        if campo in config:
            config[campo] = _MASCARA_SECRETO
    sistemas = {s.seq_sistema_origem: s.txt_sigla for s in SistemaOrigem.query.all()}
    return {
        "seq_fonte_extracao": fonte.seq_fonte_extracao,
        "nom_fonte": fonte.nom_fonte,
        "cod_tipo_conector": fonte.cod_tipo_conector,
        "cod_destino": fonte.cod_destino,
        "sistema_origem": sistemas.get(fonte.seq_sistema_origem, ""),
        "txt_cron": fonte.txt_cron or "",
        "json_config": config,
        "json_layout": fonte.json_layout,  # pré-carga do editor de layout (R17)
    }


def montar_layout_do_form(valores: dict) -> dict | None:
    """Layout do editor (R17): o cliente serializa escalares + colunas em
    `json_layout_raw`. Aqui só desserializa; a validação de conteúdo
    (transformação/destino/estrutura) fica no `_validar_layout` do cadastro,
    para não duplicar regra. Conector sem layout não envia o campo → None."""
    raw = (valores.get("json_layout_raw") or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        raise RegraNegocioError("Layout inválido: JSON malformado")


def montar_config_do_form(seq_fonte: int | None, cod_tipo_conector: str,
                          valores: dict) -> dict:
    """Monta o json_config a partir do form: campo secreto enviado vazio
    preserva o valor atual da fonte (na edição); ausente/vazio na criação
    simplesmente não entra (R12/D2)."""
    conector = _validar_tipo_conector(cod_tipo_conector)
    from ..extracao.credenciais import campos_secretos
    secretos = campos_secretos(conector.schema_config)
    atual = {}
    if seq_fonte is not None:
        fonte = _obter_fonte(seq_fonte)
        atual = dict(fonte.json_config or {})

    config = {}
    descricao_campos = set(conector.schema_config.model_fields)
    for campo in descricao_campos:
        valor = valores.get(campo)
        if campo in secretos and (valor is None or valor == ""):
            if campo in atual:
                config[campo] = atual[campo]  # preserva o segredo existente
            continue
        if valor is not None and valor != "":
            config[campo] = valor
    return config


def listar_execucoes(seq_fonte: int | None = None, status: str | None = None,
                     limite: int = 200) -> list[dict]:
    """Histórico de execuções, mais recentes primeiro, com detalhe de erros (R11)."""
    consulta = ExecucaoExtracao.query
    if seq_fonte is not None:
        consulta = consulta.filter_by(seq_fonte_extracao=seq_fonte)
    if status:
        consulta = consulta.filter_by(cod_status=status)

    nomes = {f.seq_fonte_extracao: f.nom_fonte for f in FonteExtracao.query.all()}
    execucoes = []
    for e in (consulta.order_by(ExecucaoExtracao.seq_execucao_extracao.desc())
              .limit(limite).all()):
        try:
            detalhe = json.loads(e.txt_detalhe_erros) if e.txt_detalhe_erros else []
        except (ValueError, TypeError):
            detalhe = [{"mensagem": e.txt_detalhe_erros}]
        execucoes.append({
            "seq_execucao_extracao": e.seq_execucao_extracao,
            "nom_fonte": nomes.get(e.seq_fonte_extracao, ""),
            "cod_status": e.cod_status,
            "cod_disparo": e.cod_disparo,
            "dat_inicio_execucao": e.dat_inicio_execucao,
            "num_duracao_segundos": e.num_duracao_segundos,
            "dat_janela_inicio": e.dat_janela_inicio,
            "dat_janela_fim": e.dat_janela_fim,
            "qtd_linhas_inseridas": e.qtd_linhas_inseridas,
            "qtd_linhas_erro": e.qtd_linhas_erro,
            "qtd_fundos_auto_cadastrados": e.qtd_fundos_auto_cadastrados,
            "detalhe_erros": detalhe,
        })
    return execucoes


__all__ = [
    'DISPARO_AGENDADO',
    'DISPARO_MANUAL',
    'JANELA_MAXIMA_DIAS',
    'alterar_fonte',
    'criar_fonte',
    'executar_fonte',
    'inativar_fonte',
    'listar_execucoes',
    'listar_fontes',
    'montar_config_do_form',
    'montar_janela',
    'montar_layout_do_form',
    'obter_fonte_para_edicao',
    'testar_conexao_fonte',
]
