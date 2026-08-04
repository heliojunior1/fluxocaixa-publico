"""Processamento da staging em lançamentos (spec automacao-lancamentos R12–R15).

Fecha o circuito: linha PENDENTE → lançamento com origem `Automático`.

**Sem bookmark, sem janela, sem cold start.** A linha pendente É o marco, e é
exato. A implementação de referência varre a staging por janela de data porque lá o
status da linha é só escape de resync; a F4.1 construiu status por linha,
indexado — portar a janela seria copiar um acidente (e o card ainda pede
`MAX(dat_lancamento)`, a data contábil, que RETROAGE; a própria referência usa
o carimbo de escrita, monotônico, justamente por isso).
"""
import json
import time
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from ..auth.contexto import cod_pessoa_atual
from ..models import (
    EtlStaging,
    ExecucaoMapeamento,
    FonteExtracao,
    Lancamento,
    Mapeamento,
)
from ..models.base import db
from ..models.etl_staging import STATUS_ERRO as STATUS_ERRO_LINHA
from ..models.etl_staging import STATUS_PENDENTE
from ..models.execucao_mapeamento import (
    DISPARO_MANUAL,
    LIMITE_DETALHE_ERROS,
    STATUS_ERRO,
    STATUS_PARCIAL,
    STATUS_SEM_DADOS,
    STATUS_SUCESSO,
)
from ..models.item_mapeamento import INVERSAO_SIM
from ..models.lancamento import TIPO_CREDITO, TIPO_DEBITO
from ..models.mapeamento import TIPO_RECEITA
from . import staging_service
from .dominio_lancamento import (
    ORIGEM_AUTOMATICO,
    TIPO_ENTRADA,
    TIPO_SAIDA,
    resolver_origem,
    resolver_tipo,
)
from .regra import traduzir_regra
from .validacao import RegraNegocioError


def _linhas_candidatas(mapeamento):
    """Linhas PENDENTES do sistema de origem + ano do mapeamento, com valor ≠ 0.

    Mesmo join do preview (F4.2): o recorte é a chave do cabeçalho.

    Defesa em profundidade (R12): linha que JÁ possui lançamento ativo
    referenciando-a não é candidata, ainda que esteja pendente — estado que só
    aparece se uma janela se abrir por fora da transação única (restore
    parcial, escrita manual no banco). A transação resolve o defeito; este
    filtro faz a duplicação exigir dois erros independentes, não um.
    """
    ja_lancada = (db.session.query(Lancamento.seq_lancamento)
                  .filter(Lancamento.seq_etl_staging == EtlStaging.seq_etl_staging)
                  .filter(Lancamento.ind_status == 'A')
                  .exists())
    return (EtlStaging.query
            .join(FonteExtracao,
                  FonteExtracao.seq_fonte_extracao == EtlStaging.seq_fonte_extracao)
            .filter(FonteExtracao.seq_sistema_origem == mapeamento.seq_sistema_origem)
            .filter(EtlStaging.num_ano_exercicio == mapeamento.num_ano_exercicio)
            .filter(EtlStaging.ind_status_processamento == STATUS_PENDENTE)
            .filter(EtlStaging.val_referencia != 0)
            .filter(~ja_lancada))


def _itens_ativos(mapeamento):
    return [i for i in mapeamento.itens if i.ind_status == 'A']


def _casamentos(mapeamento, itens) -> dict:
    """`{seq_etl_staging: [item, ...]}` — o filtro pesado fica no banco.

    Uma consulta por item (o predicado é expressão SQLAlchemy da F4.2); a
    decisão por linha fica em Python, testável.
    """
    por_linha = defaultdict(list)
    for item in itens:
        predicado = traduzir_regra(item.txt_regra)
        for (seq,) in (_linhas_candidatas(mapeamento)
                       .filter(predicado)
                       .with_entities(EtlStaging.seq_etl_staging).all()):
            por_linha[seq].append(item)
    return por_linha


def _gravar_lancamento(linha, item, mapeamento, cod_tipo, cod_origem, pessoa):
    """Grava o lançamento derivando o tipo do SINAL do valor efetivo (R10).

    A inversão do item é aplicada ANTES da derivação — assim a flag segue com
    a função de corrigir a convenção da origem, e o sinal resultante é que
    decide crédito/débito. Diferente da porta manual, aqui não há usuário para
    avisar: a staging traz o valor já assinado pelo `CASE` contábil da fonte.

    Consequência deliberada: um estorno (valor efetivo negativo) sob um
    mapeamento de RECEITA vira 'D' — reversão de crédito é débito — e continua
    no qualificador de receita do item, netando corretamente na árvore.
    `cod_tipo` (do `ind_tipo` do mapeamento) deixou de ditar o tipo; segue
    aqui só como o tipo esperado da configuração.
    """
    valor = Decimal(linha.val_referencia)
    if item.ind_inversao_sinal == INVERSAO_SIM:
        # aplicada IGUALMENTE a receita e despesa — na referência a inversão é
        # silenciosamente ignorada na despesa (o insert de despesa nem tem o token)
        valor = -valor

    # Fonte de recursos (R17): dimensão OPCIONAL estampada do json_atributos —
    # ausente/não parseável = sem fonte, nunca erro de linha. Import tardio
    # (fonte_recurso_service importa validacao, sem ciclo com este módulo).
    from .fonte_recurso_service import resolver_fonte_de_atributos

    seq_fonte = resolver_fonte_de_atributos(
        linha.json_atributos, linha.num_ano_exercicio or linha.dat_referencia.year)

    db.session.add(Lancamento(
        dat_lancamento=linha.dat_referencia,
        seq_qualificador=item.seq_qualificador,
        val_lancamento=abs(valor).quantize(Decimal("0.01")),
        cod_tipo_lancamento=TIPO_CREDITO if valor >= 0 else TIPO_DEBITO,
        cod_origem_lancamento=cod_origem,
        seq_etl_staging=linha.seq_etl_staging,   # a âncora (R12)
        seq_fonte_recurso=seq_fonte,
        cod_pessoa_inclusao=pessoa,
        ind_status='A',
    ))


def _classificar_linhas(mapeamento, itens) -> tuple[int, list, list, list]:
    """`(gerados, seqs_ok, erros, detalhe)`.

    - 1 item  → lançamento
    - 2+ itens → erro explícito na linha (classificação dá UM destino)
    - 0 itens  → segue pendente (outro mapeamento pode ser o dono)
    """
    por_linha = _casamentos(mapeamento, itens)
    if not por_linha:
        return 0, [], [], []

    linhas = {l.seq_etl_staging: l for l in
              _linhas_candidatas(mapeamento)
              .filter(EtlStaging.seq_etl_staging.in_(list(por_linha))).all()}

    cod_tipo = resolver_tipo(
        TIPO_ENTRADA if mapeamento.ind_tipo == TIPO_RECEITA else TIPO_SAIDA
    ).cod_tipo_lancamento
    cod_origem = resolver_origem(ORIGEM_AUTOMATICO).cod_origem_lancamento
    pessoa = cod_pessoa_atual()

    gerados, seqs_ok, erros, detalhe = 0, [], [], []
    for seq, casados in por_linha.items():
        linha = linhas.get(seq)
        if linha is None:  # pragma: no cover - corrida improvável
            continue
        if len(casados) > 1:
            quals = ', '.join(sorted(
                i.qualificador.num_qualificador for i in casados))
            mensagem = (f"linha casa com {len(casados)} itens do mapeamento "
                        f"(qualificadores {quals}) — as regras devem ser "
                        f"mutuamente exclusivas")
            erros.append((seq, mensagem))
            detalhe.append({"linha": seq, "mensagem": mensagem})
            continue
        _gravar_lancamento(linha, casados[0], mapeamento, cod_tipo, cod_origem, pessoa)
        seqs_ok.append(seq)
        gerados += 1

    db.session.flush()
    return gerados, seqs_ok, erros, detalhe


def _itens_sujos(itens):
    """Sujo := sem marco de execução — nunca processado, ou processado numa
    forma que já não é a atual (`alterar_mapeamento` zera o marco quando o
    conteúdo muda).

    Deliberadamente NÃO compara `dat_alteracao > dat_ultima_execucao` como a
    referência: lá as colunas são timestamp (`DTH_*`), aqui são `Date` — editar
    a regra e processar no mesmo dia jamais acusaria sujeira.
    """
    return [i for i in itens if i.dat_ultima_execucao is None]


def _resync(item, cod_origem, mapeamento) -> int:
    """Remove os lançamentos do item e devolve à staging EXATAMENTE as linhas
    que os originaram. Devolve quantos foram removidos.

    É aqui que a FK (R12) paga: a referência, sem ela, reseta o ANO INTEIRO do
    item sujo. Apaga (não inativa) — ver design D5: é linha de máquina,
    reproduzível a partir da staging, e inativar acumularia lixo que todo
    relatório teria de filtrar para sempre.

    O escopo é o do MAPEAMENTO dono do item (R14): qualificador + ano de
    exercício + sistema de origem, via join com a staging e a fonte. O mesmo
    qualificador-folha é destino de itens em mapeamentos de exercícios
    diferentes no uso normal (um mapeamento por ano) — sem o recorte, o resync
    de um item de um exercício apagaria os lançamentos dos outros, que este
    mapeamento não é capaz de regerar. O inner join com a staging já garante
    a FK não-nula.
    """
    lancamentos = (Lancamento.query
                   .join(EtlStaging,
                         EtlStaging.seq_etl_staging == Lancamento.seq_etl_staging)
                   .join(FonteExtracao,
                         FonteExtracao.seq_fonte_extracao == EtlStaging.seq_fonte_extracao)
                   .filter(Lancamento.seq_qualificador == item.seq_qualificador)
                   .filter(Lancamento.cod_origem_lancamento == cod_origem)
                   .filter(EtlStaging.num_ano_exercicio == mapeamento.num_ano_exercicio)
                   .filter(FonteExtracao.seq_sistema_origem
                           == mapeamento.seq_sistema_origem)
                   .all())
    if not lancamentos:
        return 0

    seqs = {l.seq_etl_staging for l in lancamentos}
    for lancamento in lancamentos:
        db.session.delete(lancamento)
    db.session.flush()

    for linha in EtlStaging.query.filter(
            EtlStaging.seq_etl_staging.in_(list(seqs))).all():
        linha.ind_status_processamento = STATUS_PENDENTE
        linha.dsc_erro = None
    db.session.flush()
    return len(lancamentos)


def _reabrir_linhas_em_erro(mapeamento) -> int:
    """Devolve a pendente as linhas em ERRO do escopo do mapeamento.

    A linha em erro por sobreposição nunca gerou lançamento, então o resync por
    FK (`_resync`) não a alcança — e, estando em `2`, ela deixou de ser
    candidata. Mas o erro é propriedade do **conjunto de regras**, não da linha:
    se qualquer item ficou sujo, a linha tem de ser reavaliada, senão corrigir a
    regra nunca a traria de volta.
    """
    linhas = (EtlStaging.query
              .join(FonteExtracao,
                    FonteExtracao.seq_fonte_extracao == EtlStaging.seq_fonte_extracao)
              .filter(FonteExtracao.seq_sistema_origem == mapeamento.seq_sistema_origem)
              .filter(EtlStaging.num_ano_exercicio == mapeamento.num_ano_exercicio)
              .filter(EtlStaging.ind_status_processamento == STATUS_ERRO_LINHA)
              .all())
    for linha in linhas:
        linha.ind_status_processamento = STATUS_PENDENTE
        linha.dsc_erro = None
    if linhas:
        db.session.flush()
    return len(linhas)


def _detalhe(itens_detalhe) -> str | None:
    if not itens_detalhe:
        return None
    return json.dumps(itens_detalhe, ensure_ascii=False)[:LIMITE_DETALHE_ERROS]


def processar_mapeamento(seq_mapeamento: int,
                         disparo: str = DISPARO_MANUAL) -> ExecucaoMapeamento:
    """Processa um mapeamento e SEMPRE registra a execução."""
    mapeamento = Mapeamento.query.get(seq_mapeamento)
    if mapeamento is None or mapeamento.ind_status != 'A':
        raise RegraNegocioError("Mapeamento inexistente ou inativo")

    inicio = datetime.now()
    cronometro = time.monotonic()
    gerados = erros = removidos = 0
    detalhe = None
    status = STATUS_ERRO

    try:
        itens = _itens_ativos(mapeamento)
        cod_origem = resolver_origem(ORIGEM_AUTOMATICO).cod_origem_lancamento

        # 1) resync dos itens sujos (R14) — antes de classificar
        sujos = _itens_sujos(itens)
        for item in sujos:
            removidos += _resync(item, cod_origem, mapeamento)
        if sujos:
            # regra mudou ⇒ reavaliar também as linhas que estavam em erro
            _reabrir_linhas_em_erro(mapeamento)

        # 2) classifica as pendentes (R13)
        gerados, seqs_ok, pares_erro, itens_detalhe = _classificar_linhas(
            mapeamento, itens)
        erros = len(pares_erro)

        # 3) status das linhas, na MESMA transação dos inserts (R12) —
        # comitar antes de marcar abria a janela em que o lançamento existe
        # com a linha ainda pendente: queda do processo ali e o próximo
        # processamento reclassificava as mesmas linhas, duplicando o caixa
        staging_service.marcar_ok_lote(seqs_ok, commit=False)
        staging_service.marcar_erro_lote(pares_erro, commit=False)

        # 4) carimba dat_ultima_execucao — primeiro escritor da coluna
        hoje = date.today()
        for item in itens:
            item.dat_ultima_execucao = hoje

        # 5) transação ÚNICA: lançamentos + resync + status + marco,
        # tudo-ou-nada — interrupção em qualquer ponto deixa o banco
        # ou com tudo aplicado, ou com nada
        db.session.commit()

        detalhe = _detalhe(itens_detalhe)
        if gerados == 0 and erros == 0 and removidos == 0:
            status = STATUS_SEM_DADOS
        elif gerados == 0 and erros > 0:
            status = STATUS_ERRO
        elif erros > 0:
            status = STATUS_PARCIAL
        else:
            status = STATUS_SUCESSO
    except Exception as exc:
        db.session.rollback()
        status = STATUS_ERRO
        # com a transação única, zerar é VERDADE: o rollback desfez tudo o que
        # esta execução tentou — os contadores descrevem o banco (R15)
        gerados = erros = removidos = 0
        mensagem = getattr(exc, "mensagem", None) or str(exc)
        detalhe = _detalhe([{"mensagem": mensagem}])

    execucao = ExecucaoMapeamento(
        seq_mapeamento=seq_mapeamento,
        dat_inicio_execucao=inicio,
        num_duracao_segundos=round(time.monotonic() - cronometro, 3),
        cod_disparo=disparo,
        cod_status=status,
        qtd_lancamentos_gerados=gerados,
        qtd_linhas_erro=erros,
        qtd_lancamentos_removidos=removidos,
        txt_detalhe_erros=detalhe,
        cod_pessoa_inclusao=cod_pessoa_atual(),
    )
    db.session.add(execucao)
    db.session.commit()
    return execucao


def processar_sistema_origem(seq_sistema_origem: int,
                             disparo: str = DISPARO_MANUAL) -> list:
    """Processa os mapeamentos ativos de um sistema de origem.

    O grão é o mapeamento (um sistema tem N fontes) — daí processar por sistema
    e não por fonte, sem repetir o mesmo mapeamento.
    """
    mapeamentos = Mapeamento.query.filter_by(
        seq_sistema_origem=seq_sistema_origem, ind_status='A').all()
    return [processar_mapeamento(m.seq_mapeamento, disparo=disparo)
            for m in mapeamentos]


__all__ = ['processar_mapeamento', 'processar_sistema_origem']
