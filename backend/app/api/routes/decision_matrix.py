"""Decision Matrix endpoints — composite score + tier + action.

Lista dinâmica do top N por market cap (CoinGecko), processada em paralelo
com semaphore para evitar saturar APIs.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Query

log = logging.getLogger(__name__)
router = APIRouter(prefix='/matrix', tags=['matrix'])


# Stablecoins e wrapped tokens que devem ser excluídos da matriz
EXCLUDED_SYMBOLS = {
    'USDT', 'USDC', 'DAI', 'TUSD', 'BUSD', 'USDD', 'FDUSD', 'PYUSD', 'USDE',
    'WBTC', 'WETH', 'WBNB', 'CBBTC', 'WSTETH', 'STETH', 'WEETH',  # wrapped/staked
    'LUSD', 'GUSD', 'USDP', 'USDS', 'EURS', 'EURT',  # stables minor
}


@router.get('')
async def get_decision_matrix(
    min_tier: str | None = Query(None, description="'S' | 'A' | 'B' | 'C' | 'D'"),
    action: str | None = Query(None, description="'STRONG BUY' | 'BUY' | 'HOLD' | 'SELL' | 'STRONG SELL'"),
    direction: str | None = Query(None, description="'long' | 'short'"),
    limit: int = Query(100, ge=10, le=200, description='Símbolos a processar (10-200)'),
    symbols: str | None = Query(None, description="Override (ex: 'BTC,ETH,SOL')"),
    concurrency: int = Query(20, ge=5, le=50, description='Tarefas paralelas (5-50)'),
) -> dict:
    """Decision matrix com top N por market cap (CoinGecko)."""
    from app.services.decision_matrix import compute_matrix
    from app.services.coingecko import fetch_markets
    
    # Override custom de símbolos
    if symbols:
        custom_syms = [s.strip().upper() for s in symbols.split(',') if s.strip()]
        symbols_to_fetch = custom_syms
        coin_ids_to_fetch = [None] * len(custom_syms)
    else:
        # Fetch top N + buffer (para cobrir exclusions)
        buffer_limit = min(limit + 30, 250)
        markets = await fetch_markets(limit=buffer_limit, page=1)
        
        if not markets:
            return {
                'count': 0,
                'requested': 0,
                'stats': {'bullish': 0, 'bearish': 0, 'tier_s': 0, 'tier_a': 0},
                'data': [],
                'error': 'CoinGecko unavailable — try again in a minute',
                'timestamp': int(datetime.now(timezone.utc).timestamp()),
            }
        
        # Extract symbol + coin_id, exclude stables/wrapped
        symbols_to_fetch = []
        coin_ids_to_fetch = []
        for m in markets:
            sym = (m.get('symbol') or '').upper()
            cid = m.get('id')
            if not sym or not cid:
                continue
            if sym in EXCLUDED_SYMBOLS:
                continue
            symbols_to_fetch.append(sym)
            coin_ids_to_fetch.append(cid)
            if len(symbols_to_fetch) >= limit:
                break
    
    log.info('Matrix: processing %d symbols (concurrency=%d)', len(symbols_to_fetch), concurrency)
    
    rows = await compute_matrix(
        symbols_to_fetch,
        coin_ids_to_fetch,
        max_concurrent=concurrency,
    )
    
    # Filtros pós-fetch
    if min_tier:
        tier_order = {'S': 5, 'A': 4, 'B': 3, 'C': 2, 'D': 1}
        min_t = tier_order.get(min_tier.upper(), 0)
        rows = [r for r in rows if tier_order.get(r['tier'], 0) >= min_t]
    
    if action:
        rows = [r for r in rows if r['action'] == action.upper()]
    
    if direction == 'long':
        rows = [r for r in rows if r['composite'] > 0]
    elif direction == 'short':
        rows = [r for r in rows if r['composite'] < 0]
    
    # Aggregate stats
    total = len(rows)
    bullish = sum(1 for r in rows if r['composite'] >= 3)
    bearish = sum(1 for r in rows if r['composite'] <= -3)
    
    # Stage counts
    accumulating = sum(1 for r in rows if r['stage_1d']['stage'] == 'ACCUMULATION' or (r.get('stage_1w') and r['stage_1w']['stage'] == 'ACCUMULATION'))
    early_markup = sum(1 for r in rows if r['stage_1d']['stage'] == 'MARKUP_EARLY' or (r.get('stage_1w') and r['stage_1w']['stage'] == 'MARKUP_EARLY'))
    extended = sum(1 for r in rows if r['stage_1d']['stage'] == 'EXTENDED' or (r.get('stage_1w') and r['stage_1w']['stage'] == 'EXTENDED'))
    
    tier_s = sum(1 for r in rows if r['tier'] == 'S')
    tier_a = sum(1 for r in rows if r['tier'] == 'A')
    
    return {
        'count': total,
        'requested': len(symbols_to_fetch),
        'stats': {
            'bullish': bullish,
            'bearish': bearish,
            'accumulating': accumulating,
            'early_markup': early_markup,
            'extended': extended,
            'tier_s': tier_s,
            'tier_a': tier_a,
        },
        'data': rows,
        'timestamp': int(datetime.now(timezone.utc).timestamp()),
    }


@router.get('/{symbol}')
async def get_matrix_row(symbol: str, coin_id: str | None = Query(None)) -> dict:
    """Decision matrix para um único símbolo."""
    from app.services.decision_matrix import compute_decision_row
    
    row = await compute_decision_row(symbol, coin_id)
    if not row:
        return {'error': f'Cannot compute matrix for {symbol}'}
    
    return row
