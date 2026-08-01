"""Endpoint de ingestão de saldos em lote (spec saldo-por-fundo R16).

Contrato estável para ETLs externos (Airflow etc.): o cliente autentica via
POST /login (cookie de sessão, perfil EXTRACAO) e envia lotes aqui.
"""
from fastapi.responses import JSONResponse

from . import handle_exceptions, router
from ..auth.permissoes import requer
from ..domain.importacao_lote import LoteImportacaoIn, ResultadoImportacaoOut
from ..services.importacao_lote_service import LinhaLote, importar_lote


@router.post('/api/saldo/importacao-lote', dependencies=[requer('FC_IMP_SALDO_FUNDO')])
@handle_exceptions
async def importacao_lote(lote: LoteImportacaoIn):
    linhas = [
        LinhaLote(
            cod_banco=l.cod_banco,
            num_agencia=l.num_agencia,
            num_conta=l.num_conta,
            cod_fundo=l.cod_fundo,
            dsc_fundo=l.dsc_fundo,
            val_saldo=l.val_saldo,
            val_aplicacoes=l.val_aplicacoes,
            val_resgates=l.val_resgates,
            dat_saldo=l.dat_saldo,
        )
        for l in lote.linhas
    ]
    resultado = importar_lote(
        linhas,
        dat_saldo_lote=lote.dat_saldo,
        sigla_sistema=lote.origem,
        arquivo_origem=lote.arquivo_origem,
    )
    saida = ResultadoImportacaoOut(
        linhas_inseridas=resultado.linhas_inseridas,
        linhas_com_erro=resultado.linhas_com_erro,
        fundos_auto_cadastrados=resultado.fundos_auto_cadastrados,
        detalhe_erros=resultado.detalhe_erros,
        arquivo_origem=resultado.arquivo_origem,
        falha_sistemica=resultado.falha_sistemica,
    )
    return JSONResponse(saida.model_dump(by_alias=True))
