"""Massa compartilhada dos BDDs de exercício (change exercicio-aberto-fechado).

Ilhas 2141/2142, ramo "1.84", sistemas "SIS84"/"SIS84B", fontes "Fonte BDD84"
e "Fonte ANO84". Import tardio de `fluxocaixa` em todas as funções.
"""
from datetime import date, timedelta
from decimal import Decimal

ANOS = (2141, 2142)
RAMO = "1.84"
SISTEMAS = ("SIS84", "SIS84B")
FONTES = ("Fonte BDD84", "Fonte ANO84")


def db():
    from fluxocaixa.models.base import db as _db

    return _db


def limpar():
    from fluxocaixa.models import (
        EtlStaging,
        ExecucaoMapeamento,
        FonteExtracao,
        ItemMapeamento,
        Lancamento,
        Mapeamento,
        Qualificador,
        SistemaOrigem,
    )
    from fluxocaixa.models.exercicio import Exercicio, ExercicioEvento

    sessao = db().session
    sessao.rollback()
    quals = Qualificador.query.filter(
        Qualificador.num_ano_exercicio.in_(ANOS),
        Qualificador.num_qualificador.like(f"{RAMO}%")).all()
    seqs = [q.seq_qualificador for q in quals]
    if seqs:
        Lancamento.query.filter(Lancamento.seq_qualificador.in_(seqs)).delete(
            synchronize_session=False)
    sistemas = [s.seq_sistema_origem for s in SistemaOrigem.query.filter(
        SistemaOrigem.txt_sigla.in_(SISTEMAS)).all()]
    if sistemas:
        for m in Mapeamento.query.filter(Mapeamento.seq_sistema_origem.in_(sistemas)).all():
            ExecucaoMapeamento.query.filter_by(seq_mapeamento=m.seq_mapeamento).delete()
            ItemMapeamento.query.filter_by(seq_mapeamento=m.seq_mapeamento).delete()
            sessao.delete(m)
        sessao.flush()
    for fonte in FonteExtracao.query.filter(FonteExtracao.nom_fonte.in_(FONTES)).all():
        linhas = [l.seq_etl_staging for l in EtlStaging.query.filter_by(
            seq_fonte_extracao=fonte.seq_fonte_extracao).all()]
        if linhas:
            Lancamento.query.filter(Lancamento.seq_etl_staging.in_(linhas)).delete(
                synchronize_session=False)
        EtlStaging.query.filter_by(seq_fonte_extracao=fonte.seq_fonte_extracao).delete()
    sessao.flush()
    for q in sorted(quals, key=lambda q: -len(q.num_qualificador)):
        sessao.delete(q)
        sessao.flush()
    ExercicioEvento.query.filter(ExercicioEvento.num_ano_exercicio.in_(ANOS)).delete(
        synchronize_session=False)
    Exercicio.query.filter(Exercicio.num_ano_exercicio.in_(ANOS)).delete(
        synchronize_session=False)
    sessao.commit()


def rubrica(codigo, ano, raiz=None):
    from fluxocaixa.models import Qualificador

    q = Qualificador.query.filter_by(num_qualificador=codigo, num_ano_exercicio=ano,
                                     ind_status='A').first()
    if q is not None:
        return q
    pai = None
    if codigo.count(".") > 1:
        pai = rubrica(codigo.rsplit(".", 1)[0], ano)
    q = Qualificador(num_qualificador=codigo, dsc_qualificador=f"BDD84 {codigo}",
                     num_ano_exercicio=ano, ind_status='A', cod_rubrica_raiz=raiz,
                     cod_qualificador_pai=pai.seq_qualificador if pai else None)
    db().session.add(q)
    db().session.commit()
    return q


def sistema(sigla):
    from ..conftest_extracao import garantir_sistema_origem
    from fluxocaixa.models import SistemaOrigem

    garantir_sistema_origem(sigla)
    return SistemaOrigem.query.filter_by(txt_sigla=sigla).first()


def mapeamento(ano, sigla, regra, codigo, ano_rubrica=None):
    from fluxocaixa.services.mapeamento_service import criar_mapeamento

    from .conftest_regra import garantir_termos_padrao

    garantir_termos_padrao()
    return criar_mapeamento(
        num_ano_exercicio=ano, seq_sistema_origem=sistema(sigla).seq_sistema_origem,
        dsc_mapeamento=f"BDD84 {sigla} {ano}",
        itens=[{"seq_qualificador": rubrica(codigo, ano_rubrica or ano).seq_qualificador,
                "txt_regra": regra}])


LAYOUT_LANC = {"campos": [{"caminho": "d", "destino": "dat_saldo"},
                          {"caminho": "v", "destino": "val_saldo"}],
               "capturar_atributos": True}


def fonte_lancamento(nome, sigla="SIS84", tipo="FAKE"):
    """Fonte de destino LANCAMENTO (o layout é exigido pelo cadastro; os
    fakes o ignoram e devolvem as linhas programadas)."""
    from fluxocaixa.services.extracao_service import criar_fonte

    from ..conftest_extracao import CONFIG_FAKE_VALIDO, fonte_por_nome

    sistema(sigla)
    fonte = fonte_por_nome(nome)
    if fonte is not None:
        if fonte.ind_status != 'A':  # outro cenário pode tê-la inativado
            fonte.ind_status = 'A'
            db().session.commit()
        return fonte
    return criar_fonte(nom_fonte=nome, cod_tipo_conector=tipo, sigla_sistema=sigla,
                       json_config=dict(CONFIG_FAKE_VALIDO), json_layout=LAYOUT_LANC,
                       cod_destino="LANCAMENTO")


def linha_pendente(ano, natureza, valor="123.45", dias_atras=0, sigla="SIS84"):
    from fluxocaixa.models import EtlStaging, ExecucaoExtracao

    from ..conftest_extracao import garantir_conector_fake

    garantir_conector_fake()
    fonte = fonte_lancamento("Fonte BDD84", sigla)
    execucao = ExecucaoExtracao(
        seq_fonte_extracao=fonte.seq_fonte_extracao, dat_inicio_execucao=date(ano, 6, 1),
        cod_disparo="MANUAL", cod_status="SUCESSO",
        dat_janela_inicio=date(ano, 6, 1), dat_janela_fim=date(ano, 6, 1))
    db().session.add(execucao)
    db().session.flush()
    db().session.add(EtlStaging(
        seq_fonte_extracao=fonte.seq_fonte_extracao,
        seq_execucao_extracao=execucao.seq_execucao_extracao,
        num_ano_exercicio=ano, dat_referencia=date(ano, 6, 1),
        val_referencia=Decimal(valor), json_atributos={"natureza": natureza},
        ind_status_processamento='0',
        dat_inclusao=date.today() - timedelta(days=dias_atras)))
    db().session.commit()


def fechar(ano):
    from fluxocaixa.services.exercicio_service import fechar_exercicio

    fechar_exercicio(ano, "Encerramento BDD84", confirmado=True, user_id=1)


def capturar(contexto, funcao, *args, **kwargs):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        contexto["retorno"] = funcao(*args, **kwargs)
        contexto["erro"] = None
    except RegraNegocioError as exc:
        db().session.rollback()
        contexto["erro"] = exc
