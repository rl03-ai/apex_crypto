"""Decision Matrix — Stage Detector v2 com dual timeframe (1d + 1w).

Para holds de semanas/meses:
  - Score baseado em stage (ACCUMULATION/MARKUP/EXTENDED/MARKDOWN/CHOP)
  - Penaliza setups esticados
  - Premia inícios e confirmações
  - Dual TF: 1d (entry timing) + 1w (macro context)
"""
import logging
import asyncio
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_CACHE = {}
_CACHE_TTL_SECONDS = 600  # 10 min


async def compute_decision_row(symbol: str, coin_id: str | None = None) -> dict | None:
    """Compute decision row com dual TF (1d + 1w) + stage detection."""
    cache_key = f'matrix_{symbol}'
    if cache_key in _CACHE:
        cached = _CACHE[cache_key]
        age = datetime.now(timezone.utc).timestamp() - cached['updated_at']
        if age < _CACHE_TTL_SECONDS:
            return cached['data']
    
    from app.services.instdash import analyse_symbol
    from app.services.whale_tracking import fetch_whale_metrics, compute_whale_score
    from app.services.binance import resolve_binance_symbol
    from app.services.stage_detector import detect_stage
    
    # Resolve symbol
    if symbol.upper().endswith('USDT'):
        binance_sym = symbol.upper()
        coin_short = binance_sym.replace('USDT', '')
    else:
        binance_sym = await resolve_binance_symbol(coin_id or symbol, fallback_symbol=symbol)
        if not binance_sym:
            return None
        coin_short = binance_sym.replace('USDT', '')
    
    # Fetch dual TF (1d + 1w) + Whale em paralelo
    try:
        instdash_1d, instdash_1w, whale_metrics = await asyncio.gather(
            analyse_symbol(binance_sym, interval='1d', htf_interval='1w'),
            analyse_symbol(binance_sym, interval='1w', htf_interval='1M'),
            fetch_whale_metrics(coin_short),
            return_exceptions=False,
        )
    except Exception as e:
        log.debug('decision_matrix gather falhou para %s: %s', binance_sym, e)
        return None
    
    if not instdash_1d:
        return None
    
    # Whale score
    whale_data = None
    whale_score = 0
    if whale_metrics:
        ws = compute_whale_score(
            whale_metrics.get('oi'),
            whale_metrics.get('funding'),
            whale_metrics.get('lsr'),
        )
        whale_score = ws['score']
        whale_data = {
            'score': whale_score,
            'signal': ws['signal'],
            'description': ws['description'],
            'oi_24h': whale_metrics.get('oi', {}).get('oi_24h_change_pct') if whale_metrics.get('oi') else None,
            'oi_7d': whale_metrics.get('oi', {}).get('oi_7d_change_pct') if whale_metrics.get('oi') else None,
            'funding': whale_metrics.get('funding', {}).get('funding_rate_pct') if whale_metrics.get('funding') else None,
            'funding_apr': whale_metrics.get('funding', {}).get('funding_rate_annualized_pct') if whale_metrics.get('funding') else None,
            'lsr': whale_metrics.get('lsr', {}).get('long_short_ratio') if whale_metrics.get('lsr') else None,
            'lsr_change': whale_metrics.get('lsr', {}).get('change_24h_pct') if whale_metrics.get('lsr') else None,
        }
    
    # Stage detection — 1d e 1w (whale só passa ao 1d para não duplicar peso)
    stage_1d = detect_stage(instdash_1d, whale_data)
    stage_1w = detect_stage(instdash_1w, None) if instdash_1w else None
    
    # Composite final: 1w tem mais peso (60%) porque holds são longos
    if stage_1w:
        composite = round((stage_1w['score'] * 0.6 + stage_1d['score'] * 0.4), 2)
    else:
        composite = stage_1d['score']
    
    # Tier final: usa o mais restritivo entre 1d e 1w
    tier_order = {'S': 5, 'A': 4, 'B': 3, 'C': 2, 'D': 1}
    if stage_1w and tier_order[stage_1w['tier']] >= tier_order[stage_1d['tier']]:
        # 1w domina se tier alto
        final_tier = stage_1w['tier'] if stage_1w['stage'] in ('ACCUMULATION', 'MARKUP_EARLY') else stage_1d['tier']
    else:
        final_tier = stage_1d['tier']
    
    # Action: regras combinadas
    action_1d = stage_1d['action']
    action_1w = stage_1w['action'] if stage_1w else action_1d
    
    # Convergência: ambos BUY → STRONG BUY
    if action_1d == 'STRONG BUY' and action_1w in ('STRONG BUY', 'BUY'):
        final_action = 'STRONG BUY'
    elif action_1d == 'BUY' and action_1w == 'STRONG BUY':
        final_action = 'STRONG BUY'
    elif action_1w == 'AVOID':  # 1w é prioridade — se HTF avoid, evita
        final_action = 'AVOID'
    elif action_1d in ('STRONG BUY', 'BUY') and action_1w not in ('AVOID',):
        final_action = action_1d
    else:
        final_action = action_1w if action_1w else action_1d
    
    result = {
        'symbol': binance_sym,
        'coin_id': coin_id,
        'price': instdash_1d.get('price', 0),
        'change_24h': instdash_1d.get('change_24h_pct', 0),
        'instdash': {
            'score': instdash_1d.get('score', 0),
            'rsi': instdash_1d.get('rsi'),
            'adx': instdash_1d.get('adx'),
            'ltf_trend': instdash_1d.get('ltf_trend'),
            'htf_trend': instdash_1d.get('htf_trend'),
            'setup_quality': instdash_1d.get('setup_quality'),
            'aligned': instdash_1d.get('aligned_bull') or instdash_1d.get('aligned_bear'),
            'sl_long': instdash_1d.get('sl_long'),
            'tp_long': instdash_1d.get('tp_long'),
            'ext_above_ma200_pct': instdash_1d.get('ext_above_ma200_pct'),
        },
        'stage_1d': stage_1d,
        'stage_1w': stage_1w,
        'whale': whale_data,
        'composite': composite,
        'tier': final_tier,
        'action': final_action,
        'timestamp': int(datetime.now(timezone.utc).timestamp()),
    }
    
    _CACHE[cache_key] = {
        'data': result,
        'updated_at': datetime.now(timezone.utc).timestamp(),
    }
    
    return result


async def compute_matrix(
    symbols: list[str],
    coin_ids: list[str] | None = None,
    max_concurrent: int = 20,
) -> list[dict]:
    """Compute decision matrix em paralelo controlado."""
    coin_ids = coin_ids or [None] * len(symbols)
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def _bounded(sym, cid):
        async with semaphore:
            return await compute_decision_row(sym, cid)
    
    results = await asyncio.gather(
        *[_bounded(sym, cid) for sym, cid in zip(symbols, coin_ids)],
        return_exceptions=True,
    )
    
    valid = [r for r in results if r is not None and not isinstance(r, Exception)]
    valid.sort(key=lambda r: r['composite'], reverse=True)  # mais bullish primeiro
    return valid


def clear_cache():
    global _CACHE
    _CACHE.clear()
