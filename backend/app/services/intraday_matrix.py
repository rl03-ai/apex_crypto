"""Intraday Matrix — tri-TF analysis para holds 1-24h."""
import logging
import asyncio
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_CACHE = {}
_CACHE_TTL_SECONDS = 180  # 3 min — intraday refresh frequente


def _tf_config(mode: str) -> tuple[str, str, str, str]:
    """Returns (primary, fast, macro, primary_htf)."""
    if mode == 'scalping':
        return '5m', '15m', '1h', '15m'
    # default 'day'
    return '15m', '1h', '4h', '1h'


async def compute_intraday_row(
    symbol: str,
    coin_id: str | None = None,
    mode: str = 'day',
) -> dict | None:
    """Compute intraday row tri-TF + setup detection."""
    cache_key = f'intraday_{mode}_{symbol}'
    if cache_key in _CACHE:
        cached = _CACHE[cache_key]
        age = datetime.now(timezone.utc).timestamp() - cached['updated_at']
        if age < _CACHE_TTL_SECONDS:
            return cached['data']
    
    from app.services.instdash import analyse_symbol
    from app.services.whale_tracking import fetch_whale_metrics, compute_whale_score
    from app.services.binance import resolve_binance_symbol
    from app.services.intraday_detector import detect_intraday
    
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
    
    # Fetch tri-TF + whale (paralelo)
    try:
        primary, fast, macro, whale_metrics = await asyncio.gather(
            analyse_symbol(binance_sym, interval=primary_tf, htf_interval=primary_htf),
            analyse_symbol(binance_sym, interval=fast_tf, htf_interval=primary_tf),
            analyse_symbol(binance_sym, interval=macro_tf, htf_interval='1d'),
            fetch_whale_metrics(coin_short),
            return_exceptions=False,
        )
    except Exception as e:
        log.debug('intraday_matrix gather falhou para %s: %s', binance_sym, e)
        return None
    
    if not primary:
        return None
    
    # Whale data (peso reduzido em intraday)
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
            'funding': whale_metrics.get('funding', {}).get('funding_rate_pct') if whale_metrics.get('funding') else None,
        }
    
    # Detect intraday setup
    setup = detect_intraday(
        primary=primary,
        fast=fast,
        macro=macro,
        mode=mode,
        whale=whale_data,
    )
    
    # SL/TP intraday-specific (1×ATR / 2-3×ATR)
    price = primary.get('price', 0)
    atr_pct = primary.get('atr_pct', 1.5)
    atr_value = (atr_pct / 100) * price
    
    stops = {
        'entry': round(price, 6),
        'sl': round(price - atr_value * 1.0, 6),
        'tp1': round(price + atr_value * 2.0, 6),
        'tp2': round(price + atr_value * 3.0, 6),
        'sl_pct': round(-atr_value * 1.0 / price * 100, 2),
        'tp1_pct': round(atr_value * 2.0 / price * 100, 2),
        'tp2_pct': round(atr_value * 3.0 / price * 100, 2),
        'r_multiple_1': 2.0,
        'r_multiple_2': 3.0,
    } if setup['action'] in ('STRONG BUY', 'BUY') else None
    
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
            'struct_bias': primary.get('struct_bias', 0),
            'last_event': (primary.get('structure') or {}).get('last_event', 'none'),
            'squeeze': primary.get('squeeze', False),
            'squeeze_release': primary.get('squeeze_release', False),
            'macd_bullish': primary.get('macd_bullish', False),
            'above_vwap': primary.get('above_vwap', False),
            'aligned_bull': primary.get('aligned_bull', False),
            'vol_burst': primary.get('vol_burst', False),
            'sweep_low': (primary.get('liquidity') or {}).get('sweep_low', False),
            'sweep_high': (primary.get('liquidity') or {}).get('sweep_high', False),
            'atr_pct': atr_pct,
        },
        'fast': {
            'tf': fast_tf,
            'rsi': fast.get('rsi') if fast else None,
            'struct_bias': fast.get('struct_bias', 0) if fast else 0,
            'aligned_bull': fast.get('aligned_bull', False) if fast else False,
            'above_vwap': fast.get('above_vwap', False) if fast else False,
        } if fast else None,
        'macro': {
            'tf': macro_tf,
            'htf_trend': macro.get('htf_trend') if macro else None,
            'struct_bias': macro.get('struct_bias', 0) if macro else 0,
            'above_vwap': macro.get('above_vwap', False) if macro else False,
        } if macro else None,
        'setup': setup,
        'whale': whale_data,
        'stops': stops,
        'composite': setup['score'],
        'tier': setup['tier'],
        'action': setup['action'],
        'can_hold_overnight': setup['can_hold_overnight'],
        'timestamp': int(datetime.now(timezone.utc).timestamp()),
    }
    
    _CACHE[cache_key] = {
        'data': result,
        'updated_at': datetime.now(timezone.utc).timestamp(),
    }
    
    return result


async def compute_intraday_matrix(
    symbols: list[str],
    coin_ids: list[str] | None = None,
    mode: str = 'day',
    max_concurrent: int = 12,
) -> list[dict]:
    """Compute intraday matrix em paralelo controlado.
    
    Concurrency mais baixa (12 vs 15 swing) porque candles 5m/15m
    têm rate limits mais agressivos no Binance.
    """
    coin_ids = coin_ids or [None] * len(symbols)
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def _bounded(sym, cid):
        async with semaphore:
            return await compute_intraday_row(sym, cid, mode)
    
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
