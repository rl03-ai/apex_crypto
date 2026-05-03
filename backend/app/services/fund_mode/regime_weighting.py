"""Fund Mode Regime Weighting — Multipliers por fase de market.

ACUMULAÇÃO: ×1.5 (buyer controlled, size up)
MANIPULAÇÃO: ×1.0 (trending normally)
DISTRIBUIÇÃO: ×0.3 (seller controlled, size way down)
CHOP: ×0.8 (neutral, wait)

Simples, operacional, institutional.
"""
import logging

log = logging.getLogger(__name__)


class RegimeWeighting:
    """Multipliers por phase de market."""
    
    PHASE_MULTIPLIERS = {
        'ACUMULACAO': 1.5,      # Size up — accumulation is best risk/reward
        'MANIPULACAO': 1.0,     # Normal sizing — trending
        'DISTRIBUICAO': 0.3,    # Size way down — distribution is risky
        'CHOP': 0.8,            # Wait — consolidation
    }
    
    @staticmethod
    def weight_score(
        score: int,
        phase: str,
    ) -> tuple[int, float, str]:
        """Apply phase multiplier a score.
        
        Returns:
            (weighted_score, multiplier, reason)
        """
        multiplier = RegimeWeighting.PHASE_MULTIPLIERS.get(phase, 1.0)
        weighted = round(score * multiplier)
        
        reason = {
            'ACUMULACAO': '🟢 Buyer controlled — size ↑1.5x',
            'MANIPULACAO': '📈 Trending normally — size ×1.0',
            'DISTRIBUICAO': '⛔ Seller controlled — size ↓0.3x',
            'CHOP': '⚪ Consolidation — wait (×0.8)',
        }.get(phase, 'Unknown phase')
        
        return weighted, multiplier, reason


def apply_phase_weighting(row: dict) -> dict:
    """Apply phase-based weighting to a row."""
    if not row:
        return row
    
    phase = row.get('phase', 'CHOP')
    original_score = row.get('score', 0)
    
    weighted_score, multiplier, reason = RegimeWeighting.weight_score(
        original_score,
        phase,
    )
    
    row['original_score'] = original_score
    row['phase_multiplier'] = multiplier
    row['weighted_score'] = weighted_score
    row['phase_reason'] = reason
    
    return row

