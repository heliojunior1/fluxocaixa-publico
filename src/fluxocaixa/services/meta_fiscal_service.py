"""Metas fiscais que a entidade define por ano (spec relatorios R19).

Hoje: a meta de superávit primário, que era `loa_receita_total * 0.02` — com os
2% no código. É um número que o usuário CONHECE (vem da LDO da entidade); só
estava no lugar errado.

⚠️ A meta de **dívida consolidada** NÃO entra aqui. Ela era `45.0` fixo, exibido
como "45.0% — DENTRO DA META", e foi **removida do relatório**: não há fonte no
sistema para o estoque da dívida. Parametrizar um número que ninguém consegue
apurar apenas moveria a invenção para uma tela de configuração e lhe daria
aparência de dado apurado.
"""
from decimal import Decimal

from ..models import MetaFiscalAno, db


def obter_meta_superavit(ano: int) -> Decimal | None:
    """Meta informada para o ano, ou `None` se não houver.

    `None` é resposta legítima: sem meta informada, o relatório não inventa uma
    — apresenta o superávit apurado sem veredito de cumprimento.
    """
    meta = MetaFiscalAno.query.filter_by(num_ano=ano, ind_status='A').first()
    if meta is None or meta.val_superavit_primario is None:
        return None
    return Decimal(str(meta.val_superavit_primario))


def definir_meta_superavit(ano: int, valor: Decimal) -> MetaFiscalAno:
    """Grava (ou atualiza) a meta do ano."""
    meta = MetaFiscalAno.query.filter_by(num_ano=ano).first()
    if meta is None:
        meta = MetaFiscalAno(num_ano=ano, ind_status='A')
        db.session.add(meta)
    meta.val_superavit_primario = valor
    meta.ind_status = 'A'
    db.session.commit()
    return meta
