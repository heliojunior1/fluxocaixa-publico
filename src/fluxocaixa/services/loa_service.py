"""Regra de negócio da LOA (spec cadastros-nucleo R24).

Change: loa-unicidade-e-servico-proprio. Antes o upsert e a resolução de
qualificador viviam em `web/loa.py` e o adapter de importação importava DA
WEB — camadas invertidas. A unicidade por (ano, qualificador) entre ativos
agora é garantida também no BANCO (índice único parcial, migração 0033):
duplicata dobraria o teto do autorizado, as metas fiscais e o previsto do
desembolso.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from ..auth.contexto import cod_pessoa_atual
from ..models import Loa, Qualificador
from ..models.base import db
from .validacao import RegraNegocioError


def encontrar_qualificador(ref: str) -> Qualificador | None:
    """Busca qualificador ATIVO por num_qualificador ou descrição
    (case-insensitive). Movida de `web/loa.py` — a F6.7 registra o efeito
    colateral: renomear código em cascata faz planilha com código antigo
    casar só pela descrição."""
    q = Qualificador.query.filter(
        Qualificador.num_qualificador == ref,
        Qualificador.ind_status == 'A',
    ).first()

    if not q:
        q = Qualificador.query.filter(
            func.lower(Qualificador.dsc_qualificador) == func.lower(ref),
            Qualificador.ind_status == 'A',
        ).first()

    return q


def upsert_loa(ano: int, seq_qualificador: int, valor: Decimal) -> Loa:
    """Atualiza o registro ATIVO da chave ou insere um novo. NÃO comita —
    o dono da transação é o chamador (rota ou lote de importação).

    O `flush()` faz o check-then-insert enxergar linhas inseridas pelo MESMO
    lote (duas linhas do arquivo com a mesma chave viram um update, não uma
    violação no commit).
    """
    pessoa = cod_pessoa_atual()
    existente = Loa.query.filter_by(
        num_ano=ano,
        seq_qualificador=seq_qualificador,
        ind_status='A',
    ).first()

    if existente:
        existente.val_loa = valor
        existente.dat_alteracao = date.today()
        existente.cod_pessoa_alteracao = pessoa
        registro = existente
    else:
        registro = Loa(
            num_ano=ano,
            seq_qualificador=seq_qualificador,
            val_loa=valor,
            cod_pessoa_inclusao=pessoa,
        )
        db.session.add(registro)
    db.session.flush()
    return registro


def salvar_manual(ano: int, seq_qualificador: int, valor: Decimal) -> Loa:
    """Upsert + commit da porta manual. A corrida que escapar ao
    check-then-insert bate na constraint — vira erro de negócio, nunca 500."""
    try:
        registro = upsert_loa(ano, seq_qualificador, valor)
        db.session.commit()
        return registro
    except IntegrityError:
        db.session.rollback()
        raise RegraNegocioError(
            "Já existe registro ativo da LOA para este ano e qualificador — "
            "recarregue a página e edite o registro existente")


def inativar(seq_loa: int) -> Loa:
    registro = Loa.query.get_or_404(seq_loa)
    registro.ind_status = 'I'
    registro.dat_alteracao = date.today()
    registro.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return registro
