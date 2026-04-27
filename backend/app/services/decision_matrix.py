"""Decision Matrix — combina InstDash + Whale tracking para score composto.

Composite Score:
  InstDash normalized (-16/+16 → -10/+10) × 0.6
  + Whale score (-10/+10) × 0.4
  = Composite (-10 a +10)

Tier (conviction):
  Convergence boost: se InstDash e Whale apontam mesma direcção, +1 tier
  S → |composite| >= 8 + convergence
  A → |composite| >= 6
  B → |composite| >= 4
  C → |composite| >= 2
  D → |composite| < 2

Action:
  STRONG BUY  → composite >= 6
  BUY         → composite >= 3
  HOLD        → composite > -3
  SELL        → composite > -6
  STRONG SELL → composite <= -6
"""
import logging
import asyncio
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# Cache: symbol → {data, updated_at}
_CACHE = {}
_CACHE_TTL_SECONDS = 600  # 10 min (mais curto que whale para refresh frequente)


def _norm_instdash(score: int) -> float:
    """Normaliza InstDash score (-16/+16) para (-10/+10)."""
    return round(score * 10 / 16, 2)


def _compute_tier(composite: float, instdash_norm: float, whale: int) -> str:
    """Tier S/A/B/C/D baseado em conviction.
    
    Convergence: se ambos apontam mesma direcção (sinal mesmo), bonus.
    """
    abs_score = abs(composite)
    
    # Convergence: ambos têm sinal forte e mesma direcção
    same_direction = (instdash_norm >= 2 and whale >= 2) or (instdash_norm <= -2 and whale <= -2)
    
    if abs_score >= 8 and same_direction:
        return 'S'
    if abs_score >= 6:
        return 'A'
    if abs_score >= 4:
        return 'B'
    if abs_score >= 2:
        return 'C'
    return 'D'


def _compute_action(composite: float) -> str:
    """Action baseada em composite score."""
    if composite >= 6:
        return 'STRONG BUY'
    if composite >= 3:
        return 'BUY'
    if composite > -3:
        return 'HOLD'
    if composite > -6:
        return 'SELL'
    return 'STRONG SELL'


async def compute_decision_row(symbol: str, coin_id: str | None = None) -> dict | None:
    """Compute decision matrix row para um símbolo.
    
    Args:
        symbol: 'BTCUSDT' ou 'BTC'
        coin_id: 'bitcoin' (CoinGecko id, opcional)
    
    Returns:
        {
            'symbol': 'BTCUSDT',
            'coin_id': 'bitcoin',
            'price': 67234.5,
            'change_24h': 2.34,
            'instdash': {
                'score': 8,         # raw -16/+16
                'score_norm': 5.0,  # normalized -10/+10
                'rsi': 52.3,
                'adx': 28.4,
                'ltf_trend': 'bull',
                'htf_trend': 'bull',
                'setup_quality': 'LONG válido',
                'aligned': True,
            },
            'whale': {
                'score': 4,
                'signal': 'whale_bull',
                'oi_7d': 12.3,
                'funding': 0.012,
                'lsr': 1.85,
            },
            'composite': 4.8,  # final score
            'tier': 'B',
            'action': 'BUY',
            'timestamp': 1234567890,
        }
    """
    cache_key = f'matrix_{symbol}'
    if cache_key in _CACHE:
        cached = _CACHE[cache_key]
        age = datetime.now(timezone.utc).timestamp() - cached['updated_at']
        if age < _CACHE_TTL_SECONDS:
            return cached['data']
    
    from app.services.instdash import analyse_symbol
    from app.services.whale_tracking import fetch_whale_metrics, compute_whale_score
    from app.services.binance import resolve_binance_symbol
    
    # Resolve symbol
    if symbol.upper().endswith('USDT'):
        binance_sym = symbol.upper()
        coin_short = binance_sym.replace('USDT', '')
    else:
        binance_sym = await resolve_binance_symbol(coin_id or symbol, fallback_symbol=symbol)
        if not binance_sym:
            log.debug('decision_matrix: cant resolve %s', symbol)
            return None
        coin_short = binance_sym.replace('USDT', '')
    
    # Fetch InstDash + Whale em paralelo
    try:
        instdash, whale_metrics = await asyncio.gather(
            analyse_symbol(binance_sym, interval='1d', htf_interval='1w'),
            fetch_whale_metrics(coin_short),
            return_exceptions=False,
        )
    except Exception as e:
        log.debug('decision_matrix gather falhou para %s: %s', binance_sym, e)
        return None
    
    if not instdash:
        return None
    
    # InstDash normalized
    instdash_score = instdash.get('score', 0)
    instdash_norm = _norm_instdash(instdash_score)
    
    # Whale score
    whale_score_data = None
    if whale_metrics:
        whale_score_data = compute_whale_score(
            whale_metrics.get('oi'),
            whale_metrics.get('funding'),
            whale_metrics.get('lsr'),
        )
    whale_score = whale_score_data['score'] if whale_score_data else 0
    
    # Composite (60% InstDash, 40% Whale)
    composite = (instdash_norm * 0.6) + (whale_score * 0.4)
    composite = max(-10, min(10, round(composite, 2)))
    
    # Tier + Action
    tier = _compute_tier(composite, instdash_norm, whale_score)
    action = _compute_action(composite)
    
    result = {
        'symbol': binance_sym,
        'coin_id': coin_id,
        'price': instdash.get('price', 0),
        'change_24h': instdash.get('change_24h_pct', 0),
        'instdash': {
            'score': instdash_score,
            'score_norm': instdash_norm,
            'signal': instdash.get('signal', 'neutral'),
            'rsi': instdash.get('rsi'),
            'adx': instdash.get('adx'),
            'ltf_trend': instdash.get('ltf_trend'),
            'htf_trend': instdash.get('htf_trend'),
            'setup_quality': instdash.get('setup_quality'),
            'aligned': instdash.get('aligned_bull') or instdash.get('aligned_bear'),
            'sl_long': instdash.get('sl_long'),
            'tp_long': instdash.get('tp_long'),
            'sl_short': instdash.get('sl_short'),
            'tp_short': instdash.get('tp_short'),
        },
        'whale': {
            'score': whale_score,
            'signal': whale_score_data['signal'] if whale_score_data else 'whale_neutral',
            'description': whale_score_data['description'] if whale_score_data else None,
            'oi_24h': whale_metrics.get('oi', {}).get('oi_24h_change_pct') if whale_metrics and whale_metrics.get('oi') else None,
            'oi_7d': whale_metrics.get('oi', {}).get('oi_7d_change_pct') if whale_metrics and whale_metrics.get('oi') else None,
            'funding': whale_metrics.get('funding', {}).get('funding_rate_pct') if whale_metrics and whale_metrics.get('funding') else None,
            'funding_apr': whale_metrics.get('funding', {}).get('funding_rate_annualized_pct') if whale_metrics and whale_metrics.get('funding') else None,
            'lsr': whale_metrics.get('lsr', {}).get('long_short_ratio') if whale_metrics and whale_metrics.get('lsr') else None,
            'lsr_change': whale_metrics.get('lsr', {}).get('change_24h_pct') if whale_metrics and whale_metrics.get('lsr') else None,
        } if whale_score_data else None,
        'composite': composite,
        'tier': tier,
        'action': action,
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
    """Compute decision matrix para lista de símbolos (paralelo controlado).
    
    Args:
        symbols: ['BTC', 'ETH', ...]
        coin_ids: ['bitcoin', 'ethereum', ...] opcional
        max_concurrent: máximo de tarefas paralelas (default 20).
                        Mais alto = mais rápido mas pode saturar APIs.
    
    Returns:
        Lista ordenada por |composite| desc (mais conviction primeiro).
    """
    coin_ids = coin_ids or [None] * len(symbols)
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def _bounded(sym, cid):
        async with semaphore:
            return await compute_decision_row(sym, cid)
    
    results = await asyncio.gather(
        *[_bounded(sym, cid) for sym, cid in zip(symbols, coin_ids)],
        return_exceptions=True,  # Don't fail entire batch on one error
    )
    
    # Filtra erros e Nones
    valid = []
    for r in results:
        if isinstance(r, Exception):
            log.debug('compute_matrix: row exception: %s', r)
            continue
        if r is not None:
            valid.append(r)
    
    valid.sort(key=lambda r: abs(r['composite']), reverse=True)
    return valid


def clear_cache():
    """Clear cache (testes)."""
    global _CACHE
    _CACHE.clear()
