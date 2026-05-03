"""Swing Detector — Market phases com thresholds mais flexíveis para 3-14d.

ACUMULAÇÃO: Pullback em trend (entry)
MANIPULAÇÃO: Acceleration fase (riding)
DISTRIBUIÇÃO: Exhaustion (exit)
CHOP: Sem rumo (wait)

Diferente de Matrix porque:
- Thresholds mais agressivos (RSI>55 já pode ser MANIP vs >60 em Matrix)
- Volume less critical (mais movement-driven)
- Shorter timeframes
"""
import logging
from app.services.market_phase_detector import detect_phase

log = logging.getLogger(__name__)


def detect_swing(
    rsi: float,
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
    pullback_ma21: bool = False,
    vol_burst: bool = False,
) -> dict:
    """Detect market phase para Swing (3-14 dias).
    
    Usa market_phase_detector com tweaks para swing timeframe.
    """
    structure = structure or {}
    last_event = structure.get('last_event', 'none')
    
    # Swing é mais flexible: struct_bias >= 0 é OK
    # Vol burst é squeeze_release OU volume muito alto
    _vol_burst = vol_burst or squeeze_release or (atr_pct > 3.5 and change_24h_pct > 2)
    
    # Usa detector unificado
    phase_result = detect_phase(
        rsi=rsi,
        struct_bias=struct_bias,
        last_event=last_event,
        vol_burst=_vol_burst,
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
    
    # Tier mapping para Swing (dias) — mais agressivo que Matrix
    if phase == 'ACUMULACAO':
        tier = 'S' if score >= 8 else 'A' if score >= 6 else 'B'
    elif phase == 'MANIPULACAO':
        tier = 'S' if score >= 8 else 'A' if score >= 6 else 'B'
    elif phase == 'DISTRIBUICAO':
        tier = 'D'
    else:  # CHOP
        tier = 'C' if score > 0 else 'D'
    
    # HTF filter (swing checks 4h/1d macro)
    if htf_trend == 'BAIXA' and phase == 'ACUMULACAO':
        reasons.append('⚠ Macro bear — pullback only')
        # Não reduz score em ACCUM de swing, só avisa
    
    return {
        'phase': phase,
        'score': score,
        'tier': tier,
        'action': action,
        'reasons': reasons,
    }
