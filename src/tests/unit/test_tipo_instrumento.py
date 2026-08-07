"""Tipo de instrumento financeiro e liquidez (change
tipo-instrumento-financeiro, spec saldo-por-fundo R22).

Imports de app sempre TARDIOS (isolamento de banco da suíte). A cobertura de
comportamento fim-a-fim (grupo líquido × carência, simulação, conciliação)
vive no BDD `saldo-por-fundo/tipo_instrumento.feature`; aqui ficam as
validações de serviço e o contrato novo do repositório.
"""
from datetime import date
from decimal import Decimal

import pytest


def _definir_usuario():
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(12345)


def test_criar_fundo_sem_tipo_usa_default_fundo_liquido(app):
    from fluxocaixa.models import TipoInstrumento
    from fluxocaixa.services.fundo_service import criar_fundo

    _definir_usuario()
    fundo = criar_fundo("8801", "Fundo Default Unit")
    tipo = TipoInstrumento.query.get(fundo.seq_tipo_instrumento)
    assert tipo.txt_sigla == "FUNDO"
    assert fundo.ind_liquidez_imediata == "S"
    assert fundo.dat_vencimento is None


def test_criar_cdb_com_carencia_e_vencimento(app):
    from fluxocaixa.models import TipoInstrumento
    from fluxocaixa.services.fundo_service import (
        criar_fundo,
        resolver_tipo_instrumento,
    )

    _definir_usuario()
    cdb = resolver_tipo_instrumento("CDB")
    fundo = criar_fundo("8802", "CDB Unit", seq_tipo_instrumento=cdb.seq_tipo_instrumento,
                        ind_liquidez_imediata="N",
                        dat_vencimento=date(2077, 12, 31))
    assert TipoInstrumento.query.get(fundo.seq_tipo_instrumento).txt_sigla == "CDB"
    assert fundo.ind_liquidez_imediata == "N"
    assert fundo.dat_vencimento == date(2077, 12, 31)


def test_tipo_inexistente_e_liquidez_invalida_sao_rejeitados(app):
    from fluxocaixa.services.fundo_service import criar_fundo
    from fluxocaixa.services.validacao import RegraNegocioError

    _definir_usuario()
    with pytest.raises(RegraNegocioError, match="Tipo de instrumento inexistente"):
        criar_fundo("8803", "Tipo Ruim Unit", seq_tipo_instrumento=99999999)
    with pytest.raises(RegraNegocioError, match="Liquidez imediata"):
        criar_fundo("8803", "Liquidez Ruim Unit", ind_liquidez_imediata="X")


def test_alterar_fundo_muda_classificacao_e_preserva_codigo(app):
    from fluxocaixa.services.fundo_service import (
        alterar_fundo,
        criar_fundo,
        resolver_tipo_instrumento,
    )

    _definir_usuario()
    fundo = criar_fundo("8804", "Vira CDB Unit")
    cdb = resolver_tipo_instrumento("CDB")
    alterado = alterar_fundo(
        fundo.seq_fundo, fundo.dsc_fundo,
        seq_tipo_instrumento=cdb.seq_tipo_instrumento,
        ind_liquidez_imediata="N", dat_vencimento=date(2078, 6, 30))
    assert alterado.seq_tipo_instrumento == cdb.seq_tipo_instrumento
    assert alterado.ind_liquidez_imediata == "N"
    assert alterado.dat_vencimento == date(2078, 6, 30)
    # Sentinela: chamada sem dat_vencimento PRESERVA; None explícito limpa
    preservado = alterar_fundo(alterado.seq_fundo, alterado.dsc_fundo)
    assert preservado.dat_vencimento == date(2078, 6, 30)
    limpo = alterar_fundo(alterado.seq_fundo, alterado.dsc_fundo,
                          dat_vencimento=None)
    assert limpo.dat_vencimento is None


def test_geral_e_conta_movimento_e_upsert_nasce_fundo(app):
    from fluxocaixa.models import TipoInstrumento
    from fluxocaixa.services.fundo_service import (
        garantir_fundo_geral,
        upsert_fundo_pendente,
    )

    _definir_usuario()
    geral = garantir_fundo_geral()
    assert TipoInstrumento.query.get(
        geral.seq_tipo_instrumento).txt_sigla == "CONTA_MOVIMENTO"

    pendente = upsert_fundo_pendente("8805", "Pendente Unit")
    assert TipoInstrumento.query.get(
        pendente.seq_tipo_instrumento).txt_sigla == "FUNDO"
    assert pendente.ind_liquidez_imediata == "S"


def test_saldo_bruto_por_grupo_separa_liquido_de_carencia(app):
    """Contrato novo do repositório (D5): {liquido, carencia, total} por
    grupo — recorte por DATA-ilha para não depender de massa alheia."""
    from fluxocaixa.models import ContaBancaria
    from fluxocaixa.models.base import db
    from fluxocaixa.repositories.saldo_fundo_repository import saldo_bruto_por_grupo
    from fluxocaixa.services.fundo_service import (
        criar_fundo,
        resolver_tipo_instrumento,
    )
    from fluxocaixa.services.saldo_fundo_service import gravar_saldo

    _definir_usuario()
    conta = ContaBancaria(cod_banco='001', num_agencia='0001',
                          num_conta='UNIT-TI-1', dsc_conta='Conta unit tipo')
    db.session.add(conta)
    db.session.commit()

    liquido = criar_fundo("8806", "Liquido Unit")
    cdb = criar_fundo(
        "8807", "Carencia Unit",
        seq_tipo_instrumento=resolver_tipo_instrumento("CDB").seq_tipo_instrumento,
        ind_liquidez_imediata="N")
    dia = date(2042, 2, 10)  # ilha 2042 (data não usada pelo BDD do change)
    gravar_saldo(seq_conta=conta.seq_conta, seq_fundo=liquido.seq_fundo,
                 dat_saldo=dia, val_saldo=Decimal("700.00"))
    gravar_saldo(seq_conta=conta.seq_conta, seq_fundo=cdb.seq_fundo,
                 dat_saldo=dia, val_saldo=Decimal("300.00"))

    grupos = saldo_bruto_por_grupo(dia)
    # Ambos sem fonte → grupo P (pendente)
    assert grupos["P"]["liquido"] == Decimal("700.00")
    assert grupos["P"]["carencia"] == Decimal("300.00")
    assert grupos["P"]["total"] == Decimal("1000.00")
    assert grupos["total"]["total"] == (
        grupos["L"]["total"] + grupos["V"]["total"] + grupos["P"]["total"])
