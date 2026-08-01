"""Importação de saldos em lote (spec saldo-por-fundo R14/R15).

Orquestra `gravar_saldo` (F2.1) e `upsert_fundo_pendente` (F2.2), linha a
linha com sucesso parcial. Consumidores: extração embutida (F3.x), endpoint
HTTP de ingestão (R16) e importação CSV manual (F2.5).

Recuperação de falha no meio do lote: reimportar — a gravação é idempotente
por chave (versionamento por inativação), o mesmo modelo das DAGs do Java.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from ..models import ContaBancaria, Fundo
from .fundo_service import upsert_fundo_pendente
from .origem_saldo import resolver_sistema, resolver_tipo
from .saldo_fundo_service import gravar_saldo
from .validacao import RegraNegocioError


@dataclass
class LinhaLote:
    cod_banco: str
    num_agencia: str
    num_conta: str
    cod_fundo: str
    dsc_fundo: str
    val_saldo: Decimal
    val_aplicacoes: Decimal = Decimal("0")
    val_resgates: Decimal = Decimal("0")
    dat_saldo: date | None = None  # default: data do lote


@dataclass
class ResultadoImportacaoLote:
    arquivo_origem: str | None = None
    linhas_inseridas: int = 0
    linhas_com_erro: int = 0
    fundos_auto_cadastrados: list = field(default_factory=list)
    detalhe_erros: list = field(default_factory=list)

    @property
    def falha_sistemica(self) -> bool:
        """Nenhuma linha entrou e há erros — problema de configuração/fonte."""
        return self.linhas_inseridas == 0 and self.linhas_com_erro > 0


def _resolver_conta(cache: dict, linha: LinhaLote) -> ContaBancaria:
    chave = (
        (linha.cod_banco or "").strip(),
        (linha.num_agencia or "").strip(),
        (linha.num_conta or "").strip(),
    )
    if chave not in cache:
        cache[chave] = ContaBancaria.query.filter_by(
            cod_banco=chave[0], num_agencia=chave[1], num_conta=chave[2]
        ).first()
    conta = cache[chave]
    if conta is None:
        raise RegraNegocioError(
            f"Conta bancária {chave[0]}/{chave[1]}/{chave[2]} não cadastrada"
        )
    return conta


def importar_lote(
    linhas: list[LinhaLote],
    dat_saldo_lote: date,
    sigla_sistema: str | None = None,
    arquivo_origem: str | None = None,
) -> ResultadoImportacaoLote:
    """Processa o lote linha a linha, com sucesso parcial (R14)."""
    # Origem inválida é erro de CHAMADA — validada antes de qualquer linha
    sigla_tipo = 'AUTOMATIZADO' if sigla_sistema else 'IMPORTADO'
    resolver_tipo(sigla_tipo)
    resolver_sistema(sigla_tipo, sigla_sistema)

    resultado = ResultadoImportacaoLote(arquivo_origem=arquivo_origem)
    cache_contas: dict = {}

    for numero, linha in enumerate(linhas, start=1):
        try:
            conta = _resolver_conta(cache_contas, linha)

            cod_fundo = (linha.cod_fundo or "").strip()
            fundo = Fundo.query.filter_by(cod_fundo=cod_fundo).first()
            if fundo is None:
                fundo = upsert_fundo_pendente(cod_fundo, linha.dsc_fundo, sigla_sistema)
                resultado.fundos_auto_cadastrados.append(fundo.cod_fundo)

            gravar_saldo(
                seq_conta=conta.seq_conta,
                seq_fundo=fundo.seq_fundo,
                dat_saldo=linha.dat_saldo or dat_saldo_lote,
                val_saldo=Decimal(linha.val_saldo),
                val_aplicacoes=Decimal(linha.val_aplicacoes),
                val_resgates=Decimal(linha.val_resgates),
                sigla_tipo_origem=sigla_tipo,
                sigla_sistema_origem=sigla_sistema,
            )
            resultado.linhas_inseridas += 1
        except (RegraNegocioError, InvalidOperation) as exc:
            mensagem = getattr(exc, "mensagem", None) or "Valor monetário inválido"
            resultado.linhas_com_erro += 1
            resultado.detalhe_erros.append({"linha": numero, "mensagem": mensagem})

    return resultado
