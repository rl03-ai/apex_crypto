"""Regime Weighting Engine — HTF trend modifica scoring.

Princípio: Fund não bloqueia em macro bear, mas redimensiona.

Regime = HTF trend + struct_bias + vol

Multipliers:
  ALTA (bull):       score × 1.3  (opportunity)
  LATERAL (range):   score × 1.0  (neutral)
  BAIXA (bear):      score × 0.6  (risk reduction, oversold only)
  
Com struct_bias:
  bull (1):   +0.15x multiplier
  neutral:    ±0x
  bear (-1):  -0.25x multiplier (bloqueia se BAIXA + bear)
"""
import logging

log = logging.getLogger(__name__)


class RegimeWeighting:
    """Calcula regime multiplier para score."""
    
    # HTF trend multipliers (base)
    TREND_MULTIPLIERS = {
        'ALTA': 1.3,      # Bull trend — accept all setups, size up
        'LATERAL': 1.0,   # Range — neutral
        'BAIXA': 0.6,     # Bear trend — size down, oversold only
    }
    
    # Struct bias modifiers (adiciona ao multiplier)
    STRUCT_MODIFIERS = {
        1: 0.15,     # Bull structure — add confidence
        0: 0.0,      # Neutral
        -1: -0.25,   # Bear structure — reduce or block
    }
    
    # Vol regime (HTF momentum)
    VOL_REGIME_MODIFIERS = {
        'extreme_vol': -0.3,    # High vol = risk, reduce
        'normal_vol': 0.0,
        'low_vol': -0.1,        # Low vol = low conviction
    }
    
    @staticmethod
    def classify_vol_regime(atr_pct: float, change_7d_pct: float) -> str:
        """Classifica vol regime baseado em ATR% e 7d change."""
        if atr_pct > 8 or abs(change_7d_pct) > 25:
            return 'extreme_vol'
        if atr_pct < 1.5:
            return 'low_vol'
        return 'normal_vol'
    
    @staticmethod
    def weight_score(
        score: int,
        htf_trend: str | None = None,
        struct_bias: int = 0,
        atr_pct: float | None = None,
        change_7d_pct: float | None = None,
    ) -> tuple[int, float, list[str]]:
        """Apply regime weighting a score.
        
        Returns:
            (weighted_score, multiplier, reasons)
        """
        reasons = []
        
        # Base multiplier from HTF trend
        trend_mult = RegimeWeighting.TREND_MULTIPLIERS.get(htf_trend or 'LATERAL', 1.0)
        reasons.append(f'HTF {htf_trend or "LATERAL"}: ×{trend_mult:.2f}')
        
        multiplier = trend_mult
        
        # Struct bias modifier
        struct_mod = RegimeWeighting.STRUCT_MODIFIERS.get(struct_bias, 0.0)
        if struct_mod != 0:
            multiplier += struct_mod
            struct_label = {1: 'bull', 0: 'neutral', -1: 'bear'}.get(struct_bias, '?')
            reasons.append(f'Struct {struct_label}: {struct_mod:+.2f}')
        
        # Vol regime modifier
        if atr_pct is not None and change_7d_pct is not None:
            vol_regime = RegimeWeighting.classify_vol_regime(atr_pct, change_7d_pct)
            vol_mod = RegimeWeighting.VOL_REGIME_MODIFIERS.get(vol_regime, 0.0)
            if vol_mod != 0:
                multiplier += vol_mod
                reasons.append(f'Vol {vol_regime}: {vol_mod:+.2f}')
        
        # Hard block: BAIXA + struct_bias=-1
        if htf_trend == 'BAIXA' and struct_bias == -1:
            reasons.append('⛔ BAIXA + struct bear → BLOCKED')
            return -99, 0.0, reasons
        
        # Cap multiplier at bounds
        multiplier = max(0.3, min(1.5, multiplier))
        
        # Apply to score
        weighted = round(score * multiplier)
        
        if weighted != score:
            reasons.append(f'Score: {score} × {multiplier:.2f} = {weighted}')
        
        return weighted, multiplier, reasons


def apply_regime_to_matrix_row(row: dict) -> dict:
    """Apply regime weighting to a matrix row."""
    if not row or 'composite' not in row:
        return row
    
    macro = row.get('macro') or {}
    primary = row.get('primary') or {}
    
    htf_trend = macro.get('htf_trend')
    struct_bias = primary.get('struct_bias', 0)
    atr_pct = primary.get('atr_pct')
    change_7d = primary.get('price_change_7d_pct')
    
    original_score = row['composite']
    weighted_score, multiplier, reasons = RegimeWeighting.weight_score(
        original_score,
        htf_trend=htf_trend,
        struct_bias=struct_bias,
        atr_pct=atr_pct,
        change_7d_pct=change_7d,
    )
    
    # Update row
    row['original_score'] = original_score
    row['regime_multiplier'] = multiplier
    row['composite'] = weighted_score
    row['regime_reasons'] = reasons
    
    # Update tier/action based on weighted score
    if weighted_score <= -99:
        row['action'] = 'AVOID'
        row['tier'] = 'D'
    
    return row
