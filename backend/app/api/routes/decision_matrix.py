"""Decision Matrix endpoints — composite score + tier + action."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)
router = APIRouter(prefix='/matrix', tags=['matrix'])

# Top 50 símbolos por market cap (manual map para velocidade)
# (Binance symbol short, CoinGecko id)
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
    ('IMX', 'immutable-x'),
    ('STX', 'blockstack'),
    ('FTM', 'fantom'),
    ('ALGO', 'algorand'),
    ('MATIC', 'matic-network'),
    ('HBAR', 'hedera-hashgraph'),
    ('VET', 'vechain'),
    ('ICP', 'internet-computer'),
    ('THETA', 'theta-token'),
    ('XLM', 'stellar'),
    ('GRT', 'the-graph'),
    ('LDO', 'lido-dao'),
    ('SAND', 'the-sandbox'),
    ('MANA', 'decentraland'),
    ('AXS', 'axie-infinity'),
    ('CRV', 'curve-dao-token'),
    ('SNX', 'havven'),
    ('PEPE', 'pepe'),
    ('WLD', 'worldcoin-wld'),
    ('ORDI', 'ordinals'),
    ('JUP', 'jupiter-exchange-solana'),
    ('PYTH', 'pyth-network'),
    ('JTO', 'jito-governance-token'),
    ('STRK', 'starknet'),
    ('ENA', 'ethena'),
]


@router.get('')
async def get_decision_matrix(
    min_tier: str | None = Query(None, description="'S' | 'A' | 'B' | 'C' | 'D'"),
    action: str | None = Query(None, description="'STRONG BUY' | 'BUY' | 'HOLD' | 'SELL' | 'STRONG SELL'"),
    direction: str | None = Query(None, description="'long' (composite > 0) | 'short' (< 0)"),
    limit: int = Query(50, ge=5, le=100, description='Max símbolos a processar (5-100)'),
    symbols: str | None = Query(None, description="Override lista (ex: 'BTC,ETH,SOL')"),
) -> dict:
    """Decision matrix para top símbolos (composite InstDash + Whale)."""
    from app.services.decision_matrix import compute_matrix
    
    # Override custom de símbolos
    if symbols:
        custom_syms = [s.strip().upper() for s in symbols.split(',') if s.strip()]
        # Procura coin_ids no map
        sym_list = []
        for s in custom_syms:
            cid = next((c for sym, c in TOP_SYMBOLS_MAP if sym == s), None)
            sym_list.append((s, cid))
        symbols_to_fetch = [s for s, _ in sym_list]
        coin_ids_to_fetch = [c for _, c in sym_list]
    else:
        # Default: top N por market cap
        sym_list = TOP_SYMBOLS_MAP[:limit]
        symbols_to_fetch = [s for s, _ in sym_list]
        coin_ids_to_fetch = [c for _, c in sym_list]
    
    rows = await compute_matrix(symbols_to_fetch, coin_ids_to_fetch)
    
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
    tier_s = sum(1 for r in rows if r['tier'] == 'S')
    tier_a = sum(1 for r in rows if r['tier'] == 'A')
    
    return {
        'count': total,
        'requested': len(symbols_to_fetch),
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
    
    coin_id = next((c for s, c in TOP_SYMBOLS_MAP if s == symbol.upper()), None)
    
    row = await compute_decision_row(symbol, coin_id)
    if not row:
        return {'error': f'Cannot compute matrix for {symbol}'}
    
    return row
