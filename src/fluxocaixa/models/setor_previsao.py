from datetime import date

from sqlalchemy import Column, Date, Integer, String

from .base import Base


class SetorPrevisao(Base):
    """Setor responsável por um recorte da previsão (previsao R23–R24).

    Domínio cadastrável. O recorte é marcado NO QUALIFICADOR
    (`flc_qualificador.seq_setor_previsao`) com herança pela árvore, como a
    categoria fiscal — o setor resolvido é derivado na leitura
    (`setor_previsao_service.setor_resolvido`) e nunca persistido.

    Opcional por construção: sem setores cadastrados o sistema se comporta
    exatamente como antes — um cenário projeta a árvore inteira.
    """

    __tablename__ = 'flc_setor_previsao'

    seq_setor_previsao = Column(Integer, primary_key=True)
    nom_setor = Column(String(100), nullable=False)
    sgl_setor = Column(String(20), nullable=False)
    dsc_setor = Column(String(255))
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer, nullable=True)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)
