"""Indicadores técnicos — replicação fiel do Pine v6.

Funções puras pandas/numpy, sem dependências extra.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ── Médias Móveis ────────────────────────────────────────────────────────────

def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(window=length, min_periods=length).mean()


# ── RSI ──────────────────────────────────────────────────────────────────────

def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """Wilder's RSI (igual ao ta.rsi do Pine)."""
    delta = close.diff()
    gain  = delta.clip(lower=0).ewm(alpha=1/length, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(alpha=1/length, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


# ── MACD ─────────────────────────────────────────────────────────────────────

def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal_len: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
    macd_line   = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal_len)
    hist        = macd_line - signal_line
    return macd_line, signal_line, hist


# ── Bollinger ────────────────────────────────────────────────────────────────

def bollinger(close: pd.Series, length: int = 20, mult: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Devolve (basis, upper, lower)."""
    basis = sma(close, length)
    dev   = close.rolling(length).std()
    return basis, basis + mult * dev, basis - mult * dev


# ── True Range / ATR ─────────────────────────────────────────────────────────

def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    return pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Wilder's ATR."""
    tr = true_range(df['high'], df['low'], df['close'])
    return tr.ewm(alpha=1/length, adjust=False).mean()


# ── ADX ──────────────────────────────────────────────────────────────────────

def adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Devolve (ADX, +DI, -DI)."""
    up   = high.diff()
    down = -low.diff()
    plus  = ((up   > down) & (up   > 0)).astype(float) * up
    minus = ((down > up)   & (down > 0)).astype(float) * down

    tr = true_range(high, low, close)
    atr_v = tr.ewm(alpha=1/length, adjust=False).mean()
    pdi = 100 * plus.ewm(alpha=1/length, adjust=False).mean() / atr_v.replace(0, np.nan)
    mdi = 100 * minus.ewm(alpha=1/length, adjust=False).mean() / atr_v.replace(0, np.nan)
    dx  = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1/length, adjust=False).mean(), pdi, mdi


# ── VWAP (session-anchored, daily reset) ──────────────────────────────────────

def vwap_anchored(df: pd.DataFrame, anchor_freq: str = 'D') -> pd.Series:
    """VWAP com reset por dia (anchor_freq='D') ou semana ('W').

    Pine usa ta.vwap(hlc3) com reset diário por defeito.
    """
    if df.empty:
        return pd.Series(dtype=float)
    typical = (df['high'] + df['low'] + df['close']) / 3.0
    pv      = typical * df['volume']

    # Marcar grupos por anchor — cada novo dia/semana reinicia o cálculo
    # Convertemos para naive antes do to_period (PeriodIndex não tem timezone)
    idx = df.index.tz_convert(None) if df.index.tz is not None else df.index
    groups = idx.to_period(anchor_freq)
    cum_pv  = pv.groupby(groups).cumsum()
    cum_vol = df['volume'].groupby(groups).cumsum()
    return cum_pv / cum_vol.replace(0, np.nan)


def vwap_stdev(df: pd.DataFrame, length: int = 20) -> pd.Series:
    """Stdev do hlc3 para construir bandas do VWAP. Pine: ta.stdev(hlc3, 20)."""
    typical = (df['high'] + df['low'] + df['close']) / 3.0
    return typical.rolling(length).std()


# ── Volume Delta aproximado ──────────────────────────────────────────────────

def volume_delta(df: pd.DataFrame) -> pd.Series:
    """Aproximação do delta bull/bear igual ao Pine.

    bull_vol = se close>=open: volume; senão volume * (close-low)/(high-low)
    bear_vol = se close<open: volume; senão volume * (high-close)/(high-low)
    delta = bull - bear
    """
    rng = (df['high'] - df['low']).replace(0, np.nan)
    bull_full = df['close'] >= df['open']

    bull_vol = np.where(
        bull_full,
        df['volume'],
        df['volume'] * (df['close'] - df['low']) / (rng + 1e-9),
    )
    bear_vol = np.where(
        ~bull_full,
        df['volume'],
        df['volume'] * (df['high'] - df['close']) / (rng + 1e-9),
    )
    return pd.Series(bull_vol - bear_vol, index=df.index)
