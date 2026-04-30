"""Intraday Detector — para holds 1h a 24h.

Tri-TF analysis:
  - Scalping mode: 5m + 15m + 1h
  - Day mode:      15m + 1h + 4h

Setups intraday:
  - 💥 ORB (Opening Range Breakout) — break do high/low das primeiras 1-2h
  - 🌊 VWAP Reclaim — preço reclama VWAP em trend
  - 🔵 Micro Pullback — RSI 30-50 em trend curto
  - 🎣 Liquidity Sweep — stops hunt + reversão imediata
  - 🎯 Squeeze Breakout — squeeze release em TF curto
  - 🟠 EXHAUSTION — esticado intraday
  - 🔴 BEARISH — estrutura/macro contra long

Score: -10 a +10 (consistente)
Overnight rule: só permitir hold > sessão se tier S/A
"""
import logging
from typing import Literal

log = logging.getLogger(__name__)

IntradayStage = Literal['TREND_BO', 'VWAP_RECLAIM', 'MICRO_PULLBACK',
                        'LIQ_SWEEP', 'SQUEEZE_BO', 'EXHAUSTION',
                        'BEARISH', 'NO_SETUP']

IntradayMode = Literal['scalping', 'day']


IntradayPhase = Literal['MOMENTUM_TREND', 'REVERSAL_UP', 'PULLBACK',
                        'DISTRIBUTION', 'EXHAUSTION', 'BEARISH', 'RANGE']


def _detect_intraday_phase(
    *, p_rsi: float, p_struct_bias: int, p_above_vwap: bool,
    p_pullback_ma21: bool, p_sweep_low: bool, p_choch_bull: bool,
    p_last_event: str, f_above_vwap: bool, f_macd_bull: bool,
    m_htf_trend: str, m_struct_bias: int, p_change_24h: float,
    whale_funding: float, p_dist_ma21: float,
) -> IntradayPhase:
    primary_bear = p_struct_bias == -1 or p_last_event in ('choch_bear', 'bos_bear')
    macro_bear = m_htf_trend == 'BAIXA' and m_struct_bias == -1

    if primary_bear and not (p_sweep_low and p_choch_bull):
        return 'BEARISH'
    if macro_bear:
        return 'BEARISH'
    if p_rsi > 80 or p_change_24h > 18:
        return 'EXHAUSTION'

    distribution_flags = 0
    if p_rsi > 73:
        distribution_flags += 1
    if p_change_24h > 12:
        distribution_flags += 1
    if whale_funding > 0.05:
        distribution_flags += 1
    if p_dist_ma21 > 6:
        distribution_flags += 1
    if distribution_flags >= 2:
        return 'DISTRIBUTION'

    structure_supports = p_struct_bias == 1 and p_last_event in ('choch_bull', 'bos_bull')
    if p_sweep_low and p_choch_bull:
        return 'REVERSAL_UP'
    if structure_supports and p_above_vwap and (f_above_vwap or f_macd_bull) and 45 <= p_rsi <= 70:
        return 'MOMENTUM_TREND'
    if structure_supports and p_pullback_ma21 and 30 <= p_rsi <= 55:
        return 'PULLBACK'
    return 'RANGE'


def _phase_adjust_intraday_score(
    stage: IntradayStage, base_score: int, phase: IntradayPhase, *,
    trigger: bool, mode: IntradayMode, reasons: list[str],
) -> int:
    trend_setups = {'SQUEEZE_BO', 'TREND_BO', 'VWAP_RECLAIM', 'MICRO_PULLBACK'}
    reversal_setups = {'LIQ_SWEEP'}
    phase_weights = {
        'MOMENTUM_TREND': {'trend': 2, 'reversal': 0, 'trigger': 1, 'penalty': 0},
        'REVERSAL_UP': {'trend': 0, 'reversal': 2, 'trigger': 1, 'penalty': 0},
        'PULLBACK': {'trend': 1, 'reversal': 1, 'trigger': 1, 'penalty': 0},
        'RANGE': {'trend': 0, 'reversal': 1, 'trigger': 1, 'penalty': 0},
        'DISTRIBUTION': {'trend': -2, 'reversal': 0, 'trigger': 0, 'penalty': -1},
        'EXHAUSTION': {'trend': -3, 'reversal': -1, 'trigger': 0, 'penalty': -2},
        'BEARISH': {'trend': -3, 'reversal': -1, 'trigger': 0, 'penalty': -2},
    }
    weights = phase_weights.get(phase, phase_weights['RANGE'])

    adjusted = base_score
    if stage in trend_setups:
        adjusted += weights['trend']
    if stage in reversal_setups:
        adjusted += weights['reversal']
    if trigger:
        adjusted += weights['trigger']
    adjusted += weights['penalty']

    # Scalping reage mais cedo; day mode fica ligeiramente mais seletivo.
    if mode == 'scalping' and phase in ('MOMENTUM_TREND', 'REVERSAL_UP', 'PULLBACK') and stage != 'NO_SETUP':
        adjusted += 1

    if adjusted != base_score:
        reasons.append(f'Phase score: {phase} ({base_score} → {adjusted})')

    return max(-10, min(10, adjusted))


def _classify_intraday(
    primary: dict,    # 5m (scalping) ou 15m (day) — entry timing
    fast: dict,       # 15m (scalping) ou 1h (day)
    macro: dict,      # 1h (scalping) ou 4h (day)
    mode: IntradayMode = 'day',
    whale: dict | None = None,
) -> tuple[IntradayStage, int, list[str], IntradayPhase]:
    """Classifica setup intraday com tri-TF gatekeeping."""
    reasons = []
    
    # Inputs primary (entry TF)
    p_rsi = primary.get('rsi') or 50
    p_struct_bias = primary.get('struct_bias', 0)
    p_squeeze = primary.get('squeeze', False)
    p_squeeze_release = primary.get('squeeze_release', False)
    p_vol_burst = primary.get('vol_burst', False)
    p_macd_bull = primary.get('macd_bullish', False)
    p_above_vwap = primary.get('above_vwap', False)
    p_atr_pct = primary.get('atr_pct', 1.5)
    p_vol_ratio = primary.get('vol_ratio', 1)
    p_dist_ma21 = primary.get('dist_ma21_pct', 0)
    p_pullback_ma21 = primary.get('pullback_ma21_bull', False)
    p_change_24h = primary.get('change_24h_pct', 0)
    p_structure = primary.get('structure', {})
    p_last_event = p_structure.get('last_event', 'none')
    p_choch_bull = p_structure.get('choch_bull', False)
    p_bos_bull = p_structure.get('bos_bull', False)
    
    # Liquidity sweep events (do structure module)
    p_sweep_high = (primary.get('liquidity') or {}).get('sweep_high', False)
    p_sweep_low = (primary.get('liquidity') or {}).get('sweep_low', False)
    
    # Inputs fast
    f_rsi = (fast.get('rsi') or 50) if fast else 50
    f_struct_bias = fast.get('struct_bias', 0) if fast else 0
    f_aligned_bull = fast.get('aligned_bull', False) if fast else False
    f_above_vwap = fast.get('above_vwap', False) if fast else False
    f_macd_bull = fast.get('macd_bullish', False) if fast else False
    
    # Inputs macro
    m_htf_trend = macro.get('htf_trend', 'LATERAL') if macro else 'LATERAL'
    m_struct_bias = macro.get('struct_bias', 0) if macro else 0
    m_above_vwap = macro.get('above_vwap', False) if macro else False
    
    # Whale (funding mais relevante em intraday)
    whale_score = whale.get('score', 0) if whale else 0
    whale_funding = whale.get('funding', 0) if whale else 0

    phase = _detect_intraday_phase(
        p_rsi=p_rsi,
        p_struct_bias=p_struct_bias,
        p_above_vwap=p_above_vwap,
        p_pullback_ma21=p_pullback_ma21,
        p_sweep_low=p_sweep_low,
        p_choch_bull=p_choch_bull,
        p_last_event=p_last_event,
        f_above_vwap=f_above_vwap,
        f_macd_bull=f_macd_bull,
        m_htf_trend=m_htf_trend,
        m_struct_bias=m_struct_bias,
        p_change_24h=p_change_24h,
        whale_funding=whale_funding,
        p_dist_ma21=p_dist_ma21,
    )
    reasons.append(f'Phase intraday: {phase}')
    
    # ════════════════════════════════════════════════════════════════════════
    # GATEKEEPING #1: Estrutura primary bearish → não bullish
    # Excepção: liquidity sweep low + reversal candle
    # ════════════════════════════════════════════════════════════════════════
    
    primary_struct_bear = p_struct_bias == -1 or p_last_event in ('choch_bear', 'bos_bear')
    
    intraday_penalty = 0
    if primary_struct_bear and not (p_sweep_low and p_choch_bull):
        reasons.append(f'Estrutura primary bearish ({p_last_event}): penalização')
        intraday_penalty -= 3
        if m_htf_trend == 'BAIXA':
            reasons.append('Macro confirma bear: penalização extra')
            intraday_penalty -= 2
    
    # ════════════════════════════════════════════════════════════════════════
    # GATEKEEPING #2: Macro hostile no day mode
    # Agora é penalização. Intraday deve conseguir gerar WATCH/READY em
    # reversões ou micro setups, mesmo se o macro ainda não virou.
    # ════════════════════════════════════════════════════════════════════════
    
    if mode == 'day' and m_htf_trend == 'BAIXA' and m_struct_bias == -1:
        reasons.append('Macro 4h bearish — penaliza, não rejeita')
        intraday_penalty -= 2
    
    # ════════════════════════════════════════════════════════════════════════
    # GATEKEEPING #3: EXHAUSTION (multi-flag intraday-specific)
    # ════════════════════════════════════════════════════════════════════════
    
    # Intraday usa thresholds mais tight (movimento já feito intra-dia)
    critical_flags = []
    if p_rsi > 80 and not p_pullback_ma21:
        critical_flags.append(f'RSI {p_rsi:.0f} extremo (intraday)')
    if p_change_24h > 18:
        critical_flags.append(f'+{p_change_24h:.0f}% 24h — vertical')
    
    if critical_flags:
        reasons.extend(critical_flags)
        reasons.append('EXHAUSTION intraday: penalização forte')
        intraday_penalty -= 4
    
    moderate_flags = []
    if p_rsi > 73:
        moderate_flags.append(f'RSI {p_rsi:.0f}')
    if p_change_24h > 12:
        moderate_flags.append(f'+{p_change_24h:.0f}% 24h')
    if whale_funding > 0.05:
        moderate_flags.append(f'Funding {whale_funding:.3f}%')
    if p_dist_ma21 > 6:
        moderate_flags.append(f'{p_dist_ma21:.1f}% above MA21')
    
    if len(moderate_flags) >= 2:
        reasons.extend(moderate_flags)
        reasons.append('Multi-flag exhaustion: penalização moderada')
        intraday_penalty -= 2
    
    # ════════════════════════════════════════════════════════════════════════
    # SETUP #1: LIQUIDITY SWEEP + REVERSAL (highest priority — high R)
    # ════════════════════════════════════════════════════════════════════════
    
    if p_sweep_low and p_choch_bull:
        reasons.append('🎣 Liquidity sweep low + CHoCH bull')
        if f_struct_bias >= 0:
            reasons.append('Fast TF não destrutiva')
        score = 8
        if m_htf_trend == 'ALTA':
            reasons.append('Macro bull confirma')
            score = 10
        elif m_htf_trend == 'BAIXA':
            reasons.append('⚠ Counter-trend macro')
            score = 6
        score = _phase_adjust_intraday_score('LIQ_SWEEP', score, phase, trigger=p_choch_bull, mode=mode, reasons=reasons)
        score = max(1, min(10, score + intraday_penalty))
        return 'LIQ_SWEEP', score, reasons, phase
    
    # ════════════════════════════════════════════════════════════════════════
    # SETUP #2: SQUEEZE BREAKOUT
    # ════════════════════════════════════════════════════════════════════════
    
    structure_supports = (p_struct_bias == 1 and (p_choch_bull or p_bos_bull))
    
    if p_squeeze_release and p_vol_burst and structure_supports:
        reasons.append('💥 Squeeze release + vol burst')
        if p_choch_bull:
            reasons.append('CHoCH bull')
        if p_bos_bull:
            reasons.append('BOS bull')
        score = 8
        if m_htf_trend == 'ALTA' and m_struct_bias >= 0:
            score = 10
            reasons.append('Macro alinhado')
        if f_above_vwap:
            reasons.append('Fast above VWAP')
            score = min(10, score + 1)
        score = _phase_adjust_intraday_score('SQUEEZE_BO', score, phase, trigger=(p_squeeze_release and p_vol_burst), mode=mode, reasons=reasons)
        score = max(1, min(10, score + intraday_penalty))
        return 'SQUEEZE_BO', score, reasons, phase
    
    # ════════════════════════════════════════════════════════════════════════
    # SETUP #3: VWAP RECLAIM (preço reclama VWAP em trend)
    # ════════════════════════════════════════════════════════════════════════
    
    # VWAP reclaim: above_vwap=True mas estava abaixo recentemente (proxy: pullback to MA21)
    vwap_reclaim_bull = (
        p_above_vwap
        and p_pullback_ma21
        and structure_supports
        and 40 < p_rsi < 65
    )
    
    if vwap_reclaim_bull:
        reasons.append('🌊 VWAP reclaim em pullback')
        if structure_supports:
            reasons.append(f'Estrutura: {p_last_event}')
        score = 7
        if m_above_vwap and m_htf_trend == 'ALTA':
            reasons.append('Macro também above VWAP + ALTA')
            score = 9
        if f_aligned_bull:
            score = min(10, score + 1)
        score = _phase_adjust_intraday_score('VWAP_RECLAIM', score, phase, trigger=p_above_vwap, mode=mode, reasons=reasons)
        score = max(1, min(10, score + intraday_penalty))
        return 'VWAP_RECLAIM', score, reasons, phase
    
    # ════════════════════════════════════════════════════════════════════════
    # SETUP #4: TREND BREAKOUT (trend day momentum entry)
    # 
    # Trend continuation com volume confirmação:
    #   - Vol burst (>2× média)
    #   - Above VWAP
    #   - Estrutura bull confirmada (CHoCH/BOS recente)
    #   - RSI ainda saudável (<70)
    #   - MACD bull
    #
    # Apanha casos não cobertos por SQUEEZE_BO (sem squeeze recente)
    # ou VWAP_RECLAIM (sem pullback to MA21).
    # ════════════════════════════════════════════════════════════════════════
    
    trend_bo_bullish = (
        p_vol_burst
        and p_above_vwap
        and structure_supports
        and p_struct_bias == 1
        and p_rsi < 70
        and p_macd_bull
    )
    
    if trend_bo_bullish:
        reasons.append('💥 Trend breakout: vol burst + above VWAP + struct bull')
        if p_choch_bull:
            reasons.append('CHoCH bull')
        if p_bos_bull:
            reasons.append('BOS bull (continuation)')
        score = 7
        if m_htf_trend == 'ALTA':
            reasons.append('Macro alinhado bull')
            score = 9
        if f_above_vwap and f_macd_bull:
            score = min(10, score + 1)
        score = _phase_adjust_intraday_score('TREND_BO', score, phase, trigger=(p_vol_burst and p_macd_bull), mode=mode, reasons=reasons)
        score = max(1, min(10, score + intraday_penalty))
        return 'TREND_BO', score, reasons, phase
    
    # ════════════════════════════════════════════════════════════════════════
    # SETUP #5: MICRO PULLBACK
    # RSI 30-50 em trend curto (struct bull) + VWAP support
    # ════════════════════════════════════════════════════════════════════════
    
    micro_pullback = (
        30 <= p_rsi <= 50
        and structure_supports
        and p_struct_bias == 1
        and (p_above_vwap or f_above_vwap)
        and not primary_struct_bear
    )
    
    if micro_pullback:
        reasons.append(f'🔵 Micro pullback: RSI {p_rsi:.0f} em trend')
        if p_above_vwap:
            reasons.append('Above VWAP')
        if structure_supports:
            reasons.append(f'Estrutura: {p_last_event}')
        score = 6
        if m_htf_trend == 'ALTA' and structure_supports:
            score = 8
            reasons.append('Macro bull')
        if f_macd_bull:
            score = min(10, score + 1)
        score = _phase_adjust_intraday_score('MICRO_PULLBACK', score, phase, trigger=(p_pullback_ma21 and (p_above_vwap or f_above_vwap)), mode=mode, reasons=reasons)
        score = max(1, min(10, score + intraday_penalty))
        return 'MICRO_PULLBACK', score, reasons, phase
    
    # ════════════════════════════════════════════════════════════════════════
    # FALLBACK: NO SETUP
    # ════════════════════════════════════════════════════════════════════════
    
    reasons.append('Sem setup intraday classico')

    soft_score = 0
    if p_struct_bias >= 0:
        soft_score += 1
        reasons.append('Soft: estrutura nao bearish')
    if p_above_vwap:
        soft_score += 1
        reasons.append('Soft: acima da VWAP')
    if p_macd_bull:
        soft_score += 1
        reasons.append('Soft: MACD bull')
    if f_above_vwap or f_macd_bull or f_aligned_bull:
        soft_score += 1
        reasons.append('Soft: fast TF confirma')
    if m_htf_trend != 'BAIXA' and m_struct_bias >= 0:
        soft_score += 1
        reasons.append('Soft: macro nao hostil')
    if 35 <= p_rsi <= 68:
        soft_score += 1
        reasons.append('Soft: RSI utilizavel')
    if p_vol_ratio and p_vol_ratio >= 1.2:
        soft_score += 1
        reasons.append('Soft: volume acima da media')
    if p_pullback_ma21:
        soft_score += 1
        reasons.append('Soft: pullback MA21')

    if phase in ('MOMENTUM_TREND', 'PULLBACK', 'REVERSAL_UP'):
        soft_score += 1
        reasons.append('Soft: fase favoravel')
    elif phase in ('DISTRIBUTION', 'EXHAUSTION', 'BEARISH'):
        soft_score -= 2
        reasons.append('Soft: fase penaliza')

    if soft_score >= 5:
        score = max(1, min(5, soft_score + intraday_penalty))
        reasons.append('Setup intraday suave por confluencia')
        return 'MICRO_PULLBACK', score, reasons, phase
    if soft_score >= 3:
        score = max(1, min(3, soft_score + intraday_penalty))
        reasons.append('Watchlist intraday por confluencia parcial')
        return 'NO_SETUP', score, reasons, phase

    score = max(1, soft_score + intraday_penalty)
    return 'NO_SETUP', score, reasons, phase


def _intraday_action(stage: IntradayStage, score: int) -> str:
    if stage == 'LIQ_SWEEP' and score >= 8:
        return 'STRONG BUY'
    if stage in ('SQUEEZE_BO', 'TREND_BO') and score >= 8:
        return 'STRONG BUY'
    if stage == 'VWAP_RECLAIM' and score >= 8:
        return 'STRONG BUY'
    if stage in ('LIQ_SWEEP', 'SQUEEZE_BO', 'TREND_BO', 'VWAP_RECLAIM',
                 'MICRO_PULLBACK') and score >= 4:
        return 'BUY'
    if stage in ('LIQ_SWEEP', 'SQUEEZE_BO', 'TREND_BO', 'VWAP_RECLAIM',
                 'MICRO_PULLBACK'):
        return 'WATCH'
    if stage == 'EXHAUSTION':
        return 'AVOID'
    if stage == 'BEARISH':
        return 'AVOID'
    return 'WATCH'


def _intraday_tier(stage: IntradayStage, score: int) -> str:
    if stage in ('LIQ_SWEEP', 'SQUEEZE_BO') and score >= 9:
        return 'S'
    if stage in ('LIQ_SWEEP', 'SQUEEZE_BO', 'TREND_BO', 'VWAP_RECLAIM') and score >= 7:
        return 'A'
    if score >= 4:
        return 'B'
    if score >= 3:
        return 'C'
    return 'D'


def _can_hold_overnight(tier: str, stage: IntradayStage) -> bool:
    """Regra: só Tier S/A em setups direccionais podem manter overnight."""
    if tier not in ('S', 'A'):
        return False
    if stage in ('EXHAUSTION', 'BEARISH', 'NO_SETUP'):
        return False
    return True


def detect_intraday(
    primary: dict,
    fast: dict | None = None,
    macro: dict | None = None,
    mode: IntradayMode = 'day',
    whale: dict | None = None,
) -> dict:
    """Main entry — detecta intraday setup com tri-TF analysis.
    
    Args:
        primary: 5m (scalping) ou 15m (day)
        fast: 15m (scalping) ou 1h (day)
        macro: 1h (scalping) ou 4h (day)
        mode: 'scalping' ou 'day'
        whale: whale data (peso reduzido em intraday)
    
    Returns:
        {
            'stage': 'TREND_BO' | ...,
            'mode': 'scalping' | 'day',
            'score': int (-10 a +10),
            'tier': 'S' | 'A' | 'B' | 'C' | 'D',
            'action': 'STRONG BUY' | 'BUY' | 'WATCH' | 'AVOID',
            'reasons': [...],
            'can_hold_overnight': bool,
        }
    """
    if not primary:
        return {
            'stage': 'NO_SETUP',
            'mode': mode,
            'score': 0,
            'phase': 'RANGE',
            'tier': 'D',
            'action': 'WATCH',
            'reasons': ['No primary TF data'],
            'can_hold_overnight': False,
        }
    
    if not macro:
        macro = {}
    if not fast:
        fast = {}
    
    stage, score, reasons, phase = _classify_intraday(primary, fast, macro, mode, whale)
    score = max(1, min(10, score))
    tier = _intraday_tier(stage, score)
    action = _intraday_action(stage, score)
    
    return {
        'stage': stage,
        'stage_label': stage.replace('_', ' ').title(),
        'mode': mode,
        'score': score,
        'phase': phase,
        'tier': tier,
        'action': action,
        'reasons': reasons,
        'can_hold_overnight': _can_hold_overnight(tier, stage),
    }
