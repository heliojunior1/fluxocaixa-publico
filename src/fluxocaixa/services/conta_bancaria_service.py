"""Ciclo de vida da conta bancária (spec cadastros-nucleo R19–R23).

Cadastro manual, alteração com a tripla banco/agência/conta protegida por
vínculos, inativação lógica bloqueada por saldo ativo, reativação e listagem
filtrada. A unicidade da tripla é validada aqui com mensagem pt-BR; a
constraint do banco (migração 0004) permanece como rede de segurança contra
gravações concorrentes.
"""
from datetime import date

from ..auth.contexto import cod_pessoa_atual
from ..models import ContaBancaria, Lancamento, SaldoContaFundo
from ..models.base import db
from .validacao import RegraNegocioError

BANCO_MAX, AGENCIA_MAX, CONTA_MAX, DSC_MAX = 10, 20, 30, 100


def _validar_identificadores(cod_banco: str, num_agencia: str, num_conta: str):
    cod_banco = (cod_banco or "").strip()
    num_agencia = (num_agencia or "").strip()
    num_conta = (num_conta or "").strip()
    if not cod_banco:
        raise RegraNegocioError("O campo código do banco é obrigatório.")
    if not num_agencia:
        raise RegraNegocioError("O campo agência é obrigatório.")
    if not num_conta:
        raise RegraNegocioError("O campo número da conta é obrigatório.")
    if len(cod_banco) > BANCO_MAX:
        raise RegraNegocioError(f"Código do banco deve ter até {BANCO_MAX} caracteres.")
    if len(num_agencia) > AGENCIA_MAX:
        raise RegraNegocioError(f"Agência deve ter até {AGENCIA_MAX} caracteres.")
    if len(num_conta) > CONTA_MAX:
        raise RegraNegocioError(f"Número da conta deve ter até {CONTA_MAX} caracteres.")
    return cod_banco, num_agencia, num_conta


def _validar_descricao(dsc_conta: str | None) -> str | None:
    dsc_conta = (dsc_conta or "").strip() or None
    if dsc_conta and len(dsc_conta) > DSC_MAX:
        raise RegraNegocioError(f"Descrição da conta deve ter até {DSC_MAX} caracteres.")
    return dsc_conta


def _validar_unicidade(cod_banco, num_agencia, num_conta, ignorar_seq=None):
    q = ContaBancaria.query.filter_by(
        cod_banco=cod_banco, num_agencia=num_agencia, num_conta=num_conta
    )
    if ignorar_seq is not None:
        q = q.filter(ContaBancaria.seq_conta != ignorar_seq)
    if q.first() is not None:
        raise RegraNegocioError(
            "Já existe uma conta bancária com este banco, agência e conta."
        )


def _get_ou_erro(seq_conta: int) -> ContaBancaria:
    conta = ContaBancaria.query.get(seq_conta)
    if conta is None:
        raise RegraNegocioError("Conta bancária inexistente.")
    return conta


def _tem_vinculos(seq_conta: int) -> bool:
    """A conta tem saldos por fundo ou lançamentos (ativos ou não)? Origem
    única da pergunta — protege a tripla identificadora (R21)."""
    if SaldoContaFundo.query.filter_by(seq_conta=seq_conta).first() is not None:
        return True
    return Lancamento.query.filter_by(seq_conta=seq_conta).first() is not None


def conta_tem_vinculos(seq_conta: int) -> bool:
    """Versão pública do `_tem_vinculos` — a tela usa para desabilitar a
    tripla no modal de edição (conveniência; a proteção real é o serviço)."""
    return _tem_vinculos(seq_conta)


def _tem_saldo_ativo(seq_conta: int) -> bool:
    return SaldoContaFundo.query.filter_by(
        seq_conta=seq_conta, ind_status='A'
    ).first() is not None


def criar_conta(cod_banco: str, num_agencia: str, num_conta: str,
                dsc_conta: str | None = None) -> ContaBancaria:
    """Cadastro manual: nasce ativa, com auditoria de inclusão (R20)."""
    cod_banco, num_agencia, num_conta = _validar_identificadores(
        cod_banco, num_agencia, num_conta)
    _validar_unicidade(cod_banco, num_agencia, num_conta)
    conta = ContaBancaria(
        cod_banco=cod_banco,
        num_agencia=num_agencia,
        num_conta=num_conta,
        dsc_conta=_validar_descricao(dsc_conta),
        ind_status='A',
        cod_pessoa_inclusao=cod_pessoa_atual(),
    )
    db.session.add(conta)
    db.session.commit()
    return conta


def alterar_conta(seq_conta: int, cod_banco: str, num_agencia: str,
                  num_conta: str, dsc_conta: str | None) -> ContaBancaria:
    """Descrição sempre editável; tripla só sem vínculos (R21)."""
    conta = _get_ou_erro(seq_conta)
    cod_banco, num_agencia, num_conta = _validar_identificadores(
        cod_banco, num_agencia, num_conta)
    tripla_mudou = (cod_banco, num_agencia, num_conta) != (
        conta.cod_banco, conta.num_agencia, conta.num_conta)
    if tripla_mudou:
        if _tem_vinculos(seq_conta):
            raise RegraNegocioError(
                "A conta possui saldos ou lançamentos vinculados; "
                "banco, agência e conta não podem ser alterados."
            )
        _validar_unicidade(cod_banco, num_agencia, num_conta, ignorar_seq=seq_conta)
        conta.cod_banco = cod_banco
        conta.num_agencia = num_agencia
        conta.num_conta = num_conta
    conta.dsc_conta = _validar_descricao(dsc_conta)
    conta.dat_alteracao = date.today()
    conta.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return conta


def inativar_conta(seq_conta: int) -> ContaBancaria:
    """Inativação lógica bloqueada por saldo ativo; lançamentos históricos
    não bloqueiam (R22)."""
    conta = _get_ou_erro(seq_conta)
    if _tem_saldo_ativo(seq_conta):
        raise RegraNegocioError("Conta possui saldos ativos e não pode ser inativada.")
    conta.ind_status = 'I'
    conta.dat_alteracao = date.today()
    conta.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return conta


def reativar_conta(seq_conta: int) -> ContaBancaria:
    """Reativação de conta inativa (R22)."""
    conta = _get_ou_erro(seq_conta)
    if conta.ind_status == 'A':
        raise RegraNegocioError("Conta já está ativa.")
    conta.ind_status = 'A'
    conta.dat_alteracao = date.today()
    conta.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()
    return conta


def listar_contas(cod_banco=None, num_agencia=None, num_conta=None,
                  dsc=None, status='ativo') -> list[ContaBancaria]:
    """Lista filtrada (AND), ordenada por banco/agência/conta (R19).

    Status default 'ativo' — a listagem da tela mostra só ativas a menos que
    o filtro peça 'todas'."""
    q = ContaBancaria.query
    if cod_banco:
        q = q.filter(ContaBancaria.cod_banco == cod_banco.strip())
    if num_agencia:
        q = q.filter(ContaBancaria.num_agencia == num_agencia.strip())
    if num_conta:
        q = q.filter(ContaBancaria.num_conta == num_conta.strip())
    if dsc:
        q = q.filter(ContaBancaria.dsc_conta.ilike(f"%{dsc.strip()}%"))
    if status in ('ativo', 'inativo'):
        q = q.filter(ContaBancaria.ind_status == ('A' if status == 'ativo' else 'I'))
    return q.order_by(
        ContaBancaria.cod_banco, ContaBancaria.num_agencia, ContaBancaria.num_conta
    ).all()
