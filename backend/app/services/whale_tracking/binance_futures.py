"""Whale data fetcher — fallback chain across exchanges.

Tries in order:
  1. Binance Futures (fapi.binance.com)
  2. Bybit (api.bybit.com)
  3. OKX (www.okx.com)

Each exchange has different geo-restrictions; first one that responds wins.
All endpoints are public (no auth required).
"""
import logging
import asyncio
from datetime import datetime, timezone

import httpx

log = logging.getLogger(__name__)

BINANCE_FAPI = 'https://fapi.binance.com'
BYBIT_API = 'https://api.bybit.com'
OKX_API = 'https://www.okx.com'
TIMEOUT = 10

# Cache: key → {data, updated_at}
_CACHE = {}
_CACHE_TTL_SECONDS = 1800  # 30min


def _normalize_symbol(symbol: str) -> str:
    """Converte 'BTC' para 'BTCUSDT'."""
    s = symbol.upper().strip()
    if not s.endswith('USDT'):
        s = f'{s}USDT'
    return s


# ═══════════════════════════════════════════════════════════════════════════
# OI History
# ═══════════════════════════════════════════════════════════════════════════
async def _fetch_oi_binance(client: httpx.AsyncClient, sym: str) -> list | None:
    """Try Binance Futures."""
    try:
        r = await client.get(
            f'{BINANCE_FAPI}/futures/data/openInterestHist',
            params={'symbol': sym, 'period': '1h', 'limit': 168},
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) >= 24:
                # Normalize to common schema: [{'usd': float, 'ts': int}]
                return [
                    {'usd': float(d.get('sumOpenInterestValue', 0)), 'ts': int(d.get('timestamp', 0))}
                    for d in data
                ]
        log.debug('Binance OI: HTTP %d para %s', r.status_code, sym)
    except Exception as e:
        log.debug('Binance OI exception: %s', e)
    return None


async def _fetch_oi_bybit(client: httpx.AsyncClient, sym: str) -> list | None:
    """Try Bybit."""
    try:
        r = await client.get(
            f'{BYBIT_API}/v5/market/open-interest',
            params={'category': 'linear', 'symbol': sym, 'intervalTime': '1h', 'limit': 168},
        )
        if r.status_code == 200:
            data = r.json()
            if data.get('retCode') == 0:
                items = data['result']['list']
                if items:
                    # Bybit returns price in BTC, need to multiply by current price
                    # For simplicity use the value at time of request (approximation)
                    # Actually Bybit returns "openInterest" in contract count, not USD
                    # We'll convert by getting current ticker price as multiplier
                    ticker_r = await client.get(
                        f'{BYBIT_API}/v5/market/tickers',
                        params={'category': 'linear', 'symbol': sym},
                    )
                    price = 1.0
                    if ticker_r.status_code == 200:
                        td = ticker_r.json()
                        if td.get('retCode') == 0 and td['result']['list']:
                            price = float(td['result']['list'][0].get('lastPrice', 1))
                    
                    # Bybit returns DESC (newest first), reverse to ASC
                    return [
                        {
                            'usd': float(d.get('openInterest', 0)) * price,
                            'ts': int(d.get('timestamp', 0)),
                        }
                        for d in reversed(items)
                    ]
        log.debug('Bybit OI: HTTP %d para %s', r.status_code, sym)
    except Exception as e:
        log.debug('Bybit OI exception: %s', e)
    return None


async def _fetch_oi_okx(client: httpx.AsyncClient, sym: str) -> list | None:
    """Try OKX. OKX usa formato diferente: BTC-USDT-SWAP"""
    try:
        # Convert BTCUSDT → BTC-USDT-SWAP
        coin = sym.replace('USDT', '')
        okx_sym = f'{coin}-USDT-SWAP'
        
        r = await client.get(
            f'{OKX_API}/api/v5/rubik/stat/contracts/open-interest-history',
            params={'instId': okx_sym, 'period': '1H'},
        )
        if r.status_code == 200:
            data = r.json()
            if data.get('code') == '0':
                items = data.get('data', [])
                if items:
                    # OKX returns: [[ts, openInterestUsd, openInterestCcy], ...]
                    return [
                        {'usd': float(d[1]), 'ts': int(d[0])}
                        for d in reversed(items)
                    ]
        log.debug('OKX OI: HTTP %d para %s', r.status_code, sym)
    except Exception as e:
        log.debug('OKX OI exception: %s', e)
    return None


async def fetch_oi_history(symbol: str) -> dict | None:
    """Fetch OI 7d com fallback chain.
    
    Returns:
        {'symbol', 'oi_current_usd', 'oi_24h_change_pct', 'oi_7d_change_pct', 'source'}
    """
    sym = _normalize_symbol(symbol)
    cache_key = f'oi_{sym}'
    
    if cache_key in _CACHE:
        cached = _CACHE[cache_key]
        age = datetime.now(timezone.utc).timestamp() - cached['updated_at']
        if age < _CACHE_TTL_SECONDS:
            return cached['data']
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Try chain
        for name, fetcher in [
            ('binance', _fetch_oi_binance),
            ('bybit', _fetch_oi_bybit),
            ('okx', _fetch_oi_okx),
        ]:
            data = await fetcher(client, sym)
            if data and len(data) >= 24:
                # Compute trend from normalized data
                now_oi = data[-1]['usd']
                oi_24h_ago = data[-24]['usd'] if len(data) >= 24 else now_oi
                oi_7d_ago = data[0]['usd']
                
                change_24h = ((now_oi - oi_24h_ago) / oi_24h_ago * 100) if oi_24h_ago > 0 else 0
                change_7d = ((now_oi - oi_7d_ago) / oi_7d_ago * 100) if oi_7d_ago > 0 else 0
                
                result = {
                    'symbol': sym,
                    'oi_current_usd': round(now_oi, 0),
                    'oi_24h_change_pct': round(change_24h, 2),
                    'oi_7d_change_pct': round(change_7d, 2),
                    'source': name,
                    'timestamp': int(datetime.now(timezone.utc).timestamp()),
                }
                
                _CACHE[cache_key] = {
                    'data': result,
                    'updated_at': datetime.now(timezone.utc).timestamp(),
                }
                log.info('OI %s: %s (%s)', sym, name, f'{change_7d:+.1f}% 7d')
                return result
    
    log.warning('OI %s: todos os fallbacks falharam', sym)
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Funding Rate
# ═══════════════════════════════════════════════════════════════════════════
async def _fetch_funding_binance(client: httpx.AsyncClient, sym: str) -> dict | None:
    try:
        r = await client.get(f'{BINANCE_FAPI}/fapi/v1/premiumIndex', params={'symbol': sym})
        if r.status_code == 200:
            d = r.json()
            return {
                'rate': float(d.get('lastFundingRate', 0)),
                'next': int(d.get('nextFundingTime', 0)),
            }
    except Exception:
        pass
    return None


async def _fetch_funding_bybit(client: httpx.AsyncClient, sym: str) -> dict | None:
    try:
        r = await client.get(
            f'{BYBIT_API}/v5/market/tickers',
            params={'category': 'linear', 'symbol': sym},
        )
        if r.status_code == 200:
            d = r.json()
            if d.get('retCode') == 0 and d['result']['list']:
                t = d['result']['list'][0]
                return {
                    'rate': float(t.get('fundingRate', 0)),
                    'next': int(t.get('nextFundingTime', 0)),
                }
    except Exception:
        pass
    return None


async def _fetch_funding_okx(client: httpx.AsyncClient, sym: str) -> dict | None:
    try:
        coin = sym.replace('USDT', '')
        okx_sym = f'{coin}-USDT-SWAP'
        r = await client.get(
            f'{OKX_API}/api/v5/public/funding-rate',
            params={'instId': okx_sym},
        )
        if r.status_code == 200:
            d = r.json()
            if d.get('code') == '0' and d.get('data'):
                t = d['data'][0]
                return {
                    'rate': float(t.get('fundingRate', 0)),
                    'next': int(t.get('nextFundingTime', 0)),
                }
    except Exception:
        pass
    return None


async def fetch_funding_rate(symbol: str) -> dict | None:
    """Fetch funding rate com fallback chain."""
    sym = _normalize_symbol(symbol)
    cache_key = f'funding_{sym}'
    
    if cache_key in _CACHE:
        cached = _CACHE[cache_key]
        age = datetime.now(timezone.utc).timestamp() - cached['updated_at']
        if age < _CACHE_TTL_SECONDS:
            return cached['data']
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for name, fetcher in [
            ('binance', _fetch_funding_binance),
            ('bybit', _fetch_funding_bybit),
            ('okx', _fetch_funding_okx),
        ]:
            d = await fetcher(client, sym)
            if d and 'rate' in d:
                rate_pct = d['rate'] * 100
                result = {
                    'symbol': sym,
                    'funding_rate_pct': round(rate_pct, 4),
                    'funding_rate_annualized_pct': round(rate_pct * 3 * 365, 2),
                    'next_funding_time': d.get('next', 0),
                    'source': name,
                    'timestamp': int(datetime.now(timezone.utc).timestamp()),
                }
                _CACHE[cache_key] = {
                    'data': result,
                    'updated_at': datetime.now(timezone.utc).timestamp(),
                }
                log.info('Funding %s: %s (%.4f%%)', sym, name, rate_pct)
                return result
    
    log.warning('Funding %s: todos os fallbacks falharam', sym)
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Long/Short Ratio
# ═══════════════════════════════════════════════════════════════════════════
async def fetch_long_short_ratio(symbol: str) -> dict | None:
    """Fetch top trader long/short ratio (só Binance suporta de forma fácil)."""
    sym = _normalize_symbol(symbol)
    cache_key = f'lsr_{sym}'
    
    if cache_key in _CACHE:
        cached = _CACHE[cache_key]
        age = datetime.now(timezone.utc).timestamp() - cached['updated_at']
        if age < _CACHE_TTL_SECONDS:
            return cached['data']
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await client.get(
                f'{BINANCE_FAPI}/futures/data/topLongShortPositionRatio',
                params={'symbol': sym, 'period': '1h', 'limit': 24},
            )
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and data:
                    now = data[-1]
                    day_ago = data[0]
                    now_ratio = float(now.get('longShortRatio', 1))
                    day_ago_ratio = float(day_ago.get('longShortRatio', 1))
                    change_24h = ((now_ratio - day_ago_ratio) / day_ago_ratio * 100) if day_ago_ratio > 0 else 0
                    
                    result = {
                        'symbol': sym,
                        'long_account_ratio': round(float(now.get('longAccount', 0)), 3),
                        'short_account_ratio': round(float(now.get('shortAccount', 0)), 3),
                        'long_short_ratio': round(now_ratio, 3),
                        'change_24h_pct': round(change_24h, 2),
                        'source': 'binance',
                        'timestamp': int(datetime.now(timezone.utc).timestamp()),
                    }
                    _CACHE[cache_key] = {
                        'data': result,
                        'updated_at': datetime.now(timezone.utc).timestamp(),
                    }
                    return result
        except Exception as e:
            log.debug('LSR exception: %s', e)
    
    return None


async def fetch_whale_metrics(symbol: str) -> dict | None:
    """Fetch combinado: OI + funding + LSR (paralelo)."""
    oi, funding, lsr = await asyncio.gather(
        fetch_oi_history(symbol),
        fetch_funding_rate(symbol),
        fetch_long_short_ratio(symbol),
        return_exceptions=False,
    )
    
    if not oi and not funding and not lsr:
        return None
    
    return {
        'symbol': _normalize_symbol(symbol),
        'oi': oi,
        'funding': funding,
        'lsr': lsr,
        'timestamp': int(datetime.now(timezone.utc).timestamp()),
    }


def clear_cache():
    """Clear cache (testes)."""
    global _CACHE
    _CACHE.clear()
