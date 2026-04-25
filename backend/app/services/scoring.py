"""Scoring crypto — 6 dimensões → score total /100.

  adoption   — market cap rank + liquidez relativa
  quality    — rank + capitalização mínima
  valuation  — distância ao ATH + momentum 30d
  market     — momentum 7d + 30d + 24h
  catalysts  — volume spike + momentum forte
  risk       — volatilidade + drawdown do ATH
"""
from __future__ import annotations


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _pct_score(value: float | None, low: float, high: float) -> float:
    if value is None:
        return 50.0
    return _clamp((value - low) / (high - low) * 100)


def crypto_score(c: dict) -> dict:
    if not c:
        return {
            'adoption': 50, 'quality': 50, 'valuation': 50,
            'market': 50, 'catalysts': 50, 'risk': 50,
            'total_score': 50, 'priority_score': 50, 'state': 'watchlist',
        }

    p24 = c.get('price_change_percentage_24h') or 0.0
    p7d = c.get('price_change_percentage_7d_in_currency') or 0.0
    p30d = c.get('price_change_percentage_30d_in_currency') or 0.0
    vol = c.get('total_volume') or 0.0
    mcap = c.get('market_cap') or 1.0
    ath_chg = c.get('ath_change_percentage') or -80.0
    rank = c.get('market_cap_rank') or 999

    vol_ratio = vol / max(mcap, 1)

    adoption = _clamp(
        100 - min(rank, 250) / 250 * 70
        + _pct_score(vol_ratio, 0.01, 0.25) * 0.30
    )
    quality = _clamp(
        100 - min(rank, 300) / 300 * 45
        + (20 if mcap > 10_000_000_000 else 10 if mcap > 1_000_000_000 else 0)
    )
    valuation = _clamp(70 + abs(ath_chg) * 0.25 - max(p30d, 0) * 0.25)
    market = _clamp(45 + p7d * 1.5 + p30d * 0.6 + p24 * 0.8)
    catalysts = _clamp(
        50
        + (12 if vol_ratio > 0.08 else 6 if vol_ratio > 0.04 else 0)
        + (10 if p7d > 10 else 5 if p7d > 5 else 0)
    )
    risk = _clamp(
        35
        + abs(p24) * 2.0
        + abs(p7d) * 0.5
        + max(0, 80 + ath_chg) * 0.4
    )

    total = _clamp(
        adoption * 0.20
        + quality * 0.20
        + valuation * 0.15
        + market * 0.20
        + catalysts * 0.10
        + (100 - risk) * 0.15
    )
    priority = _clamp(total * 0.75 + market * 0.25)

    if total >= 70 and market >= 55:
        state = 'confirming'
    elif total >= 55:
        state = 'watchlist'
    else:
        state = 'avoid'

    return {
        'adoption': round(adoption, 1),
        'quality': round(quality, 1),
        'valuation': round(valuation, 1),
        'market': round(market, 1),
        'catalysts': round(catalysts, 1),
        'risk': round(risk, 1),
        'total_score': round(total, 1),
        'priority_score': round(priority, 1),
        'state': state,
    }


def reasons(c: dict, s: dict) -> list[str]:
    vol_ratio = (c.get('total_volume') or 0) / max(c.get('market_cap') or 1, 1) * 100
    p7d = c.get('price_change_percentage_7d_in_currency') or 0
    p30d = c.get('price_change_percentage_30d_in_currency') or 0
    ath = c.get('ath_change_percentage') or 0

    out = []
    if abs(p7d) >= 5:
        out.append(f"Momentum 7d: {p7d:+.1f}% — {'forte alta' if p7d > 0 else 'pressão vendedora'}.")
    if abs(p30d) >= 10:
        out.append(f"Momentum 30d: {p30d:+.1f}%.")
    out.append(f"Distância ao ATH: {ath:.1f}%.")
    out.append(f"Liquidez relativa (vol/mcap): {vol_ratio:.1f}%.")
    out.append(f"Risco estimado: {s.get('risk', 50):.0f}/100.")
    return out
