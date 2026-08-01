"""Rede de caracterização dos relatórios derivados de lançamento (F6.1a, R8).

Congela os números de todos os relatórios que leem `flc_lancamento`, para que
a F6.1b (valor sempre positivo + tipo 'C'/'D') possa ser provada inerte: a
mesma golden tem de bater depois da migração.

⚠️ Massa PRÓPRIA, não `seed_data()`: o seed demo usa `date.today()` (saldos) e
produziria golden instável — a orientação do plano (§9.2) é seed determinístico
por contexto.

⚠️ A ilha é **2019**, ANTES do seed demo (lançamentos 2022–2026; saldos de
2022-01-01 até `date.today()`), e não depois. Motivo: os relatórios de saldo
carregam o último saldo ANTERIOR à data quando não há saldo no dia — uma ilha
posterior herdaria o carry-forward do seed, que se move com o dia de hoje e
faria a golden quebrar da noite para o dia. Antes de 2022 não há nada para
carregar, então a massa fica hermética.

⚠️ A massa é DELIBERADAMENTE COERENTE (sinal e tipo concordam em toda linha).
Ela já teve linhas anômalas — receita negativa, despesa positiva —, e a F6.1b
mostrou por que elas não cabem aqui: a migração deriva o tipo do SINAL, então
uma linha anômala **muda de tipo** por construção. O valor com sinal e o
resultado líquido continuam idênticos, mas todo relatório que separa receita de
despesa POR TIPO redistribui entre as duas colunas. Misturar isso na golden
confundiria duas coisas: "os relatórios não mudam para dado válido" (a promessa
desta rede, que precisa valer sem asterisco) e "o que a migração faz com dado
inválido" (semântica coberta pelo BDD `tipo_lancamento_cd.feature`, que fixa o
valor com sinal de cada forma).

A massa mantém as formas ESTRUTURAIS que os relatórios precisam enxergar:
lançamento sem conta vinculada e de origem automática (F4.3).

Campos EXCLUÍDOS do snapshot (dependem da data corrente, não da convenção de
sinal, e a F6.1 não os toca) — ver `CAMPOS_EXCLUIDOS`.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

# ---------------------------------------------------------------------------
# Ilha de datas e identificadores da massa (todos fictícios)
# ---------------------------------------------------------------------------
ANO = 2019
DIA_BASE = date(ANO, 3, 10)
DIA_SEGUINTE = date(ANO, 3, 11)

CONTA_A = ("901", "0001", "CARACT-1")
CONTA_B = ("902", "0002", "CARACT-2")

QUAL_RECEITA = "1.99.1"
QUAL_RECEITA_2 = "1.99.2"
QUAL_DESPESA = "2.99.1"
QUAL_DESPESA_2 = "2.99.2"

FUNDO = "9990"

# Campos dependentes de "hoje" — a F6.1 não altera nenhum deles.
CAMPOS_EXCLUIDOS = {
    # KPIs: semáforo usa datetime.now(); ultima_inclusao é dat_inclusao (=hoje na gravação)
    "kpis.defasagem",
    # DFC projetado: _meses_abertos usa date.today() (coberto pelo BDD da F5.2)
    "dfc_projetado",
}


def caminho_golden() -> Path:
    return (
        Path(__file__).resolve().parent
        / "fixtures"
        / "caracterizacao"
        / "golden_lancamento.json"
    )


# ---------------------------------------------------------------------------
# Massa
# ---------------------------------------------------------------------------

def _db():
    from fluxocaixa.models.base import db

    return db


def _conta(ident: tuple[str, str, str]):
    from fluxocaixa.models import ContaBancaria

    db = _db()
    banco, agencia, num = ident
    conta = ContaBancaria.query.filter_by(
        cod_banco=banco, num_agencia=agencia, num_conta=num
    ).first()
    if conta is None:
        conta = ContaBancaria(cod_banco=banco, num_agencia=agencia, num_conta=num,
                              dsc_conta=f"Conta caracterização {num}")
        db.session.add(conta)
        db.session.commit()
    return conta


def _qualificador(num: str):
    from fluxocaixa.models import Qualificador

    db = _db()
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    if q is not None:
        return q
    partes = num.split(".")
    pai = _qualificador(".".join(partes[:-1])) if len(partes) > 1 else None
    q = Qualificador(
        num_qualificador=num,
        dsc_qualificador=f"Rubrica caracterização {num}",
        cod_qualificador_pai=pai.seq_qualificador if pai else None,
    )
    db.session.add(q)
    db.session.commit()
    return q


def _lancamento(qual_num: str, valor: str, dat: date, tipo_desc: str,
                seq_conta: int | None, origem_desc: str = "Manual"):
    """Grava o lançamento a partir do seu valor COM SINAL (o fato econômico).

    `valor` é sempre o efeito no caixa — negativo é saída de dinheiro. O tipo
    e o valor gravados são derivados exatamente como a migração 0011 faz
    (`tipo = 'C' se valor >= 0 senão 'D'`, `val = abs(valor)`), para que a
    massa exprima os MESMOS fatos antes e depois da F6.1b e a golden não se
    mexa. `tipo_desc` fica como documentação da intenção de negócio: nos casos
    anômalos ele diverge do tipo derivado de propósito — estorno de receita
    ("Entrada" com valor negativo) vira 'D' sob qualificador de receita, e
    despesa mal configurada ("Saída" positiva) vira 'C' sob qualificador de
    despesa, que é precisamente o que a migração produz.
    """
    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.lancamento import TIPO_CREDITO, TIPO_DEBITO
    from fluxocaixa.services.dominio_lancamento import resolver_origem

    db = _db()
    com_sinal = Decimal(valor)
    db.session.add(Lancamento(
        dat_lancamento=dat,
        seq_qualificador=_qualificador(qual_num).seq_qualificador,
        val_lancamento=abs(com_sinal),
        cod_tipo_lancamento=TIPO_CREDITO if com_sinal >= 0 else TIPO_DEBITO,
        cod_origem_lancamento=resolver_origem(origem_desc).cod_origem_lancamento,
        seq_conta=seq_conta,
        cod_pessoa_inclusao=1,
        ind_status='A',
    ))
    db.session.commit()


def _saldo(conta, dat: date, valor: str):
    from fluxocaixa.models import Fundo, SaldoContaFundo, TipoOrigemSaldo
    from fluxocaixa.services.saldo_fundo_service import gravar_saldo

    db = _db()
    fundo = Fundo.query.filter_by(cod_fundo=FUNDO).first()
    if fundo is None:
        tipo = TipoOrigemSaldo.query.filter_by(txt_sigla="MANUAL").first()
        fundo = Fundo(cod_fundo=FUNDO, dsc_fundo="Fundo caracterização",
                      seq_tipo_origem=tipo.seq_tipo_origem_saldo)
        db.session.add(fundo)
        db.session.commit()
    existe = SaldoContaFundo.query.filter_by(
        seq_conta=conta.seq_conta, seq_fundo=fundo.seq_fundo,
        dat_saldo=dat, ind_status='A',
    ).first()
    if existe is None:
        gravar_saldo(seq_conta=conta.seq_conta, seq_fundo=fundo.seq_fundo,
                     dat_saldo=dat, val_saldo=Decimal(valor))


def limpar_massa() -> None:
    """Remove a massa da ilha (idempotência entre execuções)."""
    from sqlalchemy import extract

    from fluxocaixa.models import ContaBancaria, Lancamento, SaldoContaFundo

    db = _db()
    db.session.rollback()
    Lancamento.query.filter(
        extract("year", Lancamento.dat_lancamento) == ANO
    ).delete(synchronize_session=False)
    seqs = [
        c.seq_conta
        for ident in (CONTA_A, CONTA_B)
        if (c := ContaBancaria.query.filter_by(
            cod_banco=ident[0], num_agencia=ident[1], num_conta=ident[2]).first())
    ]
    if seqs:
        SaldoContaFundo.query.filter(
            SaldoContaFundo.seq_conta.in_(seqs)
        ).delete(synchronize_session=False)
    db.session.commit()


def montar_massa() -> dict:
    """Constrói a massa congelada e devolve os identificadores criados."""
    limpar_massa()
    conta_a = _conta(CONTA_A)
    conta_b = _conta(CONTA_B)

    # Saldos por fundo (relatórios de saldo): véspera, dia e dia seguinte
    _saldo(conta_a, date(ANO, 3, 9), "1000.00")
    _saldo(conta_a, DIA_BASE, "1200.00")
    _saldo(conta_a, DIA_SEGUINTE, "1150.00")
    _saldo(conta_b, DIA_BASE, "500.00")

    # --- Casos normais -----------------------------------------------------
    _lancamento(QUAL_RECEITA, "1000.00", DIA_BASE, "Entrada", conta_a.seq_conta)
    _lancamento(QUAL_RECEITA_2, "400.00", DIA_BASE, "Entrada", conta_b.seq_conta)
    _lancamento(QUAL_DESPESA, "-300.00", DIA_BASE, "Saída", conta_a.seq_conta)
    _lancamento(QUAL_DESPESA_2, "-120.00", DIA_SEGUINTE, "Saída", conta_b.seq_conta)
    # Outro mês, para a evolução mensal ter mais de um ponto com movimento
    _lancamento(QUAL_RECEITA, "800.00", date(ANO, 6, 15), "Entrada", conta_a.seq_conta)
    _lancamento(QUAL_DESPESA, "-250.00", date(ANO, 6, 15), "Saída", conta_a.seq_conta)

    # --- Formas estruturais que os relatórios precisam ver ------------------
    # Automático sem conta vinculada (F4.3)
    _lancamento(QUAL_RECEITA, "100.00", DIA_BASE, "Entrada", None,
                origem_desc="Automático")

    return {"conta_a": conta_a.seq_conta, "conta_b": conta_b.seq_conta}


# ---------------------------------------------------------------------------
# Canonicalização
# ---------------------------------------------------------------------------

def canonicalizar(valor):
    """Normaliza para comparação estável: número → string com 2 casas,
    data → ISO, chaves ordenadas, objeto ORM → repr identificável."""
    if valor is None or isinstance(valor, bool):
        return valor
    if isinstance(valor, (int,)) and not isinstance(valor, bool):
        return valor
    if isinstance(valor, (float, Decimal)):
        return f"{Decimal(str(valor)).quantize(Decimal('0.01'))}"
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, str):
        return valor
    if isinstance(valor, dict):
        return {str(k): canonicalizar(v) for k, v in sorted(valor.items(), key=lambda kv: str(kv[0]))}
    if isinstance(valor, (list, tuple)):
        return [canonicalizar(v) for v in valor]
    # Objetos ORM que os relatórios devolvem (ex.: ContaBancaria, Fundo)
    for attr in ("num_conta", "cod_fundo", "num_qualificador"):
        if hasattr(valor, attr):
            return f"<{type(valor).__name__} {getattr(valor, attr)}>"
    return f"<{type(valor).__name__}>"


# ---------------------------------------------------------------------------
# Poda: o snapshot congela NÚMEROS, não identidades nem vizinhos
# ---------------------------------------------------------------------------
# Dois vazamentos aparecem quando a suíte inteira roda antes desta rede:
#
#  (a) chaves surrogate (`seq_*`, `*_id`, `id`) mudam com a ordem de inserção
#      de TODOS os testes — não são fato financeiro. `podar` as remove.
#
#  (b) três relatórios varrem a árvore INTEIRA de qualificadores (DFC,
#      comparativa, LDO) e trazem os qualificadores criados por outras
#      features. `restringir_a_ilha` os recorta pelo código/descrição.
#
# ⚠️ Tentativa descartada: podar entradas "sem movimento" olhando os números.
# Não há como distinguir dinheiro de rótulo pela forma — o código de
# qualificador "1.90" é idêntico a R$ 1,90 —, e vários serviços (KPIs, por
# exemplo) já devolvem o valor como string formatada, então nem etiquetar na
# canonicalização resolve. O recorte por identidade da ilha é inequívoco.

MARCA_ILHA = "caracterização"          # aparece na descrição dos qualificadores
PREFIXOS_ILHA = ("1.99", "2.99")       # códigos dos qualificadores da massa
RAIZES = ("1", "2")


def _e_surrogada(chave: str) -> bool:
    return chave == "id" or chave.startswith("seq_") or chave.endswith("_id")


def podar(valor):
    """Remove identidades surrogate; ordena listas de registros por conteúdo,
    para não depender da ordem de varredura do banco."""
    if isinstance(valor, dict):
        return {
            chave: podar(bruto)
            for chave, bruto in valor.items()
            if not _e_surrogada(str(chave))
        }
    if isinstance(valor, list):
        itens = [podar(v) for v in valor]
        if itens and all(isinstance(item, dict) for item in itens):
            itens.sort(key=lambda i: json.dumps(i, sort_keys=True, ensure_ascii=False))
        return itens
    return valor


def _recortar_arvore(nos: list) -> list:
    """Mantém só as raízes e os nós da ilha na árvore do DFC.

    Os valores das raízes já são island-only (o relatório filtra por ano); o
    que vaza é a LISTA de filhos.
    """
    saida = []
    for no in nos:
        numero = str(no.get("number", ""))
        if numero in RAIZES or numero.startswith(PREFIXOS_ILHA):
            copia = dict(no)
            copia["children"] = _recortar_arvore(no.get("children") or [])
            saida.append(copia)
    return saida


def restringir_a_ilha(nome: str, dados):
    """Recorta os relatórios que varrem a árvore global de qualificadores."""
    if nome in ("dfc_mes", "dfc_ano") and isinstance(dados, dict):
        dados = dict(dados)
        dados["dre_data"] = _recortar_arvore(dados.get("dre_data") or [])
        return dados
    if nome == "comparativa" and isinstance(dados, dict):
        dados = dict(dados)
        bruto = dados.get("data") or {}
        dados["data"] = {
            chave: valor for chave, valor in bruto.items() if MARCA_ILHA in str(chave)
        }
        return dados
    if nome == "ldo" and isinstance(dados, dict):
        dados = dict(dados)
        linhas = dados.get("comparativo") or []
        dados["comparativo"] = [
            linha for linha in linhas
            if MARCA_ILHA in str(linha.get("categoria", ""))
        ]
        return dados
    return dados


# ---------------------------------------------------------------------------
# Coleta
# ---------------------------------------------------------------------------

def coletar_snapshot() -> dict:
    """Roda os relatórios cobertos sobre a massa e devolve o snapshot canônico.

    Só estratégia REALIZADO no DFC e sem o bloco de defasagem dos KPIs — ver
    CAMPOS_EXCLUIDOS.
    """
    from fluxocaixa.services.relatorio import (
        get_analise_comparativa_data,
        get_controle_despesa_data,
        get_dfc_data,
        get_indicadores_data,
        get_kpis_data,
        get_ldo_orcamento_data,
        get_resumo_data,
        get_saldos_diarios_data,
    )
    from fluxocaixa.services.previsao_service import get_previsao_realizado_data

    meses = list(range(1, 13))
    quals_despesa = [
        _qualificador(QUAL_DESPESA).seq_qualificador,
        _qualificador(QUAL_DESPESA_2).seq_qualificador,
    ]
    # previsão×realizado exige lista explícita de qualificadores (usa IN)
    quals_todos = quals_despesa + [
        _qualificador(QUAL_RECEITA).seq_qualificador,
        _qualificador(QUAL_RECEITA_2).seq_qualificador,
    ]

    kpis = get_kpis_data(
        data_referencia=DIA_BASE,
        data_inicio=date(ANO, 1, 1),
        data_fim=date(ANO, 12, 31),
    )
    kpis = {k: v for k, v in kpis.items() if k != "defasagem"}

    snapshot = {
        "dfc_mes": get_dfc_data("mes", ANO, 3, meses, "realizado", None),
        "dfc_ano": get_dfc_data("ano", ANO, None, meses, "realizado", None),
        "kpis": kpis,
        "saldos_diarios_agregado": get_saldos_diarios_data(DIA_BASE, visao="agregado"),
        "saldos_diarios_fundo": get_saldos_diarios_data(DIA_BASE, visao="fundo"),
        "resumo": get_resumo_data(ANO, meses, "realizado", None),
        "indicadores": get_indicadores_data(ANO, meses, "ambos"),
        "controle_despesa": get_controle_despesa_data(ANO, None, quals_despesa, meses),
        "ldo": get_ldo_orcamento_data(ANO),
        "previsao_realizado": get_previsao_realizado_data(ANO, None, meses, quals_todos),
        "comparativa": get_analise_comparativa_data(ANO, ANO - 1, meses, "ambos"),
    }
    # Poda POR RELATÓRIO: as chaves de topo são o contrato de cobertura do
    # R8 e precisam existir mesmo quando o relatório não tem movimento.
    return {
        nome: podar(canonicalizar(restringir_a_ilha(nome, dados)))
        for nome, dados in snapshot.items()
    }


RELATORIOS_COBERTOS = (
    "dfc_mes", "dfc_ano", "kpis", "saldos_diarios_agregado",
    "saldos_diarios_fundo", "resumo", "indicadores", "controle_despesa",
    "ldo", "previsao_realizado", "comparativa",
)


# ---------------------------------------------------------------------------
# Comparação
# ---------------------------------------------------------------------------

def diferencas(esperado, obtido, caminho: str = "") -> list[str]:
    """Lista as divergências entre dois snapshots, com o caminho de cada uma."""
    if isinstance(esperado, dict) and isinstance(obtido, dict):
        saida = []
        for chave in sorted(set(esperado) | set(obtido)):
            sub = f"{caminho}.{chave}" if caminho else str(chave)
            if chave not in esperado:
                saida.append(f"{sub}: ausente na golden (obtido {obtido[chave]!r})")
            elif chave not in obtido:
                saida.append(f"{sub}: ausente no obtido (golden {esperado[chave]!r})")
            else:
                saida.extend(diferencas(esperado[chave], obtido[chave], sub))
        return saida
    if isinstance(esperado, list) and isinstance(obtido, list):
        if len(esperado) != len(obtido):
            return [f"{caminho}: tamanho {len(esperado)} → {len(obtido)}"]
        saida = []
        for i, (e, o) in enumerate(zip(esperado, obtido)):
            saida.extend(diferencas(e, o, f"{caminho}[{i}]"))
        return saida
    if esperado != obtido:
        return [f"{caminho}: golden {esperado!r} ≠ obtido {obtido!r}"]
    return []


def salvar_golden(snapshot: dict) -> None:
    caminho = caminho_golden()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def carregar_golden() -> dict:
    return json.loads(caminho_golden().read_text(encoding="utf-8"))
