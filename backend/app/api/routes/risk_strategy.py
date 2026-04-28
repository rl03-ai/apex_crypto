"""Risk + Strategy endpoints — position sizing, allocations, DCA, sector rotation."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Query

log = logging.getLogger(__name__)
risk_router = APIRouter(prefix='/risk', tags=['risk'])
strategy_router = APIRouter(prefix='/strategy', tags=['strategy'])


@risk_router.get('/position-size')
async def calculate_position_size(
    symbol: str,
    portfolio_usd: float = Query(10000, gt=0),
    profile: str = Query('aggressive', regex='^(conservative|balanced|aggressive)$'),
) -> dict:
    """Calcula position size + SL/TP para um símbolo específico."""
    from app.services.decision_matrix import compute_decision_row
    from app.services.risk_model import compute_position_size, compute_stop_levels
    
    # Get matrix row para este symbol
    row = await compute_decision_row(symbol, None)
    if not row:
        return {'error': f'Cannot analyse {symbol}'}
    
    # Get atr from analyser (pela instdash data — atr_pct)
    from app.services.instdash import analyse_symbol
    from app.services.binance import resolve_binance_symbol
    
    if symbol.upper().endswith('USDT'):
        binance_sym = symbol.upper()
    else:
        binance_sym = await resolve_binance_symbol(symbol, fallback_symbol=symbol)
    
    if not binance_sym:
        return {'error': f'Cannot resolve symbol {symbol}'}
    
    instdash = await analyse_symbol(binance_sym, interval='1d', htf_interval='1w')
    if not instdash:
        return {'error': f'No data for {binance_sym}'}
    
    atr_pct = instdash.get('atr_pct', 3.0)
    price = instdash.get('price', 0)
    
    # Stage detection
    stage = row['stage_1d']['stage']
    aligned = bool(instdash.get('aligned_bull') or instdash.get('aligned_bear'))
    
    # Compute SL/TP
    stops = compute_stop_levels(price, atr_pct, stage, aligned)
    
    if not stops.get('recommended'):
        return {
            'symbol': binance_sym,
            'price': price,
            'stage': stage,
            'tier': row['tier'],
            'action': row['action'],
            'stops': stops,
            'position': None,
            'reason': stops.get('reason'),
        }
    
    # Compute position size
    position = compute_position_size(
        portfolio_usd=portfolio_usd,
        entry_price=price,
        sl_price=stops['sl'],
        tier=row['tier'],
        stage=stage,
        profile=profile,
        score=row['stage_1d']['score'],
    )
    
    return {
        'symbol': binance_sym,
        'price': price,
        'stage': stage,
        'tier': row['tier'],
        'action': row['action'],
        'profile': profile,
        'stops': stops,
        'position': position,
        'timestamp': int(datetime.now(timezone.utc).timestamp()),
    }


@risk_router.get('/portfolio')
async def calculate_portfolio_risk(
    portfolio_usd: float = Query(10000, gt=0),
    profile: str = Query('aggressive', regex='^(conservative|balanced|aggressive)$'),
) -> dict:
    """Compute portfolio-level risk metrics.
    
    Nota: Por enquanto usa portfolio sintético (sem lookup ao DB).
    Endpoint expect query string ou body com positions reais (TODO).
    """
    from app.services.risk_model import compute_portfolio_risk, PROFILES
    
    # TODO: integrar com /portfolios para buscar positions reais
    # Por agora devolve só os limites do profile
    return {
        'portfolio_usd': portfolio_usd,
        'profile': profile,
        'limits': PROFILES[profile],
        'note': 'Integrar com /portfolios endpoint para risk real',
    }


@strategy_router.get('')
async def get_strategy_recommendations(
    portfolio_usd: float = Query(10000, gt=0),
    profile: str = Query('aggressive', regex='^(conservative|balanced|aggressive)$'),
    limit: int = Query(100, ge=10, le=200),
) -> dict:
    """Get strategy recommendations: top picks + allocations + DCA + sector rotation."""
    from app.services.coingecko import fetch_markets
    from app.services.decision_matrix import compute_matrix
    from app.services.strategy_model import compute_strategy_recommendations
    
    EXCLUDED_SYMBOLS = {
        'USDT', 'USDC', 'DAI', 'TUSD', 'BUSD', 'USDD', 'FDUSD', 'PYUSD', 'USDE',
        'WBTC', 'WETH', 'WBNB', 'CBBTC', 'WSTETH', 'STETH', 'WEETH',
        'LUSD', 'GUSD', 'USDP', 'USDS', 'EURS', 'EURT',
    }
    
    # Fetch top N
    markets = await fetch_markets(limit=min(limit + 30, 250), page=1)
    if not markets:
        return {
            'error': 'CoinGecko unavailable',
            'top_picks': [],
            'sector_rotation': {'sectors': [], 'rotation_signal': None},
        }
    
    symbols, coin_ids = [], []
    for m in markets:
        sym = (m.get('symbol') or '').upper()
        cid = m.get('id')
        if not sym or not cid or sym in EXCLUDED_SYMBOLS:
            continue
        symbols.append(sym)
        coin_ids.append(cid)
        if len(symbols) >= limit:
            break
    
    rows = await compute_matrix(symbols, coin_ids, max_concurrent=20)
    
    recommendations = compute_strategy_recommendations(rows, portfolio_usd, profile)
    recommendations['timestamp'] = int(datetime.now(timezone.utc).timestamp())
    
    return recommendations


@strategy_router.get('/sectors')
async def get_sector_rotation(limit: int = Query(100, ge=10, le=200)) -> dict:
    """Sector rotation analysis only (sem allocation suggestions)."""
    from app.services.coingecko import fetch_markets
    from app.services.decision_matrix import compute_matrix
    from app.services.strategy_model import compute_sector_rotation
    
    EXCLUDED_SYMBOLS = {
        'USDT', 'USDC', 'DAI', 'TUSD', 'BUSD', 'USDD', 'FDUSD', 'PYUSD', 'USDE',
        'WBTC', 'WETH', 'WBNB', 'CBBTC', 'WSTETH', 'STETH', 'WEETH',
    }
    
    markets = await fetch_markets(limit=min(limit + 30, 250), page=1)
    if not markets:
        return {'sectors': [], 'rotation_signal': None}
    
    symbols, coin_ids = [], []
    for m in markets:
        sym = (m.get('symbol') or '').upper()
        cid = m.get('id')
        if not sym or not cid or sym in EXCLUDED_SYMBOLS:
            continue
        symbols.append(sym)
        coin_ids.append(cid)
        if len(symbols) >= limit:
            break
    
    rows = await compute_matrix(symbols, coin_ids, max_concurrent=20)
    return {
        'data': compute_sector_rotation(rows),
        'count': len(rows),
        'timestamp': int(datetime.now(timezone.utc).timestamp()),
    }
