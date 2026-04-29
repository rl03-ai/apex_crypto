"""Intraday Matrix endpoints — tri-TF para holds 1-24h (scalping ou day)."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Query

log = logging.getLogger(__name__)
router = APIRouter(prefix='/intraday', tags=['intraday'])

EXCLUDED_SYMBOLS = {
    'USDT', 'USDC', 'DAI', 'TUSD', 'BUSD', 'USDD', 'FDUSD', 'PYUSD', 'USDE',
    'WBTC', 'WETH', 'WBNB', 'CBBTC', 'WSTETH', 'STETH', 'WEETH',
    'LUSD', 'GUSD', 'USDP', 'USDS', 'EURS', 'EURT',
}


@router.get('')
async def get_intraday_matrix(
    mode: str = Query('day', regex='^(scalping|day)$', description='scalping=5m+15m+1h, day=15m+1h+4h'),
    min_tier: str | None = Query(None),
    action: str | None = Query(None),
    stage: str | None = Query(None),
    overnight_only: bool = Query(False, description='Apenas setups que aguentam overnight'),
    limit: int = Query(60, ge=10, le=120, description='Intraday usa menos símbolos por causa do rate limit em candles 5m/15m'),
    symbols: str | None = Query(None),
    concurrency: int = Query(12, ge=5, le=25),
) -> dict:
    """Intraday matrix tri-TF."""
    from app.services.intraday_matrix import compute_intraday_matrix
    from app.services.coingecko import fetch_markets
    
    if symbols:
        custom_syms = [s.strip().upper() for s in symbols.split(',') if s.strip()]
        symbols_to_fetch = custom_syms
        coin_ids_to_fetch = [None] * len(custom_syms)
    else:
        buffer_limit = min(limit + 30, 200)
        markets = await fetch_markets(limit=buffer_limit, page=1)
        
        if not markets:
            return {
                'count': 0,
                'requested': 0,
                'mode': mode,
                'stats': {},
                'data': [],
                'error': 'CoinGecko unavailable',
                'timestamp': int(datetime.now(timezone.utc).timestamp()),
            }
        
        symbols_to_fetch, coin_ids_to_fetch = [], []
        for m in markets:
            sym = (m.get('symbol') or '').upper()
            cid = m.get('id')
            if not sym or not cid or sym in EXCLUDED_SYMBOLS:
                continue
            symbols_to_fetch.append(sym)
            coin_ids_to_fetch.append(cid)
            if len(symbols_to_fetch) >= limit:
                break
    
    log.info('Intraday matrix (%s): %d symbols', mode, len(symbols_to_fetch))
    
    rows = await compute_intraday_matrix(
        symbols_to_fetch, coin_ids_to_fetch, mode=mode, max_concurrent=concurrency,
    )
    
    if min_tier:
        tier_order = {'S': 5, 'A': 4, 'B': 3, 'C': 2, 'D': 1}
        min_t = tier_order.get(min_tier.upper(), 0)
        rows = [r for r in rows if tier_order.get(r['tier'], 0) >= min_t]
    
    if action:
        rows = [r for r in rows if r['action'] == action.upper()]
    
    if stage:
        rows = [r for r in rows if r['setup']['stage'] == stage.upper()]
    
    if overnight_only:
        rows = [r for r in rows if r.get('can_hold_overnight', False)]
    
    # Stats
    trend_bo = sum(1 for r in rows if r['setup']['stage'] == 'TREND_BO')
    vwap = sum(1 for r in rows if r['setup']['stage'] == 'VWAP_RECLAIM')
    pullback = sum(1 for r in rows if r['setup']['stage'] == 'MICRO_PULLBACK')
    sweep = sum(1 for r in rows if r['setup']['stage'] == 'LIQ_SWEEP')
    squeeze = sum(1 for r in rows if r['setup']['stage'] == 'SQUEEZE_BO')
    overnight = sum(1 for r in rows if r.get('can_hold_overnight', False))
    tier_s = sum(1 for r in rows if r['tier'] == 'S')
    tier_a = sum(1 for r in rows if r['tier'] == 'A')
    
    return {
        'count': len(rows),
        'requested': len(symbols_to_fetch),
        'mode': mode,
        'stats': {
            'trend_breakouts': trend_bo,
            'vwap_reclaims': vwap,
            'micro_pullbacks': pullback,
            'liq_sweeps': sweep,
            'squeeze_bos': squeeze,
            'overnight_eligible': overnight,
            'tier_s': tier_s,
            'tier_a': tier_a,
        },
        'data': rows,
        'timestamp': int(datetime.now(timezone.utc).timestamp()),
    }


@router.get('/{symbol}')
async def get_intraday_row(
    symbol: str,
    mode: str = Query('day', regex='^(scalping|day)$'),
    coin_id: str | None = Query(None),
) -> dict:
    """Intraday row para 1 símbolo."""
    from app.services.intraday_matrix import compute_intraday_row
    
    row = await compute_intraday_row(symbol, coin_id, mode)
    if not row:
        return {'error': f'Cannot compute intraday for {symbol}'}
    
    return row
