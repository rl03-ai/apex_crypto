"""Análise técnica — indicadores e detectores extraídos do trend_change.py.

Funções puras sem dependência do TrendChangeDetector completo.
Recebem séries pandas e devolvem dicts/listas serializáveis.

Indicadores: RSI, ADX, Bollinger Bands width
Detectores: SuperTrend state, Donchian state, swing pivots
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


# ── Indicadores base ──────────────────────────────────────────────────────────

def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    return pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = _true_range(df['high'], df['low'], df['close'])
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Devolve (ADX, +DI, -DI). +DI > -DI = bull; -DI > +DI = bear; ADX > 25 = trend forte."""
    up    = high.diff()
    down  = -low.diff()
    plus  = ((up   > down) & (up   > 0)).astype(float) * up
    minus = ((down > up)   & (down > 0)).astype(float) * down

    tr  = _true_range(high, low, close)
    atr_v = tr.ewm(alpha=1 / period, adjust=False).mean()
    pdi = 100 * plus.ewm(alpha=1 / period, adjust=False).mean() / atr_v.replace(0, np.nan)
    mdi = 100 * minus.ewm(alpha=1 / period, adjust=False).mean() / atr_v.replace(0, np.nan)
    dx  = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean(), pdi, mdi


def bollinger(close: pd.Series, period: int = 20, n_std: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Devolve (middle, upper, lower, width%). width% = (upper - lower) / middle."""
    mid   = close.rolling(period, min_periods=period).mean()
    std   = close.rolling(period, min_periods=period).std()
    upper = mid + n_std * std
    lower = mid - n_std * std
    width = (upper - lower) / mid.replace(0, np.nan) * 100
    return mid, upper, lower, width


# ── Detectores de estado ──────────────────────────────────────────────────────

def supertrend_state(df: pd.DataFrame, atr_period: int = 10, mult: float = 3.0) -> pd.Series:
    """SuperTrend simplificado. Devolve série de strings: 'up' / 'down'."""
    atr_v = _atr(df, atr_period)
    hl2   = (df['high'] + df['low']) / 2.0
    upper = hl2 + mult * atr_v
    lower = hl2 - mult * atr_v
    state = pd.Series('up', index=df.index)
    for i in range(1, len(df)):
        if df['close'].iloc[i] > upper.iloc[i - 1]:
            state.iloc[i] = 'up'
        elif df['close'].iloc[i] < lower.iloc[i - 1]:
            state.iloc[i] = 'down'
        else:
            state.iloc[i] = state.iloc[i - 1]
    return state


def donchian_state(df: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """Donchian breakout. Devolve 'up' (bate alta), 'down' (bate baixa) ou 'flat'."""
    hh    = df['high'].rolling(lookback, min_periods=lookback).max().shift(1)
    ll    = df['low'].rolling(lookback, min_periods=lookback).min().shift(1)
    state = pd.Series('flat', index=df.index)
    state[df['close'] >= hh] = 'up'
    state[df['close'] <= ll] = 'down'
    return state


def detect_swing_pivots(df: pd.DataFrame, n_left: int = 3, n_right: int = 2, max_pivots: int = 3) -> tuple[list[float], list[float]]:
    """Swing lows e highs por pivot clássico — mais recentes primeiro."""
    if df is None or df.empty or len(df) < n_left + n_right + 2:
        return [], []

    highs = df['high'].astype(float).tolist()
    lows  = df['low'].astype(float).tolist()
    n     = len(lows)
    sw_lows: list[float]  = []
    sw_highs: list[float] = []

    for i in range(n - n_right - 1, n_left - 1, -1):
        if len(sw_lows) < max_pivots:
            is_low = (
                all(lows[i] <= lows[i - j] for j in range(1, n_left + 1))
                and all(lows[i] <= lows[i + j] for j in range(1, n_right + 1))
            )
            if is_low:
                sw_lows.append(round(float(lows[i]), 6))

        if len(sw_highs) < max_pivots:
            is_high = (
                all(highs[i] >= highs[i - j] for j in range(1, n_left + 1))
                and all(highs[i] >= highs[i + j] for j in range(1, n_right + 1))
            )
            if is_high:
                sw_highs.append(round(float(highs[i]), 6))

        if len(sw_lows) >= max_pivots and len(sw_highs) >= max_pivots:
            break

    return sw_lows, sw_highs


# ── Agregador para a API ──────────────────────────────────────────────────────

def analyse_chart(prices: list[float | int]) -> Optional[dict]:
    """Recebe uma série de preços diários (do /coins/{id}/market_chart)
    e devolve um snapshot de análise técnica.

    Como o CoinGecko grátis só expõe preços (sem OHLC), aproximamos
    high=low=close. ADX e SuperTrend ficam menos precisos mas ainda
    informativos para tendência.
    """
    if not prices or len(prices) < 30:
        return None

    s = pd.Series([float(p) for p in prices])
    df = pd.DataFrame({'high': s, 'low': s, 'close': s})

    try:
        rsi_v   = float(rsi(df['close'], 14).iloc[-1])
        adx_s, pdi_s, mdi_s = adx(df['high'], df['low'], df['close'], 14)
        adx_v   = float(adx_s.iloc[-1])
        pdi_v   = float(pdi_s.iloc[-1])
        mdi_v   = float(mdi_s.iloc[-1])

        mid, upper, lower, width = bollinger(df['close'], 20, 2.0)
        bb_width = float(width.iloc[-1])
        # posição relativa: 0 = lower band, 100 = upper band
        rng = float(upper.iloc[-1] - lower.iloc[-1])
        bb_position = float((s.iloc[-1] - lower.iloc[-1]) / rng * 100) if rng > 0 else 50.0

        st_state = str(supertrend_state(df, 10, 3.0).iloc[-1])
        dc_state = str(donchian_state(df, 20).iloc[-1])
        sw_lows, sw_highs = detect_swing_pivots(df, n_left=3, n_right=2, max_pivots=3)

        # Verdict combinado simples
        bull_signals = sum([
            rsi_v >= 50,
            pdi_v > mdi_v,
            st_state == 'up',
            dc_state == 'up',
        ])
        if bull_signals >= 3:
            trend = 'uptrend'
        elif bull_signals <= 1:
            trend = 'downtrend'
        else:
            trend = 'range'

        # Helper — guard contra NaN antes de serializar
        def _f(x: float) -> Optional[float]:
            try:
                return None if pd.isna(x) else round(float(x), 2)
            except Exception:
                return None

        return {
            'trend':           trend,             # 'uptrend' | 'downtrend' | 'range'
            'rsi':             _f(rsi_v),
            'rsi_zone':        _rsi_zone(rsi_v),  # 'oversold' | 'neutral' | 'overbought'
            'adx':             _f(adx_v),
            'adx_strength':    _adx_strength(adx_v),  # 'weak' | 'moderate' | 'strong'
            'di_plus':         _f(pdi_v),
            'di_minus':        _f(mdi_v),
            'bb_width':        _f(bb_width),
            'bb_position':     _f(bb_position),
            'supertrend':      st_state,
            'donchian':        dc_state,
            'swing_lows':      sw_lows,           # mais recente primeiro
            'swing_highs':     sw_highs,
            'bull_signals':    bull_signals,      # 0-4 (de quantos sinais bullish concordam)
        }
    except Exception:
        return None


def _rsi_zone(v: float) -> str:
    if v < 30:  return 'oversold'
    if v > 70:  return 'overbought'
    return 'neutral'


def _adx_strength(v: float) -> str:
    if v < 20:  return 'weak'
    if v < 40:  return 'moderate'
    return 'strong'
