"""Perfis e permissões (controle de acesso verbo+recurso).

Gestão de usuários/perfis é feita via banco (cada SEFAZ integra seu próprio
sistema de identidade — ver README, seção "Gestão de usuários e permissões").
"""
from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Integer, String, UniqueConstraint

from .base import Base


class Permissao(Base):
    """Catálogo de eventos FC_<VERBO>_<RECURSO>.

    O código é atômico de propósito: mantém paridade com sistemas de
    identidade corporativos, que costumam modelar permissão como evento
    único em vez de par verbo/recurso separado.
    """

    __tablename__ = 'flc_permissao'

    seq_permissao = Column(Integer, primary_key=True)
    cod_permissao = Column(String(60), nullable=False, unique=True)
    dsc_permissao = Column(String(255))
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)


class Perfil(Base):
    __tablename__ = 'flc_perfil'

    seq_perfil = Column(Integer, primary_key=True)
    cod_perfil = Column(String(30), nullable=False, unique=True)
    dsc_perfil = Column(String(255))
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)


class PerfilPermissao(Base):
    __tablename__ = 'flc_perfil_permissao'
    __table_args__ = (
        UniqueConstraint('seq_perfil', 'seq_permissao', name='uq_perfil_permissao'),
    )

    seq_perfil_permissao = Column(Integer, primary_key=True)
    seq_perfil = Column(Integer, ForeignKey('flc_perfil.seq_perfil'), nullable=False)
    seq_permissao = Column(Integer, ForeignKey('flc_permissao.seq_permissao'), nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)


class UsuarioPerfil(Base):
    __tablename__ = 'flc_usuario_perfil'
    __table_args__ = (
        UniqueConstraint('seq_usuario', 'seq_perfil', name='uq_usuario_perfil'),
    )

    seq_usuario_perfil = Column(Integer, primary_key=True)
    seq_usuario = Column(Integer, ForeignKey('flc_usuario.seq_usuario'), nullable=False)
    seq_perfil = Column(Integer, ForeignKey('flc_perfil.seq_perfil'), nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
