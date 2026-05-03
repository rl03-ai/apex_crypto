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
    from app.services.phase_strength_detector import apply_phase_strength
    
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
    stage_1d = detect_stage(
        rsi=instdash_1d.get('rsi', 50),
        adx=instdash_1d.get('adx', 20),
        struct_bias=instdash_1d.get('struct_bias', 0),
        squeeze=instdash_1d.get('squeeze', False),
        squeeze_release=instdash_1d.get('squeeze_release', False),
        macd_bullish=instdash_1d.get('macd_bullish', False),
        aligned_bull=instdash_1d.get('aligned_bull', False),
        above_vwap=instdash_1d.get('above_vwap', False),
        dist_ma21_pct=instdash_1d.get('dist_ma21_pct', 0),
        atr_pct=instdash_1d.get('atr_pct', 1.5),
        change_24h_pct=instdash_1d.get('change_24h_pct', 0),
        price_change_7d_pct=instdash_1d.get('price_change_7d_pct', 0),
        structure=instdash_1d.get('structure'),
        htf_trend=None,  # 1d is primary, no HTF
        ext_above_ma200_pct=instdash_1d.get('ext_above_ma200_pct', 0),
    )
    
    stage_1w = detect_stage(
        rsi=instdash_1w.get('rsi', 50),
        adx=instdash_1w.get('adx', 20),
        struct_bias=instdash_1w.get('struct_bias', 0),
        squeeze=instdash_1w.get('squeeze', False),
        squeeze_release=instdash_1w.get('squeeze_release', False),
        macd_bullish=instdash_1w.get('macd_bullish', False),
        aligned_bull=instdash_1w.get('aligned_bull', False),
        above_vwap=instdash_1w.get('above_vwap', False),
        dist_ma21_pct=instdash_1w.get('dist_ma21_pct', 0),
        atr_pct=instdash_1w.get('atr_pct', 1.5),
        change_24h_pct=instdash_1w.get('change_24h_pct', 0),
        price_change_7d_pct=instdash_1w.get('price_change_7d_pct', 0),
        structure=instdash_1w.get('structure'),
        htf_trend='LATERAL',  # 1w is HTF ref for 1d
        ext_above_ma200_pct=instdash_1w.get('ext_above_ma200_pct', 0),
    ) if instdash_1w else None
    
    # ════════════════════════════════════════════════════════════════════════
    # CROSS-TF COHERENCE GATEKEEPING
    # Princípio: se 1w está em DISTRIBUIÇÃO, NUNCA dar BUY mesmo se 1d for bull.
    # 1w domina porque holds são semanas/meses.
    # ════════════════════════════════════════════════════════════════════════
    
    BEARISH_PHASES = {'DISTRIBUICAO'}
    BULLISH_PHASES = {'ACUMULACAO', 'MANIPULACAO'}
    
    # Composite: se 1w DISTRIBUIÇÃO, força composite negativo (ou no máximo zero)
    if stage_1w:
        if stage_1w['phase'] in BEARISH_PHASES:
            # 1w distribuição → cap composite a min(1d_score, 1w_score)
            composite = min(stage_1d['score'], stage_1w['score'])
            # Se 1d é bull mas 1w é distribuição → composite negativo
            if composite > 0:
                composite = -2  # forçar negativo: estrutura macro em distribuição
        else:
            # Ambos OK → ponderação normal (1w domina com 60%)
            composite = round((stage_1w['score'] * 0.6 + stage_1d['score'] * 0.4), 2)
    else:
        composite = stage_1d['score']
    
    composite = round(composite, 2)
    
    # ════════════════════════════════════════════════════════════════════════
    # FINAL ACTION — strict cross-TF rules
    # ════════════════════════════════════════════════════════════════════════
    
    action_1d = stage_1d['action']
    action_1w = stage_1w['action'] if stage_1w else action_1d
    
    # REGRA: 1w DISTRIBUIÇÃO → AVOID, sem excepções
    if stage_1w and stage_1w['phase'] in BEARISH_PHASES:
        final_action = 'AVOID'
    
    # REGRA: 1d DISTRIBUIÇÃO → AVOID
    elif stage_1d['phase'] == 'DISTRIBUICAO':
        final_action = 'AVOID'
    
    # REGRA: convergência bull em ambos TFs → STRONG BUY
    elif (action_1d == 'STRONG BUY' and action_1w in ('STRONG BUY', 'BUY')) or \
         (action_1d == 'BUY' and action_1w == 'STRONG BUY'):
        final_action = 'STRONG BUY'
    
    # REGRA: 1d bull + 1w bull (mas nenhum strong) → BUY
    elif action_1d in ('STRONG BUY', 'BUY') and action_1w in ('STRONG BUY', 'BUY', 'HOLD'):
        final_action = action_1d
    
    # REGRA: 1d bull mas 1w neutral/wait → HOLD (não BUY agressivo)
    elif action_1d in ('STRONG BUY', 'BUY') and action_1w in ('HOLD', 'WAIT'):
        final_action = 'HOLD'
    
    else:
        final_action = action_1w if action_1w else action_1d
    
    # Tier final: o mais restritivo dos dois TFs
    tier_order = {'S': 5, 'A': 4, 'B': 3, 'C': 2, 'D': 1}
    if stage_1w:
        # Se 1w é bearish, tier do 1w domina (puxa para baixo)
        if stage_1w['phase'] in BEARISH_PHASES:
            final_tier = stage_1w['tier']  # tipicamente D
        else:
            # Pega no menor tier (mais conservador)
            tier_1d_val = tier_order.get(stage_1d['tier'], 0)
            tier_1w_val = tier_order.get(stage_1w['tier'], 0)
            final_tier = stage_1d['tier'] if tier_1d_val < tier_1w_val else stage_1w['tier']
    else:
        final_tier = stage_1d['tier']
    
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
            'vol_burst': instdash_1d.get('vol_burst', False),
            'squeeze': instdash_1d.get('squeeze', False),
            'squeeze_release': instdash_1d.get('squeeze_release', False),
            'macd_bullish': instdash_1d.get('macd_bullish', False),
            'above_vwap': instdash_1d.get('above_vwap', False),
            'dist_ma21_pct': instdash_1d.get('dist_ma21_pct', 0),
            'atr_pct': instdash_1d.get('atr_pct', 1.5),
            'price_change_7d_pct': instdash_1d.get('price_change_7d_pct', 0),
        },
        'stage_1d': stage_1d,
        'stage_1w': stage_1w,
        'whale': whale_data,
        'composite': composite,
        'tier': final_tier,
        'action': final_action,
        'timestamp': int(datetime.now(timezone.utc).timestamp()),
    }
    
    # Apply phase strength analysis with the real primary TF metrics.
    # Without this, apply_phase_strength() falls back to neutral defaults.
    result['phase'] = stage_1d['phase']  # Main phase
    result['primary'] = {
        'rsi': instdash_1d.get('rsi', 50),
        'vol_burst': instdash_1d.get('vol_burst', False),
        'squeeze_release': instdash_1d.get('squeeze_release', False),
        'atr_pct': instdash_1d.get('atr_pct', 1.5),
        'change_24h_pct': instdash_1d.get('change_24h_pct', 0),
        'price_change_7d_pct': instdash_1d.get('price_change_7d_pct', 0),
        'dist_ma21_pct': instdash_1d.get('dist_ma21_pct', 0),
        'struct_bias': instdash_1d.get('struct_bias', 0),
        'above_vwap': instdash_1d.get('above_vwap', False),
        'aligned_bull': instdash_1d.get('aligned_bull', False),
        'macd_bullish': instdash_1d.get('macd_bullish', False),
    }
    result = apply_phase_strength(result)
    
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
