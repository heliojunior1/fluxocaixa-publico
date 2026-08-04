"""Helpers dos steps do processamento (F4.3). Import tardio de `fluxocaixa`."""
from datetime import date
from decimal import Decimal

# Linhas fictícias (repo público): natureza 1112/2222, UG 999xxx.
LINHAS_PADRAO = [
    {"natureza": "11120000", "ug": "999001", "valor": "100.00"},
    {"natureza": "11120001", "ug": "999002", "valor": "200.00"},
    # despesa chega assinada do CASE contábil da fonte (ver CLAUDE.md)
    {"natureza": "22220000", "ug": "999001", "valor": "-300.00"},
]


def semear_staging(sigla, nom_fonte, linhas, ano=2026):
    """Cria (se preciso) uma fonte do sistema e deposita linhas na staging."""
    from fluxocaixa.models import EtlStaging, ExecucaoExtracao
    from fluxocaixa.models.base import db

    from ..conftest_extracao import (
        criar_fonte_fake,
        fonte_por_nome,
        garantir_conector_fake,
        garantir_sistema_origem,
    )

    garantir_conector_fake()
    garantir_sistema_origem(sigla)
    fonte = fonte_por_nome(nom_fonte)
    if fonte is None:
        fonte = criar_fonte_fake(nom_fonte, sigla_sistema=sigla)

    execucao = ExecucaoExtracao(
        seq_fonte_extracao=fonte.seq_fonte_extracao,
        dat_inicio_execucao=date(ano, 7, 10), cod_disparo="MANUAL",
        cod_status="SUCESSO", dat_janela_inicio=date(ano, 7, 10),
        dat_janela_fim=date(ano, 7, 10),
    )
    db.session.add(execucao)
    db.session.flush()

    criadas = []
    for linha in linhas:
        registro = EtlStaging(
            seq_fonte_extracao=fonte.seq_fonte_extracao,
            seq_execucao_extracao=execucao.seq_execucao_extracao,
            num_ano_exercicio=ano, dat_referencia=date(ano, 7, 10),
            val_referencia=Decimal(linha["valor"]), json_atributos=dict(linha),
            ind_status_processamento='0',
        )
        db.session.add(registro)
        criadas.append(registro)
    db.session.commit()
    return fonte, criadas


def linha_por_natureza(natureza):
    from fluxocaixa.models import EtlStaging
    from fluxocaixa.models.base import db

    db.session.expire_all()
    for linha in EtlStaging.query.all():
        if (linha.json_atributos or {}).get("natureza") == natureza:
            return linha
    return None


def lancamentos_do_qualificador(num_qualificador):
    from fluxocaixa.models import Lancamento, Qualificador
    from fluxocaixa.models.base import db

    db.session.expire_all()
    q = Qualificador.query.filter_by(num_qualificador=num_qualificador).first()
    if q is None:
        return []
    return (Lancamento.query
            .filter_by(seq_qualificador=q.seq_qualificador, ind_status='A')
            .all())


def ultima_execucao_mapeamento(seq_mapeamento=None):
    from fluxocaixa.models import ExecucaoMapeamento
    from fluxocaixa.models.base import db

    db.session.expire_all()
    consulta = ExecucaoMapeamento.query
    if seq_mapeamento is not None:
        consulta = consulta.filter_by(seq_mapeamento=seq_mapeamento)
    return consulta.order_by(ExecucaoMapeamento.seq_execucao_mapeamento.desc()).first()


def limpar_estado_processamento():
    """Cada módulo do processamento conta linhas/lançamentos: parte do zero."""
    from fluxocaixa.models import (
        EtlStaging,
        ExecucaoMapeamento,
        ItemMapeamento,
        Lancamento,
        Mapeamento,
    )
    from fluxocaixa.models.base import db

    db.session.rollback()
    db.session.query(ExecucaoMapeamento).delete()
    db.session.query(Lancamento).delete()
    db.session.query(ItemMapeamento).delete()
    db.session.query(Mapeamento).delete()
    db.session.query(EtlStaging).delete()
    db.session.commit()
