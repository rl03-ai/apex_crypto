"""Stage Detector — para holds de semanas/meses.

Substitui composite anterior. Detecta em que fase macro está o ativo:
  ACCUMULATION → MARKUP EARLY → MARKUP MATURE → EXTENDED → DISTRIBUTION → MARKDOWN → ...

Para holds de semanas/meses, queremos entrar em ACCUMULATION ou MARKUP EARLY.
EXTENDED é um warning para evitar entradas.
"""
import logging
from typing import Literal

log = logging.getLogger(__name__)

Stage = Literal['ACCUMULATION', 'MARKUP_EARLY', 'MARKUP_MATURE', 'EXTENDED',
                'DISTRIBUTION', 'MARKDOWN', 'CHOP']


def _classify_stage(instdash: dict, whale: dict | None = None) -> tuple[Stage, int, list[str]]:
    """Classifica stage e devolve score raw + reasons.
    
    Score range: -10 a +10
    
    Returns:
        (stage, score, reasons)
    """
    reasons = []
    
    # Inputs
    rsi = instdash.get('rsi') or 50
    htf_trend = instdash.get('htf_trend', 'LATERAL')  # ALTA / BAIXA / LATERAL
    ltf_trend = instdash.get('ltf_trend', 'LATERAL')
    aligned_bull = instdash.get('aligned_bull', False)
    aligned_bear = instdash.get('aligned_bear', False)
    
    squeeze = instdash.get('squeeze', False)
    squeeze_release = instdash.get('squeeze_release', False)
    pullback_ma21 = instdash.get('pullback_ma21_bull', False)
    
    ext_above_ma200 = instdash.get('ext_above_ma200_pct', 0)
    dist_ma21 = instdash.get('dist_ma21_pct', 0)
    
    vol_burst = instdash.get('vol_burst', False)
    price_change_7d = instdash.get('price_change_7d_pct', 0)
    atr_pct = instdash.get('atr_pct', 3)
    
    above_vwap = instdash.get('above_vwap', False)
    
    # Whale signals
    whale_oi_7d = 0
    whale_funding = 0
    whale_score = 0
    if whale:
        whale_oi_7d = whale.get('oi_7d') or 0
        whale_funding = whale.get('funding') or 0
        whale_score = whale.get('score') or 0
    
    # ── Detect stages, ordem de prioridade ──────────────────────────────
    
    # 🔴 MARKDOWN — HTF bear
    if htf_trend == 'BAIXA' and aligned_bear:
        reasons.append('HTF bear trend confirmed')
        score = -7
        if rsi < 30:
            reasons.append(f'RSI oversold ({rsi:.0f}) — potential bounce')
            score = -5
        return 'MARKDOWN', score, reasons
    
    # 🟠 EXTENDED — esticado, evitar entradas
    extended_flags = []
    if ext_above_ma200 > 60:
        extended_flags.append(f'Preço {ext_above_ma200:.0f}% acima MA200d')
    if rsi > 75:
        extended_flags.append(f'RSI overbought ({rsi:.0f})')
    if whale_funding and whale_funding > 0.05:
        extended_flags.append(f'Funding overheated ({whale_funding:.3f}%)')
    if price_change_7d > 25:
        extended_flags.append(f'Vol blow-off (+{price_change_7d:.0f}% 7d)')
    if vol_burst and rsi > 70:
        extended_flags.append('Volume blow-off + RSI alto')
    
    if len(extended_flags) >= 2:
        reasons.extend(extended_flags)
        reasons.append('⚠ AVOID: setup esticado')
        score = -2 if htf_trend == 'ALTA' else -5
        return 'EXTENDED', score, reasons
    
    # 🟢 ACCUMULATION — silent accumulation
    is_chop = atr_pct < 4 and -10 <= price_change_7d <= 10
    silent_accum = squeeze and is_chop and abs(dist_ma21) < 5
    whale_quiet_buy = whale_oi_7d > 8 and atr_pct < 5 and abs(price_change_7d) < 8
    
    if silent_accum or whale_quiet_buy:
        reasons.append('Silent accumulation: vol comprimida, OI subindo')
        if squeeze:
            reasons.append('BB Squeeze active')
        if whale_oi_7d > 8:
            reasons.append(f'Whale OI 7d: +{whale_oi_7d:.1f}%')
        score = 8
        if htf_trend == 'ALTA':
            reasons.append('HTF bull trend confirms accumulation')
            score = 10
        return 'ACCUMULATION', score, reasons
    
    # 🔵 MARKUP EARLY — acabou breakout, ainda perto MA21
    early_breakout = squeeze_release and vol_burst
    early_pullback = pullback_ma21 and aligned_bull and rsi < 65
    
    if early_breakout or early_pullback:
        if early_breakout:
            reasons.append('Squeeze breakout + volume burst')
        if early_pullback:
            reasons.append('Pullback to MA21 in trend')
        if aligned_bull:
            reasons.append('LTF + HTF alignment bull')
        score = 7
        if whale_score > 2:
            reasons.append(f'Whale supporting (+{whale_score})')
            score = 9
        return 'MARKUP_EARLY', score, reasons
    
    # 🟡 MARKUP MATURE — em trend bull mas evoluído
    if htf_trend == 'ALTA' and ltf_trend == 'ALTA':
        reasons.append('HTF + LTF trend bull')
        score = 4
        # Penaliza se já está esticado
        if ext_above_ma200 > 30:
            reasons.append(f'Já {ext_above_ma200:.0f}% acima MA200d')
            score = 2
        if rsi > 65:
            reasons.append(f'RSI {rsi:.0f} — momentum forte')
        if whale_score > 0:
            score += 1
            reasons.append(f'Whale supporting (+{whale_score})')
        return 'MARKUP_MATURE', score, reasons
    
    # ⚪ CHOP — sem direcção clara
    reasons.append('Sem direcção HTF clara')
    score = 0
    if whale_oi_7d > 5:
        reasons.append(f'Whale acumulando lentamente (OI +{whale_oi_7d:.0f}% 7d)')
        score = 2
    if rsi < 40:
        reasons.append(f'RSI baixo ({rsi:.0f}) — oversold em chop')
        score += 1
    return 'CHOP', score, reasons


def _stage_action(stage: Stage, score: int) -> str:
    """Decide action baseada em stage + score."""
    if stage == 'ACCUMULATION' and score >= 7:
        return 'STRONG BUY'
    if stage == 'MARKUP_EARLY' and score >= 6:
        return 'STRONG BUY'
    if stage in ('ACCUMULATION', 'MARKUP_EARLY'):
        return 'BUY'
    if stage == 'MARKUP_MATURE' and score >= 3:
        return 'BUY'
    if stage == 'MARKUP_MATURE':
        return 'HOLD'
    if stage == 'EXTENDED':
        return 'AVOID'  # Special: not SELL, just don't enter
    if stage == 'MARKDOWN' and score <= -5:
        return 'AVOID'
    if stage == 'MARKDOWN':
        return 'WATCH'  # Wait for reversal
    return 'WATCH'


def _stage_tier(stage: Stage, score: int) -> str:
    """Tier S/A/B/C/D — agora baseado em conviction de stage."""
    if stage == 'ACCUMULATION' and score >= 9:
        return 'S'
    if stage in ('ACCUMULATION', 'MARKUP_EARLY') and score >= 7:
        return 'A'
    if stage in ('ACCUMULATION', 'MARKUP_EARLY'):
        return 'B'
    if stage == 'MARKUP_MATURE' and score >= 4:
        return 'B'
    if stage == 'MARKUP_MATURE':
        return 'C'
    if stage in ('EXTENDED', 'MARKDOWN', 'CHOP'):
        return 'D'
    return 'C'


def detect_stage(instdash: dict, whale: dict | None = None) -> dict:
    """Main entry point — detecta stage + score + tier + action.
    
    Args:
        instdash: output de analyse_symbol()
        whale: whale_score data (opcional)
    
    Returns:
        {
            'stage': 'ACCUMULATION',
            'score': 8,           # -10 a +10
            'tier': 'S',
            'action': 'STRONG BUY',
            'reasons': [...]
        }
    """
    stage, score, reasons = _classify_stage(instdash, whale)
    score = max(-10, min(10, score))
    
    return {
        'stage': stage,
        'stage_label': stage.replace('_', ' ').title(),
        'score': score,
        'tier': _stage_tier(stage, score),
        'action': _stage_action(stage, score),
        'reasons': reasons,
    }


def stage_emoji(stage: Stage) -> str:
    return {
        'ACCUMULATION': '🟢',
        'MARKUP_EARLY': '🔵',
        'MARKUP_MATURE': '🟡',
        'EXTENDED': '🟠',
        'DISTRIBUTION': '🟠',
        'MARKDOWN': '🔴',
        'CHOP': '⚪',
    }.get(stage, '⚪')
