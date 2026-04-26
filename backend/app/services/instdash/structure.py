"""Estrutura de mercado — CHoCH, BOS, HH/LL.

Replicação fiel do Pine.

  CHoCH (Change of Character): preço quebra estrutura contrária = mudança de tendência
  BOS (Break of Structure): preço quebra estrutura a favor = continuação

Pine usa `ta.pivothigh(high, ms_len, ms_len)` — pivot confirmado com ms_len velas
à esquerda e à direita. ms_len default = 10.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def pivot_highs(high: pd.Series, n_left: int = 10, n_right: int = 10) -> pd.Series:
    """Para cada barra, devolve o valor do pivot high se essa barra for um pivot,
    senão NaN.

    Equivalente a `ta.pivothigh(high, n_left, n_right)` do Pine, com offset corrigido
    (Pine devolve no índice da barra original, não na barra de confirmação).
    """
    pivots = pd.Series(np.nan, index=high.index)
    arr = high.values
    n = len(arr)
    for i in range(n_left, n - n_right):
        candidate = arr[i]
        is_pivot = (
            all(candidate >= arr[i - j] for j in range(1, n_left + 1))
            and all(candidate >= arr[i + j] for j in range(1, n_right + 1))
        )
        if is_pivot:
            pivots.iloc[i] = candidate
    return pivots


def pivot_lows(low: pd.Series, n_left: int = 10, n_right: int = 10) -> pd.Series:
    pivots = pd.Series(np.nan, index=low.index)
    arr = low.values
    n = len(arr)
    for i in range(n_left, n - n_right):
        candidate = arr[i]
        is_pivot = (
            all(candidate <= arr[i - j] for j in range(1, n_left + 1))
            and all(candidate <= arr[i + j] for j in range(1, n_right + 1))
        )
        if is_pivot:
            pivots.iloc[i] = candidate
    return pivots


def detect_structure(df: pd.DataFrame, ms_len: int = 10) -> dict:
    """Replica a lógica Pine de structure bias e events.

    Devolve:
      {
        'last_hh': float,   # último higher high
        'prev_hh': float,
        'last_ll': float,   # último lower low
        'prev_ll': float,
        'choch_bull': bool, # ocorreu na última barra
        'choch_bear': bool,
        'bos_bull': bool,
        'bos_bear': bool,
        'struct_bias': int, # 1 = bullish, -1 = bearish, 0 = neutro
        'last_event': str,  # 'choch_bull' | 'bos_bull' | 'choch_bear' | 'bos_bear' | 'none'
        'event_bars_ago': int,
      }
    """
    if len(df) < ms_len * 2 + 2:
        return {
            'last_hh': None, 'prev_hh': None, 'last_ll': None, 'prev_ll': None,
            'choch_bull': False, 'choch_bear': False,
            'bos_bull': False, 'bos_bear': False,
            'struct_bias': 0, 'last_event': 'none', 'event_bars_ago': None,
        }

    ph = pivot_highs(df['high'], ms_len, ms_len)
    pl = pivot_lows(df['low'], ms_len, ms_len)
    closes = df['close'].values
    n = len(df)

    # Acumular state ao longo do tempo (igual ao Pine com `var`)
    last_hh = prev_hh = None
    last_ll = prev_ll = None
    struct_bias = 0
    last_event = 'none'
    last_event_idx: Optional[int] = None

    # Para detectar crossovers, varremos sequencialmente
    for i in range(n):
        # Actualizar pivots quando uma nova barra de pivot é confirmada
        # (no Pine, `ta.pivothigh(high, n_left, n_right)` devolve no momento i mas
        # representa o pivot que aconteceu i-n_right barras atrás.
        # Para simplicidade, aqui actualizamos quando o pivot está marcado.)
        ph_val = ph.iloc[i]
        pl_val = pl.iloc[i]
        if not np.isnan(ph_val):
            prev_hh = last_hh
            last_hh = float(ph_val)
        if not np.isnan(pl_val):
            prev_ll = last_ll
            last_ll = float(pl_val)

        # Crossovers de close vs último pivot
        if i == 0:
            continue
        c_now = closes[i]
        c_prev = closes[i - 1]

        cross_up_hh = (last_hh is not None and c_prev <= last_hh < c_now)
        cross_dn_ll = (last_ll is not None and c_prev >= last_ll > c_now)

        # CHoCH bull: cross up no last_hh + estrutura anterior era bearish (last_ll > prev_ll)
        if cross_up_hh and last_ll is not None and prev_ll is not None and last_ll > prev_ll:
            struct_bias = 1
            last_event = 'choch_bull'
            last_event_idx = i
        # BOS bull: cross up no last_hh + last_hh > prev_hh (continuação)
        elif cross_up_hh and last_hh is not None and prev_hh is not None and last_hh > prev_hh:
            struct_bias = 1
            last_event = 'bos_bull'
            last_event_idx = i

        # CHoCH bear
        if cross_dn_ll and last_hh is not None and prev_hh is not None and last_hh < prev_hh:
            struct_bias = -1
            last_event = 'choch_bear'
            last_event_idx = i
        # BOS bear
        elif cross_dn_ll and last_ll is not None and prev_ll is not None and last_ll < prev_ll:
            struct_bias = -1
            last_event = 'bos_bear'
            last_event_idx = i

    bars_ago = None if last_event_idx is None else (n - 1 - last_event_idx)

    return {
        'last_hh': last_hh,
        'prev_hh': prev_hh,
        'last_ll': last_ll,
        'prev_ll': prev_ll,
        # "ocorreu na última barra" = só se o índice do evento é a barra mais recente
        'choch_bull': last_event == 'choch_bull' and bars_ago == 0,
        'choch_bear': last_event == 'choch_bear' and bars_ago == 0,
        'bos_bull':   last_event == 'bos_bull'   and bars_ago == 0,
        'bos_bear':   last_event == 'bos_bear'   and bars_ago == 0,
        'struct_bias': struct_bias,
        'last_event': last_event,
        'event_bars_ago': bars_ago,
    }
