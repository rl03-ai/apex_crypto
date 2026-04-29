"""Swing Matrix endpoints — tri-TF analysis para holds 3-14d ou 1-4 semanas."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Query

log = logging.getLogger(__name__)
router = APIRouter(prefix='/swing', tags=['swing'])

EXCLUDED_SYMBOLS = {
    'USDT', 'USDC', 'DAI', 'TUSD', 'BUSD', 'USDD', 'FDUSD', 'PYUSD', 'USDE',
    'WBTC', 'WETH', 'WBNB', 'CBBTC', 'WSTETH', 'STETH', 'WEETH',
    'LUSD', 'GUSD', 'USDP', 'USDS', 'EURS', 'EURT',
}


@router.get('')
async def get_swing_matrix(
    mode: str = Query('short', regex='^(short|medium)$', description='short=3-14d, medium=1-4 sem'),
    min_tier: str | None = Query(None, description="'S' | 'A' | 'B' | 'C' | 'D'"),
    action: str | None = Query(None),
    stage: str | None = Query(None, description='BREAKOUT | PULLBACK | MOMENTUM | REVERSAL'),
    limit: int = Query(80, ge=10, le=150),
    symbols: str | None = Query(None),
    concurrency: int = Query(15, ge=5, le=30),
) -> dict:
    """Swing matrix tri-TF (1h+4h+1d ou 4h+1d+1w)."""
    from app.services.swing_matrix import compute_swing_matrix
    from app.services.coingecko import fetch_markets
    
    # Override custom de símbolos
    if symbols:
        custom_syms = [s.strip().upper() for s in symbols.split(',') if s.strip()]
        symbols_to_fetch = custom_syms
        coin_ids_to_fetch = [None] * len(custom_syms)
    else:
        # Fetch top N + buffer
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
    
    log.info('Swing matrix (%s): %d symbols', mode, len(symbols_to_fetch))
    
    rows = await compute_swing_matrix(
        symbols_to_fetch, coin_ids_to_fetch, mode=mode, max_concurrent=concurrency,
    )
    
    # Filtros pós-fetch
    if min_tier:
        tier_order = {'S': 5, 'A': 4, 'B': 3, 'C': 2, 'D': 1}
        min_t = tier_order.get(min_tier.upper(), 0)
        rows = [r for r in rows if tier_order.get(r['tier'], 0) >= min_t]
    
    if action:
        rows = [r for r in rows if r['action'] == action.upper()]
    
    if stage:
        rows = [r for r in rows if r['swing']['stage'] == stage.upper()]
    
    # Aggregate stats
    breakouts = sum(1 for r in rows if r['swing']['stage'] == 'BREAKOUT')
    pullbacks = sum(1 for r in rows if r['swing']['stage'] == 'PULLBACK')
    momentum = sum(1 for r in rows if r['swing']['stage'] == 'MOMENTUM')
    reversal = sum(1 for r in rows if r['swing']['stage'] == 'REVERSAL')
    avoid = sum(1 for r in rows if r['action'] == 'AVOID')
    tier_s = sum(1 for r in rows if r['tier'] == 'S')
    tier_a = sum(1 for r in rows if r['tier'] == 'A')
    
    return {
        'count': len(rows),
        'requested': len(symbols_to_fetch),
        'mode': mode,
        'stats': {
            'breakouts': breakouts,
            'pullbacks': pullbacks,
            'momentum': momentum,
            'reversal': reversal,
            'avoid': avoid,
            'tier_s': tier_s,
            'tier_a': tier_a,
        },
        'data': rows,
        'timestamp': int(datetime.now(timezone.utc).timestamp()),
    }


@router.get('/{symbol}')
async def get_swing_row(
    symbol: str,
    mode: str = Query('short', regex='^(short|medium)$'),
    coin_id: str | None = Query(None),
) -> dict:
    """Swing row para 1 símbolo."""
    from app.services.swing_matrix import compute_swing_row
    
    row = await compute_swing_row(symbol, coin_id, mode)
    if not row:
        return {'error': f'Cannot compute swing for {symbol}'}
    
    return row
