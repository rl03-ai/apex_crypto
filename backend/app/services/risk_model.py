"""Risk Model — position sizing, SL/TP dinâmicos, portfolio risk constraints.

Profile Agressivo (default):
  - risk_per_trade: 10% do portfolio
  - max_exposure: 80% do portfolio
  - max_per_coin: 15% do portfolio
  - max_per_sector: 30% do portfolio
  - min_tier: B
"""
import logging
from typing import Literal

log = logging.getLogger(__name__)

RiskProfile = Literal['conservative', 'balanced', 'aggressive']

PROFILES = {
    'conservative': {
        'risk_per_trade': 0.03,    # 3%
        'max_exposure': 0.50,      # 50%
        'max_per_coin': 0.10,      # 10%
        'max_per_sector': 0.20,    # 20%
        'min_tier': 'A',
        'tier_alloc': {'S': 0.10, 'A': 0.05, 'B': 0.0, 'C': 0.0, 'D': 0.0},
    },
    'balanced': {
        'risk_per_trade': 0.05,
        'max_exposure': 0.65,
        'max_per_coin': 0.12,
        'max_per_sector': 0.25,
        'min_tier': 'B',
        'tier_alloc': {'S': 0.12, 'A': 0.08, 'B': 0.05, 'C': 0.0, 'D': 0.0},
    },
    'aggressive': {
        'risk_per_trade': 0.10,
        'max_exposure': 0.80,
        'max_per_coin': 0.15,
        'max_per_sector': 0.30,
        'min_tier': 'B',
        'tier_alloc': {'S': 0.15, 'A': 0.10, 'B': 0.05, 'C': 0.0, 'D': 0.0},
    },
}


def compute_stop_levels(
    price: float,
    atr_pct: float,
    stage: str,
    aligned: bool = False,
) -> dict:
    """Calcula SL/TP dinâmicos baseado em stage + ATR.
    
    Stages:
      - ACCUMULATION: SL apertado (1.5×ATR), TP grande (5×ATR)
      - MARKUP_EARLY: SL moderado (2×ATR abaixo MA21), TP médio (4×ATR)
      - MARKUP_MATURE: SL trailing (2.5×ATR), TP curto (3×ATR)
      - EXTENDED: não recomenda entry — devolve None
      - MARKDOWN/CHOP: não recomenda entry
    
    Args:
        price: preço actual
        atr_pct: ATR como % do preço
        stage: stage detectado
    
    Returns:
        {
            'entry': price,
            'sl': stop loss price,
            'tp1': take profit 1 (50% position out),
            'tp2': take profit 2 (full out),
            'sl_pct': % loss em SL,
            'tp1_pct': % gain em TP1,
            'tp2_pct': % gain em TP2,
            'r_multiple': risk:reward ratio,
            'note': explicação,
        }
        ou {'recommended': False, 'reason': '...'} se stage não permite
    """
    if stage in ('EXTENDED', 'MARKDOWN', 'DISTRIBUTION'):
        return {
            'recommended': False,
            'reason': f'Stage {stage} — não entrar long',
            'entry': price,
        }
    
    atr_value = (atr_pct / 100) * price  # ATR absoluto
    
    if stage == 'ACCUMULATION':
        sl_atr_mult = 1.5
        tp1_atr_mult = 3.0
        tp2_atr_mult = 6.0
        note = 'SL apertado (1.5×ATR), TPs grandes — trade de potencial alto'
    elif stage == 'MARKUP_EARLY':
        sl_atr_mult = 2.0
        tp1_atr_mult = 2.5
        tp2_atr_mult = 5.0
        note = 'SL moderado (2×ATR), TP1 conservador, deixa correr até TP2'
    elif stage == 'MARKUP_MATURE':
        sl_atr_mult = 2.5
        tp1_atr_mult = 2.0
        tp2_atr_mult = 4.0
        note = 'SL trailing (2.5×ATR), TPs curtos — momentum saudável mas evoluído'
    else:  # CHOP
        sl_atr_mult = 2.0
        tp1_atr_mult = 1.5
        tp2_atr_mult = 3.0
        note = 'CHOP — entry pequena, SL apertado'
    
    # Boost se aligned
    if aligned:
        tp1_atr_mult *= 1.2
        tp2_atr_mult *= 1.2
    
    sl = price - (atr_value * sl_atr_mult)
    tp1 = price + (atr_value * tp1_atr_mult)
    tp2 = price + (atr_value * tp2_atr_mult)
    
    sl_pct = ((sl - price) / price) * 100
    tp1_pct = ((tp1 - price) / price) * 100
    tp2_pct = ((tp2 - price) / price) * 100
    
    risk = price - sl
    reward1 = tp1 - price
    reward2 = tp2 - price
    r_multiple_1 = reward1 / risk if risk > 0 else 0
    r_multiple_2 = reward2 / risk if risk > 0 else 0
    
    return {
        'recommended': True,
        'entry': round(price, 6),
        'sl': round(sl, 6),
        'tp1': round(tp1, 6),
        'tp2': round(tp2, 6),
        'sl_pct': round(sl_pct, 2),
        'tp1_pct': round(tp1_pct, 2),
        'tp2_pct': round(tp2_pct, 2),
        'r_multiple_1': round(r_multiple_1, 2),
        'r_multiple_2': round(r_multiple_2, 2),
        'note': note,
    }


def compute_position_size(
    portfolio_usd: float,
    entry_price: float,
    sl_price: float,
    tier: str,
    stage: str,
    profile: RiskProfile = 'aggressive',
    score: int = 0,
) -> dict:
    """Calcula tamanho da posição baseado em risk per trade + tier multiplier.
    
    Formula:
        risk_amount = portfolio × risk_per_trade × tier_multiplier × stage_multiplier
        position_usd = risk_amount / (entry - sl) × entry
        coins = position_usd / entry
    
    Args:
        portfolio_usd: tamanho total do portfolio
        entry_price: preço de entrada
        sl_price: stop loss
        tier: S/A/B/C/D
        stage: stage detectado
        profile: conservative/balanced/aggressive
        score: score raw (-10 a +10) para fine-tune
    
    Returns:
        {
            'position_usd': USD a investir,
            'coins': quantidade de coins,
            'risk_usd': quanto perderia se SL bater,
            'risk_pct': % portfolio em risco,
            'allocated_pct': % portfolio alocado nesta posição,
            'tier_mult': multiplier aplicado,
            'recommended': True/False,
            'warnings': [...],
        }
    """
    p = PROFILES[profile]
    warnings = []
    
    # Tier multiplier (S = 1.5, A = 1.0, B = 0.5, C = 0.25, D = 0)
    tier_mult = {'S': 1.5, 'A': 1.0, 'B': 0.5, 'C': 0.25, 'D': 0.0}.get(tier, 0)
    
    if tier_mult == 0:
        return {
            'recommended': False,
            'reason': f'Tier {tier} abaixo do mínimo ({p["min_tier"]})',
            'position_usd': 0, 'coins': 0, 'risk_usd': 0,
            'risk_pct': 0, 'allocated_pct': 0, 'tier_mult': 0,
            'warnings': [],
        }
    
    # Stage multiplier
    stage_mult = {
        'ACCUMULATION': 1.2,    # boost (alta convicção)
        'MARKUP_EARLY': 1.0,
        'MARKUP_MATURE': 0.8,
        'EXTENDED': 0.0,
        'DISTRIBUTION': 0.0,
        'MARKDOWN': 0.0,
        'CHOP': 0.4,
    }.get(stage, 0.5)
    
    if stage_mult == 0:
        return {
            'recommended': False,
            'reason': f'Stage {stage} — não recomenda entrar long',
            'position_usd': 0, 'coins': 0, 'risk_usd': 0,
            'risk_pct': 0, 'allocated_pct': 0, 'tier_mult': 0,
            'warnings': [],
        }
    
    # Risk amount
    risk_amount = portfolio_usd * p['risk_per_trade'] * tier_mult * stage_mult
    
    # Position size baseada em SL distance
    sl_distance = abs(entry_price - sl_price)
    if sl_distance <= 0:
        return {
            'recommended': False,
            'reason': 'SL inválido',
            'position_usd': 0, 'coins': 0, 'risk_usd': 0,
            'risk_pct': 0, 'allocated_pct': 0, 'tier_mult': tier_mult,
            'warnings': [],
        }
    
    coins = risk_amount / sl_distance
    position_usd = coins * entry_price
    
    # Cap por max_per_coin
    max_per_coin_usd = portfolio_usd * p['max_per_coin']
    if position_usd > max_per_coin_usd:
        warnings.append(f'Capped at {p["max_per_coin"]*100:.0f}% per coin')
        position_usd = max_per_coin_usd
        coins = position_usd / entry_price
        risk_amount = coins * sl_distance  # recalcula risk
    
    return {
        'recommended': True,
        'position_usd': round(position_usd, 2),
        'coins': round(coins, 6),
        'risk_usd': round(risk_amount, 2),
        'risk_pct': round((risk_amount / portfolio_usd) * 100, 2),
        'allocated_pct': round((position_usd / portfolio_usd) * 100, 2),
        'tier_mult': tier_mult,
        'stage_mult': round(stage_mult, 2),
        'warnings': warnings,
    }


def compute_portfolio_risk(
    positions: list[dict],
    portfolio_usd: float,
    profile: RiskProfile = 'aggressive',
) -> dict:
    """Compute portfolio-level risk metrics.
    
    Args:
        positions: lista de dicts com {symbol, sector, value_usd, risk_usd}
        portfolio_usd: tamanho total
        profile: profile name
    
    Returns:
        {
            'total_exposure_pct': %,
            'total_risk_pct': %,
            'sector_breakdown': {sector: {value_usd, pct}},
            'warnings': [...],
            'capacity_remaining_usd': quanto ainda podes adicionar,
        }
    """
    p = PROFILES[profile]
    warnings = []
    
    total_value = sum(pos.get('value_usd', 0) for pos in positions)
    total_risk = sum(pos.get('risk_usd', 0) for pos in positions)
    
    exposure_pct = (total_value / portfolio_usd * 100) if portfolio_usd > 0 else 0
    risk_pct = (total_risk / portfolio_usd * 100) if portfolio_usd > 0 else 0
    
    # Sector breakdown
    sector_totals = {}
    for pos in positions:
        sector = pos.get('sector', 'unknown')
        sector_totals[sector] = sector_totals.get(sector, 0) + pos.get('value_usd', 0)
    
    sector_breakdown = {
        sector: {
            'value_usd': round(value, 2),
            'pct': round((value / portfolio_usd * 100), 2) if portfolio_usd > 0 else 0,
        }
        for sector, value in sector_totals.items()
    }
    
    # Warnings
    if exposure_pct > p['max_exposure'] * 100:
        warnings.append(f'⚠ Exposição {exposure_pct:.1f}% excede max {p["max_exposure"]*100:.0f}%')
    
    for sector, data in sector_breakdown.items():
        if data['pct'] > p['max_per_sector'] * 100:
            warnings.append(f'⚠ Sector {sector}: {data["pct"]:.1f}% excede max {p["max_per_sector"]*100:.0f}%')
    
    # Capacity remaining
    max_value = portfolio_usd * p['max_exposure']
    capacity = max(0, max_value - total_value)
    
    return {
        'total_exposure_pct': round(exposure_pct, 2),
        'total_risk_pct': round(risk_pct, 2),
        'positions_count': len(positions),
        'sector_breakdown': sector_breakdown,
        'warnings': warnings,
        'capacity_remaining_usd': round(capacity, 2),
        'profile': profile,
        'limits': {
            'max_exposure_pct': p['max_exposure'] * 100,
            'max_per_coin_pct': p['max_per_coin'] * 100,
            'max_per_sector_pct': p['max_per_sector'] * 100,
            'risk_per_trade_pct': p['risk_per_trade'] * 100,
            'min_tier': p['min_tier'],
        },
    }
