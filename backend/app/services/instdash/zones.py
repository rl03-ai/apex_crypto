"""Zonas institucionais — FVG, OB, Liquidity Sweeps, S/R.

Replicação simplificada do Pine: detectamos as zonas activas no momento do scan,
sem tracking persistente cruzado de mitigação.

  FVG: gap de preço entre 3 velas (low actual > high de 2 atrás = bull FVG)
  OB:  última vela bearish antes de impulso bull (e vice-versa)
  Liquidity Sweep: high actual > high anterior do range, mas close volta atrás
  S/R: pivots clássicos com largura configurável
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from app.services.instdash.indicators import atr


def detect_fvg(df: pd.DataFrame, min_pct: float = 0.1) -> dict:
    """Detecta o FVG mais recente bull e bear ainda não mitigado.

    Bull FVG: low[i] > high[i-2] (gap por baixo, espera-se preenchimento)
    Bear FVG: high[i] < low[i-2]

    min_pct: tamanho mínimo do gap em % do preço

    Devolve:
      {
        'bull_top': float | None,      # topo do gap bull (low[i])
        'bull_bot': float | None,      # base do gap bull (high[i-2])
        'bear_top': float | None,      # topo do gap bear (low[i-2])
        'bear_bot': float | None,      # base do gap bear (high[i])
        'in_bull_fvg': bool,           # close actual dentro do bull FVG
        'in_bear_fvg': bool,
      }
    """
    if len(df) < 3:
        return _empty_fvg()

    high = df['high'].values
    low  = df['low'].values
    close = df['close'].values
    n = len(df)
    current_close = close[-1]

    bull_top = bull_bot = None
    bear_top = bear_bot = None

    # Procurar do mais recente para o mais antigo, parar no primeiro não mitigado
    for i in range(n - 1, 1, -1):
        # Bull FVG candidato
        if bull_top is None:
            if low[i] > high[i - 2]:
                gap_pct = (low[i] - high[i - 2]) / high[i - 2] * 100
                if gap_pct >= min_pct:
                    candidate_top = float(low[i])
                    candidate_bot = float(high[i - 2])
                    # Verificar se foi mitigado: alguma vela depois fechou abaixo do bot
                    mitigated = any(close[j] < candidate_bot for j in range(i + 1, n))
                    if not mitigated:
                        bull_top, bull_bot = candidate_top, candidate_bot
        # Bear FVG candidato
        if bear_top is None:
            if high[i] < low[i - 2]:
                gap_pct = (low[i - 2] - high[i]) / low[i - 2] * 100
                if gap_pct >= min_pct:
                    candidate_top = float(low[i - 2])
                    candidate_bot = float(high[i])
                    mitigated = any(close[j] > candidate_top for j in range(i + 1, n))
                    if not mitigated:
                        bear_top, bear_bot = candidate_top, candidate_bot
        if bull_top is not None and bear_top is not None:
            break

    in_bull_fvg = bull_top is not None and bull_bot <= current_close <= bull_top
    in_bear_fvg = bear_top is not None and bear_bot <= current_close <= bear_top

    return {
        'bull_top': bull_top, 'bull_bot': bull_bot,
        'bear_top': bear_top, 'bear_bot': bear_bot,
        'in_bull_fvg': in_bull_fvg, 'in_bear_fvg': in_bear_fvg,
    }


def _empty_fvg() -> dict:
    return {'bull_top': None, 'bull_bot': None, 'bear_top': None, 'bear_bot': None,
            'in_bull_fvg': False, 'in_bear_fvg': False}


def detect_order_blocks(df: pd.DataFrame, ob_len: int = 5, strength_atr: float = 1.5) -> dict:
    """Detecta o último OB bullish e bearish ainda não mitigado.

    Bull OB: vela bearish imediatamente antes de um movimento impulsivo bull
             (close - close[ob_len] > ATR * strength)
    Bear OB: simétrico.
    """
    if len(df) < ob_len + 14:
        return _empty_ob()

    atr_v = atr(df, 14)
    high = df['high'].values
    low  = df['low'].values
    open_ = df['open'].values
    close = df['close'].values
    atr_arr = atr_v.values
    n = len(df)
    current_close = close[-1]

    bull_top = bull_bot = None
    bear_top = bear_bot = None

    for i in range(n - 1, ob_len, -1):
        # Bull impulse?
        if bull_top is None:
            if (close[i] - close[i - ob_len]) > atr_arr[i] * strength_atr and close[i] > open_[i]:
                # Bull OB = vela bearish em i-ob_len
                ob_top = float(open_[i - ob_len])
                ob_bot = float(close[i - ob_len])
                if ob_top > ob_bot:
                    # Verificar mitigação
                    mitigated = any(close[j] < ob_bot for j in range(i + 1, n))
                    if not mitigated:
                        bull_top, bull_bot = ob_top, ob_bot
        # Bear impulse?
        if bear_top is None:
            if (close[i - ob_len] - close[i]) > atr_arr[i] * strength_atr and close[i] < open_[i]:
                ob_top = float(close[i - ob_len])
                ob_bot = float(open_[i - ob_len])
                if ob_top > ob_bot:
                    mitigated = any(close[j] > ob_top for j in range(i + 1, n))
                    if not mitigated:
                        bear_top, bear_bot = ob_top, ob_bot
        if bull_top is not None and bear_top is not None:
            break

    in_bull_ob = bull_top is not None and bull_bot <= current_close <= bull_top
    in_bear_ob = bear_top is not None and bear_bot <= current_close <= bear_top

    return {
        'bull_top': bull_top, 'bull_bot': bull_bot,
        'bear_top': bear_top, 'bear_bot': bear_bot,
        'in_bull_ob': in_bull_ob, 'in_bear_ob': in_bear_ob,
    }


def _empty_ob() -> dict:
    return {'bull_top': None, 'bull_bot': None, 'bear_top': None, 'bear_bot': None,
            'in_bull_ob': False, 'in_bear_ob': False}


def detect_liquidity_sweeps(df: pd.DataFrame, lookback: int = 20) -> dict:
    """Detecta sweeps de liquidez na última vela e níveis de liquidez actuais.

    Sweep High: high actual > maior high dos últimos N (excluindo actual) E close < esse high
    Sweep Low: simétrico
    """
    if len(df) < lookback + 1:
        return {
            'sweep_high': False, 'sweep_low': False,
            'liq_high': None, 'liq_low': None,
            'near_liq_high': False, 'near_liq_low': False,
        }

    # Maior high dos últimos N (excluindo barra actual) — shift(1) para excluir
    liq_high = df['high'].rolling(lookback).max().shift(1).iloc[-1]
    liq_low  = df['low'].rolling(lookback).min().shift(1).iloc[-1]

    last = df.iloc[-1]
    close = float(last['close'])
    high  = float(last['high'])
    low   = float(last['low'])

    sweep_high = high > liq_high and close < liq_high
    sweep_low  = low  < liq_low  and close > liq_low

    near_liq_high = abs(close - liq_high) / liq_high * 100 < 0.5 if liq_high else False
    near_liq_low  = abs(close - liq_low)  / liq_low  * 100 < 0.5 if liq_low else False

    return {
        'sweep_high': sweep_high, 'sweep_low': sweep_low,
        'liq_high': float(liq_high) if not pd.isna(liq_high) else None,
        'liq_low':  float(liq_low)  if not pd.isna(liq_low)  else None,
        'near_liq_high': near_liq_high, 'near_liq_low': near_liq_low,
    }


def detect_support_resistance(df: pd.DataFrame, sr_left: int = 5, sr_right: int = 2,
                               sr_width_pct: float = 0.5) -> dict:
    """Última faixa de S e R baseada em pivots clássicos.

    Devolve:
      {
        'res_top': float, 'res_mid': float, 'res_bot': float,
        'sup_top': float, 'sup_mid': float, 'sup_bot': float,
        'dist_to_res_pct': float | None,   # % positivo = resistência ainda acima
        'dist_to_sup_pct': float | None,   # % positivo = suporte ainda abaixo
        'near_res': bool,
        'near_sup': bool,
      }
    """
    if len(df) < sr_left + sr_right + 2:
        return _empty_sr()

    high_pivots: list[float] = []
    low_pivots: list[float]  = []
    high = df['high'].values
    low  = df['low'].values
    n = len(df)

    for i in range(sr_left, n - sr_right):
        if all(high[i] >= high[i - j] for j in range(1, sr_left + 1)) and \
           all(high[i] >= high[i + j] for j in range(1, sr_right + 1)):
            high_pivots.append(float(high[i]))
        if all(low[i] <= low[i - j] for j in range(1, sr_left + 1)) and \
           all(low[i] <= low[i + j] for j in range(1, sr_right + 1)):
            low_pivots.append(float(low[i]))

    if not high_pivots or not low_pivots:
        return _empty_sr()

    res_mid = high_pivots[-1]
    sup_mid = low_pivots[-1]
    half = sr_width_pct / 100.0 / 2.0

    res_top = res_mid * (1 + half)
    res_bot = res_mid * (1 - half)
    sup_top = sup_mid * (1 + half)
    sup_bot = sup_mid * (1 - half)

    close = float(df['close'].iloc[-1])
    dist_res = (res_bot - close) / close * 100
    dist_sup = (close - sup_top) / close * 100

    near_res = abs(dist_res) < sr_width_pct * 2
    near_sup = abs(dist_sup) < sr_width_pct * 2

    return {
        'res_top': res_top, 'res_mid': res_mid, 'res_bot': res_bot,
        'sup_top': sup_top, 'sup_mid': sup_mid, 'sup_bot': sup_bot,
        'dist_to_res_pct': round(dist_res, 2),
        'dist_to_sup_pct': round(dist_sup, 2),
        'near_res': near_res, 'near_sup': near_sup,
    }


def _empty_sr() -> dict:
    return {
        'res_top': None, 'res_mid': None, 'res_bot': None,
        'sup_top': None, 'sup_mid': None, 'sup_bot': None,
        'dist_to_res_pct': None, 'dist_to_sup_pct': None,
        'near_res': False, 'near_sup': False,
    }
