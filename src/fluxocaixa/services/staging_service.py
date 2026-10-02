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
from .validacao import RegraNegocioError
from ..models.etl_staging import (
    DSC_ERRO_MAX,
    STATUS_ERRO,
    STATUS_OK,
    STATUS_PENDENTE,
)


def _como_data(valor) -> date | None:
    """Data crua da origem → `date` (ISO, dd/mm/aaaa ou date/datetime)."""
    from datetime import datetime

    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto[:10], formato).date()
        except ValueError:
            continue
    raise RegraNegocioError(f"Data inválida na linha extraída: {valor!r}")


def ano_da_linha(linha, ano_padrao: int) -> int:
    """Exercício da linha (extracao R24): o informado pela origem; na falta,
    o ano da data do MOVIMENTO; na falta, o padrão (o exercício da chamada
    ou o ano do fim da janela). Antes toda linha recebia o ano do fim da
    janela — dezembro de um ano ia para o mapeamento do ano seguinte."""
    informado = getattr(linha, "num_ano_exercicio", None)
    if informado not in (None, ""):
        try:
            return int(str(informado).strip())
        except ValueError:
            raise RegraNegocioError(f"Exercício inválido na linha extraída: {informado!r}")
    movimento = _como_data(linha.dat_saldo)
    return movimento.year if movimento else ano_padrao


def gravar_lote(seq_fonte: int, seq_execucao: int, ano: int, linhas) -> int:
    """Insere as linhas extraídas na staging (status pendente). Retorna a
    quantidade gravada. `linhas` são `LinhaExtraida` (dat_saldo/val_saldo +
    json_atributos com a linha crua); `ano` é só o PADRÃO — cada linha leva o
    seu exercício (`ano_da_linha`) e a sua data de registro."""
    pessoa = cod_pessoa_atual()
    total = 0
    for linha in linhas:
        db.session.add(EtlStaging(
            seq_fonte_extracao=seq_fonte,
            seq_execucao_extracao=seq_execucao,
            num_ano_exercicio=ano_da_linha(linha, ano),
            dat_referencia=_como_data(linha.dat_saldo),
            dat_registro=_como_data(getattr(linha, "dat_registro", None)),
            val_referencia=Decimal(linha.val_saldo),
            json_atributos=linha.json_atributos,
            ind_status_processamento=STATUS_PENDENTE,
            cod_pessoa_inclusao=pessoa,
        ))
        total += 1
    db.session.commit()
    return total


def substituir_janela(seq_fonte: int, anos, data_inicio: date, data_fim: date) -> int:
    """Reextração SUBSTITUI, nunca acumula (extracao R25): apaga as linhas da
    staging da MESMA fonte e exercícios cuja data de registro — ou do
    movimento, quando a linha não tem registro — cai na janela, e antes delas
    os lançamentos AUTOMÁTICOS que as referenciam (o processamento os refaz a
    partir das linhas novas). Sem commit: roda na transação da gravação.
    Devolve quantas linhas saíram."""
    from sqlalchemy import func

    from ..models import Lancamento

    anos = sorted(set(anos))
    if not anos:
        return 0
    data_janela = func.coalesce(EtlStaging.dat_registro, EtlStaging.dat_referencia)
    seqs = [seq for (seq,) in db.session.query(EtlStaging.seq_etl_staging).filter(
        EtlStaging.seq_fonte_extracao == seq_fonte,
        EtlStaging.num_ano_exercicio.in_(anos),
        data_janela >= data_inicio,
        data_janela <= data_fim,
    ).all()]
    if not seqs:
        return 0
    for inicio in range(0, len(seqs), 500):
        lote = seqs[inicio:inicio + 500]
        Lancamento.query.filter(Lancamento.seq_etl_staging.in_(lote)).delete(
            synchronize_session=False)
        EtlStaging.query.filter(EtlStaging.seq_etl_staging.in_(lote)).delete(
            synchronize_session=False)
    db.session.flush()
    return len(seqs)


def pendencias(dias: int = 7, hoje: date | None = None) -> list[dict]:
    """Linhas PENDENTES há mais de `dias` dias, por exercício e sistema de
    origem (automacao R21) — linha que nenhuma regra casa não pode ficar
    parada em silêncio."""
    from datetime import timedelta

    from sqlalchemy import func

    from ..models import FonteExtracao, SistemaOrigem

    limite = (hoje or date.today()) - timedelta(days=dias)
    linhas = (db.session.query(EtlStaging.num_ano_exercicio, SistemaOrigem.txt_sigla,
                               func.count(EtlStaging.seq_etl_staging),
                               func.min(EtlStaging.dat_inclusao))
              .join(FonteExtracao,
                    FonteExtracao.seq_fonte_extracao == EtlStaging.seq_fonte_extracao)
              .join(SistemaOrigem,
                    SistemaOrigem.seq_sistema_origem == FonteExtracao.seq_sistema_origem)
              .filter(EtlStaging.ind_status_processamento == STATUS_PENDENTE)
              .filter(EtlStaging.dat_inclusao <= limite)
              .group_by(EtlStaging.num_ano_exercicio, SistemaOrigem.txt_sigla)
              .order_by(EtlStaging.num_ano_exercicio, SistemaOrigem.txt_sigla)
              .all())
    return [{'ano': ano, 'sistema': sigla, 'quantidade': qtd, 'mais_antiga': antiga}
            for ano, sigla, qtd, antiga in linhas]


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
