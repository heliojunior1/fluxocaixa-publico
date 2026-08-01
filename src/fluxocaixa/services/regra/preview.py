"""Preview da regra sobre a staging (spec automacao-lancamentos R8).

Traduz a regra e EXECUTA o predicado contra `flc_etl_staging`, devolvendo
contagem + amostra. Não grava e não altera o status de nenhuma linha.

O recorte é o MESMO do mapeamento — (sistema de origem, ano) —, não uma fonte:
um sistema de origem pode ter várias fontes, e prever por fonte seria um
recorte sem significado de negócio.

Duplo papel: prova o renderer de ponta a ponta (o BDD roda contra SQLite real,
não por inspeção da expressão compilada) e é o seam que a tela chama.
"""
from decimal import Decimal

from ...models.etl_staging import EtlStaging
from ...models.extracao import FonteExtracao

LIMITE_PADRAO = 20


def preview_regra(txt_regra: str, seq_sistema_origem: int,
                  num_ano_exercicio: int | None = None,
                  limite: int = LIMITE_PADRAO) -> dict:
    """`{total, amostra}` das linhas do sistema de origem que casam com a regra.

    Termo de ATRIBUTO ausente no `json_atributos` da linha vira NULL na
    comparação → a linha não casa (sem erro). É o comportamento correto: fontes
    diferentes do mesmo sistema têm chaves diferentes.
    """
    from . import traduzir_regra  # evita ciclo na importação do pacote

    predicado = traduzir_regra(txt_regra)
    consulta = (EtlStaging.query
                .join(FonteExtracao,
                      FonteExtracao.seq_fonte_extracao == EtlStaging.seq_fonte_extracao)
                .filter(FonteExtracao.seq_sistema_origem == seq_sistema_origem)
                .filter(predicado))
    if num_ano_exercicio is not None:
        consulta = consulta.filter(EtlStaging.num_ano_exercicio == num_ano_exercicio)

    total = consulta.count()
    linhas = consulta.order_by(EtlStaging.seq_etl_staging).limit(limite).all()

    return {
        "total": total,
        "amostra": [
            {
                "seq_etl_staging": ln.seq_etl_staging,
                "dat_referencia": ln.dat_referencia,
                # monetário sempre Decimal com 2 casas
                "val_referencia": (Decimal(ln.val_referencia).quantize(Decimal("0.01"))
                                   if ln.val_referencia is not None else None),
                "num_ano_exercicio": ln.num_ano_exercicio,
                "json_atributos": ln.json_atributos,
            }
            for ln in linhas
        ],
    }
