"""Agendador embutido das fontes de extração (spec R5, design D8).

`BackgroundScheduler` iniciado no lifespan do FastAPI, atrás da flag
`EXTRACAO_SCHEDULER` (default true). Os jobs são funções SÍNCRONAS (o
conector e o `importar_lote` são bloqueantes) — o BackgroundScheduler as
roda no seu próprio thread pool, sem depender de um event loop. Isso mantém
o agendador independente do asyncio (não interfere no event loop do
servidor nem no do TestClient nos testes) e faz o comportamento ser idêntico
em produção e em teste. Perfil single-instance: em produção rode 1 worker
(ver render.yaml); com N workers cada processo agendaria os mesmos jobs.

`coalesce=True` + `misfire_grace_time=3600`: disparos perdidos (app
hibernada) executam UMA vez ao acordar dentro da tolerância de 1h.
`max_instances=1`: nunca duas execuções simultâneas da mesma fonte.
"""
import logging

from ..bootstrap_db import env_flag

logger = logging.getLogger(__name__)

_scheduler = None


def habilitado() -> bool:
    return env_flag("EXTRACAO_SCHEDULER", True)


def _job_id(seq_fonte: int) -> str:
    return f"fonte-{seq_fonte}"


def _executar_job(seq_fonte: int) -> None:
    """Corpo do job agendado — roda em thread do executor (design D5).

    A thread usa a scoped_session própria; `remove()` em finally é a mesma
    disciplina do teardown de request."""
    from ..models.base import SessionLocal
    from ..services.extracao_service import DISPARO_AGENDADO, executar_fonte

    try:
        executar_fonte(seq_fonte, disparo=DISPARO_AGENDADO)
    except Exception:
        # Pré-condição violada entre o disparo e a execução (ex.: fonte
        # inativada); a execução com ERRO já é registrada pelo serviço nos
        # demais casos.
        logger.exception("Execução agendada da fonte %s falhou", seq_fonte)
    finally:
        SessionLocal.remove()


def iniciar() -> None:
    """Inicia o agendador e agenda as fontes ativas com cron (R5)."""
    global _scheduler
    if not habilitado():
        logger.info("EXTRACAO_SCHEDULER desabilitado — agendador não iniciado")
        return
    if _scheduler is not None:
        return

    from apscheduler.schedulers.background import BackgroundScheduler

    _scheduler = BackgroundScheduler(
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 3600,
        },
    )
    _scheduler.start()

    from ..models import FonteExtracao
    from ..models.base import SessionLocal

    try:
        for fonte in FonteExtracao.query.filter_by(ind_status="A").all():
            reagendar(fonte)
        logger.info("Agendador de extração iniciado (%d job(s))",
                    len(_scheduler.get_jobs()))
    finally:
        SessionLocal.remove()


def encerrar() -> None:
    global _scheduler
    if _scheduler is None:
        return
    try:
        _scheduler.shutdown(wait=False)
    except Exception:  # já parado — nada a fazer
        pass
    _scheduler = None


def reagendar(fonte) -> None:
    """Sincroniza o job da fonte com o cadastro (criar/alterar/inativar)."""
    if _scheduler is None:
        return

    from apscheduler.triggers.cron import CronTrigger

    job_id = _job_id(fonte.seq_fonte_extracao)
    if _scheduler.get_job(job_id) is not None:
        _scheduler.remove_job(job_id)
    if fonte.ind_status == "A" and fonte.txt_cron:
        _scheduler.add_job(
            _executar_job,
            CronTrigger.from_crontab(fonte.txt_cron),
            args=[fonte.seq_fonte_extracao],
            id=job_id,
            name=f"Extração: {fonte.nom_fonte}",
        )


def job_da_fonte(seq_fonte: int):
    """Job agendado da fonte, ou None (consulta para telas/testes)."""
    if _scheduler is None:
        return None
    return _scheduler.get_job(_job_id(seq_fonte))
