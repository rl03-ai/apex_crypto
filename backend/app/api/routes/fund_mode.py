"""Fund Mode endpoints — Institutional-grade portfolio construction."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Query

log = logging.getLogger(__name__)
router = APIRouter(prefix='/fund-mode', tags=['fund-mode'])


@router.get('/matrix')
async def fund_mode_matrix(
    source: str = Query('invest', regex='^(invest|swing)$', description='Use Matrix or Swing as source'),
    portfolio_usd: float = Query(100000, ge=10000, le=10000000),
    limit: int = Query(50, ge=10, le=100),
    symbols: str | None = Query(None),
) -> dict:
    """Fund-mode processed matrix (regime weighting + sector allocation + risk sizing).
    
    Flow:
      1. Fetch source matrix (invest or swing)
      2. Apply regime weighting (HTF trend modifies scores)
      3. Apply correlation penalties (flag >0.80 corr pairs)
      4. Sector-first allocation (20+ sectors)
      5. Risk-based position sizing (Kelly-inspired)
      6. Final ranking by allocation
    """
    from app.services.decision_matrix import compute_decision_matrix
    from app.services.swing_matrix import compute_swing_matrix
    from app.services.coingecko import fetch_markets
    from app.services.fund_mode.fund_pipeline import FundModePipeline
    
    # Fetch source matrix
    if symbols:
        custom_syms = [s.strip().upper() for s in symbols.split(',') if s.strip()]
        symbols_to_fetch = custom_syms
        coin_ids_to_fetch = [None] * len(custom_syms)
    else:
        markets = await fetch_markets(limit=min(limit + 30, 200), page=1)
        if not markets:
            return {
                'count': 0,
                'portfolio_usd': portfolio_usd,
                'error': 'CoinGecko unavailable',
                'timestamp': int(datetime.now(timezone.utc).timestamp()),
            }
        
        EXCLUDED = {'USDT', 'USDC', 'DAI', 'TUSD', 'BUSD', 'USDD', 'FDUSD', 'PYUSD', 'USDE',
                    'WBTC', 'WETH', 'WBNB', 'CBBTC', 'WSTETH', 'STETH', 'WEETH',
                    'LUSD', 'GUSD', 'USDP', 'USDS', 'EURS', 'EURT'}
        
        symbols_to_fetch, coin_ids_to_fetch = [], []
        for m in markets:
            sym = (m.get('symbol') or '').upper()
            cid = m.get('id')
            if not sym or not cid or sym in EXCLUDED:
                continue
            symbols_to_fetch.append(sym)
            coin_ids_to_fetch.append(cid)
            if len(symbols_to_fetch) >= limit:
                break
    
    log.info(f'Fund Mode: {source.upper()} source, {len(symbols_to_fetch)} symbols, ${portfolio_usd}')
    
    # Fetch matrix
    if source == 'invest':
        rows = await compute_decision_matrix(symbols_to_fetch, coin_ids_to_fetch, limit=limit)
    else:  # swing
        rows = await compute_swing_matrix(symbols_to_fetch, coin_ids_to_fetch, mode='short', max_concurrent=15)
    
    if not rows:
        return {
            'count': 0,
            'portfolio_usd': portfolio_usd,
            'error': 'No valid data',
            'timestamp': int(datetime.now(timezone.utc).timestamp()),
        }
    
    # Apply fund-mode pipeline
    pipeline = FundModePipeline(portfolio_usd=portfolio_usd)
    processed, summary = pipeline.process_matrix(rows)
    
    return {
        'count': len(processed),
        'portfolio_usd': portfolio_usd,
        'source': source,
        'total_exposure_usd': summary.get('total_exposure_usd', 0),
        'total_exposure_pct': summary.get('total_exposure_pct', 0),
        'sector_summary': summary.get('sector_summary', {}),
        'positions': processed,
        'timestamp': int(datetime.now(timezone.utc).timestamp()),
    }


@router.get('/summary')
async def fund_mode_summary(
    portfolio_usd: float = Query(100000, ge=10000, le=10000000),
) -> dict:
    """Fund mode configuration + risk profile."""
    from app.services.fund_mode.risk_based_sizing import RiskProfile
    
    profile = RiskProfile(portfolio_usd=portfolio_usd)
    
    return {
        'portfolio_usd': portfolio_usd,
        'risk_per_trade': profile.risk_per_trade * 100,
        'max_exposure_single_symbol': profile.max_exposure_pct * 100,
        'max_exposure_single_sector': profile.max_per_sector * 100,
        'max_positions': profile.max_positions,
        'min_position_usd': profile.min_position_usd,
        'regime_weighting': {
            'ALTA (bull)': 'score × 1.3',
            'LATERAL': 'score × 1.0',
            'BAIXA (bear)': 'score × 0.6',
        },
        'correlation_threshold': 0.80,
        'sectors_tracked': 12,
        'timestamp': int(datetime.now(timezone.utc).timestamp()),
    }
