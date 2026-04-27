"""Whale score — detecção de smart money accumulation vs panic selling.

Score range: -10 (whale panic dump) a +10 (whale massive accumulation)

Factores:
  1. OI 7d trend: +5 se OI > +15%, -5 se OI < -15%
  2. OI 24h trend: +2 se > +5%, -2 se < -5%
  3. Liquidation ratio: +3 se shorts > 70%, -3 se longs > 70%
"""
import logging

log = logging.getLogger(__name__)


def compute_whale_score(oi_metrics: dict | None, liq_metrics: dict | None) -> dict:
    """Compute whale score de -10 a +10.

    Args:
        oi_metrics: output de coinglass.fetch_oi_trending()
        liq_metrics: output de coinglass.fetch_liquidations()

    Returns:
        {
            'score': -2,
            'components': {
                'oi_7d': 2,      # +2 pour OI crescente (bullish)
                'oi_24h': -1,    # -1 pour OI caindo hoje (bearish)
                'liq_pressure': -3,  # -3 pour mais longs liquidados (bearish)
            },
            'signal': 'whale_bear',  # whale_bull | whale_neutral | whale_bear
            'description': 'Whale activity: more longs liquidated, but OI still up 7d',
        }
    """
    score = 0
    components = {}

    # ── OI 7d trend (acumulação institucional) ──────────────────────────
    if oi_metrics and 'oi_7d_change_pct' in oi_metrics:
        oi_7d = oi_metrics['oi_7d_change_pct']
        
        if oi_7d > 15:  # Strong accumulation
            components['oi_7d'] = 5
            score += 5
        elif oi_7d > 5:   # Moderate accumulation
            components['oi_7d'] = 2
            score += 2
        elif oi_7d > 0:   # Slight accumulation
            components['oi_7d'] = 1
            score += 1
        elif oi_7d > -5:  # Slight decline
            components['oi_7d'] = -1
            score -= 1
        elif oi_7d > -15: # Moderate decline
            components['oi_7d'] = -2
            score -= 2
        else:             # Strong decline
            components['oi_7d'] = -5
            score -= 5

    # ── OI 24h trend (short-term momentum) ─────────────────────────────
    if oi_metrics and 'oi_24h_change_pct' in oi_metrics:
        oi_24h = oi_metrics['oi_24h_change_pct']
        
        if oi_24h > 5:
            components['oi_24h'] = 2
            score += 2
        elif oi_24h > 0:
            components['oi_24h'] = 1
            score += 1
        elif oi_24h > -5:
            components['oi_24h'] = -1
            score -= 1
        else:
            components['oi_24h'] = -2
            score -= 2

    # ── Liquidation pressure (shorts vs longs) ────────────────────────
    if liq_metrics and 'shorts_pct' in liq_metrics:
        shorts_pct = liq_metrics['shorts_pct']
        
        # Se muitos shorts liquidados (>70%) = bearish (whale shorted, got liquidated)
        # Se muitos longs liquidados (<30%) = bullish (whale bought, longs panicked)
        
        if shorts_pct > 70:  # Whale shorters getting liquidated
            components['liq_pressure'] = 3
            score += 3
        elif shorts_pct > 55:
            components['liq_pressure'] = 1
            score += 1
        elif shorts_pct < 30:  # Whale buyers panic selling
            components['liq_pressure'] = -3
            score -= 3
        elif shorts_pct < 45:
            components['liq_pressure'] = -1
            score -= 1

    # ── Clamp score a [-10, +10] ──────────────────────────────────────
    score = max(-10, min(10, score))

    # ── Sinal e descrição ─────────────────────────────────────────────
    if score >= 6:
        signal = 'whale_bull'
        desc = 'Strong whale buying: OI growing, liquidations favor shorts'
    elif score >= 2:
        signal = 'whale_bull'
        desc = 'Whale accumulation: moderate OI growth'
    elif score >= -1:
        signal = 'whale_neutral'
        desc = 'Balanced whale activity'
    elif score >= -5:
        signal = 'whale_bear'
        desc = 'Whale distribution: OI declining, longs liquidating'
    else:
        signal = 'whale_bear'
        desc = 'Strong whale dump: OI dropping, cascading liquidations'

    return {
        'score': score,
        'components': components,
        'signal': signal,
        'description': desc,
    }


def whale_score_to_factor(score: int) -> float:
    """Convert whale_score (-10 to +10) para factor InstDash (-1 to +1).

    Usado para integrar no InstDash 16-factor scoring.
    """
    return score / 10.0
