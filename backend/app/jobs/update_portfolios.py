"""Job: update_portfolio_prices

Corre a cada N minutos (definido no scheduler).

Lógica:
  1. Recolhe todas as posições abertas de todos os portfolios
  2. Batch fetch de preços ao CoinGecko (um único request)
  3. Actualiza current_price, current_value, pnl, pnl_pct em cada posição
  4. Se P&L > +20% ou < -15% cria alerta de sistema para o utilizador

Isolamento de erros por posição — uma falha não afecta as restantes.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.jobs.check_alerts import DEDUP_HOURS, _already_fired, _fire
from app.models.portfolio import Portfolio, Position

log = logging.getLogger(__name__)

# Thresholds para alertas automáticos de P&L
PNL_ALERT_GAIN_PCT  =  20.0   # +20% → alerta de ganho
PNL_ALERT_LOSS_PCT  = -15.0   # -15% → alerta de perda


async def _run_async() -> dict:
    from app.services.coingecko import fetch_markets_by_ids

    db = SessionLocal()
    stats = {'updated': 0, 'no_price': 0, 'alerts_fired': 0, 'errors': 0}

    try:
        positions = (
            db.query(Position)
            .filter(Position.status == 'open')
            .all()
        )

        if not positions:
            log.info('update_portfolio_prices: sem posições abertas.')
            return stats

        # Mapa posição → user_id (via portfolio)
        portfolio_ids = list({p.portfolio_id for p in positions})
        portfolios    = {p.id: p for p in db.query(Portfolio).filter(Portfolio.id.in_(portfolio_ids)).all()}

        coin_ids = list({p.coin_id for p in positions})
        log.info('update_portfolio_prices: a actualizar %d posições / %d moedas…', len(positions), len(coin_ids))

        markets   = await fetch_markets_by_ids(coin_ids)
        price_map = {m['id']: m.get('current_price') for m in markets}
        now       = datetime.now(timezone.utc)

        for pos in positions:
            try:
                price = price_map.get(pos.coin_id)
                if price is None:
                    stats['no_price'] += 1
                    continue

                old_value = pos.current_value

                pos.current_price   = price
                pos.current_value   = round(price * pos.quantity, 2)
                pos.pnl             = round(pos.current_value - pos.invested_amount, 2)
                pos.pnl_pct         = round(pos.pnl / pos.invested_amount * 100, 2) if pos.invested_amount else 0.0
                pos.last_refreshed_at = now
                stats['updated'] += 1

                # Alertas automáticos de P&L
                portfolio = portfolios.get(pos.portfolio_id)
                if portfolio:
                    user_id = portfolio.user_id
                    sym = pos.symbol or pos.coin_id.upper()

                    if pos.pnl_pct >= PNL_ALERT_GAIN_PCT:
                        _fire(
                            db, user_id, pos.coin_id, 'pnl_gain',
                            title=f'{sym} P&L +{pos.pnl_pct:.1f}%',
                            message=(
                                f'A tua posição em {sym} ({portfolio.name}) '
                                f'está com P&L de +{pos.pnl_pct:.1f}% '
                                f'(${pos.pnl:,.2f}). Preço actual: ${price:,.2f}.'
                            ),
                            severity='info',
                        )
                        stats['alerts_fired'] += 1

                    elif pos.pnl_pct <= PNL_ALERT_LOSS_PCT:
                        _fire(
                            db, user_id, pos.coin_id, 'pnl_loss',
                            title=f'{sym} P&L {pos.pnl_pct:.1f}%',
                            message=(
                                f'A tua posição em {sym} ({portfolio.name}) '
                                f'está com P&L de {pos.pnl_pct:.1f}% '
                                f'(${pos.pnl:,.2f}). Preço actual: ${price:,.2f}.'
                            ),
                            severity='warning',
                        )
                        stats['alerts_fired'] += 1

            except Exception as exc:
                log.warning('Erro ao actualizar posição %s: %s', pos.coin_id, exc)
                stats['errors'] += 1

        db.commit()

    except Exception as exc:
        log.exception('update_portfolio_prices: erro crítico — %s', exc)
        stats['errors'] += 1
    finally:
        db.close()

    log.info(
        'update_portfolio_prices: actualizadas=%d sem_preço=%d alertas=%d erros=%d',
        stats['updated'], stats['no_price'], stats['alerts_fired'], stats['errors'],
    )
    return stats


def run() -> dict:
    """Entry point síncrono para APScheduler."""
    return asyncio.run(_run_async())
