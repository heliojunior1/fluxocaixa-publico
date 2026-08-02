"""Fonte/destinação de recursos — catálogo padrão STN (spec fonte-recurso R1–R4).

O código é **decomposto** (identificador de exercício + fonte de 3 dígitos +
detalhamento local) e o catálogo é **versionado por exercício de vigência**: a
tabela oficial da STN muda a cada ano, e a mesma fonte pode existir com
descrição/status diferentes em exercícios diferentes. O código completo de
exibição (ex.: ``1.500``) é sempre derivado das partes — nunca persistido.

⚠️ **`ind_vinculada` é explícita, nunca derivada do código**: a regra geral
(5xx livres, resto vinculado) tem exceções e a tabela muda por exercício.
Fonte desconhecida que apareça em dado importado nasce **vinculada + pendente
de revisão** — errar para baixo na disponibilidade é prudência; errar para
cima é liberar dinheiro que não existe.

A unicidade composta (vigência, identificador, fonte, detalhamento) vale
**entre ativos** e é validada no serviço (uma constraint de banco não
permitiria a convivência com inativas — mesmo padrão da unicidade de
mapeamentos).
"""
from datetime import date

from sqlalchemy import Column, Date, Integer, String

from .base import Base

#: Vinculação da fonte (lente 1 da disponibilidade — doc do módulo, seção 4.4).
IND_LIVRE = 'L'      #: paga qualquer despesa
IND_VINCULADA = 'V'  #: só paga a sua finalidade legal

#: Origem da classificação no catálogo.
ORIGEM_STN = 'STN'      #: importada da tabela oficial do exercício
ORIGEM_LOCAL = 'LOCAL'  #: criada pelo ente (detalhamento/auto-cadastro)

#: Grupos da disponibilidade (saída da view vw_flc_saldo_fundo_fonte).
GRUPO_LIVRE = 'L'
GRUPO_VINCULADO = 'V'
GRUPO_PENDENTE = 'P'  #: fundo sem fonte — fora do livre (conservador)

#: Identificadores de exercício válidos (padrão STN).
IDENTIFICADORES_EXERCICIO = ('1', '2', '9')


class FonteRecurso(Base):
    """Catálogo de fontes/destinações de recursos (decomposto e versionado)."""

    __tablename__ = 'flc_fonte_recurso'

    seq_fonte_recurso = Column(Integer, primary_key=True)
    #: '1' exercício corrente | '2' exercícios anteriores | '9' condicionados
    cod_identificador_exercicio = Column(String(1), nullable=False, default='1')
    #: os 3 dígitos padronizados da STN (ex.: '500')
    cod_fonte_stn = Column(String(3), nullable=False)
    #: desdobramento local do ente (opcional)
    cod_detalhamento = Column(String(10))
    #: exercício de vigência do catálogo (a tabela STN é anual)
    num_exercicio_vigencia = Column(Integer, nullable=False)
    dsc_fonte_recurso = Column(String(200), nullable=False)
    ind_vinculada = Column(String(1), nullable=False, default=IND_VINCULADA)
    cod_origem_classificacao = Column(String(5), nullable=False, default=ORIGEM_LOCAL)
    #: agrupador livre para relatório ("Saúde", "Educação", "Convênios"...)
    dsc_grupo_destinacao = Column(String(60))
    #: 'S' = auto-cadastrada por carga, aguardando revisão (nasce vinculada)
    ind_pendente_revisao = Column(String(1), default='N', nullable=False)
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)

    @property
    def codigo_completo(self) -> str:
        """Código de exibição derivado das partes (ex.: ``1.500`` ou ``1.500.0001``)."""
        base = f"{self.cod_identificador_exercicio}.{self.cod_fonte_stn}"
        if self.cod_detalhamento:
            return f"{base}.{self.cod_detalhamento}"
        return base

    @property
    def grupo(self) -> str:
        """Grupo da disponibilidade a que a fonte pertence ('L' ou 'V')."""
        return GRUPO_LIVRE if self.ind_vinculada == IND_LIVRE else GRUPO_VINCULADO
