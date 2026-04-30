"""Swing Detector — phase-aware, compatible with swing_matrix/frontend."""
from __future__ import annotations

from typing import Literal

SwingStage = Literal['BREAKOUT', 'PULLBACK', 'MOMENTUM', 'REVERSAL', 'EXHAUSTION', 'BEARISH', 'NO_SETUP']
SwingMode = Literal['short', 'medium']
SwingPhase = Literal['TREND', 'REVERSAL_UP', 'DISTRIBUTION', 'REVERSAL_DOWN', 'RANGE']


def _tier(score: int) -> str:
    if score >= 8:
        return 'S'
    if score >= 6:
        return 'A'
    if score >= 4:
        return 'B'
    if score >= 2:
        return 'C'
    return 'D'


def _action(stage: SwingStage, score: int, blocked: bool = False) -> str:
    if blocked or stage in ('EXHAUSTION', 'BEARISH'):
        return 'AVOID'
    if stage in ('BREAKOUT', 'REVERSAL') and score >= 7:
        return 'STRONG BUY'
    if stage in ('BREAKOUT', 'PULLBACK', 'MOMENTUM', 'REVERSAL') and score >= 4:
        return 'BUY'
    if stage in ('BREAKOUT', 'PULLBACK', 'MOMENTUM', 'REVERSAL') and score >= 2:
        return 'WATCH'
    return 'WATCH'


def _detect_phase(p_rsi: float, p_struct_bias: int, p_last_event: str, bars_since_event: int) -> SwingPhase:
    if p_struct_bias == 1 and p_last_event in ('bos_bull', 'choch_bull') and bars_since_event < 12 and 42 < p_rsi < 68:
        return 'TREND'
    if p_rsi < 35 and p_last_event == 'choch_bull' and bars_since_event < 8:
        return 'REVERSAL_UP'
    if p_rsi > 72 and p_last_event in ('choch_bear', 'bos_bear'):
        return 'REVERSAL_DOWN'
    if p_struct_bias == 1 and p_rsi > 68:
        return 'DISTRIBUTION'
    return 'RANGE'


def detect_swing(
    primary: dict,
    fast: dict | None = None,
    macro: dict | None = None,
    mode: SwingMode = 'short',
    whale: dict | None = None,
    prev: dict | None = None,
) -> dict:
    """Detecta setup swing e devolve o formato esperado pela API/frontend.

    A fase influencia o score, mas não substitui os setups base.
    Mantém thresholds menos restritivos para voltar a mostrar sinais.
    """
    prev = prev or {}
    fast = fast or {}
    macro = macro or {}

    p_rsi = primary.get('rsi') or 50
    p_adx = primary.get('adx') or 0
    p_struct_bias = prev.get('p_struct_bias', primary.get('struct_bias', 0))
    p_atr_pct = primary.get('atr_pct') or 0
    p_squeeze_release = bool(primary.get('squeeze_release', False))
    p_squeeze = bool(primary.get('squeeze', False))
    p_macd_bull = bool(primary.get('macd_bullish', False))
    p_aligned_bull = bool(primary.get('aligned_bull', False))
    p_ltf_trend = primary.get('ltf_trend', 'LATERAL')

    structure = primary.get('structure') or {}
    p_choch_bull = bool(structure.get('choch_bull', False))
    p_choch_bear = bool(structure.get('choch_bear', False))
    p_bos_bull = bool(structure.get('bos_bull', False))
    p_bos_bear = bool(structure.get('bos_bear', False))
    p_last_event = prev.get('p_last_event', structure.get('last_event', 'none'))
    bars_since_event = int(prev.get('bars_since_event', 999))

    if p_choch_bull:
        p_last_event = 'choch_bull'
        p_struct_bias = 1
        bars_since_event = 0
    elif p_choch_bear:
        p_last_event = 'choch_bear'
        p_struct_bias = -1
        bars_since_event = 0
    elif p_bos_bull:
        p_last_event = 'bos_bull'
        p_struct_bias = 1
        bars_since_event = 0
    elif p_bos_bear:
        p_last_event = 'bos_bear'
        p_struct_bias = -1
        bars_since_event = 0
    else:
        bars_since_event += 1

    f_struct_bias = fast.get('struct_bias', 0)
    f_aligned_bull = bool(fast.get('aligned_bull', False))
    f_macd_bull = bool(fast.get('macd_bullish', False))
    f_structure = fast.get('structure') or {}
    f_choch_bull = bool(f_structure.get('choch_bull', False) or fast.get('choch_bull', False))

    htf_trend = macro.get('htf_trend', 'LATERAL')
    m_struct_bias = macro.get('struct_bias', 0)
    m_ext = macro.get('ext_above_ma200_pct') or 0

    phase = _detect_phase(p_rsi, p_struct_bias, p_last_event, bars_since_event)

    reasons: list[str] = [f'Phase swing: {phase}']
    blocked = False
    if htf_trend == 'BAIXA' and m_struct_bias == -1:
        blocked = True
        reasons.append('Macro bearish')
    if phase in ('DISTRIBUTION', 'REVERSAL_DOWN') and m_ext > 25:
        blocked = True
        reasons.append('Extensão elevada em fase perigosa')

    structure_supports = p_struct_bias == 1 and p_last_event in ('choch_bull', 'bos_bull') and bars_since_event < 14
    fast_supports = f_struct_bias >= 0 and (f_aligned_bull or f_macd_bull or f_choch_bull)

    stage: SwingStage = 'NO_SETUP'
    base_score = 0

    if p_struct_bias == -1 and htf_trend == 'BAIXA':
        stage = 'BEARISH'
        base_score = -4
        reasons.append('Estrutura primary + macro bearish')
    elif p_rsi > 78 or (phase == 'DISTRIBUTION' and m_ext > 35):
        stage = 'EXHAUSTION'
        base_score = -3
        reasons.append('Exhaustion/overextension')
    elif p_squeeze_release and structure_supports and (p_macd_bull or f_macd_bull):
        stage = 'BREAKOUT'
        base_score = 5
        reasons.append('Squeeze release + estrutura bull')
    elif structure_supports and 38 <= p_rsi <= 56 and (p_aligned_bull or fast_supports):
        stage = 'PULLBACK'
        base_score = 4
        reasons.append('Pullback em estrutura bull')
    elif structure_supports and 50 <= p_rsi <= 70 and (p_macd_bull or p_aligned_bull):
        stage = 'MOMENTUM'
        base_score = 4
        reasons.append('Momentum bull saudável')
    elif phase == 'REVERSAL_UP' or (p_choch_bull and p_rsi < 45):
        stage = 'REVERSAL'
        base_score = 4
        reasons.append('Reversal up / CHoCH bull')
    elif structure_supports:
        stage = 'MOMENTUM'
        base_score = 2
        reasons.append('Estrutura bull, mas faltam confirmações')
    else:
        soft_score = 0
        if p_struct_bias == 1 or p_last_event in ('choch_bull', 'bos_bull'):
            soft_score += 1
            reasons.append('Soft: estrutura nao bearish/bullish')
        if p_macd_bull:
            soft_score += 1
            reasons.append('Soft: MACD bull')
        if p_aligned_bull:
            soft_score += 1
            reasons.append('Soft: medias alinhadas')
        if fast_supports:
            soft_score += 1
            reasons.append('Soft: fast TF neutro/positivo')
        if htf_trend == 'ALTA' or m_struct_bias >= 0:
            soft_score += 1
            reasons.append('Soft: macro nao hostil')
        if 38 <= p_rsi <= 65:
            soft_score += 1
            reasons.append('Soft: RSI saudavel')
        if p_squeeze or p_squeeze_release:
            soft_score += 1
            reasons.append('Soft: compressao/squeeze')

        if soft_score >= 4 and phase not in ('DISTRIBUTION', 'REVERSAL_DOWN'):
            stage = 'MOMENTUM'
            base_score = 3
            reasons.append('Setup swing suave por confluencia')
        elif soft_score >= 2 and phase not in ('REVERSAL_DOWN',):
            stage = 'NO_SETUP'
            base_score = 1
            reasons.append('Watchlist swing por confluencia parcial')
        else:
            reasons.append('Sem setup swing claro')

    if p_atr_pct and p_atr_pct < 0.6 and base_score > 0:
        base_score = max(1, base_score - 1)
        reasons.append('ATR baixo: score reduzido')

    phase_weights = {
        'TREND': {'trend': 2, 'reversal': 0, 'trigger': 1, 'penalty': 0},
        'REVERSAL_UP': {'trend': 0, 'reversal': 2, 'trigger': 1, 'penalty': 0},
        'RANGE': {'trend': 0, 'reversal': 1, 'trigger': 1, 'penalty': 0},
        'DISTRIBUTION': {'trend': -1, 'reversal': 0, 'trigger': 0, 'penalty': -1},
        'REVERSAL_DOWN': {'trend': -2, 'reversal': -1, 'trigger': 0, 'penalty': -2},
    }
    weights = phase_weights.get(phase, phase_weights['RANGE'])
    score = base_score

    if stage in ('BREAKOUT', 'PULLBACK', 'MOMENTUM'):
        score += weights['trend']
    if stage == 'REVERSAL':
        score += weights['reversal']
    if f_choch_bull or p_bos_bull or p_squeeze_release:
        score += weights['trigger']
    score += weights['penalty']

    if htf_trend == 'ALTA':
        score += 1
        reasons.append('Macro ALTA')
    if fast_supports and stage not in ('NO_SETUP', 'BEARISH', 'EXHAUSTION'):
        score += 1
        reasons.append('Fast TF confirma')
    if whale and (whale.get('score') or 0) > 0 and stage not in ('NO_SETUP', 'BEARISH', 'EXHAUSTION'):
        score += 1
        reasons.append('Whale/funding favorável')

    if mode == 'medium' and stage in ('BREAKOUT', 'MOMENTUM') and htf_trend != 'BAIXA':
        score += 1

    score = max(-10, min(10, int(score)))
    tier = _tier(score)
    action = _action(stage, score, blocked=blocked)

    return {
        'stage': stage,
        'stage_label': stage.replace('_', ' ').title(),
        'mode': mode,
        'score': score,
        'phase': phase,
        'tier': tier,
        'action': action,
        'signal': 'BUY' if action in ('STRONG BUY', 'BUY') else ('WEAK_BUY' if action == 'WATCH' and score >= 2 else 'NEUTRAL'),
        'reasons': reasons,
        'p_struct_bias': p_struct_bias,
        'p_last_event': p_last_event,
        'bars_since_event': bars_since_event,
    }
