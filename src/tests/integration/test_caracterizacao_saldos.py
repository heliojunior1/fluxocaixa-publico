"""Caracterização da leitura de saldos pelos relatórios (spec saldo-por-fundo R18).

Rede anti-regressão do corte do legado (F2.4): pinela o que os métodos de
leitura do repositório e o relatório de saldos diários retornam para uma
massa determinística e controlada. DEVE passar tanto no código legado
(flc_saldo_conta) quanto após a migração 0006 + strangler (leitura via
vw_flc_saldo_conta_agregado) — mesmos números, mesma interface.

A massa é criada pela API pública apropriada a cada época:
- enquanto o modelo legado existe (antes da 0006): via SaldoContaRepository;
- após a 0006: via gravar_saldo no fundo GERAL.
`_semear_saldo` esconde essa diferença atrás de uma única chamada.
"""
from datetime import date
from decimal import Decimal

import pytest

# Massa controlada: 2 contas, saldos em datas fixas de 2025 (dentro do range
# histórico do seed, independente de "hoje").
CONTA_A = ("111", "0001", "AAA-1")
CONTA_B = ("222", "0002", "BBB-2")
DIA_1 = date(2025, 3, 10)
DIA_2 = date(2025, 3, 11)


def _conta(ident):
    from fluxocaixa.models import ContaBancaria

    banco, ag, num = ident
    c = ContaBancaria.query.filter_by(cod_banco=banco, num_agencia=ag, num_conta=num).first()
    if c is None:
        from fluxocaixa.models.base import db

        c = ContaBancaria(cod_banco=banco, num_agencia=ag, num_conta=num,
                          dsc_conta=f"Caracterização {banco}")
        db.session.add(c)
        db.session.commit()
    return c


def _fundo_geral():
    """Fundo GERAL (existe após a 0006; criado aqui se ainda não houver)."""
    from fluxocaixa.models import Fundo
    from fluxocaixa.services.fundo_service import criar_fundo

    f = Fundo.query.filter_by(cod_fundo='GERAL').first()
    return f or criar_fundo('GERAL', 'Saldo geral da conta')


def _semear_saldo(conta, dat, valor):
    """Grava um saldo pela via apropriada à época (legado ou novo)."""
    from fluxocaixa.models.base import db

    try:
        from fluxocaixa.models import SaldoConta  # existe só antes da 0006
    except ImportError:
        SaldoConta = None

    if SaldoConta is not None and _tabela_existe('flc_saldo_conta'):
        db.session.add(SaldoConta(seq_conta=conta.seq_conta, dat_saldo=dat,
                                  val_saldo=Decimal(valor), cod_pessoa_inclusao=1))
        db.session.commit()
    else:
        from fluxocaixa.services.saldo_fundo_service import gravar_saldo

        gravar_saldo(seq_conta=conta.seq_conta, seq_fundo=_fundo_geral().seq_fundo,
                     dat_saldo=dat, val_saldo=Decimal(valor))


def _tabela_existe(nome):
    from sqlalchemy import inspect

    from fluxocaixa.models.base import engine

    return nome in inspect(engine).get_table_names()


def _limpar_massa():
    """Remove saldos das contas de caracterização (idempotência entre testes)."""
    from fluxocaixa.models import ContaBancaria
    from fluxocaixa.models.base import db

    seqs = [
        c.seq_conta
        for ident in (CONTA_A, CONTA_B)
        if (c := ContaBancaria.query.filter_by(
            cod_banco=ident[0], num_agencia=ident[1], num_conta=ident[2]).first())
    ]
    if not seqs:
        return
    if _tabela_existe('flc_saldo_conta'):
        db.session.execute(
            __import__('sqlalchemy').text("DELETE FROM flc_saldo_conta WHERE seq_conta IN :s")
            .bindparams(__import__('sqlalchemy').bindparam("s", expanding=True)), {"s": seqs})
    from fluxocaixa.models import SaldoContaFundo

    SaldoContaFundo.query.filter(SaldoContaFundo.seq_conta.in_(seqs)).delete(synchronize_session=False)
    db.session.commit()


@pytest.fixture()
def massa(app):
    """Massa controlada + baselines dos totais globais (a demo também semeia
    nessas datas, então os totais são verificados por DELTA — isola da demo e
    é preservado pela migração)."""
    from fluxocaixa.models.base import db
    from fluxocaixa.repositories.saldo_conta_repository import SaldoContaRepository

    db.session.rollback()
    _limpar_massa()
    repo = SaldoContaRepository()
    base_total_dia1 = Decimal(str(repo.get_saldo_total_by_date(DIA_1)))
    base_total_antes = Decimal(str(repo.get_latest_saldo_total_before_date(date(2025, 3, 12))))

    ca, cb = _conta(CONTA_A), _conta(CONTA_B)
    _semear_saldo(ca, DIA_1, "1000.00")
    _semear_saldo(cb, DIA_1, "2000.00")
    _semear_saldo(ca, DIA_2, "1500.00")
    return {"ca": ca, "cb": cb,
            "base_total_dia1": base_total_dia1, "base_total_antes": base_total_antes}


def test_leitura_por_conta_e_data(massa):
    from fluxocaixa.repositories.saldo_conta_repository import SaldoContaRepository

    repo = SaldoContaRepository()
    s = repo.get_saldo_by_conta_and_date(massa["ca"].seq_conta, DIA_1)
    assert s is not None and Decimal(str(s.val_saldo)) == Decimal("1000.00")


def test_leitura_total_por_data(massa):
    from fluxocaixa.repositories.saldo_conta_repository import SaldoContaRepository

    repo = SaldoContaRepository()
    total = Decimal(str(repo.get_saldo_total_by_date(DIA_1)))
    assert total - massa["base_total_dia1"] == Decimal("3000.00")  # 1000 + 2000


def test_ultimo_saldo_antes_da_data(massa):
    from fluxocaixa.repositories.saldo_conta_repository import SaldoContaRepository

    repo = SaldoContaRepository()
    s = repo.get_latest_saldo_before_date(massa["ca"].seq_conta, date(2025, 3, 12))
    assert s is not None and Decimal(str(s.val_saldo)) == Decimal("1500.00")  # DIA_2


def test_total_ultimo_saldo_antes_da_data(massa):
    from fluxocaixa.repositories.saldo_conta_repository import SaldoContaRepository

    repo = SaldoContaRepository()
    total = Decimal(str(repo.get_latest_saldo_total_before_date(date(2025, 3, 12))))
    assert total - massa["base_total_antes"] == Decimal("3500.00")  # ca=1500 + cb=2000


def test_relatorio_saldos_diarios_usa_saldo_inicial(massa):
    """Contrato da F5.3 (spec relatorios R14): o saldo inicial passou a ser o
    DERIVADO (último dia anterior com saldo) e o registro do próprio dia virou
    a coluna `saldo_registrado`. A rede original desta caracterização (mesmos
    números através da migração 0006/strangler) foi cumprida e arquivada."""
    from fluxocaixa.services.relatorio.saldos_service import get_saldos_diarios_data

    dados = get_saldos_diarios_data(DIA_2)
    alvo = next((r for r in dados["rows"] if r["conta"].seq_conta == massa["ca"].seq_conta), None)
    assert alvo is not None, "conta A de caracterização não apareceu no relatório"
    # inicial derivado do DIA_1; registro do DIA_2 exposto em separado
    assert Decimal(str(alvo["saldo_inicial"])) == Decimal("1000.00")
    assert Decimal(str(alvo["saldo_registrado"])) == Decimal("1500.00")
    assert alvo["saldo_exato"] is True  # derivado exatamente da véspera
