"""Serviço DefiLlama — TVL de protocolos DeFi e chains L1/L2.

DefiLlama distingue dois conceitos:
  - Protocol TVL: Uniswap, Aave, Curve, etc. (dApps)
  - Chain TVL:    Ethereum, Solana, BNB Chain, etc. (redes)

Mapeamento coin_id (CoinGecko) → slug DefiLlama mantido aqui.
Para moedas sem presença DeFi (BTC, XRP) devolve None.
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings
from app.services.cache import TTLCache

log = logging.getLogger(__name__)
settings = get_settings()
BASE = settings.defillama_base_url

# Cache separado para TVL — muda mais lentamente
_tvl_cache = TTLCache(ttl_seconds=300)  # 5 minutos

# ── Mapeamento coin_id → DefiLlama slug ──────────────────────────────────────
# Formato: coin_id → ('protocol' | 'chain', slug_defillama)
COIN_TO_DEFILLAMA: dict[str, tuple[str, str]] = {
    # Chains L1 / L2
    'ethereum':          ('chain', 'Ethereum'),
    'binancecoin':       ('chain', 'BSC'),
    'solana':            ('chain', 'Solana'),
    'avalanche-2':       ('chain', 'Avalanche'),
    'matic-network':     ('chain', 'Polygon'),
    'arbitrum':          ('chain', 'Arbitrum'),
    'optimism':          ('chain', 'Optimism'),
    'fantom':            ('chain', 'Fantom'),
    'near':              ('chain', 'Near'),
    'tron':              ('chain', 'Tron'),
    'cosmos':            ('chain', 'CosmosHub'),
    'the-open-network':  ('chain', 'TON'),
    'sui':               ('chain', 'Sui'),
    'aptos':             ('chain', 'Aptos'),
    'cardano':           ('chain', 'Cardano'),

    # Protocolos DeFi
    'uniswap':           ('protocol', 'uniswap'),
    'aave':              ('protocol', 'aave'),
    'compound-governance-token': ('protocol', 'compound'),
    'curve-dao-token':   ('protocol', 'curve'),
    'chainlink':         ('protocol', 'chainlink'),
    'maker':             ('protocol', 'makerdao'),
    'lido-dao':          ('protocol', 'lido'),
    'pancakeswap-token': ('protocol', 'pancakeswap'),
    'sushi':             ('protocol', 'sushiswap'),
    'balancer':          ('protocol', 'balancer'),
    'yearn-finance':     ('protocol', 'yearn-finance'),
    'convex-finance':    ('protocol', 'convex-finance'),
    'frax-share':        ('protocol', 'frax'),
    'rocket-pool':       ('protocol', 'rocket-pool'),
    'gmx':               ('protocol', 'gmx'),
    'dydx':              ('protocol', 'dydx'),
    'the-graph':         ('protocol', 'the-graph'),
    'enjincoin':         ('protocol', 'enjin'),
    'stepn':             ('protocol', 'stepn'),

    # Sem TVL relevante — return None implícito
    # bitcoin, ripple, dogecoin, litecoin, etc.
}


async def fetch_tvl(coin_id: str) -> dict | None:
    """Devolve dict com tvl, kind ('protocol'|'chain'), slug — ou None."""
    mapping = COIN_TO_DEFILLAMA.get(coin_id)
    if not mapping:
        return None

    kind, slug = mapping
    cache_key = f'tvl:{kind}:{slug}'
    cached = _tvl_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        if kind == 'chain':
            result = await _fetch_chain_tvl(slug)
        else:
            result = await _fetch_protocol_tvl(slug)

        if result:
            _tvl_cache.set(cache_key, result)
        return result

    except Exception as exc:
        log.warning('DefiLlama TVL fetch falhou para %s/%s: %s', kind, slug, exc)
        return None


async def _fetch_chain_tvl(chain: str) -> dict | None:
    """TVL de uma chain usando o endpoint /v2/chains."""
    async with httpx.AsyncClient(timeout=8) as client:
        r = await client.get(f'{BASE}/v2/chains')
        r.raise_for_status()
        chains: list[dict] = r.json()

    match = next(
        (c for c in chains if c.get('name', '').lower() == chain.lower()),
        None,
    )
    if not match:
        return None

    return {
        'tvl': match.get('tvl'),
        'tvl_1d_change': match.get('change_1d'),
        'tvl_7d_change': match.get('change_7d'),
        'kind': 'chain',
        'slug': chain,
        'source': 'defillama',
    }


async def _fetch_protocol_tvl(slug: str) -> dict | None:
    """TVL de um protocolo DeFi usando o endpoint /tvl/{slug}."""
    async with httpx.AsyncClient(timeout=8) as client:
        # Endpoint simples que devolve só o TVL actual
        r = await client.get(f'{BASE}/tvl/{slug}')
        r.raise_for_status()
        tvl = r.json()  # número float

    if not isinstance(tvl, (int, float)) or tvl <= 0:
        return None

    return {
        'tvl': tvl,
        'tvl_1d_change': None,
        'tvl_7d_change': None,
        'kind': 'protocol',
        'slug': slug,
        'source': 'defillama',
    }
