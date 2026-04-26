"""Volume Profile simplificado — POC, VAH, VAL.

Replica a lógica do Pine v6 mas usando apenas 20 buckets e sem persistir histórico.
Calcula no scan e devolve snapshot.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def volume_profile(df: pd.DataFrame, lookback: int = 100, n_buckets: int = 20,
                   value_area_pct: float = 0.70) -> dict:
    """Calcula POC (Point of Control), VAH (Value Area High), VAL (Value Area Low).

    POC = preço com mais volume nos últimos N períodos.
    Value Area = range de preços que contém value_area_pct do volume total, centrado no POC.
    """
    if len(df) < lookback:
        lookback = len(df)
    if lookback < 10:
        return _empty()

    recent = df.iloc[-lookback:]
    hi = float(recent['high'].max())
    lo = float(recent['low'].min())
    rng = hi - lo
    if rng <= 0:
        return _empty()

    bucket_size = rng / n_buckets
    bucket_volumes = np.zeros(n_buckets, dtype=float)

    # Distribuir volume de cada vela proporcional ao overlap com cada bucket
    for _, row in recent.iterrows():
        c_lo = float(row['low'])
        c_hi = float(row['high'])
        c_vol = float(row['volume'])
        c_range = c_hi - c_lo
        if c_range <= 0:
            continue

        for b in range(n_buckets):
            b_lo = lo + bucket_size * b
            b_hi = lo + bucket_size * (b + 1)
            ov_lo = max(b_lo, c_lo)
            ov_hi = min(b_hi, c_hi)
            if ov_hi > ov_lo:
                bucket_volumes[b] += c_vol * (ov_hi - ov_lo) / c_range

    # POC = bucket com mais volume
    poc_idx = int(np.argmax(bucket_volumes))
    poc_price = lo + bucket_size * (poc_idx + 0.5)

    # Expandir a value area simetricamente
    total_vol = bucket_volumes.sum()
    if total_vol == 0:
        return _empty()
    target = total_vol * value_area_pct
    va_vol = bucket_volumes[poc_idx]
    va_lo = va_hi = poc_idx

    while va_vol < target and (va_lo > 0 or va_hi < n_buckets - 1):
        # Expandir para o lado com mais volume
        next_up = bucket_volumes[va_hi + 1] if va_hi < n_buckets - 1 else -1
        next_dn = bucket_volumes[va_lo - 1] if va_lo > 0 else -1
        if next_up >= next_dn:
            va_hi += 1
            va_vol += next_up
        else:
            va_lo -= 1
            va_vol += next_dn

    vah_price = lo + bucket_size * (va_hi + 1)
    val_price = lo + bucket_size * va_lo

    current_close = float(df['close'].iloc[-1])
    above_poc = current_close > poc_price
    in_value_area = val_price <= current_close <= vah_price
    above_va = current_close > vah_price
    below_va = current_close < val_price

    return {
        'poc': round(poc_price, 6),
        'vah': round(vah_price, 6),
        'val': round(val_price, 6),
        'above_poc': above_poc,
        'in_value_area': in_value_area,
        'above_value_area': above_va,
        'below_value_area': below_va,
    }


def _empty() -> dict:
    return {
        'poc': None, 'vah': None, 'val': None,
        'above_poc': False, 'in_value_area': False,
        'above_value_area': False, 'below_value_area': False,
    }
