"""Endpoints whale tracking — Binance Futures public API.

GET /whales              → lista whale activity para top símbolos
GET /whales/{symbol}     → whale metrics para um símbolo específico
"""
import logging
from datetime import datetime, timezone
import asyncio

from fastapi import APIRouter, Query

log = logging.getLogger(__name__)
router = APIRouter(prefix='/whales', tags=['whales'])

# Top symbols para tracking (todos têm USDT pairs em Binance Futures)
TOP_SYMBOLS = [
    'BTC', 'ETH', 'BNB', 'SOL', 'ADA', 'DOGE', 'XRP', 'TON', 'LINK',
    'UNI', 'AVAX', 'AAVE', 'MATIC', 'ARB', 'NEAR',
]


@router.get('')
async def list_whale_activity(
    min_score: int | None = Query(None, description='Filter por whale_score >= min_score'),
) -> dict:
    """Lista whale activity (OI + funding + LSR) para top símbolos."""
    from app.services.whale_tracking import fetch_whale_metrics, compute_whale_score
    
    results = []
    
    metrics_list = await asyncio.gather(
        *[fetch_whale_metrics(s) for s in TOP_SYMBOLS],
        return_exceptions=False,
    )
    
    for sym, metrics in zip(TOP_SYMBOLS, metrics_list):
        if not metrics:
            continue
        
        whale_score = compute_whale_score(
            metrics.get('oi'),
            metrics.get('funding'),
            metrics.get('lsr'),
        )
        
        if min_score is not None and whale_score['score'] < min_score:
            continue
        
        results.append({
            'symbol': sym,
            'metrics': metrics,
            'whale_score': whale_score,
        })
    
    # Sort por score absoluto (mais extremos primeiro)
    results.sort(key=lambda x: abs(x['whale_score']['score']), reverse=True)
    
    return {
        'count': len(results),
        'data': results,
        'timestamp': int(datetime.now(timezone.utc).timestamp()),
    }


@router.get('/{symbol}')
async def get_whale_metrics(symbol: str) -> dict:
    """Get whale metrics para 1 símbolo (com fallback neutral se falhar)."""
    from app.services.whale_tracking import fetch_whale_metrics, compute_whale_score
    
    metrics = await fetch_whale_metrics(symbol)
    
    if metrics:
        whale_score = compute_whale_score(
            metrics.get('oi'),
            metrics.get('funding'),
            metrics.get('lsr'),
        )
        return {
            'symbol': metrics['symbol'],
            'oi': metrics.get('oi'),
            'funding': metrics.get('funding'),
            'lsr': metrics.get('lsr'),
            'whale_score': whale_score,
            'timestamp': int(datetime.now(timezone.utc).timestamp()),
        }
    
    # Fallback: símbolo inválido ou Binance Futures não tem este pair
    return {
        'symbol': symbol.upper(),
        'oi': None,
        'funding': None,
        'lsr': None,
        'whale_score': {
            'score': 0,
            'signal': 'whale_neutral',
            'description': f'{symbol} não disponível em Binance Futures (sem dados)',
            'components': {},
        },
        'timestamp': int(datetime.now(timezone.utc).timestamp()),
    }
