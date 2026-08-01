#!/bin/sh
# Sobe a aplicação para os testes E2E com banco descartável.
# SEED_DEMO_DATA=false: o seed de demo LIMPA e repopula os dados de exemplo a
# cada boot, o que apagaria os dados criados por seed_usuarios_e2e.py — o
# ambiente E2E usa apenas os dados de domínio + o que o script semeia.
cd "$(dirname "$0")/.."
rm -f e2e/.data/e2e.db
mkdir -p e2e/.data
export PYTHONPATH=src
export DATABASE_URL="sqlite:///./e2e/.data/e2e.db"
export SEED_DEMO_DATA=false
export APP_ENV=dev
export SECRET_KEY=e2e-secret-key
export ADMIN_INITIAL_PASSWORD=admin
# Andaime de extração: registra o conector DEMO_MANUAL para os testes de tela
# (produção fica sem conector até a F3.2). Agendador desligado — os testes
# disparam execução manualmente.
export EXTRACAO_DEMO_CONNECTOR=1
export EXTRACAO_SCHEDULER=false
.venv/bin/python e2e/seed_usuarios_e2e.py
exec .venv/bin/uvicorn fluxocaixa.main:app --port 8433
