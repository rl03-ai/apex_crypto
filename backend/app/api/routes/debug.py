"""Debug endpoint — testa qual endpoint Binance funciona a partir do servidor Render.

Útil para diagnóstico de geo-blocks. Endpoint protegido por auth.
"""
from __future__ import annotations

import time
from typing import Optional

import httpx
from fastapi import APIRouter

from app.api.deps import CurrentUser

router = APIRouter()


async def _test(url: str) -> dict:
    """Faz um GET ao endpoint e devolve resultado resumido."""
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            elapsed_ms = int((time.time() - start) * 1000)
            body = r.text[:200] if r.is_error else f'{len(r.text)} bytes OK'
            return {
                'url': url,
                'status': r.status_code,
                'elapsed_ms': elapsed_ms,
                'works': r.is_success,
                'body_preview': body,
            }
    except Exception as exc:
        return {
            'url': url,
            'status': None,
            'elapsed_ms': int((time.time() - start) * 1000),
            'works': False,
            'body_preview': f'EXCEPTION: {type(exc).__name__}: {exc}',
        }


@router.get('/binance-test')
async def binance_test() -> dict:
    """Testa múltiplos endpoints Binance para descobrir qual funciona daqui.
    
    Endpoint público (sem auth) para diagnosticar bloqueios de IP do servidor Render.
    """
    endpoints = [
        # Primário: api.binance.com (sabemos que falha em IPs US com 451)
        'https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=2',
        # Subdomínio data-api (oficial, sem geo-block segundo docs)
        'https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=2',
        # api1, api2, api3, api4 (mirrors oficiais)
        'https://api1.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=2',
        'https://api4.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=2',
        # Binance.US (subset de pares)
        'https://api.binance.us/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=2',
        # Plano C: Kraken (alternativa não-Binance)
        'https://api.kraken.com/0/public/OHLC?pair=XBTUSDT&interval=1440',
    ]

    results = []
    for url in endpoints:
        results.append(await _test(url))

    # Identificar quais funcionam
    working = [r for r in results if r['works']]
    return {
        'total_tested': len(results),
        'working_count': len(working),
        'working_endpoints': [r['url'] for r in working],
        'all_results': results,
    }
