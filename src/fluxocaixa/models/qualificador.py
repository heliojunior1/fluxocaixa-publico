from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .base import Base


class Qualificador(Base):
    __tablename__ = 'flc_qualificador'
    seq_qualificador = Column(Integer, primary_key=True)
    # 60, não 20: um código de 6 níveis com segmentos de três dígitos
    # ("1.100.200.300.400.500") tem 21 caracteres. SQLite não impõe tamanho de
    # VARCHAR e aceitava calado; PostgreSQL recusa (migração 0014).
    num_qualificador = Column(String(60), nullable=False, unique=True)
    dsc_qualificador = Column(String(255), nullable=False)
    cod_qualificador_pai = Column(Integer, ForeignKey('flc_qualificador.seq_qualificador'))
    # Marcação de categoria fiscal (F6.5) — OPCIONAL e, ao contrário de
    # lançamento/ajuste/mapeamento (R12–R14), permitida em nó com filhos: o
    # propósito é marcar o BLOCO e as folhas herdarem. Guarda só a marcação
    # PRÓPRIA; a categoria efetiva é derivada na leitura por
    # `categoria_fiscal_service.categoria_resolvida` e nunca persistida —
    # reapontar um pai a mudaria para toda a subárvore.
    cod_categoria_fiscal = Column(
        Integer, ForeignKey('flc_categoria_fiscal.seq_categoria_fiscal'))
    dat_inclusao = Column(Date, default=date.today, nullable=False)
    ind_status = Column(String(1), default='A', nullable=False)

    pai = relationship('Qualificador', remote_side=[seq_qualificador], backref='filhos')
    categoria_fiscal = relationship('CategoriaFiscal')

    def _erro_ciclo(self):
        from ..services.validacao import RegraNegocioError

        return RegraNegocioError(
            f"A hierarquia do qualificador {self.num_qualificador} tem um "
            "ciclo — corrija o qualificador pai antes de continuar"
        )

    @property
    def get_root(self):
        """Raiz da árvore.

        ⚠️ Era `while node.pai: node = node.pai`, SEM proteção. Num ciclo isso
        não levantava nada: **travava a thread para sempre**. Pior que os 500 de
        `nivel`/`path_completo` (que ao menos terminam), porque `tipo_fluxo`
        depende daqui e aparece em ~47 pontos — e produção roda
        `gunicorn --workers 1`, então UMA requisição derrubava o app inteiro.

        A guarda de ciclo do serviço impede CRIAR o estado; esta impede que
        dado legado, importação ou escrita direta no banco travem a aplicação.
        """
        node = self
        vistos = {self.seq_qualificador}
        while node.pai:
            node = node.pai
            if node.seq_qualificador in vistos:
                raise self._erro_ciclo()
            vistos.add(node.seq_qualificador)
        return node

    @property
    def tipo_fluxo(self):
        root_num = self.get_root.num_qualificador
        if root_num.startswith('1'):
            return 'receita'
        elif root_num.startswith('2'):
            return 'despesa'
        return 'indefinido'

    @property
    def nivel(self):
        """Profundidade na árvore. Iterativo, não recursivo: em ciclo a
        recursão dava `RecursionError` (500), e o R1 diz que erro de negócio
        nunca vira 500."""
        nivel = 0
        node = self
        vistos = {self.seq_qualificador}
        while node.cod_qualificador_pai is not None:
            node = node.pai
            if node is None:
                break
            if node.seq_qualificador in vistos:
                raise self._erro_ciclo()
            vistos.add(node.seq_qualificador)
            nivel += 1
        return nivel

    @property
    def path_completo(self):
        """Caminho da raiz até aqui. Iterativo pelo mesmo motivo do `nivel`."""
        partes = [self.dsc_qualificador]
        node = self
        vistos = {self.seq_qualificador}
        while node.cod_qualificador_pai is not None:
            node = node.pai
            if node is None:
                break
            if node.seq_qualificador in vistos:
                raise self._erro_ciclo()
            vistos.add(node.seq_qualificador)
            partes.append(node.dsc_qualificador)
        return " > ".join(reversed(partes))

    def get_todos_filhos(self, _vistos=None):
        """Descendentes ativos. `_vistos` corta ciclo — a descida também pode
        não terminar se a árvore estiver ciclada."""
        if _vistos is None:
            _vistos = {self.seq_qualificador}
        result = []
        for filho in self.filhos:
            if filho.ind_status != 'A':
                continue
            if filho.seq_qualificador in _vistos:
                raise self._erro_ciclo()
            _vistos.add(filho.seq_qualificador)
            result.append(filho)
            result.extend(filho.get_todos_filhos(_vistos))
        return result

    def is_folha(self):
        return len([f for f in self.filhos if f.ind_status == 'A']) == 0
