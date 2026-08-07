"""Cria usuários de teste E2E — executado pelo start-server.sh antes do uvicorn.

Importa create_app() para migrar/seedar o banco descartável e então garante
um usuário com perfil CONSULTA para os testes de visibilidade por permissão.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from fluxocaixa import create_app  # noqa: E402

create_app()

from fluxocaixa.auth.service import gerar_hash  # noqa: E402
from fluxocaixa.models import Perfil, Usuario, UsuarioPerfil  # noqa: E402
from fluxocaixa.models.base import db  # noqa: E402

LOGIN = "consulta.e2e"
SENHA = "E2e-Consulta-123"

if not Usuario.query.filter_by(nom_usuario=LOGIN).first():
    usuario = Usuario(
        nom_usuario=LOGIN,
        nom_completo="Usuário Consulta (E2E)",
        txt_hash_senha=gerar_hash(SENHA),
        ind_troca_senha='N',
        ind_status='A',
    )
    db.session.add(usuario)
    db.session.commit()

    perfil = Perfil.query.filter_by(cod_perfil='CONSULTA').first()
    db.session.add(UsuarioPerfil(seq_usuario=usuario.seq_usuario, seq_perfil=perfil.seq_perfil))
    db.session.commit()

# Usuário de perfil EXTRACAO — telas de extração (executa/consulta fontes)
LOGIN_EXTRACAO = "extracao.e2e"
SENHA_EXTRACAO = "E2e-Extracao-123"
if not Usuario.query.filter_by(nom_usuario=LOGIN_EXTRACAO).first():
    usuario_ext = Usuario(
        nom_usuario=LOGIN_EXTRACAO,
        nom_completo="Usuário Extração (E2E)",
        txt_hash_senha=gerar_hash(SENHA_EXTRACAO),
        ind_troca_senha='N',
        ind_status='A',
    )
    db.session.add(usuario_ext)
    db.session.commit()
    perfil_ext = Perfil.query.filter_by(cod_perfil='EXTRACAO').first()
    db.session.add(UsuarioPerfil(seq_usuario=usuario_ext.seq_usuario, seq_perfil=perfil_ext.seq_perfil))
    db.session.commit()

# Qualificador dedicado com lançamento — usado pelo teste de exclusão com
# confirmação (validacoes.spec.ts). Fica numa raiz própria (9) para não
# interferir na árvore de demonstração.
from datetime import date  # noqa: E402
from decimal import Decimal  # noqa: E402

from fluxocaixa.models import Lancamento, OrigemLancamento, Qualificador, TipoLancamento  # noqa: E402

if not Qualificador.query.filter_by(num_qualificador='9.9.9').first():
    q = Qualificador(
        num_qualificador='9.9.9',
        dsc_qualificador='Rubrica E2E Exclusao',
        ind_status='A',
    )
    db.session.add(q)
    db.session.commit()

    tipo = TipoLancamento.query.filter_by(dsc_tipo_lancamento='Entrada').first()
    origem = OrigemLancamento.query.filter_by(dsc_origem_lancamento='Manual').first()
    db.session.add(
        Lancamento(
            dat_lancamento=date(2026, 7, 1),
            seq_qualificador=q.seq_qualificador,
            val_lancamento=Decimal("123.45"),
            cod_tipo_lancamento=tipo.cod_tipo_lancamento,
            cod_origem_lancamento=origem.cod_origem_lancamento,
            cod_pessoa_inclusao=1,
            ind_status='A',
        )
    )
    db.session.commit()

# Usuário dedicado ao teste de revogação de sessão (seguranca.spec.ts). Precisa
# ser SÓ dele: o teste troca a senha, o que revoga todas as sessões daquele
# usuário — usar o admin derrubaria o storageState dos outros specs.
from fluxocaixa.auth.service import gerar_hash as _gerar_hash  # noqa: E402
from fluxocaixa.models.usuario import Usuario as _Usuario  # noqa: E402

if _Usuario.query.filter_by(nom_usuario='sessao.e2e').first() is None:
    _u = _Usuario(
        nom_usuario='sessao.e2e',
        nom_completo='Usuário Sessão E2E',
        txt_hash_senha=_gerar_hash('E2e-Sessao-123'),
        ind_troca_senha='N',
        ind_status='A',
    )
    db.session.add(_u)
    db.session.commit()
    _perfil = Perfil.query.filter_by(cod_perfil='CONSULTA').first()
    db.session.add(UsuarioPerfil(seq_usuario=_u.seq_usuario,
                                 seq_perfil=_perfil.seq_perfil))
    db.session.commit()

# Usuário dedicado ao teste de bloqueio por tentativas (seguranca.spec.ts).
# Precisa ser SÓ dele: o teste o bloqueia por 15 minutos de propósito, e
# bloquear um usuário compartilhado derrubaria os demais specs.
if _Usuario.query.filter_by(nom_usuario='bloqueio.e2e').first() is None:
    _ub = _Usuario(
        nom_usuario='bloqueio.e2e',
        nom_completo='Usuário Bloqueio E2E',
        txt_hash_senha=_gerar_hash('E2e-Bloqueio-123'),
        ind_troca_senha='N',
        ind_status='A',
    )
    db.session.add(_ub)
    db.session.commit()
    db.session.add(UsuarioPerfil(
        seq_usuario=_ub.seq_usuario,
        seq_perfil=Perfil.query.filter_by(cod_perfil='CONSULTA').first().seq_perfil))
    db.session.commit()

# Rubrica com marcação HTML na descrição, para o teste de XSS armazenado
# (seguranca.spec.ts). A descrição é campo LIVRE — o serviço valida o formato do
# CÓDIGO e a unicidade, não o conteúdo —, e é assim que o payload entra pela
# porta legítima de cadastro (perfil OPERADOR basta). Raiz própria (8) para não
# poluir a árvore de demonstração nem o DFC dos outros specs.
_DSC_XSS = '<img src=x onerror="window.__xss_e2e=1">Rubrica'
if not Qualificador.query.filter_by(num_qualificador='8.8.8').first():
    _q_xss = Qualificador(
        num_qualificador='8.8.8',
        dsc_qualificador=_DSC_XSS,
        ind_status='A',
    )
    db.session.add(_q_xss)
    db.session.commit()

    _tipo = TipoLancamento.query.filter_by(dsc_tipo_lancamento='Entrada').first()
    _origem = OrigemLancamento.query.filter_by(dsc_origem_lancamento='Manual').first()
    db.session.add(
        Lancamento(
            dat_lancamento=date(2026, 7, 1),
            seq_qualificador=_q_xss.seq_qualificador,
            val_lancamento=Decimal("456.78"),
            cod_tipo_lancamento=_tipo.cod_tipo_lancamento,
            cod_origem_lancamento=_origem.cod_origem_lancamento,
            cod_pessoa_inclusao=1,
            ind_status='A',
        )
    )
    db.session.commit()

# Fundo pendente de revisão para o teste de aprovação (fundos.spec.ts).
from fluxocaixa.models import Fundo, SistemaOrigem  # noqa: E402
from fluxocaixa.services.fundo_service import upsert_fundo_pendente  # noqa: E402

if not SistemaOrigem.query.filter_by(txt_sigla='SIS_E2E').first():
    db.session.add(SistemaOrigem(txt_sigla='SIS_E2E', dsc_sistema_origem='Sistema E2E'))
    db.session.commit()

if not Fundo.query.filter_by(cod_fundo='9911').first():
    upsert_fundo_pendente('9911', 'Fundo Pendente E2E', 'SIS_E2E')

# Conta + saldos no modelo novo — dão conteúdo às visões da tela de saldos
# (agregado e por fundo) e opções aos selects do modal (fundos.spec/saldos).
from datetime import date as _date  # noqa: E402
from decimal import Decimal as _Dec  # noqa: E402

from fluxocaixa.models import ContaBancaria  # noqa: E402
from fluxocaixa.services.fundo_service import criar_fundo, garantir_fundo_geral  # noqa: E402
from fluxocaixa.services.saldo_fundo_service import gravar_saldo  # noqa: E402

if not ContaBancaria.query.filter_by(cod_banco='104', num_agencia='0001', num_conta='E2E-1').first():
    db.session.add(ContaBancaria(cod_banco='104', num_agencia='0001', num_conta='E2E-1',
                                 dsc_conta='Conta E2E'))
    db.session.commit()

# Conta inativa de massa (contas-bancarias.spec.ts — reativação pela tela).
# Dados fictícios, como tudo neste seed.
if not ContaBancaria.query.filter_by(cod_banco='237', num_agencia='0009', num_conta='INAT-1').first():
    db.session.add(ContaBancaria(cod_banco='237', num_agencia='0009', num_conta='INAT-1',
                                 dsc_conta='Conta E2E Inativa', ind_status='I'))
    db.session.commit()

_conta_e2e = ContaBancaria.query.filter_by(cod_banco='104', num_agencia='0001', num_conta='E2E-1').first()
_geral = garantir_fundo_geral()
if not Fundo.query.filter_by(cod_fundo='FIE2E').first():
    criar_fundo('FIE2E', 'Fundo Investimento E2E')
_fie2e = Fundo.query.filter_by(cod_fundo='FIE2E').first()

# Instrumento CDB com carência (change tipo-instrumento-financeiro) — massa
# do filtro por tipo em fundos.spec.ts e do split líquido × carência em
# fontes_recurso.spec.ts. Ilha 2048.
from fluxocaixa.services.fundo_service import resolver_tipo_instrumento  # noqa: E402

if not Fundo.query.filter_by(cod_fundo='CDBE2E').first():
    criar_fundo('CDBE2E', 'CDB Carencia E2E',
                seq_tipo_instrumento=resolver_tipo_instrumento(
                    'CDB').seq_tipo_instrumento,
                ind_liquidez_imediata='N',
                dat_vencimento=_date(2048, 12, 31))
_cdbe2e = Fundo.query.filter_by(cod_fundo='CDBE2E').first()

from fluxocaixa.models import SaldoContaFundo  # noqa: E402

if not SaldoContaFundo.query.filter_by(seq_conta=_conta_e2e.seq_conta).first():
    gravar_saldo(seq_conta=_conta_e2e.seq_conta, seq_fundo=_geral.seq_fundo,
                 dat_saldo=_date(2025, 4, 1), val_saldo=_Dec("100000.00"))
    gravar_saldo(seq_conta=_conta_e2e.seq_conta, seq_fundo=_fie2e.seq_fundo,
                 dat_saldo=_date(2025, 4, 1), val_saldo=_Dec("50000.00"),
                 val_aplicacoes=_Dec("1000.00"))
    # Posição do CDB com carência — alimenta o "aplicado com carência" do
    # painel de disponibilidade (fontes_recurso.spec.ts)
    gravar_saldo(seq_conta=_conta_e2e.seq_conta, seq_fundo=_cdbe2e.seq_fundo,
                 dat_saldo=_date(2025, 4, 1), val_saldo=_Dec("20000.00"))

# --- Editor de layout / conector de arquivo (editor-layout.spec.ts) ---
# Contas (número canônico só-dígitos, como o parser normaliza) + uma pasta
# com um CSV de amostra de nome FIXO (sem placeholder de data → "executar
# agora" no dia corrente o encontra).
for _num in ("123456", "987654"):
    if not ContaBancaria.query.filter_by(cod_banco="104", num_agencia="0001", num_conta=_num).first():
        db.session.add(ContaBancaria(cod_banco="104", num_agencia="0001",
                                     num_conta=_num, dsc_conta=f"Conta arquivo {_num}"))
db.session.commit()

_fixt_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".data", "fixtures")
os.makedirs(_fixt_dir, exist_ok=True)
_amostra = (
    "Banco;Agência;Conta;Data;Descrição;Saldo\n"
    "104;0001;12345-6;10/07/2026;9999-FUNDO ALFA E2E;1.234,56\n"
    "104;0001;98765-4;10/07/2026;8888-FUNDO BETA E2E;7.890,12\n"
)
with open(os.path.join(_fixt_dir, "AMOSTRA_EXTRATO.csv"), "w", encoding="utf-8-sig", newline="") as _f:
    _f.write(_amostra)

# ---------------------------------------------------------------------------
# Motor de mapeamentos (F4.2b): vocabulário + staging para o preview da regra.
# Identificadores TODOS fictícios (repo público): natureza 1112xxxx, UG 999xxx.
# ---------------------------------------------------------------------------
from fluxocaixa.models import (  # noqa: E402
    EtlStaging, ExecucaoExtracao, FonteExtracao, SistemaOrigem, TermoRegra,
)

for _nom, _origem, _campo, _tipo in (
    ("Natureza", "ATRIBUTO", "natureza", "TEXTO"),
    ("Unidade Gestora", "ATRIBUTO", "ug", "TEXTO"),
    ("Valor", "COLUNA", "val_referencia", "NUMERO"),
):
    if not TermoRegra.query.filter_by(nom_termo=_nom).first():
        db.session.add(TermoRegra(nom_termo=_nom, cod_origem_campo=_origem,
                                  nom_campo=_campo, cod_tipo=_tipo, ind_status='A'))
db.session.commit()

_sis = SistemaOrigem.query.filter_by(txt_sigla="SIS_E2E").first()
if _sis is None:
    _sis = SistemaOrigem(txt_sigla="SIS_E2E", dsc_sistema_origem="Sistema E2E")
    db.session.add(_sis)
    db.session.commit()

# Qualificador folha de receita para o item do mapeamento
if not Qualificador.query.filter_by(num_qualificador='1.9.9').first():
    _raiz = Qualificador.query.filter_by(num_qualificador='1').first()
    if _raiz is None:
        _raiz = Qualificador(num_qualificador='1', dsc_qualificador='Receitas E2E',
                             ind_status='A')
        db.session.add(_raiz)
        db.session.commit()
    db.session.add(Qualificador(num_qualificador='1.9.9',
                                dsc_qualificador='Receita E2E Mapeável',
                                cod_qualificador_pai=_raiz.seq_qualificador,
                                ind_status='A'))
    db.session.commit()

# Qualificador folha de DESPESA para o item misto do mapeamento (change
# mapeamento-sem-dimensao-receita-despesa: receita e despesa convivem)
if not Qualificador.query.filter_by(num_qualificador='2.9.9').first():
    _raiz2 = Qualificador.query.filter_by(num_qualificador='2').first()
    if _raiz2 is None:
        _raiz2 = Qualificador(num_qualificador='2', dsc_qualificador='Despesas E2E',
                              ind_status='A')
        db.session.add(_raiz2)
        db.session.commit()
    db.session.add(Qualificador(num_qualificador='2.9.9',
                                dsc_qualificador='Despesa E2E Mapeável',
                                cod_qualificador_pai=_raiz2.seq_qualificador,
                                ind_status='A'))
    db.session.commit()

# Fonte de destino LANCAMENTO + linhas de staging para o preview casar
_fonte = FonteExtracao.query.filter_by(nom_fonte="Fonte E2E Lancamento").first()
if _fonte is None:
    _fonte = FonteExtracao(
        nom_fonte="Fonte E2E Lancamento", cod_tipo_conector="DEMO_MANUAL",
        cod_destino="LANCAMENTO", seq_sistema_origem=_sis.seq_sistema_origem,
        json_config={}, ind_status='A',
    )
    db.session.add(_fonte)
    db.session.commit()

if not EtlStaging.query.filter_by(seq_fonte_extracao=_fonte.seq_fonte_extracao).first():
    _exec = ExecucaoExtracao(
        seq_fonte_extracao=_fonte.seq_fonte_extracao,
        dat_inicio_execucao=date(2026, 7, 10), cod_disparo="MANUAL",
        cod_status="SUCESSO", dat_janela_inicio=date(2026, 7, 10),
        dat_janela_fim=date(2026, 7, 10),
    )
    db.session.add(_exec)
    db.session.flush()
    for _nat, _ug, _val in (("11120001", "999001", "100.00"),
                            ("11120002", "999002", "200.00"),
                            ("22220003", "999001", "300.00")):
        db.session.add(EtlStaging(
            seq_fonte_extracao=_fonte.seq_fonte_extracao,
            seq_execucao_extracao=_exec.seq_execucao_extracao,
            num_ano_exercicio=2026, dat_referencia=date(2026, 7, 10),
            val_referencia=Decimal(_val),
            json_atributos={"natureza": _nat, "ug": _ug, "valor": _val},
            ind_status_processamento='0',
        ))
    db.session.commit()

# --- Processamento (F4.3) --------------------------------------------------
# Sistema de origem PRÓPRIO: a unicidade do mapeamento é (ano, tipo, sistema),
# e o spec da F4.2b cria mapeamentos 2026/Receita em SIS_E2E — disputar o mesmo
# sistema faria um quebrar o outro.
from fluxocaixa.models import ItemMapeamento, Mapeamento  # noqa: E402

_sis_proc = SistemaOrigem.query.filter_by(txt_sigla="SIS_E2E_PROC").first()
if _sis_proc is None:
    _sis_proc = SistemaOrigem(txt_sigla="SIS_E2E_PROC",
                              dsc_sistema_origem="Sistema E2E Processamento")
    db.session.add(_sis_proc)
    db.session.commit()

_fonte_proc = FonteExtracao.query.filter_by(nom_fonte="Fonte E2E Processamento").first()
if _fonte_proc is None:
    _fonte_proc = FonteExtracao(
        nom_fonte="Fonte E2E Processamento", cod_tipo_conector="DEMO_MANUAL",
        cod_destino="LANCAMENTO", seq_sistema_origem=_sis_proc.seq_sistema_origem,
        json_config={}, ind_status='A',
    )
    db.session.add(_fonte_proc)
    db.session.commit()

if not EtlStaging.query.filter_by(
        seq_fonte_extracao=_fonte_proc.seq_fonte_extracao).first():
    _exec_proc = ExecucaoExtracao(
        seq_fonte_extracao=_fonte_proc.seq_fonte_extracao,
        dat_inicio_execucao=date(2026, 7, 10), cod_disparo="MANUAL",
        cod_status="SUCESSO", dat_janela_inicio=date(2026, 7, 10),
        dat_janela_fim=date(2026, 7, 10),
    )
    db.session.add(_exec_proc)
    db.session.flush()
    for _nat, _ug, _val in (("11120001", "999001", "100.00"),
                            ("11120002", "999002", "200.00"),
                            ("22220003", "999001", "300.00")):
        db.session.add(EtlStaging(
            seq_fonte_extracao=_fonte_proc.seq_fonte_extracao,
            seq_execucao_extracao=_exec_proc.seq_execucao_extracao,
            num_ano_exercicio=2026, dat_referencia=date(2026, 7, 10),
            val_referencia=Decimal(_val),
            json_atributos={"natureza": _nat, "ug": _ug, "valor": _val},
            ind_status_processamento='0',
        ))
    db.session.commit()

# regra casa com as 2 linhas de natureza 1112xxxx
if not Mapeamento.query.filter_by(
        seq_sistema_origem=_sis_proc.seq_sistema_origem).first():
    _q = Qualificador.query.filter_by(num_qualificador='1.9.9').first()
    _map = Mapeamento(
        num_ano_exercicio=2026,
        seq_sistema_origem=_sis_proc.seq_sistema_origem,
        dsc_mapeamento='Mapeamento E2E Receita', ind_status='A',
    )
    _map.itens.append(ItemMapeamento(
        seq_qualificador=_q.seq_qualificador,
        txt_regra="Natureza começa com '1112'",
        ind_inversao_sinal='0', ind_status='A',
    ))
    db.session.add(_map)
    db.session.commit()

# ---------------------------------------------------------------------------
# Massa do relatório de KPIs (kpis.spec.ts) — ilha de datas 2031-07, fora do
# alcance do seed demo (2022–2026). Valores fictícios.
# ---------------------------------------------------------------------------
from datetime import datetime  # noqa: E402

from fluxocaixa.models import ContaBancaria, Fundo, TipoOrigemSaldo  # noqa: E402
from fluxocaixa.services.saldo_fundo_service import gravar_saldo  # noqa: E402

def _conta_kpi(cod_banco, num_conta):
    conta = ContaBancaria.query.filter_by(
        cod_banco=cod_banco, num_agencia="0001", num_conta=num_conta
    ).first()
    if conta is None:
        conta = ContaBancaria(cod_banco=cod_banco, num_agencia="0001",
                              num_conta=num_conta, dsc_conta=f"Conta KPI {num_conta}")
        db.session.add(conta)
        db.session.commit()
    return conta

_conta_kpi_1 = _conta_kpi("001", "KPI-1")
_conta_kpi_2 = _conta_kpi("104", "KPI-2")

if Fundo.query.filter_by(cod_fundo="9902").first() is None:
    from fluxocaixa.services.fundo_service import resolver_tipo_instrumento
    _tipo_manual = TipoOrigemSaldo.query.filter_by(txt_sigla="MANUAL").first()
    db.session.add(Fundo(cod_fundo="9902", dsc_fundo="Fundo KPI E2E",
                         seq_tipo_origem=_tipo_manual.seq_tipo_origem_saldo,
                         seq_tipo_instrumento=resolver_tipo_instrumento(
                             'FUNDO').seq_tipo_instrumento))
    db.session.commit()
_fundo_kpi = Fundo.query.filter_by(cod_fundo="9902").first()

from fluxocaixa.models import SaldoContaFundo  # noqa: E402

def _saldo_kpi(conta, dat, valor):
    existe = SaldoContaFundo.query.filter_by(
        seq_conta=conta.seq_conta, seq_fundo=_fundo_kpi.seq_fundo,
        dat_saldo=dat, ind_status='A',
    ).first()
    if existe is None:
        gravar_saldo(seq_conta=conta.seq_conta, seq_fundo=_fundo_kpi.seq_fundo,
                     dat_saldo=dat, val_saldo=Decimal(valor),
                     val_aplicacoes=Decimal("0"), val_resgates=Decimal("0"),
                     sigla_tipo_origem="MANUAL", sigla_sistema_origem=None)

_saldo_kpi(_conta_kpi_1, date(2031, 7, 10), "900.00")
_saldo_kpi(_conta_kpi_1, date(2031, 7, 15), "1000.00")
_saldo_kpi(_conta_kpi_2, date(2031, 7, 15), "500.00")

def _qualificador_com_pais(qual_num, dsc_prefixo="Rubrica"):
    """Cria (ou reusa) o qualificador garantindo a cadeia de pais — sem isso a
    rubrica vira raiz órfã e fica fora da árvore/totais do DFC."""
    _q = Qualificador.query.filter_by(num_qualificador=qual_num).first()
    if _q is not None:
        return _q
    _partes = qual_num.split('.')
    _pai = _qualificador_com_pais('.'.join(_partes[:-1]), dsc_prefixo) \
        if len(_partes) > 1 else None
    _q = Qualificador(num_qualificador=qual_num,
                      dsc_qualificador=f"{dsc_prefixo} {qual_num}", ind_status='A',
                      cod_qualificador_pai=_pai.seq_qualificador if _pai else None)
    db.session.add(_q)
    db.session.commit()
    return _q


def _lancamento_kpi(tipo_desc, origem_desc, valor, qual_num, seq_conta):
    _tipo = TipoLancamento.query.filter_by(dsc_tipo_lancamento=tipo_desc).first()
    _origem = OrigemLancamento.query.filter_by(dsc_origem_lancamento=origem_desc).first()
    _qual = _qualificador_com_pais(qual_num, dsc_prefixo="Rubrica KPI")
    existe = Lancamento.query.filter_by(
        dat_lancamento=date(2031, 7, 5), val_lancamento=Decimal(valor),
        cod_origem_lancamento=_origem.cod_origem_lancamento, ind_status='A',
    ).first()
    if existe is None:
        db.session.add(Lancamento(
            dat_lancamento=date(2031, 7, 5), seq_qualificador=_qual.seq_qualificador,
            val_lancamento=Decimal(valor), cod_tipo_lancamento=_tipo.cod_tipo_lancamento,
            cod_origem_lancamento=_origem.cod_origem_lancamento,
            seq_conta=seq_conta, cod_pessoa_inclusao=1, ind_status='A',
        ))
        db.session.commit()

_lancamento_kpi("Entrada", "Manual", "2000.00", "1.8.1", _conta_kpi_1.seq_conta)
_lancamento_kpi("Saída", "Manual", "500.00", "2.8.1", _conta_kpi_1.seq_conta)
# Lançamento automático SEM conta: entra no total sem filtro, sai no recorte
_lancamento_kpi("Entrada", "Automático", "100.00", "1.8.2", None)

# Fonte ativa de SALDO_FUNDO com execução SUCESSO agora → semáforo OK
_sis_kpi = SistemaOrigem.query.filter_by(txt_sigla="SIS_E2E_KPI").first()
if _sis_kpi is None:
    _sis_kpi = SistemaOrigem(txt_sigla="SIS_E2E_KPI",
                             dsc_sistema_origem="Sistema E2E KPIs")
    db.session.add(_sis_kpi)
    db.session.commit()

_fonte_kpi = FonteExtracao.query.filter_by(nom_fonte="Fonte E2E KPIs").first()
if _fonte_kpi is None:
    _fonte_kpi = FonteExtracao(
        nom_fonte="Fonte E2E KPIs", cod_tipo_conector="DEMO_MANUAL",
        cod_destino="SALDO_FUNDO", seq_sistema_origem=_sis_kpi.seq_sistema_origem,
        json_config={}, ind_status='A',
    )
    db.session.add(_fonte_kpi)
    db.session.commit()

if not ExecucaoExtracao.query.filter_by(
        seq_fonte_extracao=_fonte_kpi.seq_fonte_extracao).first():
    db.session.add(ExecucaoExtracao(
        seq_fonte_extracao=_fonte_kpi.seq_fonte_extracao,
        dat_inicio_execucao=datetime.now(), cod_disparo="MANUAL",
        cod_status="SUCESSO", dat_janela_inicio=date.today(),
        dat_janela_fim=date.today(),
    ))
    db.session.commit()

# ---------------------------------------------------------------------------
# Massa do DFC projetado (dfc_projetado.spec.ts): cenário com versão publicada
# projetando 200.00/mês para o qualificador 1.8.3 em 2034 (ano futuro — todas
# as colunas abertas). Lançamento em 2034 só para o ano entrar no dropdown.
# ---------------------------------------------------------------------------
from fluxocaixa.models import ProjecaoValor, ProjecaoVersao, SimuladorCenario  # noqa: E402

_lancamento_kpi_2034 = Lancamento.query.filter(
    Lancamento.dat_lancamento == date(2034, 1, 10)).first()
if _lancamento_kpi_2034 is None:
    _q_dfc = _qualificador_com_pais('1.8.3', dsc_prefixo="Rubrica DFC")
    _tipo_e = TipoLancamento.query.filter_by(dsc_tipo_lancamento='Entrada').first()
    _origem_m = OrigemLancamento.query.filter_by(dsc_origem_lancamento='Manual').first()
    db.session.add(Lancamento(
        dat_lancamento=date(2034, 1, 10), seq_qualificador=_q_dfc.seq_qualificador,
        val_lancamento=Decimal("50.00"), cod_tipo_lancamento=_tipo_e.cod_tipo_lancamento,
        cod_origem_lancamento=_origem_m.cod_origem_lancamento,
        cod_pessoa_inclusao=1, ind_status='A',
    ))
    db.session.commit()

_cen_dfc = SimuladorCenario.query.filter_by(nom_cenario='Cenário E2E DFC').first()
if _cen_dfc is None:
    _cen_dfc = SimuladorCenario(
        nom_cenario='Cenário E2E DFC', dsc_cenario='Cenário do E2E do DFC projetado',
        ano_base=2033, num_periodos=12, cod_periodicidade='MENSAL', ind_status='A',
    )
    db.session.add(_cen_dfc)
    db.session.commit()

    _q_dfc = Qualificador.query.filter_by(num_qualificador='1.8.3').first()
    _versao_dfc = ProjecaoVersao(
        seq_simulador_cenario=_cen_dfc.seq_simulador_cenario,
        nom_versao='v1 E2E DFC', ind_publicado='S',
    )
    db.session.add(_versao_dfc)
    db.session.flush()
    # Cenário MENSAL: o período é o próprio mês (F6.3).
    for _periodo in range(1, 13):
        db.session.add(ProjecaoValor(
            seq_projecao_versao=_versao_dfc.seq_projecao_versao,
            seq_qualificador=_q_dfc.seq_qualificador,
            cod_tipo='C', ano=2034, num_periodo=_periodo,
            val_projetado=Decimal("200.00"),
        ))
    db.session.commit()

# ---------------------------------------------------------------------------
# Massa da série treinada (serie_treinada.spec.ts, F10.2): cenário SEM versão
# publicada com despesa MEDIA_HISTORICA sobre 2.8.1 (lançamento de 2031 acima)
# — abrir a página executa ao vivo e o bloco `info-serie-treinada` declara o
# treino (1 mês, ano 2031).
# ---------------------------------------------------------------------------
import json  # noqa: E402

from fluxocaixa.models.simulador_cenario import CenarioConfig  # noqa: E402

_cen_serie = SimuladorCenario.query.filter_by(
    nom_cenario='Cenário E2E Série').first()
if _cen_serie is None:
    _q_serie = Qualificador.query.filter_by(num_qualificador='2.8.1').first()
    _cen_serie = SimuladorCenario(
        nom_cenario='Cenário E2E Série',
        dsc_cenario='Cenário do E2E da série treinada (F10.2)',
        ano_base=2032, num_periodos=12, cod_periodicidade='MENSAL',
        ind_status='A',
    )
    db.session.add(_cen_serie)
    db.session.flush()
    db.session.add(CenarioConfig(
        seq_simulador_cenario=_cen_serie.seq_simulador_cenario,
        cod_tipo_lancamento='D', cod_tipo_modelo='MEDIA_HISTORICA',
        json_configuracao=json.dumps(
            {'seq_qualificador': _q_serie.seq_qualificador}),
    ))
    db.session.commit()

# ---------------------------------------------------------------------------
# Plano-ilha 2078 (telas_por_exercicio.spec.ts, F10.4): um segundo exercício
# com raiz e folha próprias — o combo da tela de qualificadores troca o plano
# exibido. Descrições distintivas para os asserts.
# ---------------------------------------------------------------------------
if not Qualificador.query.filter_by(num_ano_exercicio=2078).first():
    _raiz_2078 = Qualificador(
        num_qualificador='1', dsc_qualificador='Receita Ilha 2078',
        ind_status='A', num_ano_exercicio=2078,
    )
    db.session.add(_raiz_2078)
    db.session.commit()
    db.session.add(Qualificador(
        num_qualificador='1.1', dsc_qualificador='Rubrica Ilha 2078',
        ind_status='A', num_ano_exercicio=2078,
        cod_qualificador_pai=_raiz_2078.seq_qualificador,
    ))
    db.session.commit()

# Árvore PROFUNDA para a F6.4: 6 níveis sob 1.6, com um lançamento na folha
# "1.6.1.1.1.1.1" — é ela que prova, na tela, que folha em qualquer nível
# recebe lançamento e que transformá-la em pai pede confirmação.
_RAMO_PROFUNDO = '1.6'
if not Qualificador.query.filter_by(num_qualificador='1.6.1.1.1.1.1').first():
    _pai_prof = None
    _num_prof = _RAMO_PROFUNDO
    for _passo in range(6):
        _existente = Qualificador.query.filter_by(num_qualificador=_num_prof).first()
        if _existente is None:
            _existente = Qualificador(
                num_qualificador=_num_prof,
                dsc_qualificador=f"Rubrica Profunda N{_passo + 1}",
                cod_qualificador_pai=_pai_prof.seq_qualificador if _pai_prof else None,
                ind_status='A',
            )
            db.session.add(_existente)
            db.session.commit()
        _pai_prof = _existente
        _num_prof = f"{_num_prof}.1"

    _tipo_prof = TipoLancamento.query.filter_by(dsc_tipo_lancamento='Entrada').first()
    _origem_prof = OrigemLancamento.query.filter_by(dsc_origem_lancamento='Manual').first()
    db.session.add(Lancamento(
        dat_lancamento=date(2016, 5, 12),
        seq_qualificador=_pai_prof.seq_qualificador,
        val_lancamento=Decimal("1234.56"),
        cod_tipo_lancamento=_tipo_prof.cod_tipo_lancamento,
        cod_origem_lancamento=_origem_prof.cod_origem_lancamento,
        cod_pessoa_inclusao=1, ind_status='A',
    ))
    db.session.commit()

# F6.5: bloco de despesa MARCADO como EDUCACAO, com folhas herdando. As folhas
# não têm "educação" na descrição de propósito — é o caso que a heurística
# antiga zerava (bloco casaria a palavra mas não é folha; folhas são folhas mas
# não casam a palavra).
from fluxocaixa.models import CategoriaFiscal  # noqa: E402

_cat_edu = CategoriaFiscal.query.filter_by(txt_sigla='EDUCACAO').first()
if _cat_edu is not None and not Qualificador.query.filter_by(
        num_qualificador='2.9').first():
    _bloco = Qualificador(
        num_qualificador='2.9', dsc_qualificador='Bloco E2E Categoria',
        ind_status='A', cod_categoria_fiscal=_cat_edu.seq_categoria_fiscal)
    db.session.add(_bloco)
    db.session.commit()

    _tipo_s = TipoLancamento.query.filter_by(dsc_tipo_lancamento='Saída').first()
    _origem_c = OrigemLancamento.query.filter_by(dsc_origem_lancamento='Manual').first()
    for _sufixo, _nome, _valor in (('1', 'Ensino Fundamental E2E', '3000.00'),
                                   ('2', 'Merenda Escolar E2E', '2000.00')):
        _folha = Qualificador(
            num_qualificador=f'2.9.{_sufixo}', dsc_qualificador=_nome,
            ind_status='A', cod_qualificador_pai=_bloco.seq_qualificador)
        db.session.add(_folha)
        db.session.commit()
        db.session.add(Lancamento(
            dat_lancamento=date(2018, 6, 15),
            seq_qualificador=_folha.seq_qualificador,
            val_lancamento=Decimal(_valor),
            cod_tipo_lancamento=_tipo_s.cod_tipo_lancamento,
            cod_origem_lancamento=_origem_c.cod_origem_lancamento,
            cod_pessoa_inclusao=1, ind_status='A',
        ))
    db.session.commit()

# ---------------------------------------------------------------------------
# F9.1 (fontes_recurso.spec.ts): fundo SEM fonte para o teste de classificação.
# As fontes vêm do seed_dominio (1.500 livre etc.). Dados fictícios.
# ---------------------------------------------------------------------------
if not Fundo.query.filter_by(cod_fundo='9931').first():
    criar_fundo('9931', 'Fundo Sem Fonte E2E')

# ---------------------------------------------------------------------------
# F7.1a (liberacoes.spec.ts): órgão ativo para o modal de liberação e um
# qualificador folha de DESPESA (raiz '2'). Dados fictícios.
# ---------------------------------------------------------------------------
from fluxocaixa.models import Orgao  # noqa: E402

if Orgao.query.get(70001) is None:
    db.session.add(Orgao(cod_orgao=70001, nom_orgao='Secretaria E2E Educação',
                         ind_status='A'))
    db.session.commit()

if not Qualificador.query.filter_by(num_qualificador='2.8.9').first():
    _raiz_desp = Qualificador.query.filter_by(num_qualificador='2').first()
    if _raiz_desp is None:
        _raiz_desp = Qualificador(num_qualificador='2', dsc_qualificador='Despesas E2E',
                                  ind_status='A')
        db.session.add(_raiz_desp)
        db.session.commit()
    db.session.add(Qualificador(num_qualificador='2.8.9',
                                dsc_qualificador='Custeio E2E Liberável',
                                cod_qualificador_pai=_raiz_desp.seq_qualificador,
                                ind_status='A'))
    db.session.commit()

print("usuarios e2e prontos")
