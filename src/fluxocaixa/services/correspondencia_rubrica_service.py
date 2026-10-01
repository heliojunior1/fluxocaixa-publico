"""Correspondência de rubricas entre exercícios — o "De/Para" (previsao R30).

Fusão (N origens → 1 destino) e desdobramento (1 origem → N destinos) por
identidade estável (`cod_rubrica_raiz`). A raiz continua cuidando da
continuidade 1:1; aqui mora só o que ela não representa.

⚠️ Estado DERIVADO DE EVENTOS (`flc_correspondencia_evento`): criação (C),
inativação (I), rateio definido (R) e rateio removido (X). O seq do último
evento é a VERSÃO do De/Para; `correspondencias(versao=V)` reconstrói o
De/Para como estava em V — é o que mantém explicável um número publicado
depois de a correspondência mudar. Nada é editado no lugar.

⚠️ Duas responsabilidades: a ESTRUTURA é mudança de classificação (exige o
ato que a fundamenta); o RATEIO é estimativa para previsão (exige fundamento,
permissão própria — tesouraria). Nenhuma divisão é inventada: desdobramento
sem reconstrução válida nem rateio fica PENDENTE (`serie_historica`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from ..models import (
    CorrespondenciaDestino,
    CorrespondenciaEvento,
    CorrespondenciaOrigem,
    CorrespondenciaRateio,
    CorrespondenciaRubrica,
    Qualificador,
)
from ..models.base import db
from ..models.correspondencia_rubrica import (
    EVENTO_CRIACAO,
    EVENTO_INATIVACAO,
    EVENTO_RATEIO,
    EVENTO_RATEIO_REMOVIDO,
    TIPO_DESDOBRAMENTO,
    TIPO_FUSAO,
)
from .validacao import RegraNegocioError

CEM = Decimal('100.0000')
QUATRO_CASAS = Decimal('0.0001')
ROTULO_TIPO = {TIPO_FUSAO: 'Fusão', TIPO_DESDOBRAMENTO: 'Desdobramento'}


@dataclass(frozen=True)
class EstadoCorrespondencia:
    """Correspondência como estava numa versão do De/Para."""

    seq: int
    tipo: str
    ano_vigencia: int
    origens: tuple
    #: raiz do destino → regra de reconstrução (ou None)
    destinos: dict = field(hash=False)
    #: raiz do destino → percentual (Decimal); None = sem rateio
    rateio: dict | None = field(default=None, hash=False)
    referencia_ato: str = ''
    fundamento: str = ''

    @property
    def inicio_vigencia(self) -> date:
        return date(self.ano_vigencia, 1, 1)


# ---------------------------------------------------------------- leitura

def versao_atual() -> int:
    from sqlalchemy import func

    return int(db.session.query(
        func.max(CorrespondenciaEvento.seq_correspondencia_evento)).scalar() or 0)


def correspondencias(versao: int | None = None) -> list[EstadoCorrespondencia]:
    """Correspondências ATIVAS na versão (default: a atual), com o rateio
    vigente naquela versão. Reconstruído dos eventos — nunca do `ind_status`."""
    if versao is None:
        versao = versao_atual()
    if not versao:
        return []
    eventos = (CorrespondenciaEvento.query
               .filter(CorrespondenciaEvento.seq_correspondencia_evento <= versao)
               .order_by(CorrespondenciaEvento.seq_correspondencia_evento).all())
    criadas: dict[int, bool] = {}
    ultimo_rateio: dict[int, CorrespondenciaEvento | None] = {}
    for evento in eventos:
        seq = evento.seq_correspondencia_rubrica
        if evento.cod_tipo_evento == EVENTO_CRIACAO:
            criadas[seq] = True
        elif evento.cod_tipo_evento == EVENTO_INATIVACAO:
            criadas[seq] = False
        elif evento.cod_tipo_evento == EVENTO_RATEIO:
            ultimo_rateio[seq] = evento
        elif evento.cod_tipo_evento == EVENTO_RATEIO_REMOVIDO:
            ultimo_rateio[seq] = None
    ativas = [seq for seq, ativa in criadas.items() if ativa]
    if not ativas:
        return []
    estados = []
    for corr in (CorrespondenciaRubrica.query
                 .filter(CorrespondenciaRubrica.seq_correspondencia_rubrica.in_(ativas))
                 .order_by(CorrespondenciaRubrica.seq_correspondencia_rubrica).all()):
        evento_rateio = ultimo_rateio.get(corr.seq_correspondencia_rubrica)
        rateio = None
        if evento_rateio is not None:
            rateio = {linha.cod_rubrica_raiz: Decimal(linha.val_percentual)
                      for linha in evento_rateio.rateio}
        estados.append(EstadoCorrespondencia(
            seq=corr.seq_correspondencia_rubrica,
            tipo=corr.cod_tipo,
            ano_vigencia=corr.num_ano_vigencia,
            origens=tuple(o.cod_rubrica_raiz for o in corr.origens),
            destinos={d.cod_rubrica_raiz: d.txt_regra_reconstrucao for d in corr.destinos},
            rateio=rateio,
            referencia_ato=corr.dsc_referencia_ato,
            fundamento=corr.dsc_fundamento,
        ))
    return estados


def rubrica_da_raiz(raiz: int) -> Qualificador | None:
    """Linha mais recente (maior exercício) de uma identidade — para exibir."""
    return (Qualificador.query.filter_by(cod_rubrica_raiz=raiz)
            .order_by(Qualificador.num_ano_exercicio.desc()).first())


# ---------------------------------------------------------------- escrita

def _autor(user_id):
    if user_id is not None:
        return user_id
    from ..auth.contexto import cod_pessoa_atual

    return cod_pessoa_atual()


def _texto(valor, campo, limite):
    texto = (valor or '').strip()
    if not texto:
        raise RegraNegocioError(f"Informe {campo}")
    if len(texto) > limite:
        raise RegraNegocioError(f"{campo[0].upper()}{campo[1:]} tem mais de {limite} caracteres")
    return texto


def _evento(seq_corr, tipo, justificativa, autor) -> CorrespondenciaEvento:
    evento = CorrespondenciaEvento(
        seq_correspondencia_rubrica=seq_corr, cod_tipo_evento=tipo,
        dsc_justificativa=justificativa, cod_pessoa_evento=autor)
    db.session.add(evento)
    db.session.flush()
    return evento


def _qualificadores(seqs, papel) -> list[Qualificador]:
    linhas = []
    for seq in seqs:
        q = db.session.get(Qualificador, int(seq))
        if q is None:
            raise RegraNegocioError(f"{papel.capitalize()} {seq} não existe")
        linhas.append(q)
    return linhas


def _antecessoras(raiz: int, por_destino: dict, caminho=None) -> set[int]:
    """Identidades que alimentam `raiz` por correspondência (transitivo)."""
    caminho = caminho or set()
    saida = set()
    for estado in por_destino.get(raiz, []):
        for origem in estado.origens:
            if origem in caminho:
                continue
            saida.add(origem)
            saida |= _antecessoras(origem, por_destino, caminho | {origem})
    return saida


def criar_correspondencia(cod_tipo: str, num_ano_vigencia: int, origens: list[int],
                          destinos: list[int], dsc_referencia_ato: str, dsc_fundamento: str,
                          regras: dict | None = None, user_id: int | None = None
                          ) -> CorrespondenciaRubrica:
    """Cria fusão ('F') ou desdobramento ('D'). `origens`/`destinos` são
    `seq_qualificador`; `regras` mapeia seq do destino → regra de
    reconstrução (todas ou nenhuma). Transação única."""
    ato = _texto(dsc_referencia_ato, 'a referência do ato', 255)
    fundamento = _texto(dsc_fundamento, 'o fundamento', 500)
    if cod_tipo not in ROTULO_TIPO:
        raise RegraNegocioError("Tipo de correspondência inválido (fusão ou desdobramento)")
    try:
        vigencia = int(num_ano_vigencia)
    except (TypeError, ValueError):
        raise RegraNegocioError("Informe o exercício de vigência") from None

    qs_origem = _qualificadores(origens, 'origem')
    qs_destino = _qualificadores(destinos, 'destino')
    if cod_tipo == TIPO_FUSAO and (len(qs_origem) < 2 or len(qs_destino) != 1):
        raise RegraNegocioError("Fusão tem duas ou mais origens e um destino")
    if cod_tipo == TIPO_DESDOBRAMENTO and (len(qs_origem) != 1 or len(qs_destino) < 2):
        raise RegraNegocioError("Desdobramento tem uma origem e dois ou mais destinos")

    raizes_origem = [q.cod_rubrica_raiz for q in qs_origem]
    raizes_destino = [q.cod_rubrica_raiz for q in qs_destino]
    if len(set(raizes_origem)) != len(raizes_origem) or len(set(raizes_destino)) != len(raizes_destino):
        raise RegraNegocioError("A mesma rubrica foi informada duas vezes")

    naturezas = {q.tipo_fluxo for q in qs_origem + qs_destino}
    if len(naturezas) != 1:
        raise RegraNegocioError(
            "Origens e destinos têm natureza diferente (receita × despesa) — "
            "a correspondência não muda a natureza da rubrica")

    for q in qs_origem:
        if q.num_ano_exercicio >= vigencia:
            raise RegraNegocioError(
                f"A origem {q.num_qualificador} é do exercício {q.num_ano_exercicio}; "
                f"tem de ser anterior à vigência {vigencia}")
    for q in qs_destino:
        if q.num_ano_exercicio != vigencia or q.ind_status != 'A':
            raise RegraNegocioError(
                f"O destino {q.num_qualificador} tem de ser rubrica ativa do plano de {vigencia}")

    por_raiz_origem = {q.cod_rubrica_raiz: q for q in qs_origem}
    for q in qs_destino:
        if q.cod_rubrica_raiz in por_raiz_origem:
            origem = por_raiz_origem[q.cod_rubrica_raiz]
            raise RegraNegocioError(
                f"O destino {q.num_qualificador} compartilha a identidade da origem "
                f"{origem.num_qualificador} — a origem seria contada duas vezes (dupla "
                "contagem). Na fusão e no desdobramento o destino tem identidade própria")

    for q in qs_origem:
        continua = Qualificador.query.filter_by(
            cod_rubrica_raiz=q.cod_rubrica_raiz, num_ano_exercicio=vigencia,
            ind_status='A').first()
        if continua is not None:
            raise RegraNegocioError(
                f"A origem {q.num_qualificador} continua ativa no exercício {vigencia} "
                f"({continua.num_qualificador}) — a série seria somada em dobro")

    vigentes = correspondencias()
    por_destino: dict[int, list] = {}
    for estado in vigentes:
        for destino in estado.destinos:
            por_destino.setdefault(destino, []).append(estado)
        for origem in estado.origens:
            if origem in raizes_origem:
                rubrica = por_raiz_origem[origem].num_qualificador
                raise RegraNegocioError(
                    f"A origem {rubrica} já é origem de outra correspondência ativa")
    for q in qs_destino:
        if q.cod_rubrica_raiz in por_destino:
            raise RegraNegocioError(
                f"O destino {q.num_qualificador} já é destino de outra correspondência ativa")
        for origem in raizes_origem:
            if q.cod_rubrica_raiz in _antecessoras(origem, por_destino) | {origem}:
                raise RegraNegocioError(
                    f"A correspondência criaria um ciclo pelo destino {q.num_qualificador}")

    regra_por_raiz = {q.cod_rubrica_raiz: None for q in qs_destino}
    if regras:
        if cod_tipo != TIPO_DESDOBRAMENTO:
            raise RegraNegocioError("Regra de reconstrução só se aplica a desdobramento")
        from .regra import validar_regra

        for q in qs_destino:
            texto = (regras.get(q.seq_qualificador) or '').strip()
            if not texto:
                raise RegraNegocioError(
                    f"Informe a regra de reconstrução de TODOS os destinos (falta "
                    f"{q.num_qualificador}) — ou de nenhum")
            ok, erro = validar_regra(texto)
            if not ok:
                raise RegraNegocioError(f"Regra do destino {q.num_qualificador}: {erro}")
            regra_por_raiz[q.cod_rubrica_raiz] = texto

    autor = _autor(user_id)
    try:
        corr = CorrespondenciaRubrica(
            cod_tipo=cod_tipo, num_ano_vigencia=vigencia, dsc_referencia_ato=ato,
            dsc_fundamento=fundamento, ind_status='A', cod_pessoa_inclusao=autor)
        db.session.add(corr)
        db.session.flush()
        for raiz in raizes_origem:
            db.session.add(CorrespondenciaOrigem(
                seq_correspondencia_rubrica=corr.seq_correspondencia_rubrica,
                cod_rubrica_raiz=raiz))
        for raiz in raizes_destino:
            db.session.add(CorrespondenciaDestino(
                seq_correspondencia_rubrica=corr.seq_correspondencia_rubrica,
                cod_rubrica_raiz=raiz, txt_regra_reconstrucao=regra_por_raiz[raiz]))
        _evento(corr.seq_correspondencia_rubrica, EVENTO_CRIACAO, fundamento, autor)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return corr


def _ativa(seq_correspondencia_rubrica) -> CorrespondenciaRubrica:
    corr = db.session.get(CorrespondenciaRubrica, int(seq_correspondencia_rubrica))
    if corr is None or corr.ind_status != 'A':
        raise RegraNegocioError("Correspondência não encontrada ou inativa")
    return corr


def inativar_correspondencia(seq_correspondencia_rubrica: int, motivo: str,
                             user_id: int | None = None) -> None:
    """Inativa (nunca apaga) — corrigir a estrutura é inativar e criar outra."""
    motivo = _texto(motivo, 'o motivo da inativação', 500)
    corr = _ativa(seq_correspondencia_rubrica)
    autor = _autor(user_id)
    try:
        corr.ind_status = 'I'
        corr.dat_alteracao = date.today()
        corr.cod_pessoa_alteracao = autor
        _evento(corr.seq_correspondencia_rubrica, EVENTO_INATIVACAO, motivo, autor)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def _percentual(valor, rubrica) -> Decimal:
    try:
        numero = Decimal(str(valor).replace(',', '.').strip())
    except (InvalidOperation, AttributeError):
        raise RegraNegocioError(f"Percentual inválido para {rubrica}") from None
    if numero < 0 or numero > CEM:
        raise RegraNegocioError(f"Percentual de {rubrica} fora de 0 a 100")
    return numero.quantize(QUATRO_CASAS, rounding=ROUND_HALF_UP)


def definir_rateio(seq_correspondencia_rubrica: int, percentuais: dict, fundamento: str,
                   user_id: int | None = None) -> None:
    """Rateio de um desdobramento: percentual de CADA destino (chave =
    `seq_qualificador` do destino), soma exatamente 100. Conjunto atômico;
    substitui o anterior por um evento novo."""
    fundamento = _texto(fundamento, 'o fundamento do rateio', 500)
    corr = _ativa(seq_correspondencia_rubrica)
    if corr.cod_tipo != TIPO_DESDOBRAMENTO:
        raise RegraNegocioError("Rateio só se aplica a desdobramento")
    raizes = {d.cod_rubrica_raiz for d in corr.destinos}
    por_raiz: dict[int, Decimal] = {}
    for seq, valor in percentuais.items():
        q = db.session.get(Qualificador, int(seq))
        if q is None or q.cod_rubrica_raiz not in raizes:
            raise RegraNegocioError("O rateio cita rubrica que não é destino do desdobramento")
        por_raiz[q.cod_rubrica_raiz] = _percentual(valor, q.num_qualificador)
    if set(por_raiz) != raizes:
        raise RegraNegocioError("Informe o percentual de todos os destinos")
    soma = sum(por_raiz.values(), Decimal('0'))
    if soma != CEM:
        raise RegraNegocioError(
            f"Os percentuais do rateio precisam somar 100 (soma informada: {soma.normalize()})")
    autor = _autor(user_id)
    try:
        evento = _evento(corr.seq_correspondencia_rubrica, EVENTO_RATEIO, fundamento, autor)
        for raiz, pct in por_raiz.items():
            db.session.add(CorrespondenciaRateio(
                seq_correspondencia_evento=evento.seq_correspondencia_evento,
                cod_rubrica_raiz=raiz, val_percentual=pct))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def remover_rateio(seq_correspondencia_rubrica: int, motivo: str,
                   user_id: int | None = None) -> None:
    """Devolve o desdobramento à pendência (evento X)."""
    motivo = _texto(motivo, 'o motivo da remoção', 500)
    corr = _ativa(seq_correspondencia_rubrica)
    if corr.cod_tipo != TIPO_DESDOBRAMENTO:
        raise RegraNegocioError("Rateio só se aplica a desdobramento")
    try:
        _evento(corr.seq_correspondencia_rubrica, EVENTO_RATEIO_REMOVIDO, motivo,
                _autor(user_id))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


# ---------------------------------------------------------------- apoio

def sugestao_rateio(seq_correspondencia_rubrica: int) -> dict[int, Decimal] | None:
    """Percentuais observados no realizado de cada destino desde a vigência
    (raiz → Decimal 4 casas, soma 100). SUGESTÃO DE TELA — gravar o rateio é
    decisão humana. None quando os destinos ainda não têm realizado."""
    from .serie_historica import realizado_proprio

    corr = _ativa(seq_correspondencia_rubrica)
    if corr.cod_tipo != TIPO_DESDOBRAMENTO:
        return None
    inicio = date(corr.num_ano_vigencia, 1, 1)
    valores = {d.cod_rubrica_raiz: abs(realizado_proprio(d.cod_rubrica_raiz, inicio))
               for d in corr.destinos}
    total = sum(valores.values())
    if total <= 0:
        return None
    sugestao = {raiz: (Decimal(str(v)) * CEM / Decimal(str(total))).quantize(
        QUATRO_CASAS, rounding=ROUND_HALF_UP) for raiz, v in valores.items()}
    maior = max(sugestao, key=sugestao.get)
    sugestao[maior] += CEM - sum(sugestao.values(), Decimal('0'))
    return sugestao


def listar_para_tela() -> list[dict]:
    """Linhas da tela: estado atual + modo resolvido + sugestão (pendente)."""
    from .serie_historica import modo_da_divisao

    linhas = []
    for estado in correspondencias():
        def _rotulo(raiz):
            q = rubrica_da_raiz(raiz)
            return {'raiz': raiz, 'seq': q.seq_qualificador if q else None,
                    'codigo': q.num_qualificador if q else str(raiz),
                    'descricao': q.dsc_qualificador if q else '',
                    'exercicio': q.num_ano_exercicio if q else None}

        modo = modo_da_divisao(estado) if estado.tipo == TIPO_DESDOBRAMENTO else None
        linhas.append({
            'estado': estado,
            'tipo': ROTULO_TIPO[estado.tipo],
            'origens': [_rotulo(r) for r in estado.origens],
            'destinos': [{**_rotulo(r), 'regra': regra,
                          'percentual': (estado.rateio or {}).get(r)}
                         for r, regra in estado.destinos.items()],
            'modo': modo,
            'sugestao': (sugestao_rateio(estado.seq)
                         if modo == 'PENDENTE' else None),
        })
    return linhas


# ---------------------------------------------------------------- tela

def _codigos(texto: str) -> list[str]:
    import re

    return [c for c in re.split(r'[,;\s]+', texto or '') if c]


def _rubrica_por_codigo(codigo: str, ano: int, papel: str, so_ativa: bool) -> Qualificador:
    consulta = Qualificador.query.filter_by(num_qualificador=codigo, num_ano_exercicio=ano)
    if so_ativa:
        consulta = consulta.filter_by(ind_status='A')
    q = consulta.order_by(Qualificador.ind_status).first()
    if q is None:
        raise RegraNegocioError(f"{papel.capitalize()} {codigo} não existe no plano de {ano}")
    return q


def criar_por_codigos(cod_tipo: str, num_ano_vigencia, origens_txt: str, destinos_txt: str,
                      dsc_referencia_ato: str, dsc_fundamento: str, regras_txt: str = '',
                      user_id: int | None = None) -> CorrespondenciaRubrica:
    """Porta da tela: códigos das ORIGENS no plano anterior à vigência
    (`resolver_exercicio_do_plano(vigência − 1)`) e dos DESTINOS no plano da
    vigência. `regras_txt`: uma linha por destino, `código | regra`."""
    from .qualificador_service import resolver_exercicio_do_plano

    try:
        vigencia = int(num_ano_vigencia)
    except (TypeError, ValueError):
        raise RegraNegocioError("Informe o exercício de vigência") from None
    plano_origem = resolver_exercicio_do_plano(vigencia - 1)
    if plano_origem is None or plano_origem >= vigencia:
        raise RegraNegocioError(f"Não há plano anterior a {vigencia} para as origens")
    origens = [_rubrica_por_codigo(c, plano_origem, 'origem', so_ativa=False)
               for c in _codigos(origens_txt)]
    destinos = [_rubrica_por_codigo(c, vigencia, 'destino', so_ativa=True)
                for c in _codigos(destinos_txt)]
    regras = None
    linhas = [linha for linha in (regras_txt or '').splitlines() if linha.strip()]
    if linhas:
        por_codigo = {}
        for linha in linhas:
            if '|' not in linha:
                raise RegraNegocioError(
                    f"Regra sem separador '|' (use 'código | regra'): {linha.strip()}")
            codigo, regra = linha.split('|', 1)
            por_codigo[codigo.strip()] = regra.strip()
        regras = {q.seq_qualificador: por_codigo.get(q.num_qualificador, '') for q in destinos}
    return criar_correspondencia(
        cod_tipo, vigencia, [q.seq_qualificador for q in origens],
        [q.seq_qualificador for q in destinos], dsc_referencia_ato, dsc_fundamento,
        regras=regras, user_id=user_id)
