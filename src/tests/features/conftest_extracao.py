"""Conector FAKE programável + helpers compartilhados pelos steps de extração.

O FAKE é o conector de teste da infra (spec extracao-configuravel R2/R3):
os cenários programam as linhas devolvidas, a exceção a lançar e inspecionam
o último config recebido (prova da resolução de credenciais ${VAR}).
"""
from pydantic import BaseModel, ConfigDict, Field

CONFIG_FAKE_VALIDO = {"caminho": "/dados/entrada"}


class ConfigFake(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caminho: str
    token: str | None = Field(default=None, json_schema_extra={"secreto": True})


class ConectorFake:
    tipo = "FAKE"
    schema_config = ConfigFake

    def __init__(self):
        self.reset()

    def reset(self):
        self.linhas = []
        self.excecao = None
        self.ultimo_config = None

    def testar_conexao(self, config):
        from fluxocaixa.extracao.conector import ResultadoTeste

        self.ultimo_config = dict(config)
        return ResultadoTeste(ok=True, mensagem="Conexão fake OK")

    def extrair(self, config, layout, janela):
        self.ultimo_config = dict(config)
        if self.excecao is not None:
            raise self.excecao
        return list(self.linhas)


_FAKE = ConectorFake()


def garantir_conector_fake() -> ConectorFake:
    """Registra o FAKE no registry (se preciso) e zera o estado programável."""
    from fluxocaixa.extracao import registry

    if "FAKE" not in registry.tipos_disponiveis():
        registry.registrar(_FAKE)
    _FAKE.reset()
    return _FAKE


def criar_fonte_fake(nome, *, tipo="FAKE", cron=None, token=None,
                     destino="SALDO_FUNDO", sigla_sistema="SIS_X",
                     json_config=None):
    from fluxocaixa.services.extracao_service import criar_fonte

    if json_config is None:
        json_config = dict(CONFIG_FAKE_VALIDO)
        if token is not None:
            json_config["token"] = token
    return criar_fonte(
        nom_fonte=nome,
        cod_tipo_conector=tipo,
        sigla_sistema=sigla_sistema,
        txt_cron=cron,
        json_config=json_config,
        cod_destino=destino,
    )


def fonte_por_nome(nome):
    from fluxocaixa.models import FonteExtracao
    from fluxocaixa.models.base import db

    db.session.expire_all()
    return FonteExtracao.query.filter_by(nom_fonte=nome).first()


def garantir_fonte_ativa(nome, **kwargs):
    """Cria a fonte se não existir; reativa se um cenário anterior inativou."""
    from fluxocaixa.models.base import db

    fonte = fonte_por_nome(nome)
    if fonte is None:
        return criar_fonte_fake(nome, **kwargs)
    if fonte.ind_status != "A":
        fonte.ind_status = "A"
        db.session.commit()
    return fonte


def execucoes_da_fonte(nome):
    from fluxocaixa.models import ExecucaoExtracao
    from fluxocaixa.models.base import db

    fonte = fonte_por_nome(nome)
    if fonte is None:
        return []
    db.session.expire_all()
    return (
        ExecucaoExtracao.query
        .filter_by(seq_fonte_extracao=fonte.seq_fonte_extracao)
        .order_by(ExecucaoExtracao.seq_execucao_extracao)
        .all()
    )


def garantir_sistema_origem(sigla):
    from fluxocaixa.models import SistemaOrigem
    from fluxocaixa.models.base import db

    db.session.rollback()
    if not SistemaOrigem.query.filter_by(txt_sigla=sigla).first():
        db.session.add(SistemaOrigem(txt_sigla=sigla, dsc_sistema_origem=f"Sistema {sigla}"))
        db.session.commit()


def garantir_conta(ident):
    from fluxocaixa.models import ContaBancaria
    from fluxocaixa.models.base import db

    banco, agencia, num = ident.split("/")
    db.session.rollback()
    if not ContaBancaria.query.filter_by(
        cod_banco=banco, num_agencia=agencia, num_conta=num
    ).first():
        db.session.add(ContaBancaria(cod_banco=banco, num_agencia=agencia,
                                     num_conta=num, dsc_conta=f"Conta {ident}"))
        db.session.commit()


def garantir_fundo(cod):
    from fluxocaixa.models import Fundo
    from fluxocaixa.services.fundo_service import criar_fundo

    if Fundo.query.filter_by(cod_fundo=cod).first() is None:
        criar_fundo(cod, f"Fundo Extraível {cod}")


def linha_extraida(ident, cod_fundo, valor, dat_saldo=None):
    from decimal import Decimal

    from fluxocaixa.extracao.conector import LinhaExtraida

    banco, agencia, num = ident.split("/")
    return LinhaExtraida(
        cod_banco=banco, num_agencia=agencia, num_conta=num,
        cod_fundo=cod_fundo, dsc_fundo=f"Fundo {cod_fundo}",
        val_saldo=Decimal(valor), dat_saldo=dat_saldo,
    )
