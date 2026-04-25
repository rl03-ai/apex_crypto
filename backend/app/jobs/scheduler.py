"""Scheduler — APScheduler BackgroundScheduler.

Jobs registados:
  check_alerts       → cada 10 min  (verificar thresholds de preço/score na watchlist)
  update_portfolios  → cada 15 min  (actualizar preços e P&L das posições abertas)
  cleanup_alerts     → uma vez por dia às 02:00 UTC

Para alterar os intervalos, mudar as variáveis de ambiente ou os defaults abaixo.
Para desactivar um job em produção sem reimplantar, basta comentar a linha add_job.

O scheduler NÃO é iniciado se SCHEDULER_ENABLED=false no .env.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings

log = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> None:
    global _scheduler

    settings = get_settings()
    if not settings.scheduler_enabled:
        log.info('Scheduler desactivado (SCHEDULER_ENABLED=false).')
        return

    if _scheduler and _scheduler.running:
        log.warning('Scheduler já está a correr.')
        return

    _scheduler = BackgroundScheduler(timezone='UTC', job_defaults={'max_instances': 1, 'misfire_grace_time': 60})

    # ── Job 1: verificar alertas de watchlist ──────────────────────────────────
    from app.jobs.check_alerts import run as run_check_alerts
    _scheduler.add_job(
        run_check_alerts,
        trigger=IntervalTrigger(minutes=settings.alert_check_interval_minutes),
        id='check_alerts',
        name='Verificar alertas watchlist',
        replace_existing=True,
    )
    log.info('Job "check_alerts" registado: cada %d min.', settings.alert_check_interval_minutes)

    # ── Job 2: actualizar preços de portfolios ─────────────────────────────────
    from app.jobs.update_portfolios import run as run_update_portfolios
    _scheduler.add_job(
        run_update_portfolios,
        trigger=IntervalTrigger(minutes=settings.portfolio_update_interval_minutes),
        id='update_portfolios',
        name='Actualizar preços portfolios',
        replace_existing=True,
    )
    log.info('Job "update_portfolios" registado: cada %d min.', settings.portfolio_update_interval_minutes)

    # ── Job 3: limpeza de alertas antigos ─────────────────────────────────────
    from app.jobs.cleanup_alerts import run as run_cleanup
    _scheduler.add_job(
        run_cleanup,
        trigger=CronTrigger(hour=2, minute=0),   # 02:00 UTC diariamente
        id='cleanup_alerts',
        name='Limpar alertas antigos',
        replace_existing=True,
    )
    log.info('Job "cleanup_alerts" registado: diariamente às 02:00 UTC.')

    _scheduler.start()
    log.info('Scheduler iniciado com %d jobs.', len(_scheduler.get_jobs()))


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info('Scheduler parado.')


def get_scheduler() -> BackgroundScheduler | None:
    return _scheduler


def get_job_status() -> list[dict]:
    """Para o endpoint /jobs/status."""
    if not _scheduler:
        return []
    return [
        {
            'id':        job.id,
            'name':      job.name,
            'next_run':  job.next_run_time.isoformat() if job.next_run_time else None,
            'trigger':   str(job.trigger),
        }
        for job in _scheduler.get_jobs()
    ]
