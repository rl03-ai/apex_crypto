"""Scanner crypto — endpoint principal de ranking de moedas."""
from __future__ import annotations

import asyncio
import logging
import re

from fastapi import APIRouter, HTTPException, Query

from app.services.coingecko import fetch_chart, fetch_coin_detail, fetch_markets, search_coins
from app.services.scoring import crypto_score, reasons

log = logging.getLogger(__name__)
router = APIRouter()


# ── helpers ───────────────────────────────────────────────────────────────────

def _enrich(row: dict) -> dict:
    score = crypto_score(row)
    # CoinGecko devolve sparkline em row['sparkline_in_7d']['price']
    sparkline = (row.get('sparkline_in_7d') or {}).get('price') or []
    return {
        'id':          row.get('id'),
        'symbol':      (row.get('symbol') or '').upper(),
        'name':        row.get('name'),
        'image':       row.get('image'),
        'price':       row.get('current_price'),
        'market_cap':  row.get('market_cap'),
        'rank':        row.get('market_cap_rank'),
        'volume_24h':  row.get('total_volume'),
        'change_24h':  row.get('price_change_percentage_24h'),
        'change_7d':   row.get('price_change_percentage_7d_in_currency'),
        'change_30d': row.get('price_change_percentage_30d_in_currency'),
        'ath_change':  row.get('ath_change_percentage'),
        'sparkline_7d': sparkline,
        **score,
        'why_selected': reasons(row, score),
    }


def _parse_tokenomics(detail: dict, md: dict) -> dict:
    circ  = md.get('circulating_supply')
    total = md.get('total_supply')
    max_s = md.get('max_supply')
    mcap  = (md.get('market_cap') or {}).get('usd')
    fdv   = (md.get('fully_diluted_valuation') or {}).get('usd')

    circ_pct  = round(circ / max_s * 100, 1) if circ and max_s else None
    fdv_ratio = round(fdv / mcap, 2) if fdv and mcap and mcap > 0 else None

    return {
        'circulating_supply': circ,
        'total_supply':       total,
        'max_supply':         max_s,
        'circulating_pct':    circ_pct,
        'fdv':                fdv,
        'fdv_ratio':          fdv_ratio,
        'genesis_date':       detail.get('genesis_date'),
    }


def _parse_ath_atl(md: dict) -> dict:
    return {
        'ath':            (md.get('ath') or {}).get('usd'),
        'ath_date':       (md.get('ath_date') or {}).get('usd'),
        'ath_change_pct': (md.get('ath_change_percentage') or {}).get('usd'),
        'atl':            (md.get('atl') or {}).get('usd'),
        'atl_date':       (md.get('atl_date') or {}).get('usd'),
        'atl_change_pct': (md.get('atl_change_percentage') or {}).get('usd'),
    }


def _parse_community(detail: dict) -> dict:
    cd = detail.get('community_data') or {}
    return {
        'reddit_subscribers':  cd.get('reddit_subscribers'),
        'twitter_followers':   cd.get('twitter_followers'),
        'telegram_user_count': cd.get('telegram_channel_user_count'),
    }


def _parse_links(detail: dict) -> dict:
    links = detail.get('links') or {}
    homepage   = next((h for h in (links.get('homepage') or []) if h), None)
    blockchain = next((b for b in (links.get('blockchain_site') or []) if b), None)
    return {
        'homepage':        homepage,
        'blockchain_site': blockchain,
        'subreddit':       links.get('subreddit_url'),
        'twitter':         links.get('twitter_screen_name'),
    }


# ── rotas ─────────────────────────────────────────────────────────────────────

@router.get('/scanner')
async def scanner(limit: int = Query(80, le=250)) -> list[dict]:
    data = await fetch_markets(limit=limit)
    enriched = [_enrich(x) for x in data]
    return sorted(enriched, key=lambda x: x['priority_score'], reverse=True)


@router.get('/search')
async def search(q: str = Query(..., min_length=1, max_length=50), limit: int = Query(15, le=30)) -> list[dict]:
    """Pesquisa global de moedas no CoinGecko (13k+ moedas)."""
    return await search_coins(q, limit=limit)


@router.get('/asset/{coin_id}')
async def asset_brief(coin_id: str) -> dict:
    """Score + preços básicos — usado na watchlist enriched."""
    data = await fetch_markets(limit=250)
    found = next(
        (x for x in data if x['id'] == coin_id or x.get('symbol', '').lower() == coin_id.lower()),
        None,
    )
    if found:
        return _enrich(found)
    detail = await fetch_coin_detail(coin_id)
    if not detail:
        raise HTTPException(404, f'Moeda {coin_id!r} não encontrada')
    md = detail.get('market_data') or {}
    row = {
        'id': detail.get('id'), 'symbol': detail.get('symbol', ''), 'name': detail.get('name'),
        'image': (detail.get('image') or {}).get('small'),
        'current_price':                          (md.get('current_price') or {}).get('usd'),
        'market_cap':                             (md.get('market_cap') or {}).get('usd'),
        'market_cap_rank':                        detail.get('market_cap_rank'),
        'total_volume':                           (md.get('total_volume') or {}).get('usd'),
        'price_change_percentage_24h':            md.get('price_change_percentage_24h'),
        'price_change_percentage_7d_in_currency': md.get('price_change_percentage_7d'),
        'price_change_percentage_30d_in_currency':md.get('price_change_percentage_30d'),
        'ath_change_percentage':                  (md.get('ath_change_percentage') or {}).get('usd'),
    }
    return _enrich(row)


@router.get('/detail/{coin_id}')
async def asset_detail_full(coin_id: str) -> dict:
    """Dados completos: tokenomics, ATH/ATL, TVL (DefiLlama), community, links, análise técnica."""
    from app.services.defillama import fetch_tvl
    from app.services.technical import analyse_chart

    detail, tvl, chart_pts = await asyncio.gather(
        fetch_coin_detail(coin_id),
        fetch_tvl(coin_id),
        fetch_chart(coin_id, days=90),
        return_exceptions=True,
    )

    if isinstance(detail, Exception):
        detail = {}
    if isinstance(tvl, Exception):
        tvl = None
    if isinstance(chart_pts, Exception):
        chart_pts = []

    if not detail:
        raise HTTPException(404, f'Moeda {coin_id!r} não encontrada')

    md = detail.get('market_data') or {}

    score_row = {
        'id': detail.get('id'),
        'current_price':                           (md.get('current_price') or {}).get('usd'),
        'market_cap':                              (md.get('market_cap') or {}).get('usd'),
        'market_cap_rank':                         detail.get('market_cap_rank'),
        'total_volume':                            (md.get('total_volume') or {}).get('usd'),
        'price_change_percentage_24h':             md.get('price_change_percentage_24h'),
        'price_change_percentage_7d_in_currency':  md.get('price_change_percentage_7d'),
        'price_change_percentage_30d_in_currency': md.get('price_change_percentage_30d'),
        'ath_change_percentage':                   (md.get('ath_change_percentage') or {}).get('usd'),
    }
    score = crypto_score(score_row)

    desc_raw = (detail.get('description') or {}).get('en') or ''
    description = re.sub(r'<[^>]+>', '', desc_raw)[:600].strip()

    return {
        'id':          detail.get('id'),
        'symbol':      (detail.get('symbol') or '').upper(),
        'name':        detail.get('name'),
        'image':       (detail.get('image') or {}).get('large') or (detail.get('image') or {}).get('small'),
        'categories':  detail.get('categories') or [],
        'description': description,
        # preço + market
        'price':       score_row['current_price'],
        'market_cap':  score_row['market_cap'],
        'rank':        score_row['market_cap_rank'],
        'volume_24h':  score_row['total_volume'],
        'change_24h':  score_row['price_change_percentage_24h'],
        'change_7d':   score_row['price_change_percentage_7d_in_currency'],
        'change_30d':  score_row['price_change_percentage_30d_in_currency'],
        # score
        **score,
        'why_selected': reasons(score_row, score),
        # enriquecimento
        'tokenomics': _parse_tokenomics(detail, md),
        'ath_atl':    _parse_ath_atl(md),
        'community':  _parse_community(detail),
        'links':      _parse_links(detail),
        'tvl':        tvl,
        'technical':  analyse_chart([p['price'] for p in (chart_pts or [])]),
    }


@router.get('/chart/{coin_id}')
async def chart(coin_id: str, days: int = Query(90, le=365)) -> list[dict]:
    return await fetch_chart(coin_id, days)
