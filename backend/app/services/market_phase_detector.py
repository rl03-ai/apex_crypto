"""Market Phase Detector — Unified stage detection (ACUMULAÇÃO, MANIPULAÇÃO, DISTRIBUIÇÃO).

Princípio: Market moves em 3 fases previsíveis:

1. ACUMULAÇÃO (Accumulation)
   - Insiders compram, suporte marcado
   - Low volume, lateral movement
   - Struct bull (CHoCH/BOS recente)
   - RSI 40-60, acima de MA21
   
2. MANIPULAÇÃO (Markup)
   - Pump coordenado, aceleração
   - Volume burst, distância de MA cresce
   - RSI 60-80, MACD bull
   - Struct mantém bull
   
3. DISTRIBUIÇÃO (Distribution)
   - Insiders saem, estrutura falha
   - Exhaustion (RSI>80, vol blow-off)
   - CHoCH bear, falha de suporte
   - Timing para sair
   
Scores: -10 a +10
  ACCUM:  +7 a +10 (buy zone)
  MANIP:  +4 a +7 (riding zone)
  DIST:   -5 a -10 (avoid/exit zone)
  CHOP:   -2 a +2 (wait zone)
"""
import logging
from typing import Literal

log = logging.getLogger(__name__)

MarketPhase = Literal['ACUMULACAO', 'MANIPULACAO', 'DISTRIBUICAO', 'CHOP']


def _classify_phase(
    rsi: float,
    struct_bias: int,
    last_event: str,
    vol_burst: bool,
    squeeze_release: bool,
    macd_bullish: bool,
    aligned_bull: bool,
    above_vwap: bool,
    dist_ma21_pct: float,
    atr_pct: float,
    change_24h_pct: float,
    price_change_7d_pct: float,
) -> tuple[MarketPhase, int, list[str]]:
    """Classifica mercado em fase de market.
    
    Args baseados no primary TF (1d para invest, 4h/1h para swing).
    """
    reasons = []
    score = 0
    
    # ════════════════════════════════════════════════════════════════════════
    # GATEKEEPING: Estrutura destruída → DISTRIBUIÇÃO
    # ════════════════════════════════════════════════════════════════════════
    
    if struct_bias == -1 or last_event in ('choch_bear', 'bos_bear'):
        reasons.append(f'⛔ Estrutura bear ({last_event})')
        return 'DISTRIBUICAO', -8, reasons
    
    # ════════════════════════════════════════════════════════════════════════
    # DISTRIBUIÇÃO: Exhaustion patterns
    # ════════════════════════════════════════════════════════════════════════
    
    exhaustion_flags = 0
    if rsi > 78:
        exhaustion_flags += 1
        reasons.append(f'RSI {rsi:.0f} (extremo)')
    if atr_pct > 7 or abs(change_24h_pct) > 15:
        exhaustion_flags += 1
        reasons.append(f'Vol spike (ATR {atr_pct:.1f}%, Δ24h {change_24h_pct:.1f}%)')
    if abs(price_change_7d_pct) > 25:
        exhaustion_flags += 1
        reasons.append(f'Blow-off move (+{price_change_7d_pct:.0f}% em 7d)')
    if dist_ma21_pct > 8:
        exhaustion_flags += 1
        reasons.append(f'{dist_ma21_pct:.1f}% above MA21 (extended)')
    
    if exhaustion_flags >= 2:
        reasons.append('⚠️ DISTRIBUIÇÃO: Multi-flag exhaustion')
        return 'DISTRIBUICAO', -6, reasons
    
    # ════════════════════════════════════════════════════════════════════════
    # MANIPULAÇÃO: Acceleration phase (vol burst + uptrend)
    # ════════════════════════════════════════════════════════════════════════
    
    if vol_burst and squeeze_release and macd_bullish and struct_bias >= 0:
        reasons.append('💥 MANIPULAÇÃO: Squeeze release + vol burst')
        if struct_bias == 1:
            reasons.append('Struct bull confirma')
        score = 8
        if aligned_bull:
            score = 9
            reasons.append('Multi-TF aligned')
        if above_vwap:
            reasons.append('Above VWAP')
        return 'MANIPULACAO', score, reasons
    
    if vol_burst and macd_bullish and aligned_bull and struct_bias == 1 and 60 < rsi < 80:
        reasons.append('📈 MANIPULAÇÃO: Volume acceleration em trend')
        score = 7
        if above_vwap:
            score = 8
        return 'MANIPULACAO', score, reasons
    
    # ════════════════════════════════════════════════════════════════════════
    # ACUMULAÇÃO: Quiet buying phase (suporte marcado, lateral)
    # ════════════════════════════════════════════════════════════════════════
    
    if struct_bias == 1 and (last_event in ('choch_bull', 'bos_bull') or struct_bias == 1):
        # Suporte recente marcado
        if 40 <= rsi <= 60 and not vol_burst and above_vwap:
            reasons.append('🟢 ACUMULAÇÃO: Suporte marcado, lateral bull')
            reasons.append(f'RSI {rsi:.0f} (neutra), struct bull')
            if squeeze_release:
                reasons.append('Squeeze release setup')
                score = 9
            elif macd_bullish:
                reasons.append('MACD ainda bull')
                score = 8
            else:
                score = 7
            return 'ACUMULACAO', score, reasons
        
        # Pullback em trend (early manipulation entry)
        if 30 <= rsi <= 50 and above_vwap and (last_event in ('choch_bull', 'bos_bull')):
            reasons.append('🔵 ACUMULAÇÃO: Pullback em trend')
            reasons.append(f'RSI {rsi:.0f}, struct {last_event}')
            if macd_bullish:
                reasons.append('MACD bullish')
                score = 8
            else:
                score = 6
            return 'ACUMULACAO', score, reasons
    
    # Oversold reversal (entrada de acumulação)
    if rsi < 35 and struct_bias >= 0 and (last_event in ('choch_bull', 'bos_bull')):
        reasons.append('🔄 ACUMULAÇÃO: Oversold + struct bull')
        reasons.append(f'RSI {rsi:.0f}, reversal zone')
        score = 5
        return 'ACUMULACAO', score, reasons
    
    # ════════════════════════════════════════════════════════════════════════
    # CHOP: Sem fase clara
    # ════════════════════════════════════════════════════════════════════════
    
    reasons.append('⚪ CHOP: Sem fase clara')
    if struct_bias == 1 and rsi < 70:
        reasons.append('Struct bull mas faltam triggers')
        score = 1
    return 'CHOP', score, reasons


def detect_phase(
    rsi: float,
    struct_bias: int = 0,
    last_event: str = 'none',
    vol_burst: bool = False,
    squeeze_release: bool = False,
    macd_bullish: bool = False,
    aligned_bull: bool = False,
    above_vwap: bool = False,
    dist_ma21_pct: float = 0,
    atr_pct: float = 1.5,
    change_24h_pct: float = 0,
    price_change_7d_pct: float = 0,
) -> dict:
    """Detect market phase (unified detector para Matrix, Swing, Fund Mode).
    
    Returns:
        {
            'phase': 'ACUMULACAO' | 'MANIPULACAO' | 'DISTRIBUICAO' | 'CHOP',
            'score': int (-10 a +10),
            'action': 'STRONG BUY' | 'BUY' | 'HOLD' | 'REDUCE' | 'AVOID',
            'tier': 'S' | 'A' | 'B' | 'C' | 'D',
            'reasons': [...]
        }
    """
    phase, score, reasons = _classify_phase(
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
    
    score = max(-10, min(10, score))
    
    # Determine action and tier
    if phase == 'ACUMULACAO':
        tier = 'S' if score >= 8 else 'A' if score >= 6 else 'B'
        action = 'STRONG BUY' if score >= 8 else 'BUY' if score >= 6 else 'HOLD'
    elif phase == 'MANIPULACAO':
        tier = 'S' if score >= 8 else 'A' if score >= 6 else 'B'
        action = 'STRONG BUY' if score >= 8 else 'BUY' if score >= 6 else 'HOLD'
    elif phase == 'DISTRIBUICAO':
        tier = 'D'
        action = 'AVOID'
    else:  # CHOP
        tier = 'C' if score >= 1 else 'D'
        action = 'HOLD' if score >= 1 else 'WAIT'
    
    return {
        'phase': phase,
        'score': score,
        'tier': tier,
        'action': action,
        'reasons': reasons,
    }
