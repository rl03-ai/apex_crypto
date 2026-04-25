"""Job: cleanup_old_alerts

Corre uma vez por dia.

Elimina alertas já lidos com mais de KEEP_DAYS dias para evitar
que a tabela de alertas cresça indefinidamente.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.core.database import SessionLocal
from app.models.alert import Alert

log = logging.getLogger(__name__)
KEEP_DAYS = 30  # manter alertas lidos durante 30 dias


def run() -> dict:
    db = SessionLocal()
    stats = {'deleted': 0}
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
        deleted = (
            db.query(Alert)
            .filter(Alert.is_read == True, Alert.created_at < cutoff)  # noqa: E712
            .delete()
        )
        db.commit()
        stats['deleted'] = deleted
        log.info('cleanup_old_alerts: eliminados %d alertas lidos com >%d dias.', deleted, KEEP_DAYS)
    except Exception as exc:
        log.exception('cleanup_old_alerts: erro — %s', exc)
    finally:
        db.close()
    return stats
