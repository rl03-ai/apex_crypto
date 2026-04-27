"""Whale tracking — smart money positioning via Binance Futures public API.

Sinais detectados:
  - OI crescente (acumulação institucional)
  - Funding rate overheating (sentiment extremo)
  - Long/short ratio rotation (whale positioning shift)
"""

from .binance_futures import (
    fetch_whale_metrics,
    fetch_oi_history,
    fetch_funding_rate,
    fetch_long_short_ratio,
    clear_cache,
)
from .scorer import compute_whale_score, whale_score_to_factor

__all__ = [
    'fetch_whale_metrics',
    'fetch_oi_history',
    'fetch_funding_rate',
    'fetch_long_short_ratio',
    'compute_whale_score',
    'whale_score_to_factor',
    'clear_cache',
]
