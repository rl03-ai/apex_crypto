"""Whale tracking — smart money & institutional positioning signals.

Módulo para detectar:
  - OI crescente (acumulação institucional)
  - Liquidações em cascata (panic selling)
  - Score integrado no InstDash
"""

from .coinglass import fetch_whale_metrics, clear_cache
from .scorer import compute_whale_score, whale_score_to_factor

__all__ = [
    'fetch_whale_metrics',
    'compute_whale_score',
    'whale_score_to_factor',
    'clear_cache',
]
