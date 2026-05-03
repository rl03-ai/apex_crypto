"""Swing Matrix — tri-TF analysis para holds 3-14d (curto) ou 1-4 semanas (médio).

Mode short:
  - primary: 4h (setup principal)
  - fast: 1h (timing fino)
  - macro: 1d (filtro macro)

Mode medium:
  - primary: 1d (setup principal)
  - fast: 4h (timing fino)
  - macro: 1w (filtro macro)
"""
import logging
import asyncio
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_CACHE = {}
_CACHE_TTL_SECONDS = 600  # 10 min


def _tf_config(mode: str) -> tuple[str, str, str, str]:
    """Devolve (primary, fast, macro, primary_htf) baseado em mode."""
    if mode == 'medium':
        return '1d', '4h', '1w', '1w'
    # default short
    return '4h', '1h', '1d', '1d'


async def compute_swing_row(
    symbol: str,
    coin_id: str | None = None,
    mode: str = 'short',
) -> dict | None:
    """Compute swing row tri-TF + stage swing detection."""
    cache_key = f'swing_{mode}_{symbol}'
    if cache_key in _CACHE:
        cached = _CACHE[cache_key]
        age = datetime.now(timezone.utc).timestamp() - cached['updated_at']
        if age < _CACHE_TTL_SECONDS:
            return cached['data']
    
    from app.services.instdash import analyse_symbol
    from app.services.whale_tracking import fetch_whale_metrics, compute_whale_score
    from app.services.binance import resolve_binance_symbol
    from app.services.swing_detector import detect_swing
    from app.services.phase_strength_detector import apply_phase_strength
    
    primary_tf, fast_tf, macro_tf, primary_htf = _tf_config(mode)
    
    # Resolve symbol
    if symbol.upper().endswith('USDT'):
        binance_sym = symbol.upper()
        coin_short = binance_sym.replace('USDT', '')
    else:
        binance_sym = await resolve_binance_symbol(coin_id or symbol, fallback_symbol=symbol)
        if not binance_sym:
            return None
        coin_short = binance_sym.replace('USDT', '')
    
    # Fetch tri-TF + whale
    try:
        primary, fast, macro, whale_metrics = await asyncio.gather(
            analyse_symbol(binance_sym, interval=primary_tf, htf_interval=primary_htf),
            analyse_symbol(binance_sym, interval=fast_tf, htf_interval=primary_tf),
            analyse_symbol(binance_sym, interval=macro_tf, htf_interval='1M' if mode == 'medium' else '1w'),
            fetch_whale_metrics(coin_short),
            return_exceptions=False,
        )
    except Exception as e:
        log.debug('swing_matrix gather falhou para %s: %s', binance_sym, e)
        return None
    
    if not primary:
        return None
    
    # Whale data
    whale_data = None
    whale_score_val = 0
    if whale_metrics:
        ws = compute_whale_score(
            whale_metrics.get('oi'),
            whale_metrics.get('funding'),
            whale_metrics.get('lsr'),
        )
        whale_score_val = ws['score']
        whale_data = {
            'score': whale_score_val,
            'signal': ws['signal'],
            'description': ws['description'],
            'oi_24h': whale_metrics.get('oi', {}).get('oi_24h_change_pct') if whale_metrics.get('oi') else None,
            'oi_7d': whale_metrics.get('oi', {}).get('oi_7d_change_pct') if whale_metrics.get('oi') else None,
            'funding': whale_metrics.get('funding', {}).get('funding_rate_pct') if whale_metrics.get('funding') else None,
        }
    
    # Detect swing phase
    swing = detect_swing(
        rsi=primary.get('rsi', 50),
        struct_bias=primary.get('struct_bias', 0),
        squeeze=primary.get('squeeze', False),
        squeeze_release=primary.get('squeeze_release', False),
        macd_bullish=primary.get('macd_bullish', False),
        aligned_bull=primary.get('aligned_bull', False),
        above_vwap=primary.get('above_vwap', False),
        dist_ma21_pct=primary.get('dist_ma21_pct', 0),
        atr_pct=primary.get('atr_pct', 1.5),
        change_24h_pct=primary.get('change_24h_pct', 0),
        price_change_7d_pct=primary.get('price_change_7d_pct', 0),
        structure=primary.get('structure'),
        htf_trend=macro.get('htf_trend') if macro else None,
        pullback_ma21=primary.get('pullback_ma21_bull', False),
        vol_burst=primary.get('vol_burst', False),
    )
    swing['mode'] = mode
    
    # SL/TP swing-specific (2×ATR / 3-4×ATR)
    price = primary.get('price', 0)
    atr_pct = primary.get('atr_pct', 3)
    atr_value = (atr_pct / 100) * price
    
    stops = None
    if swing['action'] in ('STRONG BUY', 'BUY') and price and price > 0:
        stops = {
            'entry': round(price, 6),
            'sl': round(price - atr_value * 2, 6),
            'tp1': round(price + atr_value * 3, 6),
            'tp2': round(price + atr_value * 4, 6),
            'sl_pct': round(-atr_value * 2 / price * 100, 2),
            'tp1_pct': round(atr_value * 3 / price * 100, 2),
            'tp2_pct': round(atr_value * 4 / price * 100, 2),
            'r_multiple_1': 1.5,
            'r_multiple_2': 2.0,
        }
    
    result = {
        'symbol': binance_sym,
        'coin_id': coin_id,
        'mode': mode,
        'price': price,
        'change_24h': primary.get('change_24h_pct', 0),
        'primary_tf': primary_tf,
        'fast_tf': fast_tf,
        'macro_tf': macro_tf,
        'primary': {
            'tf': primary_tf,
            'rsi': primary.get('rsi'),
            'adx': primary.get('adx'),
            'ltf_trend': primary.get('ltf_trend'),
            'htf_trend': primary.get('htf_trend'),
            'struct_bias': primary.get('struct_bias', 0),
            'last_event': (primary.get('structure') or {}).get('last_event', 'none'),
            'squeeze': primary.get('squeeze', False),
            'squeeze_release': primary.get('squeeze_release', False),
            'macd_bullish': primary.get('macd_bullish', False),
            'aligned_bull': primary.get('aligned_bull', False),
            'above_vwap': primary.get('above_vwap', False),
            'vol_burst': primary.get('vol_burst', False),
            'dist_ma21_pct': primary.get('dist_ma21_pct', 0),
            'change_24h_pct': primary.get('change_24h_pct', 0),
            'price_change_7d_pct': primary.get('price_change_7d_pct', 0),
            'atr_pct': atr_pct,
        },
        'fast': {
            'tf': fast_tf,
            'rsi': fast.get('rsi') if fast else None,
            'struct_bias': fast.get('struct_bias', 0) if fast else 0,
            'aligned_bull': fast.get('aligned_bull', False) if fast else False,
        } if fast else None,
        'macro': {
            'tf': macro_tf,
            'htf_trend': macro.get('htf_trend') if macro else None,
            'struct_bias': macro.get('struct_bias', 0) if macro else 0,
            'ext_above_ma200_pct': macro.get('ext_above_ma200_pct') if macro else 0,
        } if macro else None,
        'swing': swing,
        'whale': whale_data,
        'stops': stops,
        'composite': swing['score'],  # consistente com matriz invest
        'tier': swing['tier'],
        'action': swing['action'],
        'timestamp': int(datetime.now(timezone.utc).timestamp()),
    }
    
    # Apply phase strength analysis using primary timeframe metrics.
    result['phase'] = swing['phase']  # Main phase
    result['primary'] = {
        'rsi': primary.get('rsi', 50),
        'vol_burst': primary.get('vol_burst', False),
        'squeeze_release': primary.get('squeeze_release', False),
        'atr_pct': primary.get('atr_pct', 1.5),
        'change_24h_pct': primary.get('change_24h_pct', 0),
        'price_change_7d_pct': primary.get('price_change_7d_pct', 0),
        'dist_ma21_pct': primary.get('dist_ma21_pct', 0),
        'struct_bias': primary.get('struct_bias', 0),
        'above_vwap': primary.get('above_vwap', False),
        'aligned_bull': primary.get('aligned_bull', False),
        'macd_bullish': primary.get('macd_bullish', False),
    }
    result = apply_phase_strength(result)
    
    _CACHE[cache_key] = {
        'data': result,
        'updated_at': datetime.now(timezone.utc).timestamp(),
    }
    
    return result


async def compute_swing_matrix(
    symbols: list[str],
    coin_ids: list[str] | None = None,
    mode: str = 'short',
    max_concurrent: int = 15,
) -> list[dict]:
    """Compute swing matrix em paralelo controlado.
    
    Nota: max_concurrent é menor que matriz invest (15 vs 20) porque
    swing requer 3 TFs vs 2 TFs.
    """
    coin_ids = coin_ids or [None] * len(symbols)
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def _bounded(sym, cid):
        async with semaphore:
            return await compute_swing_row(sym, cid, mode)
    
    results = await asyncio.gather(
        *[_bounded(sym, cid) for sym, cid in zip(symbols, coin_ids)],
        return_exceptions=True,
    )
    
    valid = [r for r in results if r is not None and not isinstance(r, Exception)]
    valid.sort(key=lambda r: r['composite'], reverse=True)
    return valid


def clear_cache():
    global _CACHE
    _CACHE.clear()
