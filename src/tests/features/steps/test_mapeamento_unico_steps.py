"""Steps BDD — mapeamento único sem dimensão receita/despesa (R6/R13).

Ilha 2074. Import tardio de `fluxocaixa`. Usa a assinatura NOVA de
`criar_mapeamento` (sem ind_tipo) — nasce vermelho enquanto ela não existir.
"""
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ..conftest_extracao import garantir_sistema_origem
from .conftest_processamento import limpar_estado_processamento, semear_staging
from .conftest_regra import garantir_termos_padrao

scenarios("../automacao-lancamentos/mapeamento_unico.feature")

ANO = 2074
RECEITA = "1.76.1"
DESPESA = "2.76.1"


@pytest.fixture()
def contexto():
    return {}


@pytest.fixture(autouse=True)
def _limpo(app):
    limpar_estado_processamento()


def _folha_com_pai(num):
    """Folha com a cadeia de pais — tipo_fluxo precisa alcançar a raiz 1/2."""
    from fluxocaixa.models import Qualificador
    from fluxocaixa.models.base import db

    partes = num.split(".")
    pai = None
    for i in range(1, len(partes) + 1):
        codigo = ".".join(partes[:i])
        q = Qualificador.query.filter_by(num_qualificador=codigo).first()
        if q is None:
            q = Qualificador(
                num_qualificador=codigo,
                dsc_qualificador=f"Nó {codigo}",
                cod_qualificador_pai=pai.seq_qualificador if pai else None,
                ind_status='A')
            db.session.add(q)
            db.session.commit()
        pai = q
    return pai


def _criar_mapeamento_unico(contexto, sigla, itens):
    from .conftest_regra import criar_mapeamento

    mapeamento = criar_mapeamento(ANO, sigla, itens)
    contexto["seq_mapeamento"] = mapeamento.seq_mapeamento
    return mapeamento


def _itens_padrao():
    receita = _folha_com_pai(RECEITA)
    despesa = _folha_com_pai(DESPESA)
    return [
        {"seq_qualificador": receita.seq_qualificador,
         "txt_regra": "Natureza começa com '1113'"},
        {"seq_qualificador": despesa.seq_qualificador,
         "txt_regra": "Natureza começa com '2223'"},
    ]


@given("que estou autenticado como administrador no mapeamento único")
def autenticado(app, _admin_pronto):
    from fluxocaixa.auth.contexto import definir_usuario_corrente

    definir_usuario_corrente(777)


@given(parsers.parse('um sistema de origem "{sigla}" cadastrado para o '
                     'mapeamento único'))
def sistema(app, sigla):
    garantir_sistema_origem(sigla)


@given("os termos de regra padrão cadastrados para o mapeamento único")
def termos(app):
    garantir_termos_padrao()


@given(parsers.parse('uma folha de receita "{r}" e uma folha de despesa "{d}"'))
def folhas(app, r, d):
    _folha_com_pai(r)
    _folha_com_pai(d)


@given(parsers.parse('o mapeamento {ano:d} de "{sigla}" com item de receita '
                     '"{r}" e item de despesa "{d}"'))
def mapeamento_misto_dado(app, contexto, ano, sigla, r, d):
    _criar_mapeamento_unico(contexto, sigla, _itens_padrao())


@given(parsers.parse('linhas na staging de "{sigla}" em {ano:d} com receita '
                     '{v1}, dedução {v2} e despesa {v3}'))
def staging_mista(app, sigla, ano, v1, v2, v3):
    semear_staging(sigla, f"Fonte {sigla}", [
        {"natureza": "11130000", "ug": "999001", "valor": v1},
        {"natureza": "11139999", "ug": "999001", "valor": v2},  # dedução
        {"natureza": "22230000", "ug": "999001", "valor": v3},
    ], ano=ano)


@given(parsers.parse('o mapeamento {ano:d} de "{sigla}" com regras de '
                     'receita, dedução e despesa'))
def mapeamento_com_deducao(app, contexto, ano, sigla):
    """Bruta e dedução em folhas IRMÃS da mesma árvore de receita (1.76.x):
    dois itens ativos não podem repetir qualificador, e é assim que o domínio
    modela — a dedução é uma rubrica própria que neta a bruta na árvore."""
    receita = _folha_com_pai(RECEITA)          # 1.76.1 — bruta
    deducao = _folha_com_pai("1.76.2")         # 1.76.2 — dedução
    despesa = _folha_com_pai(DESPESA)          # 2.76.1
    _criar_mapeamento_unico(contexto, sigla, [
        {"seq_qualificador": receita.seq_qualificador,
         "txt_regra": "Natureza começa com '1113' e Natureza <> '11139999'"},
        {"seq_qualificador": deducao.seq_qualificador,
         "txt_regra": "Natureza = '11139999'"},
        {"seq_qualificador": despesa.seq_qualificador,
         "txt_regra": "Natureza começa com '2223'"},
    ])


@when(parsers.parse('crio o mapeamento {ano:d} de "{sigla}" com item de '
                    'receita "{r}" e item de despesa "{d}"'))
def cria_mapeamento_misto(app, contexto, ano, sigla, r, d):
    _criar_mapeamento_unico(contexto, sigla, _itens_padrao())


@when(parsers.parse('tento criar outro mapeamento {ano:d} de "{sigla}"'))
def tenta_duplicar(app, contexto, ano, sigla):
    from fluxocaixa.services.validacao import RegraNegocioError

    try:
        _criar_mapeamento_unico(contexto, sigla, _itens_padrao()[:1])
        contexto["erro"] = None
    except RegraNegocioError as exc:
        contexto["erro"] = exc


@when("processo o mapeamento único")
def processa(app, contexto):
    from fluxocaixa.services.processamento_service import processar_mapeamento

    contexto["execucao"] = processar_mapeamento(
        contexto["seq_mapeamento"], disparo="MANUAL")


def _lancamentos_da_subarvore(num_raiz):
    """Lançamentos ativos da rubrica e de suas folhas descendentes."""
    from fluxocaixa.models import Lancamento, Qualificador
    from fluxocaixa.models.base import db

    db.session.expire_all()
    seqs = [q.seq_qualificador for q in Qualificador.query.all()
            if q.num_qualificador == num_raiz
            or q.num_qualificador.startswith(num_raiz + ".")]
    return Lancamento.query.filter(
        Lancamento.seq_qualificador.in_(seqs),
        Lancamento.ind_status == 'A').all()


@then(parsers.parse('o mapeamento de "{sigla}" em {ano:d} existe ativo com '
                    '{n:d} itens'))
def mapeamento_existe(app, sigla, ano, n):
    from .conftest_regra import mapeamento_por_chave

    mapeamento = mapeamento_por_chave(ano, sigla)
    assert mapeamento is not None and mapeamento.ind_status == 'A'
    ativos = [i for i in mapeamento.itens if i.ind_status == 'A']
    assert len(ativos) == n, len(ativos)


@then("recebo mensagem de negócio de mapeamento duplicado")
def duplicado_recusado(contexto):
    assert contexto["erro"] is not None, (
        "o segundo mapeamento do mesmo (ano, sistema) foi aceito — a "
        "unicidade nova não está valendo")


@then(parsers.parse('a árvore de receita "{num}" tem um crédito de {vc} e '
                    'um débito de {vd}'))
def arvore_tem_credito_e_debito(app, num, vc, vd):
    lancs = _lancamentos_da_subarvore(num)
    creditos = [l for l in lancs if l.cod_tipo_lancamento == 'C']
    debitos = [l for l in lancs if l.cod_tipo_lancamento == 'D']
    assert [l.val_lancamento for l in creditos] == [Decimal(vc)], creditos
    assert [l.val_lancamento for l in debitos] == [Decimal(vd)], debitos


@then(parsers.parse('a rubrica "{num}" tem um débito de {vd}'))
def rubrica_tem_debito(app, num, vd):
    lancs = _lancamentos_da_subarvore(num)
    assert len(lancs) == 1 and lancs[0].cod_tipo_lancamento == 'D', lancs
    assert lancs[0].val_lancamento == Decimal(vd)


@then(parsers.parse('o total líquido da árvore de receita "{num}" é {valor}'))
def total_liquido(app, num, valor):
    lancs = _lancamentos_da_subarvore(num)
    liquido = sum(Decimal(l.valor_com_sinal) for l in lancs)
    assert liquido == Decimal(valor), (
        f"{liquido} — a dedução não está netando a receita bruta")
