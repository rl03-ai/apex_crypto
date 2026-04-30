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
    
    # ════════════════════════════════════════════════════════════════════════
    # CROSS-TF COHERENCE v3 — acumulativo, sem matar sinais
    # Matrix continua a ser o módulo mais seletivo, mas o 1W passa a penalizar
    # em vez de bloquear automaticamente. Isto evita composite negativo/zero
    # quando existe timing 1D interessante contra um macro ainda fraco.
    # ════════════════════════════════════════════════════════════════════════

    BEARISH_STAGES = {'MARKDOWN', 'DISTRIBUTION'}
    EXTENDED_STAGES = {'EXTENDED'}

    s1d = float(stage_1d['score'])
    s1w = float(stage_1w['score']) if stage_1w else s1d

    # Peso de longo prazo: 1W domina, mas 1D ainda conta para timing.
    composite = (s1w * 0.65 + s1d * 0.35) if stage_1w else s1d

    # Penalizações suaves em vez de hard-block.
    if stage_1w:
        if stage_1w['stage'] in BEARISH_STAGES:
            composite *= 0.60
        elif stage_1w['stage'] in EXTENDED_STAGES:
            composite *= 0.70
    if stage_1d['stage'] in EXTENDED_STAGES:
        composite *= 0.75

    # Pequeno ajuste whale, limitado para não dominar a Matrix.
    if whale_score:
        composite += max(-1.0, min(1.0, whale_score / 6.0))

    # Anti-zero: se há dados válidos, mostra pelo menos uma leitura útil.
    if composite == 0:
        composite = 0.5
    composite = round(max(-10, min(10, composite)), 2)

    # ════════════════════════════════════════════════════════════════════════
    # FINAL ACTION — baseada no score final + contexto
    # ════════════════════════════════════════════════════════════════════════

    macro_stage = stage_1w['stage'] if stage_1w else None
    macro_hostile = macro_stage in BEARISH_STAGES if macro_stage else False
    macro_extended = macro_stage in EXTENDED_STAGES if macro_stage else False

    if composite >= 7.5 and not macro_hostile and not macro_extended:
        final_action = 'STRONG BUY'
    elif composite >= 5.5 and not macro_hostile:
        final_action = 'BUY'
    elif composite >= 3.0:
        final_action = 'HOLD'
    elif composite >= 1.0:
        final_action = 'WATCH'
    else:
        final_action = 'AVOID' if macro_hostile and composite < 0 else 'WATCH'

    # Tier final por score, com ligeira degradação se o 1W estiver hostil.
    if composite >= 8:
        final_tier = 'S'
    elif composite >= 6:
        final_tier = 'A'
    elif composite >= 4:
        final_tier = 'B'
    elif composite >= 2:
        final_tier = 'C'
    else:
        final_tier = 'D'

    if macro_hostile and final_tier in ('S', 'A'):
        final_tier = 'B'
    elif macro_extended and final_tier == 'S':
        final_tier = 'A'
    
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
            'struct_bias': instdash_1d.get('struct_bias', 0),
            'last_event': (instdash_1d.get('structure') or {}).get('last_event', 'none'),
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
