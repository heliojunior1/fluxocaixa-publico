"""Setores da previsão e o recorte de cada um (previsao RN23–RN29).

**Opcional por construção** (RN23): sem setor cadastrado nada muda — um
cenário projeta a árvore inteira. Setor existe para distribuir o trabalho:
o setor de IPVA projeta o IPVA no cenário SETORIAL dele e publica uma versão
(a proposta); quem consolida fixa essa versão num nó do seu cenário com o
método `PROPOSTA_SETORIAL`.

O recorte é marcado NO QUALIFICADOR e herda pela árvore (mais próximo vence)
— o padrão da categoria fiscal. `setor_resolvido` é a origem única da
resposta "de quem é este qualificador?"; nunca persistida.
"""
from __future__ import annotations

from datetime import date, datetime

from ..auth.contexto import cod_pessoa_atual
from .validacao import RegraNegocioError

SITUACAO_ENVIADA = 'E'
SITUACAO_ACEITA = 'A'
SITUACAO_DEVOLVIDA = 'D'
ROTULO_SITUACAO = {
    SITUACAO_ENVIADA: 'Enviada',
    SITUACAO_ACEITA: 'Aceita',
    SITUACAO_DEVOLVIDA: 'Devolvida',
}


# ---------------------------------------------------------------------------
# Cadastro
# ---------------------------------------------------------------------------

def listar_setores(apenas_ativos: bool = True) -> list:
    from ..models import SetorPrevisao

    query = SetorPrevisao.query
    if apenas_ativos:
        query = query.filter_by(ind_status='A')
    return query.order_by(SetorPrevisao.sgl_setor).all()


def _validar_setor(nom_setor: str, sgl_setor: str, seq_atual: int | None = None):
    from ..models import SetorPrevisao

    nom_setor = (nom_setor or '').strip()
    sgl_setor = (sgl_setor or '').strip().upper()
    if not nom_setor:
        raise RegraNegocioError("Informe o nome do setor")
    if not sgl_setor:
        raise RegraNegocioError("Informe a sigla do setor")
    if len(nom_setor) > 100 or len(sgl_setor) > 20:
        raise RegraNegocioError("Nome até 100 e sigla até 20 caracteres")
    repetido = SetorPrevisao.query.filter(
        SetorPrevisao.sgl_setor == sgl_setor,
        SetorPrevisao.ind_status == 'A',
    ).first()
    if repetido is not None and repetido.seq_setor_previsao != seq_atual:
        raise RegraNegocioError(f"Já existe setor ativo com a sigla {sgl_setor}")
    return nom_setor, sgl_setor


def criar_setor(nom_setor: str, sgl_setor: str, dsc_setor: str | None = None,
                user_id: int | None = None):
    from ..models import SetorPrevisao
    from ..models.base import db

    nom_setor, sgl_setor = _validar_setor(nom_setor, sgl_setor)
    setor = SetorPrevisao(nom_setor=nom_setor, sgl_setor=sgl_setor,
                          dsc_setor=(dsc_setor or '').strip() or None,
                          ind_status='A',
                          cod_pessoa_inclusao=user_id or cod_pessoa_atual())
    db.session.add(setor)
    db.session.commit()
    return setor


def alterar_setor(seq_setor: int, nom_setor: str, sgl_setor: str,
                  dsc_setor: str | None = None, user_id: int | None = None):
    from ..models import SetorPrevisao
    from ..models.base import db

    setor = SetorPrevisao.query.get(seq_setor)
    if setor is None or setor.ind_status != 'A':
        raise RegraNegocioError("Setor inexistente ou inativo")
    setor.nom_setor, setor.sgl_setor = _validar_setor(nom_setor, sgl_setor, seq_setor)
    setor.dsc_setor = (dsc_setor or '').strip() or None
    setor.dat_alteracao = date.today()
    setor.cod_pessoa_alteracao = user_id or cod_pessoa_atual()
    db.session.commit()
    return setor


def inativar_setor(seq_setor: int, user_id: int | None = None):
    """Soft delete. Recusado com cenário setorial ativo: o cenário perderia o
    dono do recorte e passaria a validar contra um setor que não existe."""
    from ..models import SetorPrevisao, SimuladorCenario
    from ..models.base import db

    setor = SetorPrevisao.query.get(seq_setor)
    if setor is None or setor.ind_status != 'A':
        raise RegraNegocioError("Setor inexistente ou inativo")
    em_uso = SimuladorCenario.query.filter_by(
        seq_setor_previsao=seq_setor, ind_status='A').count()
    if em_uso:
        raise RegraNegocioError(
            f"O setor {setor.sgl_setor} tem {em_uso} cenário(s) ativo(s) — "
            "inative-os antes")
    setor.ind_status = 'I'
    setor.dat_alteracao = date.today()
    setor.cod_pessoa_alteracao = user_id or cod_pessoa_atual()
    db.session.commit()
    return setor


# ---------------------------------------------------------------------------
# Recorte na árvore (herança)
# ---------------------------------------------------------------------------

def setor_resolvido(qualificador, memo: dict | None = None):
    """`SetorPrevisao` efetivo do qualificador (próprio ou do ancestral mais
    próximo), ou `None`. Mesma mecânica de `categoria_resolvida`: `vistos`
    separado do memo (termina em árvore ciclada) e memo do caminho inteiro."""
    if qualificador is None:
        return None
    if memo is None:
        memo = {}
    caminho = []
    vistos = set()
    no = qualificador
    resolvido = None
    while no is not None:
        if no.seq_qualificador in memo:
            resolvido = memo[no.seq_qualificador]
            break
        if no.seq_qualificador in vistos:
            raise no._erro_ciclo()
        vistos.add(no.seq_qualificador)
        caminho.append(no)
        if no.seq_setor_previsao is not None:
            resolvido = no.setor_previsao
            break
        no = no.pai
    for visitado in caminho:
        memo[visitado.seq_qualificador] = resolvido
    return resolvido


def no_no_recorte(qualificador, seq_setor: int, memo: dict | None = None) -> bool:
    setor = setor_resolvido(qualificador, memo)
    return setor is not None and setor.seq_setor_previsao == seq_setor


def marcar_recorte(seq_qualificador: int, seq_setor: int | None,
                   user_id: int | None = None):
    """Marca (ou limpa, com `None`) o setor PRÓPRIO do nó. Marcar não exige
    folha — marcar o bloco é o propósito."""
    from ..models import Qualificador, SetorPrevisao
    from ..models.base import db

    qualificador = Qualificador.query.get(seq_qualificador)
    if qualificador is None or qualificador.ind_status != 'A':
        raise RegraNegocioError("Qualificador inexistente ou inativo")
    if seq_setor is not None:
        setor = SetorPrevisao.query.get(seq_setor)
        if setor is None or setor.ind_status != 'A':
            raise RegraNegocioError("Setor inexistente ou inativo")
    qualificador.seq_setor_previsao = seq_setor
    db.session.commit()
    return qualificador


def recorte_proprio(seq_setor: int) -> list:
    """Nós marcados diretamente com o setor (a herança cobre a subárvore)."""
    from ..models import Qualificador

    return (Qualificador.query
            .filter_by(seq_setor_previsao=seq_setor, ind_status='A')
            .order_by(Qualificador.num_ano_exercicio.desc(),
                      Qualificador.num_qualificador)
            .all())


def definir_setor_do_cenario(seq_simulador_cenario: int, seq_setor: int | None,
                             user_id: int | None = None):
    """Torna o cenário SETORIAL (ou global, com `None`) — RN24.

    Recusado se o cenário já tem marcação fora do recorte do setor: o cenário
    passaria a conter projeção que o setor não pode editar nem publicar.
    """
    from ..models import CenarioMetodo, SetorPrevisao, SimuladorCenario
    from ..models.base import db

    simulador = SimuladorCenario.query.get(seq_simulador_cenario)
    if simulador is None or simulador.ind_status != 'A':
        raise RegraNegocioError("Cenário inexistente ou inativo")
    if seq_setor is not None:
        setor = SetorPrevisao.query.get(seq_setor)
        if setor is None or setor.ind_status != 'A':
            raise RegraNegocioError("Setor inexistente ou inativo")
        memo: dict = {}
        fora = [m.qualificador.num_qualificador
                for m in CenarioMetodo.query.filter_by(
                    seq_simulador_cenario=seq_simulador_cenario).all()
                if not no_no_recorte(m.qualificador, seq_setor, memo)]
        if fora:
            raise RegraNegocioError(
                f"O cenário tem marcação fora do recorte de {setor.sgl_setor}: "
                f"{', '.join(sorted(fora)[:8])} — remova-as antes")
    simulador.seq_setor_previsao = seq_setor
    simulador.dat_alteracao = date.today()
    simulador.cod_pessoa_alteracao = user_id or cod_pessoa_atual()
    db.session.commit()
    return simulador


# ---------------------------------------------------------------------------
# Propostas (versões publicadas de cenários setoriais)
# ---------------------------------------------------------------------------

def situacao_inicial_da_versao(simulador) -> str | None:
    """Versão publicada de cenário setorial nasce ENVIADA (RN26)."""
    return SITUACAO_ENVIADA if simulador.seq_setor_previsao is not None else None


def listar_propostas(seq_setor: int | None = None) -> list[dict]:
    """Versões publicadas de cenários setoriais, mais recentes primeiro, com
    os cenários que as fixaram e se há versão mais nova do mesmo cenário."""
    import json

    from ..models import CenarioMetodo, ProjecaoVersao, SimuladorCenario

    query = (ProjecaoVersao.query
             .join(SimuladorCenario,
                   SimuladorCenario.seq_simulador_cenario == ProjecaoVersao.seq_simulador_cenario)
             .filter(SimuladorCenario.seq_setor_previsao.isnot(None),
                     SimuladorCenario.ind_status == 'A',
                     ProjecaoVersao.ind_publicado == 'S'))
    if seq_setor is not None:
        query = query.filter(SimuladorCenario.seq_setor_previsao == seq_setor)
    versoes = query.order_by(ProjecaoVersao.dat_versao.desc()).all()

    ultima_por_cenario: dict[int, int] = {}
    for v in versoes:
        atual = ultima_por_cenario.get(v.seq_simulador_cenario)
        if atual is None or v.seq_projecao_versao > atual:
            ultima_por_cenario[v.seq_simulador_cenario] = v.seq_projecao_versao

    usos: dict[int, list] = {}
    for m in CenarioMetodo.query.filter_by(cod_metodo='PROPOSTA_SETORIAL').all():
        if m.simulador_cenario is None or m.simulador_cenario.ind_status != 'A':
            continue  # cenário inativo não "fixa" nada
        try:
            seq_v = int(json.loads(m.json_configuracao or '{}').get('seq_projecao_versao'))
        except (TypeError, ValueError):
            continue
        usos.setdefault(seq_v, []).append(m)

    saida = []
    for v in versoes:
        cenario = SimuladorCenario.query.get(v.seq_simulador_cenario)
        resumo = {}
        try:
            resumo = json.loads(v.json_resumo or '{}')
        except (TypeError, ValueError):
            pass
        saida.append({
            'versao': v,
            'cenario': cenario,
            'setor': cenario.setor,
            'situacao': v.cod_situacao_proposta or SITUACAO_ENVIADA,
            'rotulo_situacao': ROTULO_SITUACAO.get(v.cod_situacao_proposta or SITUACAO_ENVIADA),
            'total_receita': resumo.get('total_receita', 0),
            'total_despesa': resumo.get('total_despesa', 0),
            'usos': usos.get(v.seq_projecao_versao, []),
            'mais_nova': ultima_por_cenario.get(v.seq_simulador_cenario),
            'e_a_mais_nova': ultima_por_cenario.get(v.seq_simulador_cenario) == v.seq_projecao_versao,
        })
    return saida


def propostas_para(simulador, qualificador) -> list:
    """Versões elegíveis para `PROPOSTA_SETORIAL` neste nó: publicadas, não
    devolvidas, de cenário setorial cujo setor cobre o nó, homogêneas."""
    from . import periodo_resolver

    elegiveis = []
    for p in listar_propostas():
        cenario = p['cenario']
        if p['situacao'] == SITUACAO_DEVOLVIDA:
            continue
        if cenario.seq_simulador_cenario == simulador.seq_simulador_cenario:
            continue
        if (cenario.ano_base != simulador.ano_base
                or periodo_resolver.normalizar(cenario.cod_periodicidade)
                != periodo_resolver.normalizar(simulador.cod_periodicidade)):
            continue
        if not no_no_recorte(qualificador, cenario.seq_setor_previsao):
            continue
        elegiveis.append(p)
    return elegiveis


def avaliar_proposta(seq_projecao_versao: int, aceitar: bool,
                     motivo: str | None = None, user_id: int | None = None):
    """Aceita ou devolve a proposta (RN26). Devolver exige motivo e é
    recusado se algum cenário ainda a fixa — o consumidor perderia os
    números em silêncio; troque a versão fixada antes."""
    from ..models import ProjecaoVersao, SimuladorCenario
    from ..models.base import db

    versao = ProjecaoVersao.query.get(seq_projecao_versao)
    if versao is None or versao.ind_publicado != 'S':
        raise RegraNegocioError("Proposta inexistente ou não publicada")
    cenario = SimuladorCenario.query.get(versao.seq_simulador_cenario)
    if cenario is None or cenario.seq_setor_previsao is None:
        raise RegraNegocioError("A versão não é proposta de um setor")
    if aceitar:
        versao.cod_situacao_proposta = SITUACAO_ACEITA
        versao.dsc_motivo_devolucao = None
    else:
        motivo = (motivo or '').strip()
        if not motivo:
            raise RegraNegocioError("Informe o motivo da devolução ao setor")
        usos = [p for p in listar_propostas()
                if p['versao'].seq_projecao_versao == seq_projecao_versao and p['usos']]
        if usos:
            raise RegraNegocioError(
                "Esta versão está fixada em cenário(s) — troque a versão fixada "
                "antes de devolver")
        versao.cod_situacao_proposta = SITUACAO_DEVOLVIDA
        versao.dsc_motivo_devolucao = motivo[:255]
    versao.dat_avaliacao = datetime.now()
    versao.cod_pessoa_avaliacao = user_id or cod_pessoa_atual()
    db.session.commit()
    return versao
