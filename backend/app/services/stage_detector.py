"""Stage Detector para Matrix Invest — agora integra market_phase_detector.

Matrix (semanas+) usa market phases com thresholds rigorosos.

ACUMULAÇÃO: Fase de entrada (insiders compram)
MANIPULAÇÃO: Fase de trending (pump coordenado)
DISTRIBUIÇÃO: Fase de saída (insiders vendem) → AVOID
CHOP: Consolidação sem rumo

Tiers: S=ACCUM score 9+, A=ACCUM score 7+, B=MANIP 6+, C=CHOP, D=DIST/bear
"""
import logging
from app.services.market_phase_detector import detect_phase

log = logging.getLogger(__name__)


def detect_stage(
    rsi: float,
    adx: float,
    struct_bias: int = 0,
    squeeze: bool = False,
    squeeze_release: bool = False,
    macd_bullish: bool = False,
    aligned_bull: bool = False,
    above_vwap: bool = False,
    dist_ma21_pct: float = 0,
    atr_pct: float = 1.5,
    change_24h_pct: float = 0,
    price_change_7d_pct: float = 0,
    structure: dict | None = None,
    htf_trend: str | None = None,
    ext_above_ma200_pct: float = 0,
) -> dict:
    """Detect market stage (Matrix Invest version).
    
    Uses market_phase_detector com thresholds para semanas+.
    """
    structure = structure or {}
    last_event = structure.get('last_event', 'none')
    
    # Vol burst logic (squeeze_release = squeeze liberado)
    vol_burst = squeeze_release or (atr_pct > 3.5 and change_24h_pct > 2)
    
    # Usa detector unificado
    phase_result = detect_phase(
        rsi=rsi,
        struct_bias=struct_bias,
        last_event=last_event,
        vol_burst=vol_burst,
        squeeze_release=squeeze_release,
        macd_bullish=macd_bullish,
        aligned_bull=aligned_bull,
        above_vwap=above_vwap,
        dist_ma21_pct=dist_ma21_pct,
        atr_pct=atr_pct,
        change_24h_pct=change_24h_pct,
        price_change_7d_pct=price_change_7d_pct,
    )
    
    phase = phase_result['phase']
    score = phase_result['score']
    action = phase_result['action']
    reasons = phase_result['reasons']
    
    # Tier mapping para Matrix (semanas)
    if phase == 'ACUMULACAO':
        tier = 'S' if score >= 9 else 'A' if score >= 7 else 'B'
    elif phase == 'MANIPULACAO':
        tier = 'A' if score >= 8 else 'B' if score >= 6 else 'C'
    elif phase == 'DISTRIBUICAO':
        tier = 'D'
    else:  # CHOP
        tier = 'C' if score > 0 else 'D'
    
    # Macro filter (HTF bear reduce score)
    if htf_trend == 'BAIXA' and phase == 'ACUMULACAO':
        reasons.append('⚠ Macro BAIXA — reduce conviction')
        score = max(score - 2, 0)
    
    return {
        'phase': phase,
        'score': score,
        'tier': tier,
        'action': action,
        'reasons': reasons,
    }
