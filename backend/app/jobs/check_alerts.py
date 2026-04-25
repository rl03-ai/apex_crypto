"""Job: check_watchlist_alerts

Corre a cada N minutos (definido no scheduler).

Lógica:
  1. Recolhe todos os coin_ids únicos de todas as watchlists (todos os users)
  2. Faz um único batch fetch ao CoinGecko
  3. Para cada entrada de watchlist, avalia os thresholds configurados
  4. Se algum threshold for ultrapassado, cria um Alert na DB
  5. Deduplicação: não cria o mesmo tipo de alerta para o mesmo (user, coin)
     se já existir um não lido nas últimas DEDUP_HOURS horas

Garante isolamento de erros: falha de um user/coin não afecta os outros.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.alert import Alert
from app.models.watchlist import WatchlistEntry
from app.services.coingecko import fetch_markets_by_ids
from app.services.scoring import crypto_score

log = logging.getLogger(__name__)

DEDUP_HOURS = 6  # não re-dispara o mesmo alerta durante este período


# ── helpers ───────────────────────────────────────────────────────────────────

def _already_fired(db: Session, user_id: str, coin_id: str, alert_type: str) -> bool:
    """Verifica se já existe alerta não lido recente para evitar spam."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=DEDUP_HOURS)
    return (
        db.query(Alert)
        .filter(
            Alert.user_id   == user_id,
            Alert.coin_id   == coin_id,
            Alert.alert_type == alert_type,
            Alert.is_read   == False,  # noqa: E712
            Alert.created_at >= cutoff,
        )
        .first()
    ) is not None


def _fire(db: Session, user_id: str, coin_id: str, alert_type: str,
          title: str, message: str, severity: str = 'info') -> None:
    if _already_fired(db, user_id, coin_id, alert_type):
        log.debug('Alerta duplicado ignorado: %s / %s / %s', user_id[:8], coin_id, alert_type)
        return
    alert = Alert(
        user_id=user_id,
        alert_type=alert_type,
        severity=severity,
        coin_id=coin_id,
        title=title,
        message=message,
    )
    db.add(alert)
    log.info('🔔 Alerta criado: [%s] %s — %s', severity.upper(), title, message)


def _fmt_price(p: float) -> str:
    return f'${p:,.2f}' if p < 10_000 else f'${p:,.0f}'


# ── core ──────────────────────────────────────────────────────────────────────

async def _run_async() -> dict:
    db = SessionLocal()
    stats = {'checked': 0, 'alerts_fired': 0, 'errors': 0}

    try:
        # 1. Recolher todas as entradas de watchlist com pelo menos um threshold definido
        entries = (
            db.query(WatchlistEntry)
            .filter(
                (WatchlistEntry.alert_price_above  != None) |  # noqa: E711
                (WatchlistEntry.alert_price_below  != None) |  # noqa: E711
                (WatchlistEntry.alert_score_above  != None)    # noqa: E711
            )
            .all()
        )

        if not entries:
            log.info('check_watchlist_alerts: sem entradas com alertas configurados.')
            return stats

        # 2. Batch fetch — um único request para todos os coin_ids únicos
        coin_ids = list({e.coin_id for e in entries})
        log.info('check_watchlist_alerts: a verificar %d moedas para %d entradas…', len(coin_ids), len(entries))

        markets = await fetch_markets_by_ids(coin_ids)
        price_map: dict[str, dict] = {m['id']: m for m in markets}

        # 3. Avaliar cada entrada
        alerts_before = stats['alerts_fired']
        for entry in entries:
            try:
                raw = price_map.get(entry.coin_id)
                if not raw:
                    log.debug('Sem dados para %s — a saltar.', entry.coin_id)
                    continue

                stats['checked'] += 1
                current_price = raw.get('current_price') or 0.0
                score = crypto_score(raw)
                current_score = score.get('total_score', 0.0)
                sym = entry.symbol or entry.coin_id.upper()

                # Alerta: preço acima
                if entry.alert_price_above is not None and current_price >= entry.alert_price_above:
                    _fire(
                        db, entry.user_id, entry.coin_id, 'price_above',
                        title=f'{sym} acima de {_fmt_price(entry.alert_price_above)}',
                        message=f'{sym} está a {_fmt_price(current_price)} — ultrapassou o teu alerta de {_fmt_price(entry.alert_price_above)}.',
                        severity='info',
                    )
                    stats['alerts_fired'] += 1

                # Alerta: preço abaixo
                if entry.alert_price_below is not None and current_price <= entry.alert_price_below:
                    _fire(
                        db, entry.user_id, entry.coin_id, 'price_below',
                        title=f'{sym} abaixo de {_fmt_price(entry.alert_price_below)}',
                        message=f'{sym} está a {_fmt_price(current_price)} — caiu abaixo do teu alerta de {_fmt_price(entry.alert_price_below)}.',
                        severity='warning',
                    )
                    stats['alerts_fired'] += 1

                # Alerta: score acima
                if entry.alert_score_above is not None and current_score >= entry.alert_score_above:
                    _fire(
                        db, entry.user_id, entry.coin_id, 'score_above',
                        title=f'{sym} score {current_score:.0f} — acima de {entry.alert_score_above:.0f}',
                        message=(
                            f'{sym} atingiu score {current_score:.1f}/100 '
                            f'(estado: {score.get("state","—")}). '
                            f'Preço actual: {_fmt_price(current_price)}.'
                        ),
                        severity='info' if current_score < 80 else 'warning',
                    )
                    stats['alerts_fired'] += 1

            except Exception as exc:
                log.warning('Erro ao processar entrada %s: %s', entry.coin_id, exc)
                stats['errors'] += 1

        if stats['alerts_fired'] > alerts_before:
            db.commit()
        else:
            log.info('check_watchlist_alerts: nenhum threshold ultrapassado.')

    except Exception as exc:
        log.exception('check_watchlist_alerts: erro crítico — %s', exc)
        stats['errors'] += 1
    finally:
        db.close()

    log.info(
        'check_watchlist_alerts: verificadas=%d alertas=%d erros=%d',
        stats['checked'], stats['alerts_fired'], stats['errors'],
    )
    return stats


def run() -> dict:
    """Entry point síncrono para APScheduler."""
    return asyncio.run(_run_async())
