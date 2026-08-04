"""Confinamento de destino dos conectores (spec extracao-configuravel R23).

ORIGEM ÚNICA das duas guardas — sistema de arquivos e rede. Nenhum conector
reimplementa: o motivo é histórico e concreto. Em `ftp_arquivo`, `padrao_nome`
tinha guarda anti-traversal E revalidação do nome formatado, enquanto
`diretorio`, poucas linhas abaixo, só checava `..` — e caminho absoluto passava.
Não foi desleixo; foi cada campo ganhando a guarda que parecia certa no momento
em que foi escrito, sem um lugar que respondesse "o que este conector pode
alcançar?". Este módulo é esse lugar.
"""
import ipaddress
import os
import socket
from urllib.parse import urlsplit

from ..config import BASE_DIR
from ..services.validacao import RegraNegocioError

VAR_RAIZ = "EXTRACAO_PASTA_RAIZ"
VAR_HOSTS_PERMITIDOS = "EXTRACAO_HOSTS_PERMITIDOS"

# Nomes de serviço de metadados de nuvem: resolvem para link-local e entregam
# credenciais de instância. Bloqueados por nome porque o cadastro costuma trazer
# o nome, não o IP.
_HOSTS_METADADOS = {
    "metadata.google.internal",
    "metadata.goog",
    "instance-data",
    "metadata",
}

# Dialetos SQLAlchemy que apontam para arquivo local em vez de servidor.
_DIALETOS_ARQUIVO = ("sqlite",)


def raiz_pasta_local() -> str:
    """Raiz sob a qual todo caminho local de extração deve estar.

    Default dentro de `instance/` — seguro por construção; instalação que
    guarde os arquivos em outro lugar declara a raiz no ambiente.
    """
    configurada = os.getenv(VAR_RAIZ)
    if configurada:
        return os.path.realpath(configurada)
    return os.path.realpath(os.path.join(BASE_DIR, "instance", "extracao"))


def hosts_permitidos() -> set[str]:
    """Hosts internos autorizados explicitamente pela instalação.

    Extrair de host interno é o caso de uso PRINCIPAL de um órgão público (o
    ERP e o banco de referência vivem na intranet), então a saída não é
    proibir faixa privada — é exigir que a exceção seja declarada e auditável.
    """
    bruto = os.getenv(VAR_HOSTS_PERMITIDOS) or ""
    return {h.strip().lower() for h in bruto.split(",") if h.strip()}


def _sob_a_raiz(caminho_real: str, raiz: str) -> bool:
    try:
        return os.path.commonpath([caminho_real, raiz]) == raiz
    except ValueError:
        # drives diferentes no Windows — nunca está sob a raiz
        return False


def validar_diretorio_local(diretorio: str) -> str:
    """Devolve o caminho real do diretório, exigindo que esteja sob a raiz.

    Usa `realpath`, não inspeção textual: um symlink DENTRO da raiz apontando
    para `/etc` não contém `..` e passaria por qualquer checagem de string.
    """
    if not diretorio:
        raise RegraNegocioError("Informe o diretório da fonte.")
    raiz = raiz_pasta_local()
    real = os.path.realpath(diretorio)
    if not _sob_a_raiz(real, raiz):
        raise RegraNegocioError(
            f"O diretório da fonte deve estar dentro da raiz de extração "
            f"({raiz}). Mova os arquivos para lá ou ajuste {VAR_RAIZ}."
        )
    return real


def _como_ip(host: str):
    """Interpreta o host como endereço IP, incluindo as formas legadas.

    `ipaddress` é estrito e recusa `127.1`, `0x7f000001` e `2130706433` — mas
    navegadores, curl e a própria `socket` resolvem as três para 127.0.0.1.
    Aceitar só a forma canônica deixaria o bypass mais conhecido de fora.

    `inet_aton` é conversão textual pura; NÃO faz DNS (ver design D3 — resolver
    nome na validação seria TOCTOU e quebraria rede fechada).
    """
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    try:
        return ipaddress.ip_address(socket.inet_ntoa(socket.inet_aton(host)))
    except (OSError, ValueError):
        return None


def _ip_interno(host: str) -> bool:
    endereco = _como_ip(host)
    if endereco is None:
        return False
    if endereco.version == 6 and endereco.ipv4_mapped is not None:
        # ::ffff:127.0.0.1 é loopback disfarçado de IPv6
        endereco = endereco.ipv4_mapped
    return (
        endereco.is_loopback
        or endereco.is_private
        or endereco.is_link_local      # inclui 169.254.169.254 (metadados)
        or endereco.is_multicast
        or endereco.is_reserved
        or endereco.is_unspecified     # 0.0.0.0 alcança o loopback em vários SOs
    )


def validar_host_externo(host: str | None, *, campo: str = "host") -> str:
    """Recusa destino interno, salvo se declarado em `EXTRACAO_HOSTS_PERMITIDOS`."""
    if not host:
        raise RegraNegocioError(f"Informe o {campo} da fonte.")
    normalizado = host.strip().strip("[]").lower()
    if normalizado in hosts_permitidos():
        return host
    if normalizado in _HOSTS_METADADOS or _ip_interno(normalizado):
        raise RegraNegocioError(
            f"O {campo} aponta para um destino interno ({host}). "
            f"Se a extração é de um host da rede interna, declare-o em "
            f"{VAR_HOSTS_PERMITIDOS}."
        )
    return host


def validar_url_externa(url: str | None, *, campo: str = "url") -> str:
    """Valida o host de uma URL de rede (API REST, token de OAuth)."""
    if not url:
        raise RegraNegocioError(f"Informe a {campo} da fonte.")
    partes = urlsplit(url)
    if not partes.hostname:
        raise RegraNegocioError(f"A {campo} da fonte não contém host válido.")
    validar_host_externo(partes.hostname, campo=campo)
    return url


def validar_url_conexao(url: str | None) -> str:
    """Valida a URL SQLAlchemy de um banco externo.

    Dialeto de arquivo (SQLite) é leitura de arquivo local com outra roupa —
    obedece ao MESMO confinamento do sistema de arquivos, senão fecharíamos a
    porta da frente e deixaríamos a dos fundos aberta.
    """
    if not url:
        raise RegraNegocioError("Informe a URL de conexão da fonte.")
    partes = urlsplit(url)
    dialeto = (partes.scheme or "").split("+", 1)[0].lower()

    if dialeto in _DIALETOS_ARQUIVO:
        caminho = url.split("///", 1)[-1] if "///" in url else ""
        if not caminho or caminho == ":memory:":
            return url
        validar_diretorio_local(os.path.dirname(os.path.abspath(caminho)) or ".")
        return url

    if not partes.hostname:
        # dialeto de servidor sem host: nada a alcançar, o driver é quem recusa
        return url
    validar_host_externo(partes.hostname, campo="URL de conexão")
    return url


__all__ = [
    "VAR_HOSTS_PERMITIDOS",
    "VAR_RAIZ",
    "hosts_permitidos",
    "raiz_pasta_local",
    "validar_diretorio_local",
    "validar_host_externo",
    "validar_url_conexao",
    "validar_url_externa",
]
