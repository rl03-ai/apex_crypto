"""Swing Detector — para holds 3-14 dias (curto) ou 1-4 semanas (médio).

Tri-TF analysis (1h + 4h + 1d):
  - 1h: timing fino de entry
  - 4h: setup principal
  - 1d: filtro macro (não comprar contra trend dominante)

Setups detectados:
  - BREAKOUT: squeeze release + vol burst
  - PULLBACK: preço corrigiu até MA21/MA50 em trend
  - MOMENTUM: RSI cross 50 + MACD bull crossover
  - REVERSAL: RSI extremo + bounce candle
  - EXHAUSTION: overbought/oversold sem suporte → AVOID

Score range: -10 a +10 (consistente com matriz invest)
"""
import logging
from typing import Literal

log = logging.getLogger(__name__)

SwingStage = Literal['BREAKOUT', 'PULLBACK', 'MOMENTUM', 'REVERSAL',
                     'EXHAUSTION', 'NO_SETUP', 'BEARISH']

SwingMode = Literal['short', 'medium']


def _classify_swing(
    primary: dict,       # 4h (curto) ou 1d (médio) — main setup TF
    fast: dict,          # 1h — timing
    macro: dict,         # 1d (curto) ou 1w (médio) — macro filter
    mode: SwingMode = 'short',
    whale: dict | None = None,
) -> tuple[SwingStage, int, list[str]]:
    """Classifica swing setup com tri-TF gatekeeping."""
    reasons = []
    
    # Inputs primary (setup TF)
    p_rsi = primary.get('rsi') or 50
    p_struct_bias = primary.get('struct_bias', 0)
    p_squeeze = primary.get('squeeze', False)
    p_squeeze_release = primary.get('squeeze_release', False)
    p_vol_burst = primary.get('vol_burst', False)
    p_pullback_ma21 = primary.get('pullback_ma21_bull', False)
    p_macd_bull = primary.get('macd_bullish', False)
    p_aligned_bull = primary.get('aligned_bull', False)
    p_aligned_bear = primary.get('aligned_bear', False)
    p_atr_pct = primary.get('atr_pct', 3)
    p_ext_above_ma200 = primary.get('ext_above_ma200_pct', 0)
    p_dist_ma21 = primary.get('dist_ma21_pct', 0)
    p_structure = primary.get('structure', {})
    p_last_event = p_structure.get('last_event', 'none')
    p_choch_bull = p_structure.get('choch_bull', False)
    p_bos_bull = p_structure.get('bos_bull', False)
    
    # Inputs fast (1h)
    f_rsi = (fast.get('rsi') or 50) if fast else 50
    f_struct_bias = fast.get('struct_bias', 0) if fast else 0
    f_aligned_bull = fast.get('aligned_bull', False) if fast else False
    
    # Inputs macro (1d ou 1w)
    m_htf_trend = macro.get('htf_trend', 'LATERAL') if macro else 'LATERAL'
    m_struct_bias = macro.get('struct_bias', 0) if macro else 0
    m_ext = macro.get('ext_above_ma200_pct', 0) if macro else 0
    
    # Whale (opcional, peso baixo em swing)
    whale_score = whale.get('score', 0) if whale else 0
    whale_funding = whale.get('funding', 0) if whale else 0
    
    # ════════════════════════════════════════════════════════════════════════
    # GATEKEEPING #1: Estrutura primary bearish → NUNCA bullish setup
    # ════════════════════════════════════════════════════════════════════════
    
    primary_struct_bear = p_struct_bias == -1 or p_last_event in ('choch_bear', 'bos_bear')
    
    if primary_struct_bear and not (p_rsi < 30 and p_choch_bull):
        reasons.append(f'⛔ Estrutura primary bearish ({p_last_event})')
        score = -6
        if m_htf_trend == 'BAIXA':
            reasons.append('Macro trend confirma BAIXA')
            score = -8
        return 'BEARISH', score, reasons
    
    # ════════════════════════════════════════════════════════════════════════
    # GATEKEEPING #2: Macro hostile (TREND BAIXA forte) → BEARISH
    # Em swing, podemos comprar contra macro se setup curto for forte,
    # MAS só se macro não for fortemente bear
    # ════════════════════════════════════════════════════════════════════════
    
    if m_htf_trend == 'BAIXA' and m_struct_bias == -1 and mode == 'medium':
        # Modo médio: macro bear é filtro forte
        reasons.append('Macro trend BAIXA + estrutura bear (modo médio rejeita)')
        return 'BEARISH', -5, reasons
    
    # ════════════════════════════════════════════════════════════════════════
    # GATEKEEPING #3: EXHAUSTION (multi-flag confluence)
    # 
    # Princípio: nenhum indicador isolado flagra exhaustion.
    # Precisamos de CONVERGÊNCIA de sinais para evitar falsos positivos.
    #
    # Flags possíveis (mode-aware thresholds):
    #   - Extension: m_ext acima do threshold
    #   - RSI overbought
    #   - Funding overheated (whale)
    #   - Vol blow-off (price_change_7d alto)
    #
    # Triggers:
    #   - 1 flag CRÍTICA (extreme) → EXHAUSTION
    #   - 2+ flags moderadas convergentes → EXHAUSTION
    # ════════════════════════════════════════════════════════════════════════
    
    # Mode-aware thresholds (medium mais conservador porque holds longos)
    if mode == 'medium':
        ext_critical = 60      # absolute critical
        ext_moderate = 35      # contributes to multi-flag
        rsi_critical = 80
        rsi_moderate = 72
        change_critical = 35
        change_moderate = 22
    else:  # short
        ext_critical = 70
        ext_moderate = 45
        rsi_critical = 82
        rsi_moderate = 75
        change_critical = 40
        change_moderate = 25
    
    price_change_7d = primary.get('price_change_7d_pct', 0)
    
    # Critical flags: qualquer uma sozinha → EXHAUSTION
    critical_flags = []
    if m_ext > ext_critical:
        critical_flags.append(f'Macro {m_ext:.0f}% above MA200 (critical)')
    if p_rsi > rsi_critical:
        critical_flags.append(f'RSI {p_rsi:.0f} (critical overbought)')
    if price_change_7d > change_critical:
        critical_flags.append(f'Vol blow-off +{price_change_7d:.0f}% 7d')
    
    if critical_flags:
        reasons.extend(critical_flags)
        reasons.append('⛔ EXHAUSTION: critical extension')
        return 'EXHAUSTION', -5, reasons
    
    # Moderate flags: precisa 2+ para flagar
    moderate_flags = []
    if m_ext > ext_moderate:
        moderate_flags.append(f'Macro {m_ext:.0f}% above MA200')
    if p_rsi > rsi_moderate:
        moderate_flags.append(f'RSI {p_rsi:.0f} elevated')
    if whale_funding > 0.04:
        moderate_flags.append(f'Funding overheated ({whale_funding:.3f}%)')
    if price_change_7d > change_moderate:
        moderate_flags.append(f'+{price_change_7d:.0f}% in 7d')
    
    # RSI > 78 sem pullback é flag standalone (mantém tua lógica original)
    if p_rsi > 78 and not p_pullback_ma21:
        moderate_flags.append(f'RSI {p_rsi:.0f} overbought sem pullback')
    
    if len(moderate_flags) >= 2:
        reasons.extend(moderate_flags)
        reasons.append('⚠ EXHAUSTION: multi-flag confluence')
        score = -3 if mode == 'short' else -4
        return 'EXHAUSTION', score, reasons
    
    # ════════════════════════════════════════════════════════════════════════
    # SETUP #1: BREAKOUT (squeeze release + vol burst)
    # Highest probability swing setup
    # ════════════════════════════════════════════════════════════════════════
    
    structure_supports = (
        p_struct_bias == 1
        or p_last_event in ('choch_bull', 'bos_bull')
        or p_choch_bull
        or p_bos_bull
    )
    
    if p_squeeze_release and p_vol_burst and structure_supports:
        reasons.append('💥 Squeeze breakout + volume burst')
        if p_choch_bull:
            reasons.append('CHoCH bullish confirma reversal')
        if p_bos_bull:
            reasons.append('BOS bull confirma continuation')
        score = 8
        if m_htf_trend == 'ALTA':
            reasons.append('Macro alinhado bull')
            score = 10
        elif m_htf_trend == 'BAIXA':
            reasons.append('⚠ Macro bear — counter-trend setup')
            score = 5
        if f_aligned_bull:
            reasons.append('1h confirma alignment')
            score = min(10, score + 1)
        return 'BREAKOUT', score, reasons
    
    # ════════════════════════════════════════════════════════════════════════
    # SETUP #2: PULLBACK em trend (entry em MA21/MA50)
    # ════════════════════════════════════════════════════════════════════════
    
    if p_pullback_ma21 and p_aligned_bull and p_rsi < 60:
        reasons.append(f'Pullback to MA21 in trend (dist {p_dist_ma21:.1f}%)')
        if p_macd_bull:
            reasons.append('MACD ainda bullish')
        score = 7
        if structure_supports:
            reasons.append(f'Estrutura: {p_last_event}')
            score = 9
        if m_htf_trend == 'ALTA':
            reasons.append('Macro bull confirma')
            score = min(10, score + 1)
        return 'PULLBACK', score, reasons
    
    # ════════════════════════════════════════════════════════════════════════
    # SETUP #3: MOMENTUM (RSI cross 50 + MACD bull)
    # Início de movimento, mais arriscado
    # ════════════════════════════════════════════════════════════════════════
    
    momentum_kicker = (
        50 < p_rsi < 65         # RSI cross em zona neutra
        and p_macd_bull
        and not primary_struct_bear
        and structure_supports
    )
    
    if momentum_kicker:
        reasons.append(f'Momentum: RSI {p_rsi:.0f} + MACD bull')
        if structure_supports:
            reasons.append(f'Estrutura: {p_last_event}')
        score = 5
        if m_htf_trend == 'ALTA' and structure_supports:
            reasons.append('Macro bull + estrutura confirma')
            score = 7
        if f_aligned_bull:
            score = min(10, score + 1)
        if whale_score > 2:
            reasons.append(f'Whale supporting (+{whale_score})')
            score = min(10, score + 1)
        return 'MOMENTUM', score, reasons
    
    # ════════════════════════════════════════════════════════════════════════
    # SETUP #4: REVERSAL (RSI extremo + bounce setup)
    # ════════════════════════════════════════════════════════════════════════
    
    oversold_reversal = (
        p_rsi < 30                   # oversold
        and not primary_struct_bear  # estrutura não destruída
        and m_htf_trend != 'BAIXA'   # macro não bearish forte
    )
    
    if oversold_reversal:
        reasons.append(f'Oversold reversal: RSI {p_rsi:.0f}')
        if p_choch_bull:
            reasons.append('CHoCH bull confirma reversal')
            score = 7
        else:
            reasons.append('⚠ Sem CHoCH ainda — entry especulativo')
            score = 3
        return 'REVERSAL', score, reasons
    
    # ════════════════════════════════════════════════════════════════════════
    # FALLBACK: NO SETUP — sem trade claro
    # ════════════════════════════════════════════════════════════════════════
    
    reasons.append('Sem setup swing claro')
    score = 0
    if p_rsi < 35 and structure_supports:
        reasons.append(f'RSI baixo ({p_rsi:.0f}) — possível early reversal mas sem trigger')
        score = 1
    if m_htf_trend == 'ALTA':
        reasons.append('Macro bull mas faltam triggers swing')
        score = max(score, 1)
    return 'NO_SETUP', score, reasons


def _swing_action(stage: SwingStage, score: int) -> str:
    if stage == 'BREAKOUT' and score >= 8:
        return 'STRONG BUY'
    if stage == 'PULLBACK' and score >= 8:
        return 'STRONG BUY'
    if stage in ('BREAKOUT', 'PULLBACK', 'MOMENTUM', 'REVERSAL') and score >= 5:
        return 'BUY'
    if stage in ('BREAKOUT', 'PULLBACK', 'MOMENTUM', 'REVERSAL'):
        return 'WATCH'
    if stage == 'EXHAUSTION':
        return 'AVOID'
    if stage == 'BEARISH':
        return 'AVOID'
    return 'WATCH'


def _swing_tier(stage: SwingStage, score: int) -> str:
    if stage in ('BREAKOUT', 'PULLBACK') and score >= 9:
        return 'S'
    if stage in ('BREAKOUT', 'PULLBACK', 'MOMENTUM') and score >= 7:
        return 'A'
    if stage in ('BREAKOUT', 'PULLBACK', 'MOMENTUM', 'REVERSAL') and score >= 5:
        return 'B'
    if stage in ('BREAKOUT', 'PULLBACK', 'MOMENTUM', 'REVERSAL'):
        return 'C'
    return 'D'


def detect_swing(
    primary: dict,
    fast: dict | None = None,
    macro: dict | None = None,
    mode: SwingMode = 'short',
    whale: dict | None = None,
) -> dict:
    """Main entry point — detecta swing setup com tri-TF analysis.
    
    Args:
        primary: 4h (mode=short) ou 1d (mode=medium) — setup principal
        fast: 1h — timing fino (opcional)
        macro: 1d (mode=short) ou 1w (mode=medium) — filtro macro (opcional)
        mode: 'short' (3-14d) ou 'medium' (1-4 semanas)
        whale: whale data (opcional, peso baixo em swing)
    
    Returns:
        {
            'stage': 'BREAKOUT' | 'PULLBACK' | ...,
            'mode': 'short' | 'medium',
            'score': int (-10 a +10),
            'tier': 'S' | 'A' | 'B' | 'C' | 'D',
            'action': 'STRONG BUY' | 'BUY' | 'WATCH' | 'AVOID',
            'reasons': [...],
        }
    """
    if not primary:
        return {
            'stage': 'NO_SETUP',
            'mode': mode,
            'score': 0,
            'tier': 'D',
            'action': 'WATCH',
            'reasons': ['No primary TF data'],
        }
    
    # Macro: se não fornecido, usa primary como fallback
    if not macro:
        macro = {}
    
    stage, score, reasons = _classify_swing(primary, fast or {}, macro, mode, whale)
    score = max(-10, min(10, score))
    
    return {
        'stage': stage,
        'stage_label': stage.replace('_', ' ').title(),
        'mode': mode,
        'score': score,
        'tier': _swing_tier(stage, score),
        'action': _swing_action(stage, score),
        'reasons': reasons,
    }
