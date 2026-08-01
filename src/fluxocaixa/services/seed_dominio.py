"""Seed de dados de domínio (regra dos 3 baldes).

Dados que o sistema precisa para funcionar em QUALQUER instalação,
independente do seed de demonstração (`SEED_DEMO_DATA`):

- Tipos de lançamento (Entrada/Saída)
- Origens de lançamento (Manual/Automático/Importado)
- Definições de parâmetros globais de fórmulas (nome/descrição/tipo)

Idempotente e não destrutivo: cria apenas linhas faltantes por chave
natural; nunca altera nem remove linhas existentes (edições do usuário
são preservadas).
"""
import os

from ..config import modo_demo
from ..models import OrigemLancamento, TipoLancamento, Usuario
from ..models.base import db
from ..models.categoria_fiscal import (
    BASE_DESPESA_TOTAL, BASE_RCL, SENTIDO_PISO, SENTIDO_TETO, CategoriaFiscal,
)
from ..models.formula import ParametroGlobal

# (código, descrição) — PK textual desde a F6.1b; o autoincremento
# deixou de existir, então a chave é explícita. Idempotente por chave.
TIPOS_LANCAMENTO = [("C", "Entrada"), ("D", "Saída")]

ORIGENS_LANCAMENTO = ["Manual", "Automático", "Importado"]

# (sigla, descrição, base de cálculo, sentido, limite, limite de atenção) — F6.5
# ⚠️ Valores de PARTIDA, não verdades: o piso da saúde é 15% para municípios e
# 12% para estados, e o limite de pessoal da LRF reparte por poder. É por isso
# que moram em tabela e não no código — e por isso o seed NUNCA altera o que já
# existe: a SEFAZ que ajustou o piso não pode ter o ajuste revertido no boot.
CATEGORIAS_FISCAIS = [
    ("PESSOAL", "Despesa com Pessoal", BASE_RCL, SENTIDO_TETO, 60, 70),
    ("SAUDE", "Aplicação em Saúde", BASE_DESPESA_TOTAL, SENTIDO_PISO, 15, None),
    ("EDUCACAO", "Aplicação em Educação", BASE_DESPESA_TOTAL, SENTIDO_PISO, 25, None),
]

# (nom_parametro, dsc_parametro, cod_tipo) — 'P' percentual, 'V' valor absoluto
PARAMETROS_GLOBAIS = [
    # Macro
    ("ipca", "Índice Nacional de Preços ao Consumidor Amplo", "P"),
    ("pib", "Crescimento Real do PIB", "P"),
    ("pib_real", "Crescimento real do PIB estadual", "P"),
    ("selic", "Taxa Selic Meta", "P"),
    ("populacao", "Crescimento Populacional", "P"),
    ("elasticidade", "Elasticidade-renda do tributo", "V"),
    # ICMS/IPVA/ITCMD
    ("efeito_legislacao", "Efeito ± de mudanças legais (R$)", "V"),
    ("variacao_frota", "Crescimento líquido da frota tributável (SENATRAN)", "P"),
    ("variacao_fipe", "Variação média da tabela FIPE veículos usados", "P"),
    ("crescimento_transacoes", "Variação estimada no volume de transmissões ITCMD", "P"),
    # Fundo de combate à pobreza
    ("percentual_fundo_pobreza_sobre_icms", "Participação histórica do fundo de combate à pobreza sobre o ICMS (ex: 0.05)", "P"),
    # Aplicações financeiras
    ("saldo_medio_aplicado", "Saldo médio projetado das disponibilidades aplicadas (R$)", "V"),
    ("taxa_selic_projetada", "Selic média projetada para o exercício (Focus/BCB)", "P"),
    ("fator_eficiencia", "% da Selic efetivamente capturado (0.85 a 0.98)", "P"),
    # Folha de pessoal
    ("folha_atual_anualizada", "Folha mensal atual × 13 anualizada (R$)", "V"),
    ("vegetativo", "Crescimento vegetativo da folha: progressões, anuênios", "P"),
    ("reajuste_previsto", "Reajuste salarial previsto em lei", "P"),
    ("impacto_novas_admissoes", "R$ estimado de concursos/contratações previstos", "V"),
    # IR retido
    ("aliquota_efetiva_ir", "Alíquota efetiva média de IRRF sobre a folha (0.06 a 0.10)", "P"),
    # Custeio
    ("contratos_novos_previstos", "R$ de novas contratações previstas para o exercício", "V"),
    # FPE
    ("receita_federal_projetada_ir_ipi", "Projeção federal de IR+IPI (PLOA União ou STN)", "V"),
    ("coeficiente_fpe_uf", "Coeficiente da UF no FPE (fixado pelo TCU anualmente)", "P"),
    ("deducao_fundeb", "Dedução FUNDEB (20%) + PASEP (1%) = 0.21", "P"),
    # Derivadas — receitas
    ("projecao_icms", "ICMS projetado — resultado da fórmula ICMS (R$)", "V"),
    ("projecao_ipva", "IPVA projetado — resultado da fórmula IPVA (R$)", "V"),
    ("projecao_itcmd", "ITCMD projetado — resultado da fórmula ITCMD (R$)", "V"),
    ("projecao_fpe_bruto", "FPE bruto projetado antes de deduções (R$)", "V"),
    ("projecao_folha_bruta", "Folha bruta projetada — resultado da fórmula FOLHA (R$)", "V"),
    ("repasse_fundeb", "Valor FUNDEB projetado — resultado da fórmula FUNDEB (R$)", "V"),
    # Derivadas — despesas / totais
    ("receita_corrente_projetada_total", "Soma de todas as receitas correntes projetadas (R$)", "V"),
    ("receita_impostos_transferencias", "Base: impostos próprios + transferências constitucionais (R$)", "V"),
    ("rcl_projetada", "Receita Corrente Líquida projetada (R$)", "V"),
    ("percentual_limite_poder", "% da RCL do duodécimo de cada Poder (LDO/CE)", "P"),
]


def seed_dominio(session=None):
    """Cria as linhas de domínio faltantes; nunca toca nas existentes."""
    session = session or db.session

    existentes = {t.cod_tipo_lancamento for t in TipoLancamento.query.all()}
    for cod, dsc in TIPOS_LANCAMENTO:
        if cod not in existentes:
            session.add(TipoLancamento(cod_tipo_lancamento=cod,
                                       dsc_tipo_lancamento=dsc))

    existentes = {o.dsc_origem_lancamento for o in OrigemLancamento.query.all()}
    for dsc in ORIGENS_LANCAMENTO:
        if dsc not in existentes:
            session.add(OrigemLancamento(dsc_origem_lancamento=dsc, ind_status='A'))

    existentes = {p.nom_parametro for p in ParametroGlobal.query.all()}
    for nom, dsc, tipo in PARAMETROS_GLOBAIS:
        if nom not in existentes:
            session.add(ParametroGlobal(nom_parametro=nom, dsc_parametro=dsc, cod_tipo=tipo))

    existentes = {c.txt_sigla for c in CategoriaFiscal.query.all()}
    for sigla, dsc, base, sentido, limite, atencao in CATEGORIAS_FISCAIS:
        if sigla not in existentes:
            session.add(CategoriaFiscal(
                txt_sigla=sigla, dsc_categoria=dsc, cod_base_calculo=base,
                cod_sentido=sentido, val_limite=limite,
                val_limite_atencao=atencao, ind_status='A',
            ))

    # Tipos de origem de saldo (domínio fixo). Sistemas de origem NÃO são
    # seedados — cada instalação cadastra os seus (spec saldo-por-fundo R1).
    from ..models import TipoOrigemSaldo

    existentes = {t.txt_sigla for t in TipoOrigemSaldo.query.all()}
    for sigla, dsc in [
        ("MANUAL", "Lançado manualmente pela tesouraria"),
        ("AUTOMATIZADO", "Extraído automaticamente de sistema de origem"),
        ("IMPORTADO", "Importado por arquivo (CSV/XLSX)"),
    ]:
        if sigla not in existentes:
            session.add(TipoOrigemSaldo(txt_sigla=sigla, dsc_tipo_origem=dsc))

    # Administrador inicial: criado apenas se não existir; nunca sobrescreve
    # a senha de um admin já cadastrado (spec controle-acesso R4).
    if not Usuario.query.filter_by(nom_usuario='admin').first():
        from ..auth.service import gerar_hash

        session.add(
            Usuario(
                nom_usuario='admin',
                nom_completo='Administrador',
                txt_hash_senha=gerar_hash(os.getenv('ADMIN_INITIAL_PASSWORD', 'admin')),
                # Em demo pública a troca obrigatória seria contraproducente: o
                # primeiro visitante definiria a senha e trancaria os demais.
                ind_troca_senha='N' if modo_demo() else 'S',
                ind_status='A',
            )
        )

    session.commit()

    _seed_perfis_permissoes(session)


def _seed_perfis_permissoes(session):
    """Catálogo FC_* + perfis + matriz default (spec controle-acesso R7).

    Respeita customizações da instalação: vínculos perfil↔permissão da matriz
    default só são criados para permissões RECÉM-criadas por este seed, e o
    admin só é vinculado a perfis recém-criados — remoções feitas pela SEFAZ
    nunca são recriadas.
    """
    from ..auth.catalogo import DESCRICAO_PERFIS, MATRIZ_PERFIS, PERMISSOES
    from ..models import Perfil, PerfilPermissao, Permissao, UsuarioPerfil

    existentes = {p.cod_permissao for p in Permissao.query.all()}
    permissoes_novas = {}
    for cod, dsc in PERMISSOES:
        if cod not in existentes:
            permissao = Permissao(cod_permissao=cod, dsc_permissao=dsc)
            session.add(permissao)
            permissoes_novas[cod] = permissao

    perfis = {p.cod_perfil: p for p in Perfil.query.all()}
    perfis_novos = set()
    for cod_perfil, dsc in DESCRICAO_PERFIS.items():
        if cod_perfil not in perfis:
            perfil = Perfil(cod_perfil=cod_perfil, dsc_perfil=dsc)
            session.add(perfil)
            perfis[cod_perfil] = perfil
            perfis_novos.add(cod_perfil)

    session.commit()  # garante PKs para os vínculos

    for cod_perfil, cods in MATRIZ_PERFIS.items():
        perfil = perfis[cod_perfil]
        for cod in cods:
            if cod in permissoes_novas:
                session.add(
                    PerfilPermissao(
                        seq_perfil=perfil.seq_perfil,
                        seq_permissao=permissoes_novas[cod].seq_permissao,
                    )
                )

    admin = Usuario.query.filter_by(nom_usuario='admin').first()
    if admin:
        for cod_perfil in perfis_novos:
            session.add(
                UsuarioPerfil(
                    seq_usuario=admin.seq_usuario,
                    seq_perfil=perfis[cod_perfil].seq_perfil,
                )
            )

    session.commit()
