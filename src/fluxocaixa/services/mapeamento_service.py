"""Cadastro de mapeamento e itens (spec automacao-lancamentos R6).

Cabeçalho (ano + sistema de origem) agrupando itens que ligam um
qualificador **folha** a uma regra de classificação sobre a staging.
Um mapeamento reúne itens de receita E de despesa: a classificação vem do
QUALIFICADOR do item (change mapeamento-sem-dimensao-receita-despesa).

Regras portadas da implementação de referência, mais a do projeto:
- unicidade (ano, sistema_origem) entre ATIVOS — a referência usa
  (ano, tipo) e deixa a origem fora da chave, o que bloquearia uma segunda
  origem no mesmo ano; nós somos multi-origem por construção;
- ao menos um item ativo;
- qualificador não repetido entre itens ativos;
- qualificador deve ser folha (lançamento só nasce em folha).

`ind_inversao_sinal` é só persistido aqui — sua aplicação ao valor é da F4.3.
"""
from datetime import date

from ..auth.contexto import cod_pessoa_atual
from ..models import ItemMapeamento, Mapeamento, Qualificador, SistemaOrigem
from ..models.base import db
from ..models.item_mapeamento import INVERSAO_NAO, INVERSAO_SIM
from .regra import validar_regra
from .validacao import RegraNegocioError

_INVERSOES = (INVERSAO_NAO, INVERSAO_SIM)


def _validar_cabecalho(num_ano_exercicio, seq_sistema_origem, seq_atual=None):
    if not num_ano_exercicio:
        raise RegraNegocioError("O ano de exercício é obrigatório")
    sistema = SistemaOrigem.query.get(seq_sistema_origem)
    if sistema is None or sistema.ind_status != 'A':
        raise RegraNegocioError("Sistema de origem inexistente ou inativo")

    consulta = Mapeamento.query.filter_by(
        num_ano_exercicio=num_ano_exercicio,
        seq_sistema_origem=seq_sistema_origem,
        ind_status='A',
    )
    if seq_atual is not None:
        consulta = consulta.filter(Mapeamento.seq_mapeamento != seq_atual)
    if consulta.first() is not None:
        raise RegraNegocioError(
            f"Já existe um mapeamento ativo para {num_ano_exercicio} e "
            f"origem '{sistema.txt_sigla}' — reúna os itens nele (receita e "
            f"despesa convivem no mesmo mapeamento)"
        )


def _validar_posse(mapeamento, itens):
    """Item que traz PK precisa pertencer a ESTE mapeamento.

    Sem isso, um POST forjado sequestraria item de outro mapeamento.
    """
    proprios = {i.seq_item_mapeamento for i in mapeamento.itens}
    for item in itens:
        seq = item.get('seq_item_mapeamento')
        if seq is not None and seq not in proprios:
            raise RegraNegocioError(
                f"O item {seq} não pertence a este mapeamento"
            )


def _mudou(item, dados) -> bool:
    """Conteúdo do item mudou? É o que decide carimbar `dat_alteracao`.

    Só o conteúdo conta — reenviar o item igual (o que a tela faz a cada save)
    NÃO pode marcá-lo como sujo, senão a F4.3 reprocessa tudo.
    """
    return (
        item.seq_qualificador != dados['seq_qualificador']
        or (item.txt_regra or '') != (dados.get('txt_regra') or '')
        or item.ind_inversao_sinal != dados.get('ind_inversao_sinal', INVERSAO_NAO)
        or item.ind_status != dados.get('ind_status', 'A')
    )


def _validar_itens(itens):
    ativos = [i for i in itens if i.get('ind_status', 'A') == 'A']
    if not ativos:
        raise RegraNegocioError("O mapeamento exige ao menos um item ativo")

    vistos = set()
    for item in ativos:
        seq_q = item.get('seq_qualificador')
        qualificador = Qualificador.query.get(seq_q) if seq_q else None
        if qualificador is None or qualificador.ind_status != 'A':
            raise RegraNegocioError("Qualificador inexistente ou inativo")
        if not qualificador.is_folha():
            raise RegraNegocioError(
                "Itens de mapeamento só podem apontar para qualificadores folha"
            )
        if seq_q in vistos:
            raise RegraNegocioError(
                f"Qualificador repetido entre os itens ativos: "
                f"'{qualificador.num_qualificador}'"
            )
        vistos.add(seq_q)

        inversao = item.get('ind_inversao_sinal', INVERSAO_NAO)
        if inversao not in _INVERSOES:
            raise RegraNegocioError(
                f"Inversão de sinal inválida: '{inversao}' (0=não, 1=sim)"
            )

        # A regra é validada pelo tradutor: nada não reconhecido chega ao banco
        ok, erro = validar_regra(item.get('txt_regra'))
        if not ok:
            raise RegraNegocioError(erro)


def criar_mapeamento(num_ano_exercicio, seq_sistema_origem,
                     dsc_mapeamento, itens) -> Mapeamento:
    _validar_cabecalho(num_ano_exercicio, seq_sistema_origem)
    _validar_itens(itens)

    pessoa = cod_pessoa_atual()
    mapeamento = Mapeamento(
        num_ano_exercicio=num_ano_exercicio,
        seq_sistema_origem=seq_sistema_origem,
        dsc_mapeamento=dsc_mapeamento,
        ind_status='A',
        cod_pessoa_inclusao=pessoa,
    )
    for item in itens:
        mapeamento.itens.append(ItemMapeamento(
            seq_qualificador=item['seq_qualificador'],
            txt_regra=item.get('txt_regra'),
            ind_inversao_sinal=item.get('ind_inversao_sinal', INVERSAO_NAO),
            ind_status=item.get('ind_status', 'A'),
            cod_pessoa_inclusao=pessoa,
        ))
    db.session.add(mapeamento)
    db.session.commit()
    return mapeamento


def alterar_mapeamento(seq_mapeamento, num_ano_exercicio,
                       seq_sistema_origem, dsc_mapeamento, itens) -> Mapeamento:
    mapeamento = Mapeamento.query.get(seq_mapeamento)
    if mapeamento is None or mapeamento.ind_status != 'A':
        raise RegraNegocioError("Mapeamento inexistente ou inativo")
    _validar_cabecalho(num_ano_exercicio, seq_sistema_origem,
                       seq_atual=seq_mapeamento)
    _validar_posse(mapeamento, itens)
    _validar_itens(itens)

    pessoa = cod_pessoa_atual()
    hoje = date.today()
    mapeamento.num_ano_exercicio = num_ano_exercicio
    mapeamento.seq_sistema_origem = seq_sistema_origem
    mapeamento.dsc_mapeamento = dsc_mapeamento
    mapeamento.dat_alteracao = hoje
    mapeamento.cod_pessoa_alteracao = pessoa

    # A IDENTIDADE DO ITEM É PRESERVADA. `dat_ultima_execucao` é o marco de
    # processamento que a F4.3 consome: recriar o item o zeraria, e todo save
    # marcaria tudo como sujo — a limpeza cirúrgica viraria recarga total.
    por_seq = {i.seq_item_mapeamento: i for i in mapeamento.itens}
    vistos = set()

    for dados in itens:
        seq = dados.get('seq_item_mapeamento')
        existente = por_seq.get(seq) if seq is not None else None

        if existente is None:
            # item novo: nasce sem marco de execução (nunca foi processado)
            mapeamento.itens.append(ItemMapeamento(
                seq_qualificador=dados['seq_qualificador'],
                txt_regra=dados.get('txt_regra'),
                ind_inversao_sinal=dados.get('ind_inversao_sinal', INVERSAO_NAO),
                ind_status=dados.get('ind_status', 'A'),
                cod_pessoa_inclusao=pessoa,
            ))
            continue

        vistos.add(seq)
        if not _mudou(existente, dados):
            continue  # reenviado igual: NÃO carimba — não é sujeira

        existente.seq_qualificador = dados['seq_qualificador']
        existente.txt_regra = dados.get('txt_regra')
        existente.ind_inversao_sinal = dados.get('ind_inversao_sinal', INVERSAO_NAO)
        existente.ind_status = dados.get('ind_status', 'A')
        existente.dat_alteracao = hoje
        existente.cod_pessoa_alteracao = pessoa
        # O conteúdo mudou ⇒ o item NÃO foi executado na sua forma atual: zera o
        # marco, que é o que a F4.3 lê para saber que ele está sujo.
        # (Comparar `dat_alteracao > dat_ultima_execucao` não serve: ambos são
        # Date, então editar e processar no MESMO DIA nunca acusaria sujeira.)
        existente.dat_ultima_execucao = None

    # Ausente do POST → inativa (preserva histórico e o marco de execução)
    for seq, existente in por_seq.items():
        if seq not in vistos and existente.ind_status == 'A':
            existente.ind_status = 'I'
            existente.dat_alteracao = hoje
            existente.cod_pessoa_alteracao = pessoa

    db.session.commit()
    return mapeamento


def inativar_mapeamento(seq_mapeamento) -> None:
    mapeamento = Mapeamento.query.get(seq_mapeamento)
    if mapeamento is None or mapeamento.ind_status != 'A':
        raise RegraNegocioError("Mapeamento inexistente ou inativo")
    mapeamento.ind_status = 'I'
    mapeamento.dat_alteracao = date.today()
    mapeamento.cod_pessoa_alteracao = cod_pessoa_atual()
    db.session.commit()


def listar_mapeamentos(apenas_ativos: bool = True) -> list[Mapeamento]:
    consulta = Mapeamento.query
    if apenas_ativos:
        consulta = consulta.filter_by(ind_status='A')
    return consulta.order_by(
        Mapeamento.num_ano_exercicio.desc(), Mapeamento.seq_mapeamento).all()


__all__ = [
    'alterar_mapeamento',
    'criar_mapeamento',
    'inativar_mapeamento',
    'listar_mapeamentos',
]
