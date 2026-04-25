"""Endpoints de administração dos jobs.

GET  /jobs/status             → estado do scheduler e próximas execuções
POST /jobs/run/check-alerts   → trigger manual do job de alertas
POST /jobs/run/update-portfolios → trigger manual do job de portfolios
POST /jobs/run/cleanup        → trigger manual da limpeza

Útil para testar sem esperar pelo intervalo do cron.
Requer autenticação (usa o mesmo CurrentUser dos outros endpoints).
"""
import logging
from fastapi import APIRouter, BackgroundTasks

from app.api.deps import CurrentUser
from app.jobs.scheduler import get_job_status

log = logging.getLogger(__name__)
router = APIRouter()


@router.get('/status')
def jobs_status(current_user: CurrentUser) -> dict:
    """Devolve o estado do scheduler e próximas execuções de cada job."""
    from app.core.config import get_settings
    settings = get_settings()
    return {
        'scheduler_enabled': settings.scheduler_enabled,
        'alert_check_interval_minutes': settings.alert_check_interval_minutes,
        'portfolio_update_interval_minutes': settings.portfolio_update_interval_minutes,
        'jobs': get_job_status(),
    }


@router.post('/run/check-alerts')
def trigger_check_alerts(current_user: CurrentUser, bg: BackgroundTasks) -> dict:
    """Dispara o job de alertas imediatamente em background."""
    from app.jobs.check_alerts import run
    bg.add_task(_run_and_log, 'check_alerts', run)
    return {'message': 'Job check_alerts iniciado em background.'}


@router.post('/run/update-portfolios')
def trigger_update_portfolios(current_user: CurrentUser, bg: BackgroundTasks) -> dict:
    """Dispara o job de actualização de portfolios imediatamente em background."""
    from app.jobs.update_portfolios import run
    bg.add_task(_run_and_log, 'update_portfolios', run)
    return {'message': 'Job update_portfolios iniciado em background.'}


@router.post('/run/cleanup')
def trigger_cleanup(current_user: CurrentUser, bg: BackgroundTasks) -> dict:
    """Dispara a limpeza de alertas antigos imediatamente em background."""
    from app.jobs.cleanup_alerts import run
    bg.add_task(_run_and_log, 'cleanup_alerts', run)
    return {'message': 'Job cleanup_alerts iniciado em background.'}


def _run_and_log(name: str, fn) -> None:
    try:
        result = fn()
        log.info('Job %s (manual): %s', name, result)
    except Exception as exc:
        log.exception('Job %s (manual) falhou: %s', name, exc)
