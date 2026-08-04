from datetime import date

from sqlalchemy import extract, func, or_
from sqlalchemy.orm import Session, joinedload

from ..domain import PagamentoCreate
from ..models import Orgao, Pagamento, Qualificador
from ..models.base import db


def _nos_anos(anos: list[int]):
    """`year.in_(anos)` sargável (infraestrutura-banco R12): OR de faixas."""
    return or_(*[
        Pagamento.dat_pagamento.between(date(ano, 1, 1), date(ano, 12, 31))
        for ano in anos
    ])


class PagamentoRepository:
    """Data access layer for Pagamento records."""

    def __init__(self, session: Session | None = None):
        self.session = session or db.session

    def list_pagamentos(self):
        return (
            self.session.query(Pagamento)
            .options(joinedload(Pagamento.qualificador),
                     joinedload(Pagamento.fonte_recurso))
            .filter_by(ind_status='A')
            .order_by(Pagamento.dat_pagamento.desc())
            .all()
        )

    def list_orgaos(self):
        return self.session.query(Orgao).order_by(Orgao.nom_orgao).all()
    
    def list_qualificadores(self):
        """List all active qualificadores for payment selection."""
        return self.session.query(Qualificador).filter_by(ind_status='A').order_by(Qualificador.num_qualificador).all()

    def get_available_years(self) -> list[int]:
        """Get list of years with pagamento data.
        
        Returns:
            List of years sorted descending
        """
        years = self.session.query(
            extract("year", Pagamento.dat_pagamento)
        ).distinct().all()
        
        return sorted([int(y[0]) for y in years if y[0]], reverse=True)

    def get_comparative_by_orgao(
        self,
        anos: list[int],
        meses: list[int]
    ) -> list:
        """Get comparative data by orgao.
        
        Args:
            anos: List of years to compare
            meses: List of months to include
        
        Returns:
            List of tuples (orgao, year, month, total)
        """
        results = self.session.query(
            Orgao.nom_orgao,
            extract("year", Pagamento.dat_pagamento).label("year"),
            extract("month", Pagamento.dat_pagamento).label("month"),
            func.sum(Pagamento.val_pagamento).label("total"),
        ).join(Orgao).filter(
            _nos_anos(anos),
            extract("month", Pagamento.dat_pagamento).in_(meses),
        ).group_by("nom_orgao", "year", "month").all()
        
        return results

    def get_comparative_by_qualificador(
        self,
        anos: list[int],
        meses: list[int]
    ) -> list:
        """Get comparative data by qualificador.
        
        Args:
            anos: List of years to compare
            meses: List of months to include
        
        Returns:
            List of tuples (qualificador_name, year, month, total)
        """
        results = self.session.query(
            Qualificador.dsc_qualificador,
            extract("year", Pagamento.dat_pagamento).label("year"),
            extract("month", Pagamento.dat_pagamento).label("month"),
            func.sum(Pagamento.val_pagamento).label("total"),
        ).join(Qualificador).filter(
            _nos_anos(anos),
            extract("month", Pagamento.dat_pagamento).in_(meses),
            Pagamento.ind_status == 'A',  # soft-delete fora do comparativo (R14)
        ).group_by(Qualificador.dsc_qualificador, "year", "month").all()
        
        return results

    def create(self, data: PagamentoCreate, cod_pessoa: int) -> Pagamento:
        pag = Pagamento(
            dat_pagamento=data.dat_pagamento,
            cod_orgao=data.cod_orgao,
            seq_qualificador=data.seq_qualificador,
            val_pagamento=data.val_pagamento,
            dsc_pagamento=data.dsc_pagamento,
            cod_pessoa_inclusao=cod_pessoa,
        )
        self.session.add(pag)
        self.session.commit()
        return pag

