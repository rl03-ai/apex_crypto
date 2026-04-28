"""Stage Detector v3 — STRICT structure gatekeeping.

Princípio: estrutura é PRIMEIRA — se Pine Script mostra estrutura bearish,
NENHUM stage bullish é permitido, independentemente de squeeze/RSI/whale.

Hierarquia de validação:
  1. struct_bias do analyser (CHoCH/BOS confirmados) — GATEKEEPER
  2. HTF trend (1w direction)
  3. LTF trend (1d direction)
  4. Indicadores (squeeze, RSI, etc.) — só refinam, não inverteam
"""
import logging
from typing import Literal

log = logging.getLogger(__name__)

Stage = Literal['ACCUMULATION', 'MARKUP_EARLY', 'MARKUP_MATURE', 'EXTENDED',
                'DISTRIBUTION', 'MARKDOWN', 'CHOP']


def _classify_stage(instdash: dict, whale: dict | None = None) -> tuple[Stage, int, list[str]]:
    """Classifica stage com STRICT structure gatekeeping.
    
    REGRA #1: struct_bias = -1 (bearish CHoCH/BOS recente) → MARKDOWN ou CHOP
              Nunca ACCUM/EARLY/MATURE com estrutura bearish
    
    REGRA #2: HTF trend = BAIXA → não permitir MARKUP_EARLY ou MARKUP_MATURE
    
    REGRA #3: LTF trend = BAIXA → não permitir MARKUP_EARLY (precisa LTF up)
    
    REGRA #4: ACCUMULATION só permitido se struct_bias >= 0 e HTF != BAIXA
    """
    reasons = []
    
    # Inputs
    rsi = instdash.get('rsi') or 50
    htf_trend = instdash.get('htf_trend', 'LATERAL')
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
    
    # ESTRUTURA — gatekeeper principal
    struct_bias = instdash.get('struct_bias', 0)  # 1=bull, -1=bear, 0=neutral
    structure = instdash.get('structure', {})
    last_event = structure.get('last_event', 'none')
    choch_bear_active = structure.get('choch_bear', False)
    bos_bear_active = structure.get('bos_bear', False)
    
    # Whale signals
    whale_oi_7d = 0
    whale_funding = 0
    whale_score = 0
    if whale:
        whale_oi_7d = whale.get('oi_7d') or 0
        whale_funding = whale.get('funding') or 0
        whale_score = whale.get('score') or 0
    
    # ════════════════════════════════════════════════════════════════════════
    # REGRA #1: STRUCTURE GATEKEEPER
    # Se estrutura é bearish (struct_bias=-1) OU CHoCH/BOS bear recente,
    # NUNCA permitir stages bullish. É MARKDOWN ou CHOP.
    # ════════════════════════════════════════════════════════════════════════
    
    structure_is_bearish = struct_bias == -1 or last_event in ('choch_bear', 'bos_bear')
    
    if structure_is_bearish:
        reasons.append(f'⛔ Estrutura bearish: {last_event} confirmado')
        if htf_trend == 'BAIXA':
            reasons.append('HTF trend bearish reforça')
            score = -7
            if rsi < 30:
                reasons.append(f'RSI oversold ({rsi:.0f}) — possível bounce mas estrutura ainda bear')
                score = -5
            return 'MARKDOWN', score, reasons
        else:
            # Estrutura bear mas HTF não confirma ainda → CHOP defensivo
            reasons.append('HTF não confirma bearish — chop defensivo')
            return 'CHOP', -2, reasons
    
    # ════════════════════════════════════════════════════════════════════════
    # REGRA #2: HTF GATEKEEPER (bear)
    # Se HTF é BAIXA, não permitir MARKUP. Pode ser MARKDOWN ou CHOP.
    # ════════════════════════════════════════════════════════════════════════
    
    if htf_trend == 'BAIXA':
        reasons.append('HTF trend = BAIXA')
        if aligned_bear or ltf_trend == 'BAIXA':
            reasons.append('LTF + HTF alignment bear')
            score = -6
            if rsi < 30:
                reasons.append(f'RSI oversold ({rsi:.0f})')
                score = -4
            return 'MARKDOWN', score, reasons
        else:
            # HTF bear mas LTF lateral/bull — bounce em downtrend
            reasons.append('LTF tenta bounce mas HTF dominante bear')
            return 'CHOP', -3, reasons
    
    # ════════════════════════════════════════════════════════════════════════
    # REGRA #3: EXTENDED check (esticado, evitar mesmo se trend up)
    # ════════════════════════════════════════════════════════════════════════
    
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
        score = -2
        return 'EXTENDED', score, reasons
    
    # ════════════════════════════════════════════════════════════════════════
    # REGRA #4: ACCUMULATION
    # Só permitido se: struct_bias >= 0 (não bear) e HTF != BAIXA
    # E vol comprimida + preço lateral
    # ════════════════════════════════════════════════════════════════════════
    
    is_chop = atr_pct < 4 and -10 <= price_change_7d <= 10
    silent_accum = squeeze and is_chop and abs(dist_ma21) < 5
    whale_quiet_buy = whale_oi_7d > 8 and atr_pct < 5 and abs(price_change_7d) < 8
    
    if (silent_accum or whale_quiet_buy) and struct_bias >= 0:
        reasons.append('Silent accumulation: vol comprimida, OI subindo')
        if squeeze:
            reasons.append('BB Squeeze active')
        if whale_oi_7d > 8:
            reasons.append(f'Whale OI 7d: +{whale_oi_7d:.1f}%')
        if struct_bias == 1:
            reasons.append('Estrutura bullish confirma')
            score = 10
        else:
            reasons.append('Estrutura neutra (sem CHoCH bull confirmado)')
            score = 7  # menor sem confirmação estrutural
        if htf_trend == 'ALTA':
            reasons.append('HTF bull trend')
        return 'ACCUMULATION', score, reasons
    
    # ════════════════════════════════════════════════════════════════════════
    # REGRA #5: MARKUP_EARLY
    # Requer: struct_bias = 1 OU last_event = choch_bull/bos_bull
    # E LTF trend ALTA
    # ════════════════════════════════════════════════════════════════════════
    
    structure_confirms_bull = struct_bias == 1 or last_event in ('choch_bull', 'bos_bull')
    
    early_breakout = squeeze_release and vol_burst and structure_confirms_bull
    early_pullback = pullback_ma21 and aligned_bull and rsi < 65 and structure_confirms_bull
    
    if early_breakout or early_pullback:
        if early_breakout:
            reasons.append('Squeeze breakout + volume burst')
        if early_pullback:
            reasons.append('Pullback to MA21 in trend')
        if structure_confirms_bull:
            reasons.append(f'Estrutura confirma: {last_event}')
        if aligned_bull:
            reasons.append('LTF + HTF alignment bull')
        score = 7
        if whale_score > 2:
            reasons.append(f'Whale supporting (+{whale_score})')
            score = 9
        return 'MARKUP_EARLY', score, reasons
    
    # ════════════════════════════════════════════════════════════════════════
    # REGRA #6: MARKUP_MATURE
    # HTF + LTF ambos ALTA, sem estrutura bear
    # ════════════════════════════════════════════════════════════════════════
    
    if htf_trend == 'ALTA' and ltf_trend == 'ALTA' and not structure_is_bearish:
        reasons.append('HTF + LTF trend bull')
        if structure_confirms_bull:
            reasons.append(f'Estrutura: {last_event}')
        score = 4
        if ext_above_ma200 > 30:
            reasons.append(f'Já {ext_above_ma200:.0f}% acima MA200d')
            score = 2
        if rsi > 65:
            reasons.append(f'RSI {rsi:.0f} — momentum forte')
        if whale_score > 0:
            score += 1
            reasons.append(f'Whale supporting (+{whale_score})')
        return 'MARKUP_MATURE', score, reasons
    
    # ════════════════════════════════════════════════════════════════════════
    # REGRA #7: CHOP — fallback
    # ════════════════════════════════════════════════════════════════════════
    
    reasons.append('Sem direcção HTF clara, sem estrutura confirmada')
    score = 0
    if whale_oi_7d > 5 and struct_bias >= 0:
        reasons.append(f'Whale acumulando lentamente (OI +{whale_oi_7d:.0f}% 7d)')
        score = 2
    if rsi < 40 and struct_bias >= 0:
        reasons.append(f'RSI baixo ({rsi:.0f}) — oversold em chop')
        score += 1
    return 'CHOP', score, reasons


def _stage_action(stage: Stage, score: int) -> str:
    """Action baseado em stage + score."""
    if stage == 'ACCUMULATION' and score >= 8:
        return 'STRONG BUY'
    if stage == 'MARKUP_EARLY' and score >= 7:
        return 'STRONG BUY'
    if stage in ('ACCUMULATION', 'MARKUP_EARLY'):
        return 'BUY'
    if stage == 'MARKUP_MATURE' and score >= 3:
        return 'BUY'
    if stage == 'MARKUP_MATURE':
        return 'HOLD'
    if stage == 'EXTENDED':
        return 'AVOID'
    if stage == 'MARKDOWN' and score <= -5:
        return 'AVOID'
    if stage == 'MARKDOWN':
        return 'WATCH'
    return 'WATCH'


def _stage_tier(stage: Stage, score: int) -> str:
    """Tier S/A/B/C/D."""
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
    return 'D'


def detect_stage(instdash: dict, whale: dict | None = None) -> dict:
    """Main entry — STRICT structure gatekeeping."""
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
