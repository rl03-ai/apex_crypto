"""Analyser — orquestra a análise completa de um símbolo.

Usado por:
  - GET /signals/coin/{coin_id} — análise on-demand
  - Job scan_instdash — análise periódica de todo o universo
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from app.services.binance import fetch_klines
from app.services.instdash.indicators import (
    adx as adx_func, atr as atr_func, bollinger, ema, macd, rsi,
    sma, vwap_anchored, vwap_stdev, volume_delta,
)
from app.services.instdash.structure import detect_structure
from app.services.instdash.zones import (
    detect_fvg, detect_liquidity_sweeps, detect_order_blocks, detect_support_resistance,
)
from app.services.instdash.volume_profile import volume_profile
from app.services.instdash.score import compute_score, compute_setup_quality

log = logging.getLogger(__name__)


# Defaults (hardcoded — confirmado pelo Rui)
MA1_LEN = 9
MA2_LEN = 21
MA3_LEN = 50
MA4_LEN = 200
BB_LEN = 20
BB_MULT = 2.0
VOL_LEN = 20
VOL_MULT = 1.5
MS_LEN = 10
SR_LEFT = 5
SR_RIGHT = 2
SR_WIDTH_PCT = 0.5

# Min de barras para conseguir produzir análise fiável
MIN_BARS = MA4_LEN + 50


async def analyse_symbol(symbol: str, interval: str = '1d',
                          htf_interval: str = '1w') -> Optional[dict]:
    """Análise completa de um símbolo Binance.

    symbol:        ex 'BTCUSDT'
    interval:      LTF — '1d' (default) ou '4h'
    htf_interval:  HTF — '1w' (default) para confirmação semanal

    Devolve dict completo com todos os campos. None se dados insuficientes.
    """
    # Fetch LTF + HTF em paralelo seria ideal, mas como já estão cacheados
    # e este service também é usado em loops (job), mantemos sequencial — mais simples.
    df_ltf = await fetch_klines(symbol, interval, limit=300)
    if df_ltf is None or len(df_ltf) < MIN_BARS:
        log.debug('analyse_symbol: %s/%s sem dados suficientes', symbol, interval)
        return None

    df_htf = await fetch_klines(symbol, htf_interval, limit=200)
    if df_htf is None or len(df_htf) < 60:
        log.debug('analyse_symbol: %s/%s HTF sem dados', symbol, htf_interval)
        df_htf = None

    return _compute_analysis(symbol, df_ltf, df_htf, interval, htf_interval)


def _compute_analysis(symbol: str, df: pd.DataFrame, df_htf: Optional[pd.DataFrame],
                       interval: str, htf_interval: str) -> dict:
    """Faz toda a computação. Função separada para facilitar testes."""

    # ── Indicadores básicos no LTF ───────────────────────────────────────────
    close = df['close']
    open_ = df['open']
    high  = df['high']
    low   = df['low']
    volume = df['volume']

    ma1 = ema(close, MA1_LEN)
    ma2 = ema(close, MA2_LEN)
    ma3 = ema(close, MA3_LEN)
    ma4 = ema(close, MA4_LEN)

    rsi_v = rsi(close, 14)
    macd_v, signal_v, _ = macd(close, 12, 26, 9)
    bb_basis, bb_up, bb_dn = bollinger(close, BB_LEN, BB_MULT)
    atr_v = atr_func(df, 14)
    atr_pct = (atr_v / close) * 100
    adx_v, pdi_v, mdi_v = adx_func(high, low, close, 14)

    # VWAP (anchored daily)
    vwap = vwap_anchored(df, anchor_freq='D')
    vwap_std = vwap_stdev(df, 20)
    vwap_up1 = vwap + vwap_std
    vwap_dn1 = vwap - vwap_std
    vwap_up2 = vwap + vwap_std * 2
    vwap_dn2 = vwap - vwap_std * 2

    above_vwap = close.iloc[-1] > vwap.iloc[-1] if not pd.isna(vwap.iloc[-1]) else False
    vwap_ext_up = close.iloc[-1] > vwap_up2.iloc[-1] if not pd.isna(vwap_up2.iloc[-1]) else False
    vwap_ext_dn = close.iloc[-1] < vwap_dn2.iloc[-1] if not pd.isna(vwap_dn2.iloc[-1]) else False

    # Volume
    vol_avg = sma(volume, VOL_LEN)
    hi_vol = volume.iloc[-1] > vol_avg.iloc[-1] * VOL_MULT if not pd.isna(vol_avg.iloc[-1]) else False
    vol_ratio = float(volume.iloc[-1] / vol_avg.iloc[-1]) if not pd.isna(vol_avg.iloc[-1]) and vol_avg.iloc[-1] > 0 else 1.0

    # Volume delta
    delta = volume_delta(df)
    delta_ma = sma(delta, VOL_LEN)
    delta_now = float(delta.iloc[-1])
    delta_ma_now = float(delta_ma.iloc[-1]) if not pd.isna(delta_ma.iloc[-1]) else 0.0

    # Divergências volume (simplificadas — Pine usa close vs delta de 3 barras atrás)
    if len(close) > 3:
        vol_div_bear = (close.iloc[-1] > close.iloc[-4]) and (delta.iloc[-1] < delta.iloc[-4]) and (delta.iloc[-1] < 0)
        vol_div_bull = (close.iloc[-1] < close.iloc[-4]) and (delta.iloc[-1] > delta.iloc[-4]) and (delta.iloc[-1] > 0)
    else:
        vol_div_bear = vol_div_bull = False

    # Bollinger squeeze
    bb_w = (bb_up - bb_dn) / bb_basis
    bb_w_avg = sma(bb_w, 100)
    if not pd.isna(bb_w.iloc[-1]) and not pd.isna(bb_w_avg.iloc[-1]):
        squeeze = bb_w.iloc[-1] < bb_w_avg.iloc[-1] * 0.75
    else:
        squeeze = False

    # ── HTF data ─────────────────────────────────────────────────────────────
    if df_htf is not None and len(df_htf) >= 50:
        htf_close = df_htf['close']
        htf_ma50  = ema(htf_close, 50).iloc[-1]
        htf_ma200 = ema(htf_close, 200).iloc[-1] if len(htf_close) >= 200 else htf_ma50
        htf_rsi_v = float(rsi(htf_close, 14).iloc[-1])
        htf_close_now = float(htf_close.iloc[-1])
        htf_trend_up = htf_close_now > htf_ma50 and htf_ma50 > htf_ma200
        htf_trend_dn = htf_close_now < htf_ma50 and htf_ma50 < htf_ma200
    else:
        htf_trend_up = htf_trend_dn = False
        htf_rsi_v = 50.0

    htf_trend_str = 'ALTA' if htf_trend_up else ('BAIXA' if htf_trend_dn else 'LATERAL')

    # Alinhamento
    aligned_bull = htf_trend_up and close.iloc[-1] > ma4.iloc[-1] and ma1.iloc[-1] > ma2.iloc[-1]
    aligned_bear = htf_trend_dn and close.iloc[-1] < ma4.iloc[-1] and ma1.iloc[-1] < ma2.iloc[-1]

    # ── Estrutura ────────────────────────────────────────────────────────────
    structure = detect_structure(df, MS_LEN)

    # ── Zonas ────────────────────────────────────────────────────────────────
    fvg = detect_fvg(df, min_pct=0.1)
    ob = detect_order_blocks(df, ob_len=5, strength_atr=1.5)
    liq = detect_liquidity_sweeps(df, lookback=20)
    sr = detect_support_resistance(df, SR_LEFT, SR_RIGHT, SR_WIDTH_PCT)

    # ── Volume Profile ───────────────────────────────────────────────────────
    vp = volume_profile(df, lookback=100, n_buckets=20)

    # LTF trend string
    if close.iloc[-1] > ma4.iloc[-1] and ma1.iloc[-1] > ma2.iloc[-1]:
        ltf_trend_str = 'ALTA'
    elif close.iloc[-1] < ma4.iloc[-1] and ma1.iloc[-1] < ma2.iloc[-1]:
        ltf_trend_str = 'BAIXA'
    else:
        ltf_trend_str = 'LATERAL'

    # ── State para scoring ───────────────────────────────────────────────────
    state = {
        'close': float(close.iloc[-1]),
        'open':  float(open_.iloc[-1]),
        'ma1':   float(ma1.iloc[-1]),
        'ma2':   float(ma2.iloc[-1]),
        'ma3':   float(ma3.iloc[-1]),
        'ma4':   float(ma4.iloc[-1]),
        'rsi':   float(rsi_v.iloc[-1]),
        'macd_v':   float(macd_v.iloc[-1]),
        'signal_v': float(signal_v.iloc[-1]),
        'bb_basis': float(bb_basis.iloc[-1]),
        'atr_v':    float(atr_v.iloc[-1]),
        'above_vwap': above_vwap,
        'vwap_ext_up': vwap_ext_up,
        'vwap_ext_dn': vwap_ext_dn,
        'hi_vol': hi_vol,
        'delta':    delta_now,
        'delta_ma': delta_ma_now,
        'vol_div_bull': vol_div_bull,
        'vol_div_bear': vol_div_bear,
        'htf_trend_up': htf_trend_up,
        'htf_trend_dn': htf_trend_dn,
        'htf_rsi': htf_rsi_v,
        'aligned_bull': aligned_bull,
        'aligned_bear': aligned_bear,
        'squeeze': squeeze,
        'struct_bias':  structure['struct_bias'],
        'in_bull_fvg':  fvg['in_bull_fvg'],
        'in_bear_fvg':  fvg['in_bear_fvg'],
        'in_bull_ob':   ob['in_bull_ob'],
        'in_bear_ob':   ob['in_bear_ob'],
        'sweep_high':   liq['sweep_high'],
        'sweep_low':    liq['sweep_low'],
        'near_sup':     sr['near_sup'],
        'near_res':     sr['near_res'],
        'above_poc':         vp['above_poc'],
        'above_value_area':  vp['above_value_area'],
        'below_value_area':  vp['below_value_area'],
    }

    score_data = compute_score(state)
    setup = compute_setup_quality(state, score_data)

    # ── Whale metrics (CoinGlass OI + liquidations) ────────────────────
    # Nota: whale_metrics virá de job background que popula cache
    # Por enquanto, None. Será integrado no scan_whales job depois.
    whale_score_data = None

    # ── Output ───────────────────────────────────────────────────────────────
    # Helper recursivo para converter qualquer numpy type → Python nativo
    def deep_to_py(obj):
        if isinstance(obj, dict):
            return {k: deep_to_py(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [deep_to_py(v) for v in obj]
        if isinstance(obj, (np.bool_, np.integer, np.floating)):
            return obj.item()
        return obj

    output = {
        'symbol': symbol,
        'interval': interval,
        'htf_interval': htf_interval,
        'last_close_at': df.index[-1].isoformat(),

        # Preço
        'price': float(state['close']),
        'change_24h_pct': round((float(close.iloc[-1]) / float(close.iloc[-2]) - 1) * 100, 2) if len(close) >= 2 else 0.0,

        # Indicadores
        'rsi': round(state['rsi'], 1),
        'macd_bullish': bool(state['macd_v'] > state['signal_v']),
        'atr_pct': round(float(atr_pct.iloc[-1]), 2),
        'adx': round(float(adx_v.iloc[-1]), 1) if not pd.isna(adx_v.iloc[-1]) else None,
        'di_plus': round(float(pdi_v.iloc[-1]), 1) if not pd.isna(pdi_v.iloc[-1]) else None,
        'di_minus': round(float(mdi_v.iloc[-1]), 1) if not pd.isna(mdi_v.iloc[-1]) else None,
        'vol_ratio': round(vol_ratio, 2),
        'delta_volume': int(state['delta']),

        # Trends
        'ltf_trend': ltf_trend_str,
        'htf_trend': htf_trend_str,
        'aligned_bull': bool(state['aligned_bull']),
        'aligned_bear': bool(state['aligned_bear']),

        # Score
        'score': score_data['score'],
        'score_pct': score_data['score_pct'],
        'signal': score_data['signal'],
        'factors': score_data['factors'],

        # Setup
        'setup_quality': setup['quality'],
        'setup_blocked_by': setup['blocked_by'],
        'sl_long': setup['sl_long'],
        'tp_long': setup['tp_long'],
        'sl_short': setup['sl_short'],
        'tp_short': setup['tp_short'],

        # Bollinger
        'bb_basis': state['bb_basis'],
        'bb_upper': round(float(bb_up.iloc[-1]), 6),
        'bb_lower': round(float(bb_dn.iloc[-1]), 6),
        'squeeze': bool(state['squeeze']),

        # VWAP
        'vwap': round(float(vwap.iloc[-1]), 6) if not pd.isna(vwap.iloc[-1]) else None,
        'above_vwap': bool(state['above_vwap']),
        'vwap_ext_up': bool(state['vwap_ext_up']),
        'vwap_ext_dn': bool(state['vwap_ext_dn']),

        # Estrutura
        'structure': structure,

        # Zonas
        'fvg': fvg,
        'order_block': ob,
        'liquidity':   liq,
        'support_resistance': sr,

        # Volume profile
        'volume_profile': vp,

        # Whale metrics (smart money)
        'whale_score': whale_score_data,
    }

    # Converter recursivamente todos os numpy types antes de devolver
    return deep_to_py(output)