"""Categoria fiscal — domínio das metas da LDO (F6.5).

Substitui o casamento por substring na descrição do qualificador
(`ldo_orcamento_service`, `'pessoal' in dsc.lower()` e irmãos), que não
enxergava a hierarquia: bloco "EDUCAÇÃO" casaria a palavra mas não é folha, e
as folhas sob ele não casam — a meta dava R$ 0,00 e exibia "ATENÇÃO", que se lê
como descumprimento legítimo.

⚠️ **Os limiares moram AQUI, não no código.** O piso da saúde é 15% para
municípios e **12% para estados**; o limite de pessoal da LRF reparte por poder.
Um número fixo já estava errado para parte dos usuários — somar certo e julgar
errado é a mesma classe de erro que a feature veio consertar.

⚠️ **`cod_base_calculo` não é generalização gratuita**: o serviço já usava
denominadores diferentes (pessoal sobre a RCL, saúde e educação sobre a despesa
total). Sem esta coluna a diferença voltaria como `if sigla == 'PESSOAL'` — a
heurística de novo, só que sobre a sigla em vez da descrição.
"""
from datetime import date

from sqlalchemy import Column, Date, Integer, Numeric, String

from .base import Base

#: Base de cálculo do percentual da meta.
BASE_RCL = 'R'            #: receita corrente líquida
BASE_DESPESA_TOTAL = 'D'  #: despesa total realizada no ano

#: Sentido do limite.
SENTIDO_PISO = 'P'  #: cumprir é ficar ACIMA (saúde, educação)
SENTIDO_TETO = 'T'  #: cumprir é ficar ABAIXO (pessoal)


class CategoriaFiscal(Base):
    """Domínio cadastrável: sigla, base de cálculo, sentido e limiares.

    Segue o padrão de `flc_tipo_origem_saldo` (sigla única, seedado). O seed é
    idempotente e **nunca altera existente**: a SEFAZ que ajustou o piso não
    pode ter o ajuste revertido no próximo boot.
    """

    __tablename__ = 'flc_categoria_fiscal'

    seq_categoria_fiscal = Column(Integer, primary_key=True)
    txt_sigla = Column(String(30), nullable=False, unique=True)
    dsc_categoria = Column(String(120), nullable=False)
    cod_base_calculo = Column(String(1), nullable=False, default=BASE_DESPESA_TOTAL)
    cod_sentido = Column(String(1), nullable=False, default=SENTIDO_PISO)
    #: percentual — 15.00 = 15%
    val_limite = Column(Numeric(6, 2), nullable=False)
    #: faixa intermediária, só faz sentido em teto (ex.: pessoal 60 → 70)
    val_limite_atencao = Column(Numeric(6, 2))
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)

    def rotulo_meta(self) -> str:
        """"≤ 60%" ou "≥ 15%", conforme o sentido."""
        simbolo = '≤' if self.cod_sentido == SENTIDO_TETO else '≥'
        return f"{simbolo} {self.val_limite:.0f}%"

    def status_para(self, percentual: float) -> str:
        """Veredito do percentual perante os limiares DESTA categoria."""
        limite = float(self.val_limite)
        if self.cod_sentido == SENTIDO_TETO:
            if percentual <= limite:
                return 'DENTRO DA META'
            atencao = float(self.val_limite_atencao or limite)
            return 'ATENÇÃO' if percentual <= atencao else 'CRÍTICO'
        return 'DENTRO DA META' if percentual >= limite else 'ATENÇÃO'


class MetaFiscalAno(Base):
    """Metas fiscais que a entidade define por ano — hoje, o superávit primário.

    ⚠️ Por que uma tabela própria e não `flc_parametro_global` +
    `flc_cenario_parametro_valor`: aquele par pertence ao motor de fórmulas
    (parâmetro macro **por cenário**), e a meta de superávit não pertence a
    cenário nenhum — ela é da LDO da entidade, para o ano.

    ⚠️ Por que existe: a meta era `loa_receita_total * 0.02`, com os 2% no
    código. Diferente da dívida consolidada (removida do relatório por não ter
    fonte no sistema), este é um número que o usuário CONHECE — só estava no
    lugar errado. Parametriza-se o que alguém sabe responder; remove-se o que
    ninguém consegue apurar.
    """

    __tablename__ = 'flc_meta_fiscal_ano'

    seq_meta_fiscal_ano = Column(Integer, primary_key=True)
    num_ano = Column(Integer, nullable=False, unique=True)
    val_superavit_primario = Column(Numeric(18, 2))
    ind_status = Column(String(1), default='A', nullable=False)
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    cod_pessoa_inclusao = Column(Integer)
    dat_alteracao = Column(Date)
    cod_pessoa_alteracao = Column(Integer)
