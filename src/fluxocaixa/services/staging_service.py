"""Serviço da staging genérica (spec automacao-lancamentos R1/R4).

Grava as linhas cruas de fontes com destino LANCAMENTO em `flc_etl_staging`
(status pendente) e oferece o ciclo de vida de processamento — marcar ok/erro
e reprocessar por execução — que a F4.2/F4.3 consumirão. A staging fica
PENDENTE até a classificação (F4.2); nada a lê ainda.
"""
from datetime import date
from decimal import Decimal

from ..auth.contexto import cod_pessoa_atual
from ..models import EtlStaging
from ..models.base import db
from ..models.etl_staging import (
    DSC_ERRO_MAX,
    STATUS_ERRO,
    STATUS_OK,
    STATUS_PENDENTE,
)


def gravar_lote(seq_fonte: int, seq_execucao: int, ano: int, linhas) -> int:
    """Insere as linhas extraídas na staging (status pendente). Retorna a
    quantidade gravada. `linhas` são `LinhaExtraida` (dat_saldo/val_saldo +
    json_atributos com a linha crua)."""
    pessoa = cod_pessoa_atual()
    total = 0
    for linha in linhas:
        db.session.add(EtlStaging(
            seq_fonte_extracao=seq_fonte,
            seq_execucao_extracao=seq_execucao,
            num_ano_exercicio=ano,
            dat_referencia=linha.dat_saldo,
            val_referencia=Decimal(linha.val_saldo),
            json_atributos=linha.json_atributos,
            ind_status_processamento=STATUS_PENDENTE,
            cod_pessoa_inclusao=pessoa,
        ))
        total += 1
    db.session.commit()
    return total


def marcar_ok(seq_etl_staging: int) -> None:
    linha = EtlStaging.query.get(seq_etl_staging)
    if linha is None:
        return
    linha.ind_status_processamento = STATUS_OK
    linha.dsc_erro = None
    linha.dat_alteracao = date.today()
    linha.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()


def marcar_erro(seq_etl_staging: int, dsc_erro: str) -> None:
    linha = EtlStaging.query.get(seq_etl_staging)
    if linha is None:
        return
    linha.ind_status_processamento = STATUS_ERRO
    # Truncar ANTES de gravar (a referência trunca depois de escapar e estoura)
    linha.dsc_erro = (dsc_erro or "")[:DSC_ERRO_MAX]
    linha.dat_alteracao = date.today()
    linha.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()


def marcar_ok_lote(seqs, commit: bool = True) -> int:
    """Marca N linhas como processadas com UM commit.

    As variantes unitárias (R4) commitam por chamada — num laço de
    processamento isso seria um commit por lançamento.

    `commit=False` só faz `flush()`: o processamento (R12) marca o status na
    MESMA transação dos inserts de lançamento, e comitar aqui abriria a janela
    em que o lançamento existe com a linha ainda pendente.
    """
    return _marcar_lote({seq: None for seq in seqs}, STATUS_OK, commit=commit)


def marcar_erro_lote(pares, commit: bool = True) -> int:
    """`pares`: iterável de `(seq_etl_staging, mensagem)`. Um commit."""
    return _marcar_lote(dict(pares), STATUS_ERRO, commit=commit)


def _marcar_lote(por_seq: dict, status: str, commit: bool = True) -> int:
    if not por_seq:
        return 0
    pessoa = cod_pessoa_atual()
    hoje = date.today()
    linhas = EtlStaging.query.filter(
        EtlStaging.seq_etl_staging.in_(list(por_seq))).all()
    for linha in linhas:
        linha.ind_status_processamento = status
        mensagem = por_seq.get(linha.seq_etl_staging)
        # truncar ANTES de gravar, como nas variantes unitárias
        linha.dsc_erro = (mensagem or "")[:DSC_ERRO_MAX] if mensagem else None
        linha.dat_alteracao = hoje
        linha.cod_pessoa_alteracao = pessoa
    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return len(linhas)


def reprocessar_execucao(seq_execucao: int) -> int:
    """Reseta todas as linhas de uma execução para pendente (limpa dsc_erro).
    Retorna a quantidade resetada — é o resync por execução da F4.3."""
    linhas = EtlStaging.query.filter_by(seq_execucao_extracao=seq_execucao).all()
    for linha in linhas:
        linha.ind_status_processamento = STATUS_PENDENTE
        linha.dsc_erro = None
        linha.dat_alteracao = date.today()
        linha.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return len(linhas)


__all__ = [
    'gravar_lote',
    'marcar_erro',
    'marcar_erro_lote',
    'marcar_ok',
    'marcar_ok_lote',
    'reprocessar_execucao',
]
