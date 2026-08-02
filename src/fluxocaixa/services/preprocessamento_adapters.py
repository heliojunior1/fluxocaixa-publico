"""Adapters de pré-processamento por tipo de importação (spec importacao-arquivos).

Cada adapter valida (dry-run, sem gravar) produzindo um Preview e sabe gravar
as linhas aprovadas reusando os serviços de gravação — assim preview e
gravação nunca divergem.
"""
import csv
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import StringIO

from ..models import ContaBancaria, Fundo, SaldoContaFundo
from .preprocessamento import LinhaPreview, Preview, registrar_adapter


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "")).encode("ascii", "ignore").decode()
    return s.strip().lower()


def _ler_csv(content: bytes) -> tuple:
    texto = content.decode("utf-8-sig")
    primeira = texto.splitlines()[0] if texto.strip() else ""
    sep = ";" if ";" in primeira else ","
    reader = csv.reader(StringIO(texto), delimiter=sep)
    linhas = [row for row in reader if any(c.strip() for c in row)]
    if not linhas:
        return [], []
    return linhas[0], linhas[1:]


def _dec(v) -> Decimal:
    return Decimal(str(v).replace(".", "").replace(",", ".") if (isinstance(v, str) and "," in v)
                   else str(v))


def _parse_data(v):
    for fmt in (None, "%d/%m/%Y"):
        try:
            return date.fromisoformat(v) if fmt is None else datetime.strptime(v, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


LAYOUT_NOVO = ["data", "banco", "agencia", "conta", "codfundo", "aplicacoes", "resgates", "saldo"]
LAYOUT_NOVO_MIN = ["data", "banco", "agencia", "conta", "codfundo", "saldo"]
LAYOUT_TRANSICAO = ["data", "conta", "valor"]


class _AdapterSaldos:
    tipo = "saldos"

    def parse_validar(self, content: bytes, filename: str) -> Preview:
        from .validacao import RegraNegocioError

        cabecalho, linhas = _ler_csv(content)
        cab = [_norm(c) for c in cabecalho]

        if cab[:len(LAYOUT_TRANSICAO)] == LAYOUT_TRANSICAO and len(cab) == 3:
            layout, colunas = "transicao", ["Data", "Conta", "Valor"]
        elif cab == LAYOUT_NOVO or cab == LAYOUT_NOVO_MIN:
            layout, colunas = "novo", ["Data", "Conta", "Fundo", "Aplicações", "Resgates", "Saldo", "Status"]
        else:
            raise RegraNegocioError(
                "Layout de arquivo inválido — use 'Data;Conta;Valor' ou "
                "'Data;Banco;Agencia;Conta;CodFundo;Aplicacoes;Resgates;Saldo'"
            )

        # cache de contas e fundos e das chaves ativas já existentes
        contas = {(c.cod_banco, c.num_agencia, c.num_conta): c for c in ContaBancaria.query.all()}
        fundos = {f.cod_fundo: f for f in Fundo.query.all()}
        idx = {i: _norm(c) for i, c in enumerate(cabecalho)}

        preview_linhas = []
        for n, row in enumerate(linhas, start=1):
            campos = {idx.get(i, str(i)): (row[i] if i < len(row) else "") for i in range(len(cabecalho))}
            preview_linhas.append(self._validar_linha(n, layout, campos, contas, fundos))

        return Preview(tipo=self.tipo, arquivo=filename, colunas=colunas, linhas=preview_linhas)

    def _validar_linha(self, n, layout, campos, contas, fundos) -> LinhaPreview:
        if layout == "transicao":
            dat_raw = campos.get("data")
            conta_raw = (campos.get("conta") or "").strip()
            saldo_raw = campos.get("valor")
            if "/" not in conta_raw:
                return LinhaPreview(n, "erro", "Conta deve ser Banco/Agência/Número", {})
            banco, ag, num = (p.strip() for p in conta_raw.split("/", 2))
            cod_fundo, apl_raw, resg_raw = "GERAL", "0", "0"
        else:
            dat_raw = campos.get("data")
            banco = (campos.get("banco") or "").strip()
            ag = (campos.get("agencia") or "").strip()
            num = (campos.get("conta") or "").strip()
            cod_fundo = (campos.get("codfundo") or "").strip()
            saldo_raw = campos.get("saldo")
            apl_raw = campos.get("aplicacoes") or "0"
            resg_raw = campos.get("resgates") or "0"

        dat = _parse_data(dat_raw)
        if dat is None:
            return LinhaPreview(n, "erro", f"Data inválida '{dat_raw}'", {})
        try:
            saldo = _dec(saldo_raw); apl = _dec(apl_raw); resg = _dec(resg_raw)
        except (InvalidOperation, ValueError, AttributeError):
            return LinhaPreview(n, "erro", f"Valor inválido '{saldo_raw}'", {})

        conta = contas.get((banco, ag, num))
        if conta is None:
            return LinhaPreview(n, "erro", f"Conta {banco}/{ag}/{num} não cadastrada", {})

        dados = {
            "banco": banco, "agencia": ag, "conta": num, "cod_fundo": cod_fundo,
            "dat_saldo": dat.isoformat(), "val_saldo": str(saldo),
            "val_aplicacoes": str(apl), "val_resgates": str(resg),
            "_exibe": {"Data": dat.strftime("%d/%m/%Y"), "Conta": f"{banco}/{ag}/{num}",
                       "Fundo": cod_fundo, "Aplicações": str(apl), "Resgates": str(resg),
                       "Saldo": str(saldo)},
        }

        avisos = []
        fundo = fundos.get(cod_fundo)
        if fundo is None and cod_fundo != "GERAL":
            avisos.append(f"fundo '{cod_fundo}' será auto-cadastrado pendente de revisão")
        elif fundo is not None:
            existe = SaldoContaFundo.query.filter_by(
                seq_conta=conta.seq_conta, seq_fundo=fundo.seq_fundo,
                dat_saldo=dat, ind_status='A').first()
            if existe:
                avisos.append("substituirá o saldo ativo existente")

        if avisos:
            return LinhaPreview(n, "aviso", "; ".join(avisos), dados)
        return LinhaPreview(n, "ok", None, dados)

    def gravar(self, linhas_graváveis):
        from .fundo_service import garantir_fundo_geral
        from .importacao_lote_service import LinhaLote, importar_lote

        garantir_fundo_geral()
        lote = [
            LinhaLote(
                cod_banco=l.dados["banco"], num_agencia=l.dados["agencia"],
                num_conta=l.dados["conta"], cod_fundo=l.dados["cod_fundo"],
                dsc_fundo=f"Fundo {l.dados['cod_fundo']}",
                val_saldo=Decimal(l.dados["val_saldo"]),
                val_aplicacoes=Decimal(l.dados["val_aplicacoes"]),
                val_resgates=Decimal(l.dados["val_resgates"]),
                dat_saldo=date.fromisoformat(l.dados["dat_saldo"]),
            )
            for l in linhas_graváveis
        ]
        return importar_lote(lote, dat_saldo_lote=date.today(),
                             sigla_sistema=None, arquivo_origem="preprocessado.csv")


class _AdapterLancamentos:
    tipo = "lancamentos"

    def parse_validar(self, content: bytes, filename: str) -> Preview:
        from ..models import Lancamento, OrigemLancamento, Qualificador, TipoLancamento  # noqa: F401

        cabecalho, linhas = _ler_csv(content)
        idx = {i: c.strip() for i, c in enumerate(cabecalho)}
        quals = {(q.dsc_qualificador or "").lower(): q for q in Qualificador.query.all()}
        tipos = {(t.dsc_tipo_lancamento or "").lower(): t for t in TipoLancamento.query.all()}
        colunas = ["Data", "Qualificador", "Tipo", "Valor", "Status"]

        preview_linhas = []
        for n, row in enumerate(linhas, start=1):
            campos = {idx.get(i, str(i)): (row[i] if i < len(row) else "") for i in range(len(cabecalho))}
            preview_linhas.append(self._validar(n, campos, quals, tipos))
        return Preview(tipo=self.tipo, arquivo=filename, colunas=colunas, linhas=preview_linhas)

    def _validar(self, n, campos, quals, tipos) -> LinhaPreview:
        dat_raw = campos.get("Data") or campos.get("data")
        desc = (campos.get("Qualificador") or campos.get("Descrição") or "").strip()
        valor_raw = campos.get("Valor (R$)") or campos.get("Valor") or campos.get("valor")
        tipo_raw = (campos.get("Tipo") or "").strip()
        dados = {"raw": campos, "_exibe": {"Data": str(dat_raw), "Qualificador": desc,
                                           "Tipo": tipo_raw, "Valor": str(valor_raw)}}

        if _parse_data(dat_raw) is None:
            return LinhaPreview(n, "erro", f"Data inválida '{dat_raw}'", dados)
        q = quals.get(desc.lower())
        if q is None:
            return LinhaPreview(n, "erro", f"Qualificador '{desc}' não encontrado", dados)
        if q.ind_status != 'A' or not q.is_folha():
            return LinhaPreview(n, "erro", "Qualificador deve ser folha ativa", dados)
        if tipo_raw and tipo_raw.lower() not in tipos and not tipo_raw.isdigit():
            return LinhaPreview(n, "erro", f"Tipo '{tipo_raw}' inválido", dados)
        try:
            if _dec(valor_raw) == 0:
                return LinhaPreview(n, "erro", "Valor não pode ser zero", dados)
        except (InvalidOperation, ValueError, AttributeError):
            return LinhaPreview(n, "erro", f"Valor inválido '{valor_raw}'", dados)
        return LinhaPreview(n, "ok", None, dados)

    def gravar(self, linhas_graváveis):
        import csv as _csv
        from io import StringIO

        from .lancamento_service import import_lancamentos_service

        if not linhas_graváveis:
            return {"sucesso": 0, "erros": []}
        cabecalho = list(linhas_graváveis[0].dados["raw"].keys())
        buf = StringIO()
        w = _csv.DictWriter(buf, fieldnames=cabecalho, delimiter=";")
        w.writeheader()
        for l in linhas_graváveis:
            w.writerow(l.dados["raw"])
        return import_lancamentos_service(buf.getvalue().encode("utf-8"), "preprocessado.csv")


class _AdapterLoa:
    tipo = "loa"

    def parse_validar(self, content: bytes, filename: str) -> Preview:
        from ..web.loa import _encontrar_qualificador
        from ..models import Loa

        cabecalho, linhas = _ler_csv(content)
        idx = {i: _norm(c) for i, c in enumerate(cabecalho)}
        colunas = ["Qualificador", "Valor", "Status"]
        preview_linhas = []
        for n, row in enumerate(linhas, start=1):
            campos = {idx.get(i, str(i)): (row[i] if i < len(row) else "") for i in range(len(cabecalho))}
            ref = (campos.get("qualificador") or campos.get("num_qualificador")
                   or campos.get("dsc_qualificador") or "").strip()
            valor_raw = campos.get("valor") or "0"
            dados = {"ref": ref, "valor": str(valor_raw),
                     "_exibe": {"Qualificador": ref, "Valor": str(valor_raw)}}
            if not ref:
                preview_linhas.append(LinhaPreview(n, "erro", "Qualificador vazio", dados)); continue
            try:
                _dec(valor_raw)
            except (InvalidOperation, ValueError, AttributeError):
                preview_linhas.append(LinhaPreview(n, "erro", f"Valor inválido '{valor_raw}'", dados)); continue
            q = _encontrar_qualificador(ref)
            if q is None:
                preview_linhas.append(LinhaPreview(n, "erro", f"Qualificador '{ref}' não encontrado", dados)); continue
            existe = Loa.query.filter_by(num_ano=self._ano, seq_qualificador=q.seq_qualificador).first()
            if existe:
                preview_linhas.append(LinhaPreview(n, "aviso", "atualizará o valor existente do ano/qualificador", dados))
            else:
                preview_linhas.append(LinhaPreview(n, "ok", None, dados))
        return Preview(tipo=self.tipo, arquivo=filename, colunas=colunas, linhas=preview_linhas)

    # o ano é fixado por atributo antes de parse_validar (a rota informa)
    _ano = date.today().year

    def gravar(self, linhas_graváveis):
        from ..models.base import db
        from ..web.loa import _encontrar_qualificador, _upsert_loa

        n = 0
        for l in linhas_graváveis:
            q = _encontrar_qualificador(l.dados["ref"])
            if q is not None:
                _upsert_loa(self._ano, q.seq_qualificador, _dec(l.dados["valor"]))
                n += 1
        db.session.commit()
        return {"sucesso": n, "erros": []}


class _AdapterFontesRecurso:
    """Importação da tabela oficial de fontes/destinações da STN (F9.1).

    Layout: identificador;fonte;detalhamento;descricao;vinculada;grupo
    (detalhamento e grupo opcionais; vinculada = L/V). O exercício de
    vigência é fixado pela rota antes do parse (padrão do adapter da LOA).
    Fonte já existente na vigência vira AVISO e é ignorada na gravação —
    a importação nunca altera existente (spec fonte-recurso R2/R3).
    """

    tipo = "fontes_recurso"
    _exercicio = date.today().year  # a rota informa antes de parse_validar

    def parse_validar(self, content: bytes, filename: str) -> Preview:
        from ..models import FonteRecurso
        from ..models.fonte_recurso import IDENTIFICADORES_EXERCICIO

        cabecalho, linhas = _ler_csv(content)
        idx = {i: _norm(c) for i, c in enumerate(cabecalho)}
        colunas = ["Código", "Descrição", "Vinculação", "Status"]

        existentes = {
            (f.cod_identificador_exercicio, f.cod_fonte_stn, f.cod_detalhamento)
            for f in FonteRecurso.query.filter_by(
                num_exercicio_vigencia=self._exercicio, ind_status='A').all()
        }

        preview_linhas = []
        for n, row in enumerate(linhas, start=1):
            campos = {idx.get(i, str(i)): (row[i] if i < len(row) else "") for i in range(len(cabecalho))}
            ident = (campos.get("identificador") or "1").strip()
            fonte = (campos.get("fonte") or "").strip()
            det = (campos.get("detalhamento") or "").strip() or None
            dsc = (campos.get("descricao") or "").strip()
            vinc = (campos.get("vinculada") or "V").strip().upper()
            grupo = (campos.get("grupo") or "").strip() or None
            codigo = f"{ident}.{fonte}" + (f".{det}" if det else "")
            dados = {"ident": ident, "fonte": fonte, "det": det or "", "dsc": dsc,
                     "vinc": vinc, "grupo": grupo or "",
                     "_exibe": {"Código": codigo, "Descrição": dsc,
                                "Vinculação": "livre" if vinc == "L" else "vinculada"}}

            if ident not in IDENTIFICADORES_EXERCICIO:
                preview_linhas.append(LinhaPreview(n, "erro", f"Identificador inválido '{ident}'", dados)); continue
            if not fonte.isdigit() or len(fonte) != 3:
                preview_linhas.append(LinhaPreview(n, "erro", f"Fonte STN inválida '{fonte}'", dados)); continue
            if not dsc:
                preview_linhas.append(LinhaPreview(n, "erro", "Descrição vazia", dados)); continue
            if vinc not in ("L", "V"):
                preview_linhas.append(LinhaPreview(n, "erro", f"Vinculação inválida '{vinc}'", dados)); continue
            if (ident, fonte, det) in existentes:
                preview_linhas.append(LinhaPreview(
                    n, "aviso", "já existe nesta vigência — será ignorada (nunca altera existente)", dados))
            else:
                preview_linhas.append(LinhaPreview(n, "ok", None, dados))
        return Preview(tipo=self.tipo, arquivo=filename, colunas=colunas, linhas=preview_linhas)

    def gravar(self, linhas_graváveis):
        from .fonte_recurso_service import criar_fonte
        from .validacao import RegraNegocioError
        from ..models.fonte_recurso import ORIGEM_STN

        n = 0
        for l in linhas_graváveis:
            try:
                criar_fonte(
                    l.dados["ident"], l.dados["fonte"], l.dados["dsc"],
                    self._exercicio, vinculada=l.dados["vinc"],
                    detalhamento=l.dados["det"] or None,
                    grupo_destinacao=l.dados["grupo"] or None,
                    origem=ORIGEM_STN,
                )
                n += 1
            except RegraNegocioError:
                continue  # linha de aviso (duplicada) — ignorada, nunca altera
        return {"sucesso": n, "erros": []}


registrar_adapter("saldos", _AdapterSaldos())
registrar_adapter("lancamentos", _AdapterLancamentos())
registrar_adapter("loa", _AdapterLoa())
registrar_adapter("fontes_recurso", _AdapterFontesRecurso())

class _AdapterProgramacao:
    """Importação do decreto de programação de desembolso (F7.3b).

    Layout: mes;orgao;valor;ato — o ano é fixado pela rota (padrão da LOA).
    Revisão da mesma chave inativa a anterior (nunca sobrescreve).
    """

    tipo = "programacao"
    _ano = date.today().year

    def parse_validar(self, content: bytes, filename: str) -> Preview:
        from ..models import Orgao

        cabecalho, linhas = _ler_csv(content)
        idx = {i: _norm(c) for i, c in enumerate(cabecalho)}
        colunas = ["Mês", "Órgão", "Valor", "Ato", "Status"]
        orgaos = {o.cod_orgao for o in Orgao.query.filter_by(ind_status='A').all()}

        preview_linhas = []
        for n, row in enumerate(linhas, start=1):
            campos = {idx.get(i, str(i)): (row[i] if i < len(row) else "") for i in range(len(cabecalho))}
            mes_raw = (campos.get("mes") or "").strip()
            orgao_raw = (campos.get("orgao") or "").strip()
            valor_raw = campos.get("valor") or ""
            ato = (campos.get("ato") or "").strip()
            dados = {"mes": mes_raw, "orgao": orgao_raw, "valor": str(valor_raw),
                     "ato": ato,
                     "_exibe": {"Mês": mes_raw, "Órgão": orgao_raw,
                                "Valor": str(valor_raw), "Ato": ato}}
            if not mes_raw.isdigit() or not (1 <= int(mes_raw) <= 12):
                preview_linhas.append(LinhaPreview(n, "erro", f"Mês inválido '{mes_raw}'", dados)); continue
            if not orgao_raw.isdigit() or int(orgao_raw) not in orgaos:
                preview_linhas.append(LinhaPreview(n, "erro", f"Órgão '{orgao_raw}' não cadastrado", dados)); continue
            if not ato:
                preview_linhas.append(LinhaPreview(n, "erro", "Referência do ato vazia", dados)); continue
            try:
                if _dec(valor_raw) <= 0:
                    preview_linhas.append(LinhaPreview(n, "erro", "Valor deve ser positivo", dados)); continue
            except (InvalidOperation, ValueError, AttributeError):
                preview_linhas.append(LinhaPreview(n, "erro", f"Valor inválido '{valor_raw}'", dados)); continue
            preview_linhas.append(LinhaPreview(n, "ok", None, dados))
        return Preview(tipo=self.tipo, arquivo=filename, colunas=colunas, linhas=preview_linhas)

    def gravar(self, linhas_graváveis):
        from .programacao_service import registrar_cota

        n = 0
        for l in linhas_graváveis:
            registrar_cota(self._ano, int(l.dados["mes"]), int(l.dados["orgao"]),
                           _dec(l.dados["valor"]), l.dados["ato"])
            n += 1
        return {"sucesso": n, "erros": []}


registrar_adapter("programacao", _AdapterProgramacao())


class _AdapterDotacao:
    """Importação da dotação inicial (F8.1).

    Layout: qualificador;valor — o ano é fixado pela rota (padrão da
    programação). Créditos adicionais NÃO entram por aqui: são eventos com
    ato obrigatório, registrados um a um pela tela.
    """

    tipo = "dotacao"
    _ano = date.today().year

    def parse_validar(self, content: bytes, filename: str) -> Preview:
        from ..models import Qualificador

        cabecalho, linhas = _ler_csv(content)
        idx = {i: _norm(c) for i, c in enumerate(cabecalho)}
        colunas = ["Qualificador", "Valor", "Status"]
        folhas = {q.num_qualificador: q for q in Qualificador.query.filter_by(ind_status='A').all()
                  if q.is_folha() and q.tipo_fluxo == 'despesa'}

        preview_linhas = []
        for n, row in enumerate(linhas, start=1):
            campos = {idx.get(i, str(i)): (row[i] if i < len(row) else "") for i in range(len(cabecalho))}
            qual_raw = (campos.get("qualificador") or "").strip()
            valor_raw = campos.get("valor") or ""
            dados = {"qualificador": qual_raw, "valor": str(valor_raw),
                     "_exibe": {"Qualificador": qual_raw, "Valor": str(valor_raw)}}
            if qual_raw not in folhas:
                preview_linhas.append(LinhaPreview(n, "erro", f"Qualificador '{qual_raw}' não é folha ativa de despesa", dados)); continue
            try:
                if _dec(valor_raw) < 0:
                    preview_linhas.append(LinhaPreview(n, "erro", "Valor não pode ser negativo", dados)); continue
            except (InvalidOperation, ValueError, AttributeError):
                preview_linhas.append(LinhaPreview(n, "erro", f"Valor inválido '{valor_raw}'", dados)); continue
            dados["seq_qualificador"] = folhas[qual_raw].seq_qualificador
            preview_linhas.append(LinhaPreview(n, "ok", None, dados))
        return Preview(tipo=self.tipo, arquivo=filename, colunas=colunas, linhas=preview_linhas)

    def gravar(self, linhas_graváveis):
        from .dotacao_service import criar_dotacao

        n = 0
        erros = []
        for l in linhas_graváveis:
            try:
                criar_dotacao(self._ano, int(l.dados["seq_qualificador"]),
                              _dec(l.dados["valor"]))
                n += 1
            except Exception as exc:  # dotação repetida na planilha, etc.
                erros.append(f"linha {l.numero}: {exc}")
        return {"sucesso": n, "erros": erros}


registrar_adapter("dotacao", _AdapterDotacao())


class _AdapterExecucao:
    """Importação da execução orçamentária E/L/P (F8.2).

    Layout: estagio;numero;pai;orgao;qualificador;fonte;valor;data — `pai` é
    o número do documento do estágio anterior no MESMO ano (vazio para E);
    `fonte` é o código STN cru (desconhecida → auto-cadastro pendente, F9.1).
    O ano é fixado pela rota. A ORDEM das linhas importa (o pai precisa
    existir antes do filho — E antes de L antes de P).
    """

    tipo = "execucao"
    _ano = date.today().year

    def parse_validar(self, content: bytes, filename: str) -> Preview:
        from ..models import Orgao, Qualificador

        cabecalho, linhas = _ler_csv(content)
        idx = {i: _norm(c) for i, c in enumerate(cabecalho)}
        colunas = ["Estágio", "Número", "Pai", "Órgão", "Qualificador",
                   "Fonte", "Valor", "Data", "Status"]
        orgaos = {o.cod_orgao for o in Orgao.query.filter_by(ind_status='A').all()}
        folhas = {q.num_qualificador: q for q in Qualificador.query.filter_by(ind_status='A').all()
                  if q.is_folha() and q.tipo_fluxo == 'despesa'}

        preview_linhas = []
        for n, row in enumerate(linhas, start=1):
            campos = {idx.get(i, str(i)): (row[i] if i < len(row) else "") for i in range(len(cabecalho))}
            estagio = (campos.get("estagio") or "").strip().upper()
            numero = (campos.get("numero") or "").strip()
            pai = (campos.get("pai") or "").strip()
            orgao_raw = (campos.get("orgao") or "").strip()
            qual_raw = (campos.get("qualificador") or "").strip()
            fonte = (campos.get("fonte") or "").strip()
            valor_raw = campos.get("valor") or ""
            data_raw = (campos.get("data") or "").strip()
            dados = {"estagio": estagio, "numero": numero, "pai": pai,
                     "orgao": orgao_raw, "qualificador": qual_raw,
                     "fonte": fonte, "valor": str(valor_raw), "data": data_raw,
                     "_exibe": {"Estágio": estagio, "Número": numero, "Pai": pai,
                                "Órgão": orgao_raw, "Qualificador": qual_raw,
                                "Fonte": fonte, "Valor": str(valor_raw), "Data": data_raw}}
            if estagio not in ('E', 'L', 'P'):
                preview_linhas.append(LinhaPreview(n, "erro", f"Estágio inválido '{estagio}'", dados)); continue
            if not numero:
                preview_linhas.append(LinhaPreview(n, "erro", "Número do documento vazio", dados)); continue
            if estagio != 'E' and not pai:
                preview_linhas.append(LinhaPreview(n, "erro", "Documento-pai obrigatório para L/P", dados)); continue
            if not orgao_raw.isdigit() or int(orgao_raw) not in orgaos:
                preview_linhas.append(LinhaPreview(n, "erro", f"Órgão '{orgao_raw}' não cadastrado", dados)); continue
            if qual_raw not in folhas:
                preview_linhas.append(LinhaPreview(n, "erro", f"Qualificador '{qual_raw}' não é folha ativa de despesa", dados)); continue
            try:
                if _dec(valor_raw) <= 0:
                    preview_linhas.append(LinhaPreview(n, "erro", "Valor deve ser positivo", dados)); continue
            except (InvalidOperation, ValueError, AttributeError):
                preview_linhas.append(LinhaPreview(n, "erro", f"Valor inválido '{valor_raw}'", dados)); continue
            try:
                date.fromisoformat(data_raw)
            except ValueError:
                preview_linhas.append(LinhaPreview(n, "erro", f"Data inválida '{data_raw}'", dados)); continue
            dados["seq_qualificador"] = folhas[qual_raw].seq_qualificador
            preview_linhas.append(LinhaPreview(n, "ok", None, dados))
        return Preview(tipo=self.tipo, arquivo=filename, colunas=colunas, linhas=preview_linhas)

    def gravar(self, linhas_graváveis):
        from .execucao_orcamentaria_service import registrar_documento

        n = 0
        erros = []
        for l in linhas_graváveis:
            try:
                registrar_documento(
                    cod_estagio=l.dados["estagio"], num_documento=l.dados["numero"],
                    num_ano=self._ano, cod_orgao=int(l.dados["orgao"]),
                    seq_qualificador=int(l.dados["seq_qualificador"]),
                    val_documento=_dec(l.dados["valor"]),
                    dat_documento=date.fromisoformat(l.dados["data"]),
                    codigo_fonte=l.dados["fonte"] or None,
                    num_documento_pai=l.dados["pai"] or None)
                n += 1
            except Exception as exc:  # pai ausente, estouro, duplicado…
                erros.append(f"linha {l.numero}: {exc}")
        return {"sucesso": n, "erros": erros}


registrar_adapter("execucao", _AdapterExecucao())


class _AdapterDisponibilidadeContabil:
    """Importação da disponibilidade contábil por fonte (F9.4).

    Layout: fonte;valor — a data de referência é fixada pela rota. Fonte
    desconhecida → auto-cadastro pendente (F9.1). Valor pode ser NEGATIVO
    (a contabilidade pode reportar insuficiência). Revisão da mesma
    (data, fonte) inativa a anterior.
    """

    tipo = "disponibilidade_contabil"
    _data = date.today()

    def parse_validar(self, content: bytes, filename: str) -> Preview:
        cabecalho, linhas = _ler_csv(content)
        idx = {i: _norm(c) for i, c in enumerate(cabecalho)}
        colunas = ["Fonte", "Valor", "Status"]

        preview_linhas = []
        for n, row in enumerate(linhas, start=1):
            campos = {idx.get(i, str(i)): (row[i] if i < len(row) else "") for i in range(len(cabecalho))}
            fonte = (campos.get("fonte") or "").strip()
            valor_raw = campos.get("valor") or ""
            dados = {"fonte": fonte, "valor": str(valor_raw),
                     "_exibe": {"Fonte": fonte, "Valor": str(valor_raw)}}
            if not fonte:
                preview_linhas.append(LinhaPreview(n, "erro", "Código da fonte vazio", dados)); continue
            try:
                _dec(valor_raw)
            except (InvalidOperation, ValueError, AttributeError):
                preview_linhas.append(LinhaPreview(n, "erro", f"Valor inválido '{valor_raw}'", dados)); continue
            preview_linhas.append(LinhaPreview(n, "ok", None, dados))
        return Preview(tipo=self.tipo, arquivo=filename, colunas=colunas, linhas=preview_linhas)

    def gravar(self, linhas_graváveis):
        from .conciliacao_fonte_service import registrar_disponibilidade

        n = 0
        erros = []
        for l in linhas_graváveis:
            try:
                registrar_disponibilidade(self._data, l.dados["fonte"],
                                          _dec(l.dados["valor"]))
                n += 1
            except Exception as exc:
                erros.append(f"linha {l.numero}: {exc}")
        return {"sucesso": n, "erros": erros}


registrar_adapter("disponibilidade_contabil", _AdapterDisponibilidadeContabil())


