"""Endpoints de whale tracking — OI trends + liquidation signals.

GET /whales              → lista whale activity últimas 7d
GET /whales/{symbol}     → whale metrics para um símbolo
POST /jobs/run/scan-whales → trigger manual do scan
"""
import logging
from fastapi import APIRouter, Query

log = logging.getLogger(__name__)
router = APIRouter(prefix='/whales', tags=['whales'])


@router.get('')
async def list_whale_activity(
    symbol: str | None = Query(None, description='Filtrar por símbolo'),
    min_score: int | None = Query(None, description='Filtrar por whale_score >= min_score'),
) -> dict:
    """Lista whale activity (OI trends + liquidations) — últimas 7 dias.

    Exemplo response:
        {
            'timestamp': 1234567890,
            'data': [
                {
                    'symbol': 'BTC',
                    'oi': {
                        'oi_current_usd': 12345678.0,
                        'oi_24h_change_pct': 5.2,
                        'oi_7d_change_pct': 12.1,
                    },
                    'liq': {
                        'total_liquidated_usd': 1234567.0,
                        'longs_pct': 35.0,
                        'shorts_pct': 65.0,
                    },
                    'whale_score': {
                        'score': 5,
                        'signal': 'whale_bull',
                        'description': '...',
                    },
                },
                ...
            ]
        }
    """
    from app.services.whale_tracking import fetch_whale_metrics, compute_whale_score
    from datetime import datetime, timezone
    import asyncio

    # Se especificou símbolo, devolve só esse
    if symbol:
        metrics = await fetch_whale_metrics(symbol)
        if not metrics:
            return {'symbol': symbol, 'data': None}

        whale_score = compute_whale_score(
            metrics.get('oi'),
            metrics.get('liq'),
        )

        return {
            'symbol': symbol,
            'metrics': metrics,
            'whale_score': whale_score,
            'timestamp': int(datetime.now(timezone.utc).timestamp()),
        }

    # Senão, scan top symbols
    top_symbols = [
        'BTC', 'ETH', 'BNB', 'SOL', 'ADA', 'DOGE', 'XRP', 'TON', 'LINK',
    ]

    results = []
    metrics_list = await asyncio.gather(
        *[fetch_whale_metrics(s) for s in top_symbols],
        return_exceptions=False,
    )

    for sym, metrics in zip(top_symbols, metrics_list):
        if not metrics:
            continue

        whale_score = compute_whale_score(
            metrics.get('oi'),
            metrics.get('liq'),
        )

        # Filtro min_score
        if min_score is not None and whale_score['score'] < min_score:
            continue

        results.append({
            'symbol': sym,
            'metrics': metrics,
            'whale_score': whale_score,
        })

    # Sort por whale_score DESC
    results.sort(key=lambda x: x['whale_score']['score'], reverse=True)

    return {
        'count': len(results),
        'data': results,
        'timestamp': int(datetime.now(timezone.utc).timestamp()),
    }


@router.get('/{symbol}')
async def get_whale_metrics(symbol: str) -> dict:
    """Get whale metrics para um símbolo específico."""
    from app.services.whale_tracking import fetch_whale_metrics, compute_whale_score
    from datetime import datetime, timezone

    symbol = symbol.upper()
    metrics = await fetch_whale_metrics(symbol)

    if not metrics:
        return {
            'symbol': symbol,
            'error': 'Whale metrics não disponíveis (CoinGlass rate limit ou símbolo inválido)',
        }

    whale_score = compute_whale_score(
        metrics.get('oi'),
        metrics.get('liq'),
    )

    return {
        'symbol': symbol,
        'oi': metrics.get('oi'),
        'liq': metrics.get('liq'),
        'whale_score': whale_score,
        'timestamp': int(datetime.now(timezone.utc).timestamp()),
    }
