"""Whale score — detecção de smart money positioning via Binance Futures public API.

Score range: -10 (whale panic dump) a +10 (whale massive accumulation)

Factores:
  1. OI 7d trend: +5 se OI > +15%, -5 se OI < -15% (institutional positioning)
  2. OI 24h trend: +2 se > +5%, -2 se < -5% (short-term momentum)
  3. Funding rate: -3 se >0.05% (longs overheated), +3 se <-0.05% (shorts overheated)
  4. Long/short ratio change: +2 se whales rotating long, -2 se rotating short
"""
import logging

log = logging.getLogger(__name__)


def compute_whale_score(
    oi_metrics: dict | None,
    funding_metrics: dict | None,
    lsr_metrics: dict | None,
) -> dict:
    """Compute whale score de -10 a +10.
    
    Args:
        oi_metrics: output de binance_futures.fetch_oi_history()
        funding_metrics: output de binance_futures.fetch_funding_rate()
        lsr_metrics: output de binance_futures.fetch_long_short_ratio()
    
    Returns:
        {
            'score': -2,
            'components': {
                'oi_7d': 2,
                'oi_24h': -1,
                'funding': -3,
                'lsr_rotation': -1,
            },
            'signal': 'whale_bear',
            'description': '...',
        }
    """
    score = 0
    components = {}
    
    # ── 1. OI 7d trend (institutional positioning) ──────────────────
    if oi_metrics and 'oi_7d_change_pct' in oi_metrics:
        oi_7d = oi_metrics['oi_7d_change_pct']
        if oi_7d > 15:
            components['oi_7d'] = 5
        elif oi_7d > 5:
            components['oi_7d'] = 2
        elif oi_7d > 0:
            components['oi_7d'] = 1
        elif oi_7d > -5:
            components['oi_7d'] = -1
        elif oi_7d > -15:
            components['oi_7d'] = -2
        else:
            components['oi_7d'] = -5
        score += components['oi_7d']
    
    # ── 2. OI 24h trend (short-term momentum) ───────────────────────
    if oi_metrics and 'oi_24h_change_pct' in oi_metrics:
        oi_24h = oi_metrics['oi_24h_change_pct']
        if oi_24h > 5:
            components['oi_24h'] = 2
        elif oi_24h > 0:
            components['oi_24h'] = 1
        elif oi_24h > -5:
            components['oi_24h'] = -1
        else:
            components['oi_24h'] = -2
        score += components['oi_24h']
    
    # ── 3. Funding rate (sentiment overheating) ──────────────────────
    # Funding > 0.05% per 8h (annualized ~55%) = longs overpaying = bearish reversal risk
    # Funding < -0.05% = shorts overpaying = bullish squeeze setup
    if funding_metrics and 'funding_rate_pct' in funding_metrics:
        f = funding_metrics['funding_rate_pct']
        if f > 0.05:    # Strong long bias overheated
            components['funding'] = -3
        elif f > 0.02:  # Moderate overheating
            components['funding'] = -1
        elif f < -0.05: # Strong short bias overheated (squeeze setup)
            components['funding'] = 3
        elif f < -0.02:
            components['funding'] = 1
        else:
            components['funding'] = 0
        score += components['funding']
    
    # ── 4. Long/short ratio rotation (whale positioning shift) ──────
    # Top traders' positions changing direction = whale signal
    if lsr_metrics and 'change_24h_pct' in lsr_metrics:
        lsr_change = lsr_metrics['change_24h_pct']
        if lsr_change > 10:    # Whales rotating long aggressively
            components['lsr_rotation'] = 2
        elif lsr_change > 3:
            components['lsr_rotation'] = 1
        elif lsr_change < -10: # Whales rotating short aggressively
            components['lsr_rotation'] = -2
        elif lsr_change < -3:
            components['lsr_rotation'] = -1
        else:
            components['lsr_rotation'] = 0
        score += components['lsr_rotation']
    
    # ── Clamp score a [-10, +10] ────────────────────────────────────
    score = max(-10, min(10, score))
    
    # ── Sinal e descrição ──────────────────────────────────────────
    if score >= 6:
        signal = 'whale_bull'
        desc = 'Strong whale accumulation: OI growing, positioning bullish'
    elif score >= 2:
        signal = 'whale_bull'
        desc = 'Whale accumulation in progress'
    elif score >= -1:
        signal = 'whale_neutral'
        desc = 'Balanced whale activity, no clear bias'
    elif score >= -5:
        signal = 'whale_bear'
        desc = 'Whale distribution: OI declining, bearish positioning'
    else:
        signal = 'whale_bear'
        desc = 'Strong whale dump: OI dropping, longs overheated'
    
    return {
        'score': score,
        'components': components,
        'signal': signal,
        'description': desc,
    }


def whale_score_to_factor(score: int) -> float:
    """Convert whale_score (-10 to +10) para factor InstDash (-1 to +1)."""
    return score / 10.0
