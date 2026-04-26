"""Score 16 factores + setup quality.

Replicação fiel da lógica Pine. Cada factor contribui +1 (bullish), -1 (bearish), 0 (neutro).
Score final entre -16 e +16.

Setup quality requer 4-5 condições simultâneas para validar LONG/SHORT.
"""
from __future__ import annotations


def compute_score(state: dict) -> dict:
    """state contém todos os indicadores e detectores já calculados.

    Devolve {
      'score': int,           # -16 a +16
      'score_pct': int,       # 0-100
      'signal': str,          # 'FORTE ALTA' | 'Alta' | 'Neutro' | 'Baixa' | 'FORTE BAIXA'
      'factors': dict,        # contribuição de cada factor (debug)
    }
    """
    f: dict[str, int] = {}

    # 1. Tendência LTF (MA)
    if state['close'] > state['ma4'] and state['ma1'] > state['ma2']:
        f['ltf_trend'] = 1
    elif state['close'] < state['ma4'] and state['ma1'] < state['ma2']:
        f['ltf_trend'] = -1
    else:
        f['ltf_trend'] = 0

    # 2. Tendência HTF
    f['htf_trend'] = 1 if state['htf_trend_up'] else (-1 if state['htf_trend_dn'] else 0)

    # 3. Estrutura de mercado
    f['structure'] = state['struct_bias']  # já é -1, 0, 1

    # 4. MACD LTF
    f['macd'] = 1 if state['macd_v'] > state['signal_v'] else -1

    # 5. RSI momentum
    if state['rsi'] > 55:
        f['rsi'] = 1
    elif state['rsi'] < 45:
        f['rsi'] = -1
    else:
        f['rsi'] = 0

    # 6. Preço vs BB middle
    f['bb_position'] = 1 if state['close'] > state['bb_basis'] else -1

    # 7. Preço vs VWAP
    f['vwap'] = 1 if state['above_vwap'] else -1

    # 8. Volume confirma direcção
    if state['hi_vol'] and state['close'] > state['open']:
        f['volume_dir'] = 1
    elif state['hi_vol'] and state['close'] < state['open']:
        f['volume_dir'] = -1
    else:
        f['volume_dir'] = 0

    # 9. Delta de volume
    f['delta'] = 1 if state['delta'] > state['delta_ma'] else -1

    # 10. Sem divergência
    if state['vol_div_bull']:
        f['vol_divergence'] = 1
    elif state['vol_div_bear']:
        f['vol_divergence'] = -1
    else:
        f['vol_divergence'] = 0

    # 11. RSI HTF — não sobreextendido
    if 50 < state['htf_rsi'] < 70:
        f['htf_rsi'] = 1
    elif 30 < state['htf_rsi'] < 50:
        f['htf_rsi'] = -1
    else:
        f['htf_rsi'] = 0

    # 12. Não sobreextendido no VWAP
    if state['vwap_ext_up']:
        f['vwap_extended'] = -1
    elif state['vwap_ext_dn']:
        f['vwap_extended'] = 1
    else:
        f['vwap_extended'] = 0

    # 13. FVG — preço em zona relevante
    if state['in_bull_fvg']:
        f['fvg'] = 1
    elif state['in_bear_fvg']:
        f['fvg'] = -1
    else:
        f['fvg'] = 0

    # 14. OB — preço em zona relevante
    if state['in_bull_ob']:
        f['ob'] = 1
    elif state['in_bear_ob']:
        f['ob'] = -1
    else:
        f['ob'] = 0

    # 15. Volume Profile
    if state['above_poc'] and not state['above_value_area']:
        f['vp_position'] = 1
    elif not state['above_poc'] and not state['below_value_area']:
        f['vp_position'] = -1
    else:
        f['vp_position'] = 0

    # 16. Sweep recente
    if state['sweep_low']:
        f['sweep'] = 1
    elif state['sweep_high']:
        f['sweep'] = -1
    else:
        f['sweep'] = 0

    score = sum(f.values())
    score = max(-16, min(16, score))   # clamp por segurança
    score_pct = int((score + 16) / 32.0 * 100)

    if score >= 8:
        signal = 'FORTE ALTA'
    elif score >= 5:
        signal = 'Alta'
    elif score <= -8:
        signal = 'FORTE BAIXA'
    elif score <= -5:
        signal = 'Baixa'
    else:
        signal = 'Neutro'

    return {
        'score': score,
        'score_pct': score_pct,
        'signal': signal,
        'factors': f,
    }


def compute_setup_quality(state: dict, score_data: dict) -> dict:
    """Setup quality — replicação da árvore de decisão Pine.

    LONG valido = score≥6 + alignment + sem squeeze + near_sup
    SHORT valido = score≤-6 + alignment + sem squeeze + near_res

    Devolve {
      'quality': str,        # 'LONG valido' | 'SHORT valido' | 'Aguardar zona' |
                             # 'Aguarda SQ' | 'TF divergente' | 'Score baixo' | 'Sem setup'
      'blocked_by': str,     # razão de bloqueio
      'sl_long': float, 'tp_long': float,
      'sl_short': float, 'tp_short': float,
    }
    """
    score = score_data['score']
    score_ok_bull = score >= 6
    score_ok_bear = score <= -6
    align_ok = state['aligned_bull'] or state['aligned_bear']
    sq_ok = not state['squeeze']
    zone_ok = (state['in_bull_ob'] or state['in_bull_fvg']
               or state['in_bear_ob'] or state['in_bear_fvg']
               or state['sweep_low'] or state['sweep_high'])

    near_sup = state['near_sup']
    near_res = state['near_res']

    # Determinar qualidade
    if score_ok_bull and align_ok and sq_ok and near_sup:
        quality = 'LONG valido'
    elif score_ok_bear and align_ok and sq_ok and near_res:
        quality = 'SHORT valido'
    elif (score_ok_bull or score_ok_bear) and align_ok and sq_ok:
        quality = 'Aguardar zona'
    elif (score_ok_bull or score_ok_bear) and not sq_ok:
        quality = 'Aguarda SQ'
    elif (score_ok_bull or score_ok_bear) and not align_ok:
        quality = 'TF divergente'
    elif score >= 3 or score <= -3:
        quality = 'Score baixo'
    else:
        quality = 'Sem setup'

    # Razão de bloqueio
    if not score_ok_bull and not score_ok_bear:
        blocked = 'Score insuficiente'
    elif not align_ok:
        blocked = 'Timeframes divergentes'
    elif not sq_ok:
        blocked = 'Squeeze ainda activo'
    elif not zone_ok:
        blocked = 'Fora de zona OB/FVG/sweep'
    else:
        blocked = 'OK'

    # SL/TP baseados em ATR
    atr_v = state.get('atr_v', 0)
    rr_ratio = 2.0
    close = state['close']
    sl_long = round(close - atr_v * 1.5, 6)
    tp_long = round(close + atr_v * 1.5 * rr_ratio, 6)
    sl_short = round(close + atr_v * 1.5, 6)
    tp_short = round(close - atr_v * 1.5 * rr_ratio, 6)

    return {
        'quality': quality,
        'blocked_by': blocked,
        'sl_long': sl_long, 'tp_long': tp_long,
        'sl_short': sl_short, 'tp_short': tp_short,
    }
