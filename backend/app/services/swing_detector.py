# UPDATED SWING DETECTOR WITH STATE + PHASE AWARE LOGIC

def detect_swing(primary, fast, macro, prev=None):
    prev = prev or {}

    p_rsi = primary.get('rsi', 50)
    p_struct_bias = prev.get('p_struct_bias', primary.get('struct_bias', 0))
    p_last_event = prev.get('p_last_event', 'none')
    bars_since_event = prev.get('bars_since_event', 999)

    structure = primary.get('structure', {})
    p_choch_bull = structure.get('choch_bull', False)
    p_choch_bear = structure.get('choch_bear', False)
    p_bos_bull = structure.get('bos_bull', False)
    p_bos_bear = structure.get('bos_bear', False)

    p_atr_pct = primary.get('atr_pct', 1)

    f_choch_bull = fast.get('choch_bull', False) if fast else False

    htf_trend = macro.get('htf_trend', 'LATERAL') if macro else 'LATERAL'
    m_ext = macro.get('ext_above_ma200_pct', 0) if macro else 0

    # STRUCTURE STATE
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
        bars_since_event = 0
    elif p_bos_bear:
        p_last_event = 'bos_bear'
        bars_since_event = 0
    else:
        bars_since_event += 1

    # PHASE
    phase = 'RANGE'
    if p_struct_bias == 1 and p_last_event in ['bos_bull', 'choch_bull'] and bars_since_event < 10:
        if 45 < p_rsi < 65:
            phase = 'TREND'
    elif p_rsi < 30 and p_last_event == 'choch_bull' and bars_since_event < 5:
        phase = 'REVERSAL_UP'
    elif p_rsi > 70 and p_last_event == 'choch_bear':
        phase = 'REVERSAL_DOWN'
    elif p_struct_bias == 1 and p_rsi > 65:
        phase = 'DISTRIBUTION'

    structure_supports = (
        p_struct_bias == 1 and
        p_last_event in ['choch_bull', 'bos_bull'] and
        bars_since_event < 10
    )

    bloquear_buy = False

    if phase in ['DISTRIBUTION', 'REVERSAL_DOWN'] and m_ext > 20:
        bloquear_buy = True
    elif phase == 'TREND' and m_ext > 35:
        bloquear_buy = True

    if htf_trend == 'BAIXA':
        bloquear_buy = True

    trend_setup = phase == 'TREND' and structure_supports and 50 < p_rsi < 65
    reversal_setup = phase == 'REVERSAL_UP'

    trigger = f_choch_bull

    # SCORE PHASE-AWARE
    # A fase passa a influenciar diretamente o score através de pesos próprios.
    phase_weights = {
        'TREND': {'trend': 2, 'reversal': 1, 'trigger': 1},
        'REVERSAL_UP': {'trend': 1, 'reversal': 3, 'trigger': 1},
        'DISTRIBUTION': {'trend': 0, 'reversal': 1, 'trigger': 1},
        'REVERSAL_DOWN': {'trend': 0, 'reversal': 0, 'trigger': 1},
        'RANGE': {'trend': 1, 'reversal': 1, 'trigger': 1},
    }
    weights = phase_weights.get(phase, {'trend': 1, 'reversal': 1, 'trigger': 1})

    score = 0

    if trend_setup:
        score += weights['trend']

    if reversal_setup:
        score += weights['reversal']

    if trigger:
        score += weights['trigger']

    # Penalizações conservadoras para evitar BUY em contexto fraco/perigoso.
    if phase in ['DISTRIBUTION', 'REVERSAL_DOWN']:
        score -= 1

    if htf_trend == 'BAIXA':
        score -= 1

    if p_atr_pct < 1:
        return {
            'signal': 'NEUTRAL',
            'phase': phase,
            'score': 0,
            'p_struct_bias': p_struct_bias,
            'p_last_event': p_last_event,
            'bars_since_event': bars_since_event
        }

    # Threshold dinâmico por fase.
    if phase == 'TREND':
        buy_threshold = 3
    elif phase == 'REVERSAL_UP':
        buy_threshold = 3
    elif phase == 'DISTRIBUTION':
        buy_threshold = 4
    else:
        buy_threshold = 3

    if not bloquear_buy and score >= buy_threshold:
        signal = 'BUY'
    elif not bloquear_buy and score == 2:
        signal = 'WEAK_BUY'
    else:
        signal = 'NEUTRAL'

    return {
        'signal': signal,
        'phase': phase,
        'score': score,
        'p_struct_bias': p_struct_bias,
        'p_last_event': p_last_event,
        'bars_since_event': bars_since_event
    }
