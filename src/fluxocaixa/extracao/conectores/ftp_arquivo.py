"""Conector de arquivo FTP/SFTP/pasta local (spec R15).

Genérico e parametrizável: para cada dia da janela monta o nome do arquivo
(`padrao_nome` com data), obtém o conteúdo pelo protocolo e delega ao motor
de parser (`parser_arquivo`). Arquivo ausente no dia é evento esperado
(fim de semana/feriado) — pula sem falhar. Credenciais só como `${VAR}`
(resolvidas por `executar_fonte` antes de chamar `extrair`).

Referências de comportamento portadas da DAG Caixa (FTP 550 = ausente).
`paramiko` (SFTP) é importado tardiamente — só onera quem usa SFTP.
"""
import os
from datetime import date, timedelta

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..conector import Janela, ResultadoTeste
from ..parser_arquivo import LayoutArquivo, parsear

PROTOCOLO_FTP = "FTP"
PROTOCOLO_SFTP = "SFTP"
PROTOCOLO_PASTA_LOCAL = "PASTA_LOCAL"


class ArquivoAusente(Exception):
    """Arquivo do dia não existe na origem — evento esperado, não falha."""


class ConfigFtpArquivo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolo: str = Field(description="FTP, SFTP ou PASTA_LOCAL")
    host: str | None = Field(default=None, description="Host (FTP/SFTP)")
    porta: int | None = Field(default=None, description="Porta (FTP/SFTP)")
    usuario: str | None = Field(default=None, description="Usuário (FTP/SFTP)")
    senha: str | None = Field(
        default=None, json_schema_extra={"secreto": True},
        description="Senha — referencie por ${VAR}",
    )
    diretorio: str = Field(description="Diretório remoto ou pasta local")
    padrao_nome: str = Field(
        description="Nome do arquivo com data, ex.: {:%Y%m%d}_0001_EXTRATO.csv",
    )

    @field_validator("protocolo")
    @classmethod
    def _protocolo_valido(cls, v: str) -> str:
        if v not in (PROTOCOLO_FTP, PROTOCOLO_SFTP, PROTOCOLO_PASTA_LOCAL):
            raise ValueError("protocolo deve ser FTP, SFTP ou PASTA_LOCAL")
        return v

    @field_validator("padrao_nome")
    @classmethod
    def _sem_traversal_nome(cls, v: str) -> str:
        if ".." in v or v.startswith("/") or "\\" in v:
            raise ValueError("padrao_nome não pode conter '..' nem caminho absoluto")
        return v

    @field_validator("diretorio")
    @classmethod
    def _sem_traversal_dir(cls, v: str) -> str:
        if ".." in v.split(os.sep):
            raise ValueError("diretorio não pode conter '..'")
        return v


def _formatar_nome(padrao: str, dia: date) -> str:
    nome = padrao.format(dia)
    # Defesa em profundidade: o nome formatado deve ser um basename simples.
    if os.sep in nome or (os.altsep and os.altsep in nome) or ".." in nome:
        raise ValueError(f"nome de arquivo inválido após formatação: '{nome}'")
    return nome


# --------------------------------------------------------------------------
# Backends por protocolo — retornam bytes ou levantam ArquivoAusente
# --------------------------------------------------------------------------

def _baixar_local(config: dict, nome: str) -> bytes:
    caminho = os.path.join(config["diretorio"], nome)
    try:
        with open(caminho, "rb") as f:
            return f.read()
    except FileNotFoundError as exc:
        raise ArquivoAusente(nome) from exc


def _baixar_ftp(config: dict, nome: str) -> bytes:
    from ftplib import FTP, error_perm
    from io import BytesIO

    ftp = FTP()
    conectado = False
    try:
        ftp.connect(host=config["host"], port=int(config.get("porta") or 21), timeout=30)
        conectado = True
        ftp.login(user=config.get("usuario") or "", passwd=config.get("senha") or "")
        ftp.cwd(config["diretorio"])
        bio = BytesIO()
        try:
            ftp.retrbinary(f"RETR {nome}", bio.write)
        except error_perm as exc:
            if str(exc).startswith("550"):
                raise ArquivoAusente(nome) from exc
            raise
        return bio.getvalue()
    finally:
        if conectado:
            try:
                ftp.quit()
            except Exception:
                ftp.close()


def _baixar_sftp(config: dict, nome: str) -> bytes:
    import paramiko  # import tardio — só onera o caminho SFTP

    transport = None
    try:
        transport = paramiko.Transport((config["host"], int(config.get("porta") or 22)))
        transport.connect(username=config.get("usuario"), password=config.get("senha"))
        sftp = paramiko.SFTPClient.from_transport(transport)
        caminho = config["diretorio"].rstrip("/") + "/" + nome
        try:
            with sftp.open(caminho, "rb") as f:
                return f.read()
        except FileNotFoundError as exc:
            raise ArquivoAusente(nome) from exc
    finally:
        if transport is not None:
            transport.close()


_BACKENDS = {
    PROTOCOLO_PASTA_LOCAL: _baixar_local,
    PROTOCOLO_FTP: _baixar_ftp,
    PROTOCOLO_SFTP: _baixar_sftp,
}


class ConectorFtpArquivo:
    tipo = "FTP_ARQUIVO"
    layout_kind = "ARQUIVO"
    schema_config = ConfigFtpArquivo
    schema_layout = LayoutArquivo  # valida o json_layout no cadastro (serviço)

    def testar_conexao(self, config: dict) -> ResultadoTeste:
        protocolo = config.get("protocolo")
        try:
            if protocolo == PROTOCOLO_PASTA_LOCAL:
                if not os.path.isdir(config["diretorio"]):
                    return ResultadoTeste(ok=False, mensagem=f"Pasta não encontrada: {config['diretorio']}")
                return ResultadoTeste(ok=True, mensagem="Pasta acessível")
            if protocolo == PROTOCOLO_FTP:
                from ftplib import FTP

                ftp = FTP()
                ftp.connect(host=config["host"], port=int(config.get("porta") or 21), timeout=30)
                ftp.login(user=config.get("usuario") or "", passwd=config.get("senha") or "")
                ftp.cwd(config["diretorio"])
                ftp.quit()
                return ResultadoTeste(ok=True, mensagem="Conexão FTP OK")
            if protocolo == PROTOCOLO_SFTP:
                import paramiko

                transport = paramiko.Transport((config["host"], int(config.get("porta") or 22)))
                transport.connect(username=config.get("usuario"), password=config.get("senha"))
                sftp = paramiko.SFTPClient.from_transport(transport)
                sftp.listdir(config["diretorio"])
                transport.close()
                return ResultadoTeste(ok=True, mensagem="Conexão SFTP OK")
        except Exception as exc:  # falha de conexão é resultado, não crash
            return ResultadoTeste(ok=False, mensagem=str(exc))
        return ResultadoTeste(ok=False, mensagem=f"Protocolo desconhecido: {protocolo}")

    def extrair(self, config: dict, layout: dict | None, janela: Janela):
        backend = _BACKENDS[config["protocolo"]]
        dia = janela.data_inicio
        while dia <= janela.data_fim:
            nome = _formatar_nome(config["padrao_nome"], dia)
            try:
                conteudo = backend(config, nome)
            except ArquivoAusente:
                dia += timedelta(days=1)
                continue  # dia sem arquivo é esperado — pula
            yield from parsear(conteudo, layout or {}, nome)
            dia += timedelta(days=1)
