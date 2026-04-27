"""CoinGlass API client — OI trending + liquidation cascades (whale signals).

Free tier limits: 10 req/min — usamos cache agressivo (1h TTL) + retry com backoff.

Sinais whale:
  1. OI crescente (institucionais acumulando)
  2. Liquidações em cascata (panic selling)
"""
import logging
from datetime import datetime, timezone
import asyncio

import httpx

log = logging.getLogger(__name__)

COINGLASS_BASE = 'https://api.coinglass.com'
COINGLASS_TIMEOUT = 10

# Cache: symbol → {data, updated_at}
_CACHE = {}
_CACHE_TTL_SECONDS = 3600  # 1h


async def fetch_oi_trending(symbol: str) -> dict | None:
    """Fetch OI trending com retry logic."""
    cache_key = f'oi_{symbol}'
    
    # Check cache
    if cache_key in _CACHE:
        cached = _CACHE[cache_key]
        age = datetime.now(timezone.utc).timestamp() - cached['updated_at']
        if age < _CACHE_TTL_SECONDS:
            return cached['data']
    
    # Retry logic: tenta 2x com backoff
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=COINGLASS_TIMEOUT) as client:
                r = await client.get(
                    f'{COINGLASS_BASE}/api/v4/futures/open_interest_history',
                    params={'symbol': symbol, 'days': 7, 'granularity': '1h'},
                )
                
                if r.status_code == 429:
                    log.warning('CoinGlass OI: rate limit (429) para %s (tentativa %d)', symbol, attempt+1)
                    if attempt == 0:
                        await asyncio.sleep(2)
                    continue
                
                if r.status_code != 200:
                    log.debug('CoinGlass OI: HTTP %d para %s', r.status_code, symbol)
                    if attempt == 0:
                        await asyncio.sleep(1)
                    continue
                
                data = r.json().get('data', [])
                if len(data) < 2:
                    continue
                
                now_oi = float(data[-1].get('value', 0))
                oi_24h_ago = float(data[-24].get('value', 0)) if len(data) >= 24 else now_oi
                oi_7d_ago = float(data[0].get('value', 0))
                
                change_24h = ((now_oi - oi_24h_ago) / oi_24h_ago * 100) if oi_24h_ago > 0 else 0
                change_7d = ((now_oi - oi_7d_ago) / oi_7d_ago * 100) if oi_7d_ago > 0 else 0
                
                result = {
                    'symbol': symbol,
                    'oi_current_usd': now_oi,
                    'oi_24h_change_pct': round(change_24h, 2),
                    'oi_7d_change_pct': round(change_7d, 2),
                    'timestamp': int(datetime.now(timezone.utc).timestamp()),
                }
                
                _CACHE[cache_key] = {
                    'data': result,
                    'updated_at': datetime.now(timezone.utc).timestamp(),
                }
                return result
                
        except Exception as e:
            log.debug('CoinGlass OI: exception para %s (tentativa %d): %s', symbol, attempt+1, e)
            if attempt == 0:
                await asyncio.sleep(1)
    
    log.warning('CoinGlass OI: falhou completamente para %s', symbol)
    return None


async def fetch_liquidations(symbol: str) -> dict | None:
    """Fetch liquidações com retry logic."""
    cache_key = f'liq_{symbol}'
    
    if cache_key in _CACHE:
        cached = _CACHE[cache_key]
        age = datetime.now(timezone.utc).timestamp() - cached['updated_at']
        if age < _CACHE_TTL_SECONDS:
            return cached['data']
    
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=COINGLASS_TIMEOUT) as client:
                r = await client.get(
                    f'{COINGLASS_BASE}/api/v4/futures/liquidation_history',
                    params={'symbol': symbol, 'days': 1},
                )
                
                if r.status_code == 429:
                    log.warning('CoinGlass liq: rate limit (429) para %s (tentativa %d)', symbol, attempt+1)
                    if attempt == 0:
                        await asyncio.sleep(2)
                    continue
                
                if r.status_code != 200:
                    log.debug('CoinGlass liq: HTTP %d para %s', r.status_code, symbol)
                    if attempt == 0:
                        await asyncio.sleep(1)
                    continue
                
                data = r.json().get('data', [])
                if not data:
                    continue
                
                total_longs = sum(float(d.get('longs', 0)) for d in data)
                total_shorts = sum(float(d.get('shorts', 0)) for d in data)
                total = total_longs + total_shorts
                
                longs_pct = (total_longs / total * 100) if total > 0 else 50
                shorts_pct = 100 - longs_pct
                
                result = {
                    'symbol': symbol,
                    'longs_liquidated_usd': round(total_longs, 0),
                    'shorts_liquidated_usd': round(total_shorts, 0),
                    'total_liquidated_usd': round(total, 0),
                    'longs_pct': round(longs_pct, 1),
                    'shorts_pct': round(shorts_pct, 1),
                    'timestamp': int(datetime.now(timezone.utc).timestamp()),
                }
                
                _CACHE[cache_key] = {
                    'data': result,
                    'updated_at': datetime.now(timezone.utc).timestamp(),
                }
                return result
                
        except Exception as e:
            log.debug('CoinGlass liq: exception para %s (tentativa %d): %s', symbol, attempt+1, e)
            if attempt == 0:
                await asyncio.sleep(1)
    
    log.warning('CoinGlass liq: falhou completamente para %s', symbol)
    return None


async def fetch_whale_metrics(symbol: str) -> dict | None:
    """Fetch combinado OI + liquidações com retry."""
    oi, liq = await asyncio.gather(
        fetch_oi_trending(symbol),
        fetch_liquidations(symbol),
        return_exceptions=False,
    )
    
    if not oi and not liq:
        return None
    
    return {
        'symbol': symbol,
        'oi': oi,
        'liq': liq,
        'timestamp': int(datetime.now(timezone.utc).timestamp()),
    }


def clear_cache():
    """Limpar cache (para testes)."""
    global _CACHE
    _CACHE.clear()
