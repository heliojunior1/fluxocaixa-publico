from datetime import date

from sqlalchemy import Column, Date, DateTime, Integer, String

from .base import Base


class Usuario(Base):
    """Usuário do sistema (autenticação local por login/senha).

    Perfis e permissões entram na F1.3; aqui só identidade e credencial.
    """

    __tablename__ = 'flc_usuario'

    seq_usuario = Column(Integer, primary_key=True)
    nom_usuario = Column(String(50), nullable=False, unique=True)
    nom_completo = Column(String(120))
    # Hash bcrypt (60 chars) — nunca armazenar senha em claro
    txt_hash_senha = Column(String(60), nullable=False)
    # 'S' = deve trocar a senha no próximo login
    ind_troca_senha = Column(String(1), default='N', nullable=False)
    ind_status = Column(String(1), default='A', nullable=False)
    # Revogação de sessão (R13): a sessão carrega a versão vista no login e
    # é recusada quando diverge — trocar a senha invalida as demais sessões,
    # inclusive uma roubada. server_default espelha a migração (anti-deriva).
    num_versao_credencial = Column(
        Integer, default=1, server_default='1', nullable=False)
    # Anti-força-bruta (R14). `dat_bloqueio_login` é DateTime e não Date: o
    # bloqueio é de minutos, e a granularidade de dia o tornaria inútil.
    qtd_falhas_login = Column(Integer, default=0, server_default='0', nullable=False)
    dat_bloqueio_login = Column(DateTime)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)
