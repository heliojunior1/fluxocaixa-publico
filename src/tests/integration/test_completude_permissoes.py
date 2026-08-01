"""Teste de completude: nenhuma rota de negócio sem exigência de permissão.

Spec controle-acesso R8 — mesmo espírito do anti-deriva do Alembic: rota nova
sem `requer(...)` derruba a suíte (impossível esquecer).
"""
from fastapi.routing import APIRoute

# Rotas sem permissão específica (autenticação/infra — protegidas por sessão
# onde aplicável, mas fora do catálogo verbo+recurso)
EXCECOES = {
    "/login",
    "/logout",
    "/trocar-senha",
    "/docs",
    "/openapi.json",
    # Confirmação/descarte de importação: a permissão é a do TIPO do preview,
    # verificada dentro do handler (não há uma permissão única para a rota).
    "/importacoes/{token}/confirmar",
    "/importacoes/{token}/descartar",
}


def test_toda_rota_de_negocio_exige_permissao(app):
    faltantes = []
    for rota in app.routes:
        if not isinstance(rota, APIRoute):
            continue
        if rota.path in EXCECOES:
            continue
        anotada = any(
            getattr(dep.call, "__requer_permissao__", None)
            for dep in rota.dependant.dependencies
        )
        if not anotada:
            faltantes.append(f"{sorted(rota.methods)} {rota.path}")

    assert faltantes == [], (
        "Rotas de negócio sem requer('FC_...'): adicione a dependency de "
        f"permissão ou registre exceção justificada.\n" + "\n".join(faltantes)
    )
