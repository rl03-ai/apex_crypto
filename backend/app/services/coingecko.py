"""Serviço CoinGecko — todas as chamadas HTTP em sítio único.

Suporta chave Pro (x-cg-pro-api-key) opcional via settings.
Tem fallback demo para desenvolvimento offline.
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

settings = get_settings()
BASE = settings.coingecko_base_url
log = logging.getLogger(__name__)

DEMO_MARKETS = [
    {'id': 'bitcoin', 'symbol': 'btc', 'name': 'Bitcoin', 'image': '', 'current_price': 64000,
     'market_cap': 1_260_000_000_000, 'market_cap_rank': 1, 'total_volume': 33_000_000_000,
     'price_change_percentage_24h': 1.2, 'price_change_percentage_7d_in_currency': 4.8,
     'price_change_percentage_30d_in_currency': 9.6, 'ath_change_percentage': -12.0},
    {'id': 'ethereum', 'symbol': 'eth', 'name': 'Ethereum', 'image': '', 'current_price': 3200,
     'market_cap': 386_000_000_000, 'market_cap_rank': 2, 'total_volume': 18_000_000_000,
     'price_change_percentage_24h': 0.4, 'price_change_percentage_7d_in_currency': 2.1,
     'price_change_percentage_30d_in_currency': 6.9, 'ath_change_percentage': -34.0},
    {'id': 'solana', 'symbol': 'sol', 'name': 'Solana', 'image': '', 'current_price': 145,
     'market_cap': 67_000_000_000, 'market_cap_rank': 5, 'total_volume': 4_200_000_000,
     'price_change_percentage_24h': 3.6, 'price_change_percentage_7d_in_currency': 11.2,
     'price_change_percentage_30d_in_currency': 18.7, 'ath_change_percentage': -44.0},
    {'id': 'chainlink', 'symbol': 'link', 'name': 'Chainlink', 'image': '', 'current_price': 14.2,
     'market_cap': 8_900_000_000, 'market_cap_rank': 16, 'total_volume': 650_000_000,
     'price_change_percentage_24h': -1.1, 'price_change_percentage_7d_in_currency': 6.0,
     'price_change_percentage_30d_in_currency': 3.1, 'ath_change_percentage': -73.0},
    {'id': 'bnb', 'symbol': 'bnb', 'name': 'BNB', 'image': '', 'current_price': 580,
     'market_cap': 85_000_000_000, 'market_cap_rank': 4, 'total_volume': 2_100_000_000,
     'price_change_percentage_24h': 0.8, 'price_change_percentage_7d_in_currency': 3.2,
     'price_change_percentage_30d_in_currency': 5.1, 'ath_change_percentage': -25.0},
    {'id': 'ripple', 'symbol': 'xrp', 'name': 'XRP', 'image': '', 'current_price': 0.52,
     'market_cap': 28_000_000_000, 'market_cap_rank': 6, 'total_volume': 1_200_000_000,
     'price_change_percentage_24h': -0.5, 'price_change_percentage_7d_in_currency': 1.8,
     'price_change_percentage_30d_in_currency': -3.2, 'ath_change_percentage': -88.0},
]


def _headers() -> dict[str, str]:
    h: dict[str, str] = {}
    key = settings.coingecko_api_key
    if not key:
        return h
    # Keys que começam com 'CG-' são tipicamente do tier demo (free).
    # As Pro têm formato diferente.
    # Para evitar adivinhação, podes definir COINGECKO_API_TIER=pro|demo no .env.
    if key.startswith('CG-'):
        h['x-cg-demo-api-key'] = key
    else:
        h['x-cg-pro-api-key'] = key
    return h


async def fetch_markets(limit: int = 80, page: int = 1) -> list[dict]:
    """Top N moedas ordenadas por market cap. Resultado cacheado 90 s."""
    from app.services.cache import markets_cache
    cache_key = f'markets:{limit}:{page}'
    cached = markets_cache.get(cache_key)
    if cached is not None:
        return cached

    params = {
        'vs_currency': 'usd',
        'order': 'market_cap_desc',
        'per_page': min(limit, 250),
        'page': page,
        'sparkline': 'true',
        'price_change_percentage': '7d,30d',
    }
    try:
        async with httpx.AsyncClient(timeout=20, headers=_headers()) as client:
            r = await client.get(f'{BASE}/coins/markets', params=params)
            r.raise_for_status()
            data = r.json()
            markets_cache.set(cache_key, data)
            return data
    except Exception:
        return DEMO_MARKETS


async def fetch_markets_by_ids(coin_ids: list[str]) -> list[dict]:
    """Busca dados de market para uma lista específica de coin_ids. Cacheado 90 s."""
    from app.services.cache import markets_cache
    if not coin_ids:
        return []

    cache_key = f'markets_ids:{"_".join(sorted(coin_ids))}'
    cached = markets_cache.get(cache_key)
    if cached is not None:
        return cached

    ids_str = ','.join(coin_ids)
    params = {
        'vs_currency': 'usd',
        'ids': ids_str,
        'sparkline': 'false',
        'price_change_percentage': '7d,30d',
    }
    try:
        async with httpx.AsyncClient(timeout=20, headers=_headers()) as client:
            r = await client.get(f'{BASE}/coins/markets', params=params)
            r.raise_for_status()
            data = r.json()
            markets_cache.set(cache_key, data)
            return data
    except Exception:
        return [d for d in DEMO_MARKETS if d['id'] in coin_ids]


async def fetch_coin_detail(coin_id: str) -> dict:
    """Dados completos de uma moeda (inclui tokenomics, links, etc.)."""
    params = {
        'localization': 'false',
        'tickers': 'false',
        'market_data': 'true',
        'community_data': 'true',
        'developer_data': 'false',
    }
    try:
        async with httpx.AsyncClient(timeout=25, headers=_headers()) as client:
            r = await client.get(f'{BASE}/coins/{coin_id}', params=params)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as e:
        log.warning('CoinGecko detail %s falhou: status %s — %s',
                    coin_id, e.response.status_code, e.response.text[:200])
        return {}
    except Exception as e:
        log.warning('CoinGecko detail %s falhou: %s — %s',
                    coin_id, type(e).__name__, str(e)[:200])
        return {}


async def fetch_chart(coin_id: str, days: int = 90) -> list[dict]:
    """Série temporal de preços para gráfico."""
    try:
        async with httpx.AsyncClient(timeout=20, headers=_headers()) as client:
            r = await client.get(
                f'{BASE}/coins/{coin_id}/market_chart',
                params={'vs_currency': 'usd', 'days': days},
            )
            r.raise_for_status()
            js = r.json()
            return [{'date': p[0], 'price': p[1]} for p in js.get('prices', [])]
    except Exception:
        return [{'date': i * 86_400_000, 'price': 100 + i * 0.7 + (i % 9) * 2} for i in range(days)]


async def search_coins(query: str, limit: int = 15) -> list[dict]:
    """Pesquisa moedas no CoinGecko por nome ou símbolo.

    Retorna lista de matches (sem preços — para isso, fetch_markets_by_ids).
    """
    if not query or len(query.strip()) < 1:
        return []

    try:
        async with httpx.AsyncClient(timeout=10, headers=_headers()) as client:
            r = await client.get(f'{BASE}/search', params={'query': query.strip()})
            r.raise_for_status()
            data = r.json()
            coins = data.get('coins', [])[:limit]
            # Normalizar para o formato que o frontend espera
            return [
                {
                    'id':         c.get('id'),
                    'symbol':     (c.get('symbol') or '').upper(),
                    'name':       c.get('name'),
                    'thumb':      c.get('thumb'),
                    'market_cap_rank': c.get('market_cap_rank'),
                }
                for c in coins
                if c.get('id')
            ]
    except Exception:
        # Fallback offline — pesquisa nas demos
        q = query.lower()
        return [
            {
                'id': d['id'], 'symbol': d['symbol'].upper(),
                'name': d['name'], 'thumb': None,
                'market_cap_rank': d.get('market_cap_rank'),
            }
            for d in DEMO_MARKETS
            if q in d['id'].lower() or q in d['symbol'].lower() or q in d['name'].lower()
        ][:limit]
