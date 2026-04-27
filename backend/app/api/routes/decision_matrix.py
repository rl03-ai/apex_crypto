"""Decision Matrix endpoints — composite score + tier + action.

GET /matrix              → matriz para top symbols
GET /matrix/{symbol}     → row específica
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Query

log = logging.getLogger(__name__)
router = APIRouter(prefix='/matrix', tags=['matrix'])

# Top 25 símbolos para tracking
TOP_SYMBOLS_MAP = [
    ('BTC', 'bitcoin'),
    ('ETH', 'ethereum'),
    ('BNB', 'binancecoin'),
    ('SOL', 'solana'),
    ('XRP', 'ripple'),
    ('ADA', 'cardano'),
    ('DOGE', 'dogecoin'),
    ('TON', 'the-open-network'),
    ('LINK', 'chainlink'),
    ('AVAX', 'avalanche-2'),
    ('UNI', 'uniswap'),
    ('AAVE', 'aave'),
    ('DOT', 'polkadot'),
    ('NEAR', 'near'),
    ('ATOM', 'cosmos'),
    ('LTC', 'litecoin'),
    ('SUI', 'sui'),
    ('APT', 'aptos'),
    ('ARB', 'arbitrum'),
    ('OP', 'optimism'),
    ('INJ', 'injective-protocol'),
    ('FIL', 'filecoin'),
    ('TIA', 'celestia'),
    ('SEI', 'sei-network'),
    ('RNDR', 'render-token'),
]


@router.get('')
async def get_decision_matrix(
    min_tier: str | None = Query(None, description="'S' | 'A' | 'B' | 'C' | 'D'"),
    action: str | None = Query(None, description="'STRONG BUY' | 'BUY' | 'HOLD' | 'SELL' | 'STRONG SELL'"),
    direction: str | None = Query(None, description="'long' (composite > 0) | 'short' (< 0)"),
) -> dict:
    """Decision matrix para top símbolos (composite InstDash + Whale)."""
    from app.services.decision_matrix import compute_matrix
    
    symbols = [s for s, _ in TOP_SYMBOLS_MAP]
    coin_ids = [c for _, c in TOP_SYMBOLS_MAP]
    
    rows = await compute_matrix(symbols, coin_ids)
    
    # Filtros
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
    tier_s = sum(1 for r in rows if r['tier'] == 'S')
    tier_a = sum(1 for r in rows if r['tier'] == 'A')
    
    return {
        'count': total,
        'stats': {
            'bullish': bullish,
            'bearish': bearish,
            'tier_s': tier_s,
            'tier_a': tier_a,
        },
        'data': rows,
        'timestamp': int(datetime.now(timezone.utc).timestamp()),
    }


@router.get('/{symbol}')
async def get_matrix_row(symbol: str) -> dict:
    """Decision matrix para um único símbolo."""
    from app.services.decision_matrix import compute_decision_row
    
    # Tenta resolver coin_id do nosso mapa; senão usa symbol directo
    coin_id = next((c for s, c in TOP_SYMBOLS_MAP if s == symbol.upper()), None)
    
    row = await compute_decision_row(symbol, coin_id)
    if not row:
        return {'error': f'Cannot compute matrix for {symbol}'}
    
    return row
