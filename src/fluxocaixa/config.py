import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

_FALSY = {"false", "0", "no", "off", "n"}


def env_flag(nome: str, default: bool = True) -> bool:
    """Lê uma flag booleana do ambiente.

    Vive aqui, e não em `bootstrap_db`, porque `config` é o módulo leve que
    todo mundo pode importar sem arrastar Alembic e a engine junto.
    """
    valor = os.getenv(nome)
    if valor is None:
        return default
    return valor.strip().lower() not in _FALSY


def modo_demo() -> bool:
    """Ambiente de demonstração pública — desligado por padrão.

    Muda três comportamentos que só fazem sentido numa instância aberta a
    visitantes: a tela de login exibe as credenciais, o admin nasce sem troca
    de senha obrigatória e a troca de senha é recusada.

    Os três andam juntos por necessidade. Sem o terceiro, bastaria um visitante
    trocar a senha para trancar a demo para todos os seguintes — que é o que
    acontece hoje, por acidente, via troca obrigatória no primeiro login.

    Lida a cada chamada (e não no import) para que testes e o próprio boot
    possam alternar o valor sem recarregar o módulo.
    """
    return env_flag("DEMO_MODE", False)


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', f'sqlite:///{os.path.join(BASE_DIR, "instance", "fluxo.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
