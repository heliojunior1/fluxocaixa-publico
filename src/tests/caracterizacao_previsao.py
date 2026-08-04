"""Rede de caracterização da previsão (F6.2, spec previsao R4).

Congela **dois níveis**, e a ordem importa: a golden é gerada sobre o modelo
ANTIGO (quatro tabelas) e tem de bater depois da unificação. É a única prova de
que colapsar os ramos espelhados de `executar_simulacao` não moveu número.

1. **A série histórica que ALIMENTA os modelos** — valor por (qualificador,
   período). Determinística, não depende de lib de ML, e é exatamente onde a
   F6.1b deixou passar um resíduo: quatro leituras de instância sobreviveram à
   migração para a costura e inverteram o sinal da despesa em silêncio, porque
   nada congelava esse nível.

2. **A saída de `executar_simulacao`** para os modelos DETERMINÍSTICOS —
   MANUAL, FORMULA, CRESCIMENTO_ANO, MEDIA_CRESCIMENTO, LOA, MEDIA_HISTORICA.
   FORMULA congela a FORMA (96 linhas por perna) e não valores: a massa não
   cadastra `flc_rubrica_formula`, então o motor devolve a grade zerada. Ainda
   assim pega mudança de grade — que é o que o colapso do despacho pode quebrar.

⚠️ **Mudança de número DECLARADA** (única prevista na F6.2): `MEDIA_HISTORICA`
projeta ZERO para despesa hoje, porque `projetar_media_historica` aplica um
piso `max(valor, 0)` sobre uma série que chega negativa — bug anterior a toda
esta fase. O D7 (convenção única de magnitude, ENTRADA e saída) o consertou, e a golden
deste modelo mudou de zero para valores reais — regenerada em 22/07/2026 por
esse motivo, e só por ele: a comparação acusou divergência em
`simulacoes.MEDIA_HISTORICA` e em NENHUM outro ponto. Ficou escrito aqui antes
de acontecer, e a previsão se confirmou.

Nota de implementação: a magnitude precisou valer para a ENTRADA dos modelos,
não só para a saída. `projetar_media_historica` aplica `max(valor, 0)` — com a
série chegando negativa, projetava zero e o `abs()` na saída não recuperava
nada.

⚠️ O **treino** dos econométricos (HOLT_WINTERS, ARIMA, SARIMA, REGRESSAO,
XGBOOST, LIGHTGBM) fica de fora por decisão explícita: depende de libs
opcionais (o XGBoost deste ambiente nem carrega, falta `libomp`) e não é
reprodutível o bastante para golden. A entrada deles, porém, está no nível 1.

Ilha de datas **2017** (2019 é da rede de lançamento; 2022–2026 do seed;
2031–2038 das demais features), portanto anterior ao seed — mesma razão da
outra rede: nada do seed alcança.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

ANO_BASE = 2017
ANO_HISTORICO = ANO_BASE - 1

CONTA = ("903", "0003", "PREV-1")
QUAL_RECEITA = "1.97.1"
QUAL_RECEITA_2 = "1.97.2"
QUAL_DESPESA = "2.97.1"
QUAL_DESPESA_2 = "2.97.2"

# Modelos determinísticos cobertos no nível 2 (ver docstring)
MODELOS_DETERMINISTICOS = (
    "MANUAL", "FORMULA", "CRESCIMENTO_ANO", "MEDIA_CRESCIMENTO",
    "LOA", "MEDIA_HISTORICA",
)


def caminho_golden() -> Path:
    return (
        Path(__file__).resolve().parent
        / "fixtures" / "caracterizacao" / "golden_previsao.json"
    )


# ---------------------------------------------------------------------------
# Massa
# ---------------------------------------------------------------------------

def _db():
    from fluxocaixa.models.base import db

    return db


def _qualificador(num: str):
    from fluxocaixa.models import Qualificador

    db = _db()
    q = Qualificador.query.filter_by(num_qualificador=num).first()
    if q is not None:
        return q
    partes = num.split(".")
    pai = _qualificador(".".join(partes[:-1])) if len(partes) > 1 else None
    q = Qualificador(num_qualificador=num, dsc_qualificador=f"Rubrica previsão {num}",
                     cod_qualificador_pai=pai.seq_qualificador if pai else None)
    db.session.add(q)
    db.session.commit()
    return q


def _conta():
    from fluxocaixa.models import ContaBancaria

    db = _db()
    banco, ag, num = CONTA
    conta = ContaBancaria.query.filter_by(cod_banco=banco, num_agencia=ag,
                                          num_conta=num).first()
    if conta is None:
        conta = ContaBancaria(cod_banco=banco, num_agencia=ag, num_conta=num,
                              dsc_conta="Conta previsão")
        db.session.add(conta)
        db.session.commit()
    return conta


def _lancamento(qual_num: str, com_sinal: str, dat: date):
    """Grava a partir do valor COM SINAL (o fato econômico), derivando tipo e
    magnitude como a F6.1b faz — assim a massa é estável à convenção."""
    from fluxocaixa.models import Lancamento
    from fluxocaixa.models.lancamento import TIPO_CREDITO, TIPO_DEBITO
    from fluxocaixa.services.dominio_lancamento import resolver_origem

    db = _db()
    valor = Decimal(com_sinal)
    db.session.add(Lancamento(
        dat_lancamento=dat,
        seq_qualificador=_qualificador(qual_num).seq_qualificador,
        val_lancamento=abs(valor),
        cod_tipo_lancamento=TIPO_CREDITO if valor >= 0 else TIPO_DEBITO,
        cod_origem_lancamento=resolver_origem("Manual").cod_origem_lancamento,
        seq_conta=_conta().seq_conta,
        cod_pessoa_inclusao=1,
        ind_status='A',
    ))
    db.session.commit()


def limpar_massa() -> None:
    from sqlalchemy import extract

    from fluxocaixa.models import Lancamento, SimuladorCenario

    db = _db()
    db.session.rollback()
    Lancamento.query.filter(
        extract("year", Lancamento.dat_lancamento).in_([ANO_BASE, ANO_HISTORICO])
    ).delete(synchronize_session=False)
    for cenario in SimuladorCenario.query.filter(
        SimuladorCenario.nom_cenario.like("Caracterização %")
    ).all():
        db.session.delete(cenario)
    db.session.commit()


def montar_historico() -> None:
    """Série histórica determinística — a ENTRADA dos modelos (nível 1)."""
    limpar_massa()
    for mes in range(1, 13):
        # receita cresce com o mês; despesa é negativa (efeito no caixa)
        _lancamento(QUAL_RECEITA, str(1000 + mes * 10), date(ANO_HISTORICO, mes, 15))
        _lancamento(QUAL_RECEITA_2, "500.00", date(ANO_HISTORICO, mes, 15))
        _lancamento(QUAL_DESPESA, str(-(400 + mes * 5)), date(ANO_HISTORICO, mes, 15))
        _lancamento(QUAL_DESPESA_2, "-200.00", date(ANO_HISTORICO, mes, 15))
    # um mês do ano-base, para acumulados parciais
    _lancamento(QUAL_RECEITA, "1100.00", date(ANO_BASE, 1, 15))
    _lancamento(QUAL_DESPESA, "-450.00", date(ANO_BASE, 1, 15))


# ---------------------------------------------------------------------------
# Nível 1 — série de entrada
# ---------------------------------------------------------------------------

def coletar_series() -> dict:
    """Séries históricas por qualificador, como os modelos as recebem."""
    from fluxocaixa.services import modelos_economicos_service as modelos

    inicio, fim = date(ANO_HISTORICO, 1, 1), date(ANO_BASE, 12, 31)
    saida = {}
    for num in (QUAL_RECEITA, QUAL_RECEITA_2, QUAL_DESPESA, QUAL_DESPESA_2):
        seq = _qualificador(num).seq_qualificador
        dados = modelos.obter_dados_historicos(seq, inicio, fim)
        saida[num] = [
            {"data": str(linha["data"])[:10], "valor": _num(linha["valor"])}
            for _, linha in dados.iterrows()
        ]
    agregado = modelos.obter_dados_historicos_agregados(
        [_qualificador(QUAL_DESPESA).seq_qualificador,
         _qualificador(QUAL_DESPESA_2).seq_qualificador], inicio, fim)
    saida["agregado_despesa"] = [
        {"data": str(linha["data"])[:10], "valor": _num(linha["valor"])}
        for _, linha in agregado.iterrows()
    ]
    return saida


# ---------------------------------------------------------------------------
# Nível 2 — saída dos modelos determinísticos
# ---------------------------------------------------------------------------

def _num(valor) -> str:
    return str(Decimal(str(round(float(valor), 2))).quantize(Decimal("0.01")))


def _df(dados) -> list:
    if dados is None or len(dados) == 0:
        return []
    linhas = []
    for _, linha in dados.iterrows():
        item = {"data": str(linha["data"])[:10],
                "valor_projetado": _num(linha["valor_projetado"])}
        if "seq_qualificador" in dados.columns and linha.get("seq_qualificador") is not None:
            # o surrogate não é fato: identifica pelo código do qualificador
            from fluxocaixa.models import Qualificador

            q = Qualificador.query.get(int(linha["seq_qualificador"]))
            item["qualificador"] = q.num_qualificador if q else None
        linhas.append(item)
    linhas.sort(key=lambda i: json.dumps(i, sort_keys=True))
    return linhas


def coletar_simulacoes() -> dict:
    """Executa um cenário por modelo determinístico e congela a saída."""
    from fluxocaixa.services.simulador_cenario_service import executar_simulacao

    saida = {}
    for nome, seq in _cenarios_deterministicos().items():
        resultado = executar_simulacao(seq)
        if resultado is None:
            saida[nome] = None
            continue
        saida[nome] = {
            "receita": _df(resultado.get("projecao_receita")),
            "despesa": _df(resultado.get("projecao_despesa")),
            "receita_detalhada": _df(resultado.get("projecao_receita_detalhada")),
            "despesa_detalhada": _df(resultado.get("projecao_despesa_detalhada")),
            "resumo": {k: _num(v) for k, v in (resultado.get("resumo") or {}).items()},
        }
    return saida


def _cenarios_deterministicos() -> dict:
    """Cria (idempotente) um cenário por combinação determinística e devolve
    `{nome: seq}`. As pernas são escolhidas para casar com o catálogo: modelos
    exclusivos de despesa (LOA, MEDIA_HISTORICA) vão na perna de despesa."""
    from fluxocaixa.models import SimuladorCenario
    from fluxocaixa.services.simulador_cenario_service import criar_simulador_cenario

    quals_receita = [_qualificador(QUAL_RECEITA).seq_qualificador,
                     _qualificador(QUAL_RECEITA_2).seq_qualificador]
    quals_despesa = [_qualificador(QUAL_DESPESA).seq_qualificador,
                     _qualificador(QUAL_DESPESA_2).seq_qualificador]

    combos = {
        "MANUAL": ("MANUAL", {}, "MANUAL", {}),
        "FORMULA": ("FORMULA", {}, "FORMULA", {}),
        "CRESCIMENTO_ANO": (
            "CRESCIMENTO_ANO", {"seq_qualificadores": quals_receita, "mes_referencia": 6},
            "CRESCIMENTO_ANO", {"seq_qualificadores": quals_despesa, "mes_referencia": 6}),
        "MEDIA_CRESCIMENTO": (
            "MEDIA_CRESCIMENTO", {"seq_qualificadores": quals_receita, "mes_referencia": 6},
            "MEDIA_CRESCIMENTO", {"seq_qualificadores": quals_despesa, "mes_referencia": 6}),
        # projetar_loa lê `valor_anual` da CONFIG (não a tabela flc_loa)
        "LOA": ("MANUAL", {}, "LOA", {"valor_anual": 9000, "distribuicao": "uniforme"}),
        "MEDIA_HISTORICA": (
            "MANUAL", {},
            "MEDIA_HISTORICA", {"seq_qualificadores": quals_despesa, "periodo_meses": 12}),
    }

    # Formato achatado do form web: val_ajuste_<mês>_<qualificador> +
    # cod_tipo_ajuste_<mês>_<qualificador> (ver _criar_ajustes_receita)
    def _ajustes(quals, prefixo=""):
        """`prefixo="desp_"` para a perna de despesa — o parser separa as duas
        pernas pelo prefixo da chave (ver _criar_ajustes_receita/_despesa)."""
        dados = {}
        for mes in range(1, 13):
            for seq in quals:
                dados[f"val_ajuste_{prefixo}{mes}_{seq}"] = 10 if mes % 2 else 250
                dados[f"cod_tipo_ajuste_{prefixo}{mes}_{seq}"] = "P" if mes % 2 else "V"
        return dados

    ajustes_r = _ajustes(quals_receita)
    ajustes_d = _ajustes(quals_despesa, prefixo="desp_")

    seqs = {}
    for nome, (tipo_r, cfg_r, tipo_d, cfg_d) in combos.items():
        rotulo = f"Caracterização {nome}"
        existente = SimuladorCenario.query.filter_by(nom_cenario=rotulo).first()
        if existente is None:
            existente = criar_simulador_cenario(
                nom_cenario=rotulo, dsc_cenario=f"Rede F6.2 — {nome}",
                ano_base=ANO_BASE, num_periodos=12,
                tipo_cenario_receita=tipo_r,
                config_receita={**cfg_r, "seq_qualificadores": quals_receita},
                tipo_cenario_despesa=tipo_d,
                config_despesa={**cfg_d, "seq_qualificadores": quals_despesa},
                ajustes_receita=ajustes_r if tipo_r == "MANUAL" else None,
                ajustes_despesa=ajustes_d if tipo_d == "MANUAL" else None,
                user_id=1, cod_periodicidade="MENSAL",
                json_config_base=json.dumps({"anos": [ANO_HISTORICO]}),
            )
        seqs[nome] = existente.seq_simulador_cenario

    _garantir_parametros_formula(seqs["FORMULA"])
    return seqs


def _garantir_parametros_formula(seq_cenario: int) -> None:
    """Registra valor 0 para toda variável das fórmulas cadastradas (demo).

    O Q04 (previsao R12) tornou parâmetro faltante um `RegraNegocioError`
    explícito — a massa dependia do fallback silencioso (faltante → base).
    Com todas as variáveis em 0, a projeção avalia para a própria base, que
    na ilha 2017 é 0 para os qualificadores da demo: a grade congelada na
    golden permanece IDÊNTICA, e é por isso que a golden não foi regerada.
    """
    from fluxocaixa.models import RubricaFormula
    from fluxocaixa.models.base import db
    from fluxocaixa.models.formula import CenarioParametroValor
    from fluxocaixa.services.formula_engine import extrair_variaveis

    variaveis = set()
    for formula in RubricaFormula.query.all():
        variaveis.update(extrair_variaveis(formula.dsc_formula_expressao))
    variaveis.discard("base")

    existentes = {v.nom_parametro for v in CenarioParametroValor.query
                  .filter_by(seq_simulador_cenario=seq_cenario).all()}
    for nome in sorted(variaveis - existentes):
        db.session.add(CenarioParametroValor(
            seq_simulador_cenario=seq_cenario, nom_parametro=nome,
            val_parametro=0))
    db.session.commit()


# ---------------------------------------------------------------------------
# Snapshot / golden
# ---------------------------------------------------------------------------

def coletar_snapshot() -> dict:
    montar_historico()
    return {"series": coletar_series(), "simulacoes": coletar_simulacoes()}


def diferencas(esperado, obtido, caminho: str = "") -> list[str]:
    from .caracterizacao import diferencas as _dif

    return _dif(esperado, obtido, caminho)


def salvar_golden(snapshot: dict) -> None:
    caminho = caminho_golden()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8")


def carregar_golden() -> dict:
    return json.loads(caminho_golden().read_text(encoding="utf-8"))
