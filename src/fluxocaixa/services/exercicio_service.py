"""Exercício aberto e fechado (cadastros-nucleo R31).

⚠️ Ano sem linha em `flc_exercicio` é ABERTO — instalação que nunca fechou
nada, e massa de teste que cria qualificador direto, se comportam como sempre.
Só uma linha 'F' fecha.

⚠️ `exigir_aberto` é a ORIGEM ÚNICA da guarda: plano, mapeamento, lançamento
(manual, edição, inativação, importação), extração e processamento passam por
ela — cópias divergiriam (lição da F6.4/F10.1).

Fechar é OPERACIONAL: trava escrita e automação do ano. Previsão (cenários,
versões, De/Para) não é travada.
"""
from __future__ import annotations

from datetime import date

from ..models.base import db
from ..models.exercicio import (
    EVENTO_ABERTURA,
    EVENTO_FECHAMENTO,
    EVENTO_REABERTURA,
    SITUACAO_ABERTO,
    SITUACAO_FECHADO,
    Exercicio,
    ExercicioEvento,
)
from .validacao import RegraNegocioError


# ---------------------------------------------------------------- leitura

def situacao(ano: int) -> str:
    linha = db.session.get(Exercicio, int(ano))
    return linha.cod_situacao if linha is not None else SITUACAO_ABERTO


def fechado(ano: int | None) -> bool:
    if ano is None:
        return False
    return situacao(ano) == SITUACAO_FECHADO


def anos_fechados() -> set[int]:
    return {e.num_ano_exercicio for e in
            Exercicio.query.filter_by(cod_situacao=SITUACAO_FECHADO).all()}


def exigir_aberto(ano: int | None, o_que: str) -> None:
    """Recusa a escrita `o_que` num exercício fechado."""
    if fechado(ano):
        raise RegraNegocioError(
            f"O exercício {ano} está fechado — {o_que} não é permitido. "
            "Reabra o exercício (com motivo) para alterar")


def anos_conhecidos() -> list[int]:
    """Anos com plano de qualificadores ou com situação registrada."""
    from ..models import Qualificador

    anos = {a for (a,) in db.session.query(Qualificador.num_ano_exercicio).distinct().all()
            if a is not None}
    anos |= {e.num_ano_exercicio for e in Exercicio.query.all()}
    return sorted(anos, reverse=True)


def exercicios_alvo(data_inicio: date, data_fim: date) -> list[int]:
    """Exercícios que uma extração da janela alcança (extracao R24): os
    ABERTOS entre o ano anterior ao início e o ano do fim. Documento
    registrado na janela só pode ser do ano dela ou ajuste do anterior; ano
    antigo esquecido aberto não é varrido todo dia. Sem nenhum conhecido no
    intervalo (instalação sem plano), o ano do fim."""
    fechados = anos_fechados()
    alvo = [a for a in anos_conhecidos()
            if data_inicio.year - 1 <= a <= data_fim.year and a not in fechados]
    if not alvo and data_fim.year not in fechados:
        alvo = [data_fim.year]
    return sorted(alvo)


def historico(ano: int) -> list[ExercicioEvento]:
    return (ExercicioEvento.query.filter_by(num_ano_exercicio=int(ano))
            .order_by(ExercicioEvento.seq_exercicio_evento).all())


def pendencias_do_ano(ano: int) -> dict:
    """Linhas da staging do exercício que não viraram lançamento."""
    from ..models import EtlStaging
    from ..models.etl_staging import STATUS_ERRO, STATUS_PENDENTE

    base = EtlStaging.query.filter(EtlStaging.num_ano_exercicio == int(ano))
    return {
        'pendentes': base.filter(EtlStaging.ind_status_processamento == STATUS_PENDENTE).count(),
        'erros': base.filter(EtlStaging.ind_status_processamento == STATUS_ERRO).count(),
    }


def listar_para_tela() -> list[dict]:
    return [{'ano': ano, 'situacao': situacao(ano), 'pendencias': pendencias_do_ano(ano),
             'historico': historico(ano)} for ano in anos_conhecidos()]


# ---------------------------------------------------------------- escrita

def _autor(user_id):
    if user_id is not None:
        return user_id
    from ..auth.contexto import cod_pessoa_atual

    return cod_pessoa_atual()


def _motivo(motivo: str) -> str:
    texto = (motivo or '').strip()
    if not texto:
        raise RegraNegocioError("Informe o motivo")
    return texto[:1000]


def _registrar(ano: int, tipo_evento: str, situacao_nova: str, motivo: str, autor) -> None:
    """Evento + situação atual, SEM commit (o chamador é dono da transação)."""
    linha = db.session.get(Exercicio, int(ano))
    if linha is None:
        db.session.add(Exercicio(num_ano_exercicio=int(ano), cod_situacao=situacao_nova,
                                 cod_pessoa_inclusao=autor))
    else:
        linha.cod_situacao = situacao_nova
        linha.dat_alteracao = date.today()
        linha.cod_pessoa_alteracao = autor
    db.session.add(ExercicioEvento(num_ano_exercicio=int(ano), cod_tipo_evento=tipo_evento,
                                   dsc_motivo=motivo, cod_pessoa_evento=autor))
    db.session.flush()


def registrar_abertura(ano: int, relatorio: str, autor) -> None:
    """Chamado DENTRO da transação de `abrir_exercicio`."""
    _registrar(ano, EVENTO_ABERTURA, SITUACAO_ABERTO, relatorio, autor)


def fechar_exercicio(ano: int, motivo: str, confirmado: bool = False,
                     user_id: int | None = None) -> None:
    """Fecha o exercício. Sem `confirmado`, recusa citando as pendências da
    staging do ano — fechar com linha parada é decisão consciente."""
    motivo = _motivo(motivo)
    ano = int(ano)
    if fechado(ano):
        raise RegraNegocioError(f"O exercício {ano} já está fechado")
    if not confirmado:
        pend = pendencias_do_ano(ano)
        resumo = ''
        if pend['pendentes'] or pend['erros']:
            resumo = (f" Há {pend['pendentes']} linha(s) pendente(s) e {pend['erros']} "
                      f"linha(s) em erro na automação de {ano}, que não viraram "
                      "lançamento e deixarão de ser processadas.")
        raise RegraNegocioError(
            f"Fechar {ano} trava o plano, os mapeamentos, os lançamentos e a "
            f"automação do ano.{resumo} Para continuar, confirme o fechamento")
    try:
        _registrar(ano, EVENTO_FECHAMENTO, SITUACAO_FECHADO, motivo, _autor(user_id))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def reabrir_exercicio(ano: int, motivo: str, user_id: int | None = None) -> None:
    motivo = _motivo(motivo)
    ano = int(ano)
    if not fechado(ano):
        raise RegraNegocioError(f"O exercício {ano} não está fechado")
    try:
        _registrar(ano, EVENTO_REABERTURA, SITUACAO_ABERTO, motivo, _autor(user_id))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
