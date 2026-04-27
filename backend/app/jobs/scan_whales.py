"""Job: scan_whales — detecta smart money activity via OI + liquidations.

Corre a cada 2h (complementa scan_instdash que corre a 4h).
Popula cache de whale metrics para os top symbols.
"""
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


async def run_async() -> dict:
    """Run whale scan (async version).

    Returns:
        {
            'scanned': 20,
            'with_whale_signal': 5,
            'timestamp': 1234567890,
        }
    """
    from app.services.whale_tracking import fetch_whale_metrics
    from app.services.whale_tracking.coinglass import _CACHE

    # Top 20 symbols para rastrear
    top_symbols = [
        'BTC', 'ETH', 'BNB', 'SOL', 'ADA', 'DOGE', 'XRP', 'TON', 'LINK',
        'XAG', 'USOIL', 'XAUT', 'UNI', 'AVAX', 'MATIC', 'ARB', 'FTM', 'AAVE',
    ]

    scanned = 0
    with_whale = 0

    for symbol in top_symbols:
        try:
            metrics = await fetch_whale_metrics(symbol)
            if metrics:
                scanned += 1
                # Check se há whale signal (score != 0)
                if metrics.get('oi') or metrics.get('liq'):
                    with_whale += 1
                log.debug(
                    'Whale metrics %s: OI %s, Liq %s',
                    symbol,
                    'OK' if metrics.get('oi') else '—',
                    'OK' if metrics.get('liq') else '—',
                )
        except Exception as e:
            log.debug('Whale scan %s falhou: %s', symbol, e)

    return {
        'scanned': scanned,
        'with_whale_signal': with_whale,
        'timestamp': int(datetime.now(timezone.utc).timestamp()),
    }


def run() -> dict:
    """Sync wrapper (para scheduler)."""
    import asyncio

    try:
        result = asyncio.run(run_async())
        log.info('scan_whales: %s', result)
        return result
    except Exception as e:
        log.exception('scan_whales falhou: %s', e)
        return {'error': str(e)}
