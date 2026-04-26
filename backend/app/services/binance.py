"""Binance — OHLCV e listagem de símbolos.

API pública, sem chave necessária. Rate limits são generosos (1200 reqs/min).

Filtros automáticos para excluir lixo:
  - volume USDT diário < $1M
  - stablecoins (USDT, USDC, BUSD, DAI, FDUSD, TUSD)
  - leveraged tokens (UP, DOWN, BULL, BEAR)
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import httpx
import pandas as pd

from app.services.cache import TTLCache

log = logging.getLogger(__name__)

BASE = 'https://api.binance.com'

# Stablecoins (não devem ser scanned como activos para trade)
STABLECOINS = {
    'USDT', 'USDC', 'BUSD', 'DAI', 'FDUSD', 'TUSD', 'USDP',
    'GUSD', 'PYUSD', 'USDD', 'FRAX', 'USDE', 'USDS',
}

# Sufixos de leveraged tokens (UP/DOWN/BULL/BEAR)
LEVERAGED_SUFFIXES = ('UP', 'DOWN', 'BULL', 'BEAR')

# Volume mínimo USDT para considerar liquidez aceitável
MIN_QUOTE_VOLUME_USD = 1_000_000

# Caches
_symbols_cache  = TTLCache(ttl_seconds=3600)   # 1 h — universo muda raramente
_klines_cache   = TTLCache(ttl_seconds=300)    # 5 min — para 1d e 1w


def _is_leveraged(asset: str) -> bool:
    return any(asset.endswith(s) for s in LEVERAGED_SUFFIXES) and len(asset) > len(min(LEVERAGED_SUFFIXES, key=len))


async def fetch_24h_tickers() -> list[dict]:
    """Devolve lista bruta dos 24h tickers de todos os pares spot."""
    cached = _symbols_cache.get('tickers_24h')
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f'{BASE}/api/v3/ticker/24hr')
            r.raise_for_status()
            data = r.json()
            _symbols_cache.set('tickers_24h', data)
            return data
    except Exception as exc:
        log.warning('Binance fetch_24h_tickers falhou: %s', exc)
        return []


async def list_active_symbols(extra_coingecko_ids: Optional[list[str]] = None) -> list[dict]:
    """Devolve lista de pares USDT activos, com volume mínimo, sem stables/leveraged.

    extra_coingecko_ids: lista opcional de coin_ids extra a incluir mesmo que
    fiquem abaixo do volume mínimo (ex: moedas da watchlist do user).

    Cada item:
        {
            'symbol': 'BTCUSDT',
            'base_asset': 'BTC',
            'quote_asset': 'USDT',
            'price': 64000.0,
            'change_24h_pct': 1.2,
            'quote_volume_24h': 12345678.9,
        }
    """
    cached = _symbols_cache.get('active_symbols')
    if cached is not None:
        # Se houver coingecko ids extra, processamos sempre — mas o caso comum é cached
        if not extra_coingecko_ids:
            return cached

    tickers = await fetch_24h_tickers()
    active: list[dict] = []
    for t in tickers:
        sym = t.get('symbol', '')
        if not sym.endswith('USDT'):
            continue
        base = sym[:-4]
        if base in STABLECOINS or _is_leveraged(base):
            continue
        try:
            qvol = float(t.get('quoteVolume', 0))
            price = float(t.get('lastPrice', 0))
            change = float(t.get('priceChangePercent', 0))
        except (ValueError, TypeError):
            continue
        if qvol < MIN_QUOTE_VOLUME_USD or price <= 0:
            continue
        active.append({
            'symbol': sym,
            'base_asset': base,
            'quote_asset': 'USDT',
            'price': price,
            'change_24h_pct': change,
            'quote_volume_24h': qvol,
        })

    active.sort(key=lambda x: x['quote_volume_24h'], reverse=True)
    _symbols_cache.set('active_symbols', active)
    log.info('Binance: %d pares USDT válidos detectados.', len(active))
    return active


async def fetch_klines(symbol: str, interval: str = '1d', limit: int = 300) -> Optional[pd.DataFrame]:
    """Vai buscar OHLCV do Binance.

    interval: '4h', '1d', '1w' (Binance suporta 1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M)
    limit: máximo 1000

    Devolve DataFrame com colunas: open, high, low, close, volume, quote_volume, taker_buy_volume
    Index é datetime UTC.
    """
    cache_key = f'klines:{symbol}:{interval}:{limit}'
    cached = _klines_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f'{BASE}/api/v3/klines', params={
                'symbol': symbol, 'interval': interval, 'limit': min(limit, 1000),
            })
            r.raise_for_status()
            raw = r.json()
    except Exception as exc:
        log.warning('Binance klines falhou para %s/%s: %s', symbol, interval, exc)
        return None

    if not raw:
        return None

    # Estrutura Binance:
    # [open_time, open, high, low, close, volume, close_time, quote_volume,
    #  trades, taker_buy_base, taker_buy_quote, ignore]
    df = pd.DataFrame(raw, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades',
        'taker_buy_base', 'taker_buy_quote', 'ignore',
    ])
    for col in ('open', 'high', 'low', 'close', 'volume', 'quote_volume', 'taker_buy_quote'):
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df['datetime'] = pd.to_datetime(df['open_time'], unit='ms', utc=True)
    df = df.set_index('datetime')[['open', 'high', 'low', 'close', 'volume', 'quote_volume', 'taker_buy_quote']]
    df = df.dropna()

    _klines_cache.set(cache_key, df)
    return df


def coingecko_id_to_binance_symbol(coin_id: str) -> Optional[str]:
    """Mapeia coin_id do CoinGecko (ex: 'bitcoin') para par Binance USDT (ex: 'BTCUSDT').

    Cobre os ~50 mais comuns. Para outros devolve None (e a app cai-se elegantemente).
    """
    mapping = {
        'bitcoin': 'BTC', 'ethereum': 'ETH', 'binancecoin': 'BNB', 'ripple': 'XRP',
        'cardano': 'ADA', 'solana': 'SOL', 'polkadot': 'DOT', 'dogecoin': 'DOGE',
        'avalanche-2': 'AVAX', 'matic-network': 'MATIC', 'chainlink': 'LINK',
        'litecoin': 'LTC', 'tron': 'TRX', 'cosmos': 'ATOM', 'uniswap': 'UNI',
        'stellar': 'XLM', 'monero': 'XMR', 'aave': 'AAVE', 'maker': 'MKR',
        'algorand': 'ALGO', 'vechain': 'VET', 'internet-computer': 'ICP',
        'filecoin': 'FIL', 'theta-token': 'THETA', 'fantom': 'FTM',
        'near': 'NEAR', 'arbitrum': 'ARB', 'optimism': 'OP', 'aptos': 'APT',
        'sui': 'SUI', 'hedera-hashgraph': 'HBAR', 'mantle': 'MNT',
        'sei-network': 'SEI', 'render-token': 'RNDR', 'injective-protocol': 'INJ',
        'kaspa': 'KAS', 'lido-dao': 'LDO', 'rocket-pool': 'RPL',
        'curve-dao-token': 'CRV', 'pepe': 'PEPE', 'shiba-inu': 'SHIB',
        'the-graph': 'GRT', 'sandbox': 'SAND', 'decentraland': 'MANA',
        'gala': 'GALA', 'flow': 'FLOW', 'eos': 'EOS', 'tezos': 'XTZ',
        'gmx': 'GMX', 'dydx': 'DYDX', 'compound-governance-token': 'COMP',
        'sushi': 'SUSHI', 'pancakeswap-token': 'CAKE', 'frax-share': 'FXS',
        'ondo-finance': 'ONDO', 'jupiter-exchange-solana': 'JUP',
        'wormhole': 'W', 'pyth-network': 'PYTH', 'jito-governance-token': 'JTO',
        'starknet': 'STRK', 'celestia': 'TIA', 'the-open-network': 'TON',
        'bonk': 'BONK', 'worldcoin-wld': 'WLD',
    }
    base = mapping.get(coin_id)
    return f'{base}USDT' if base else None


def binance_symbol_to_base(symbol: str) -> str:
    """BTCUSDT → BTC."""
    if symbol.endswith('USDT'):
        return symbol[:-4]
    return symbol
