"""Strategy Model — allocation por convicção, DCA scheduler, sector rotation.

Components:
  1. Allocation: % portfolio por tier (S=15%, A=10%, B=5%)
  2. DCA Scheduler: regras baseadas em stage
     - ACCUMULATION: lump sum 50% + DCA 50% (4 semanas)
     - MARKUP_EARLY: lump sum 100% (não esperar)
     - MARKUP_MATURE: DCA gradual 100% (4 semanas)
     - EXTENDED: WAIT (não entrar)
  3. Sector Rotation: força relativa entre sectores
"""
import logging

log = logging.getLogger(__name__)


# Sector mapping (symbol → sector)
SECTOR_MAP = {
    # Layer 1
    'BTC': 'Bitcoin', 'ETH': 'Ethereum',
    'SOL': 'L1', 'ADA': 'L1', 'AVAX': 'L1', 'DOT': 'L1', 'NEAR': 'L1',
    'ATOM': 'L1', 'TON': 'L1', 'SUI': 'L1', 'APT': 'L1', 'ALGO': 'L1',
    'HBAR': 'L1', 'ICP': 'L1', 'SEI': 'L1', 'TIA': 'L1', 'INJ': 'L1',
    'XRP': 'L1', 'LTC': 'L1', 'XLM': 'L1', 'BNB': 'L1', 'TRX': 'L1',
    'BCH': 'L1', 'ETC': 'L1', 'XMR': 'L1', 'KAS': 'L1',
    
    # Layer 2 / Scaling
    'MATIC': 'L2', 'ARB': 'L2', 'OP': 'L2', 'IMX': 'L2', 'STRK': 'L2',
    'STX': 'L2', 'MNT': 'L2', 'METIS': 'L2',
    
    # DeFi
    'UNI': 'DeFi', 'AAVE': 'DeFi', 'MKR': 'DeFi', 'CRV': 'DeFi',
    'SNX': 'DeFi', 'COMP': 'DeFi', 'LDO': 'DeFi', 'ENA': 'DeFi',
    'PENDLE': 'DeFi', 'GMX': 'DeFi', 'JUP': 'DeFi', 'JTO': 'DeFi',
    'DYDX': 'DeFi', 'SUSHI': 'DeFi',
    
    # AI
    'RNDR': 'AI', 'FET': 'AI', 'OCEAN': 'AI', 'AGIX': 'AI', 'TAO': 'AI',
    'WLD': 'AI', 'AKT': 'AI',
    
    # Memes
    'DOGE': 'Memes', 'SHIB': 'Memes', 'PEPE': 'Memes', 'WIF': 'Memes',
    'BONK': 'Memes', 'FLOKI': 'Memes', 'BOME': 'Memes', 'NEIRO': 'Memes',
    
    # Gaming/Metaverse
    'AXS': 'Gaming', 'SAND': 'Gaming', 'MANA': 'Gaming', 'IMX': 'Gaming',
    'GALA': 'Gaming', 'APE': 'Gaming', 'ENJ': 'Gaming',
    
    # Oracle/Data
    'LINK': 'Oracle', 'GRT': 'Oracle', 'PYTH': 'Oracle', 'API3': 'Oracle',
    
    # Storage
    'FIL': 'Storage', 'AR': 'Storage',
    
    # Privacy
    'XMR': 'Privacy', 'ZEC': 'Privacy', 'DASH': 'Privacy',
    
    # RWA / Tokenization
    'ONDO': 'RWA', 'POLYX': 'RWA',
    
    # NFT/Social
    'BLUR': 'NFT', 'FLOW': 'NFT',
    
    # Misc
    'ORDI': 'Bitcoin Ecosystem',
    'THETA': 'Media', 'VET': 'Supply Chain',
}


def get_sector(symbol: str) -> str:
    """Devolve sector para um símbolo."""
    s = symbol.upper().replace('USDT', '').strip()
    return SECTOR_MAP.get(s, 'Other')


def compute_dca_schedule(stage: str, score: int) -> dict:
    """Compute DCA strategy baseada em stage.
    
    Args:
        stage: stage detectado
        score: score raw
    
    Returns:
        {
            'mode': 'lump_sum' | 'dca' | 'split' | 'wait',
            'lump_sum_pct': % lump sum imediato (0-100),
            'dca_pct': % via DCA (0-100),
            'dca_weeks': semanas para distribuir DCA,
            'dca_intervals': quantas compras (semanal),
            'note': explicação,
        }
    """
    if stage == 'ACCUMULATION':
        return {
            'mode': 'split',
            'lump_sum_pct': 50,
            'dca_pct': 50,
            'dca_weeks': 4,
            'dca_intervals': 4,
            'note': '50% lump sum agora (alta convicção) + 50% DCA semanal por 4 semanas',
        }
    elif stage == 'MARKUP_EARLY':
        return {
            'mode': 'lump_sum',
            'lump_sum_pct': 100,
            'dca_pct': 0,
            'dca_weeks': 0,
            'dca_intervals': 0,
            'note': '100% lump sum — breakout confirmado, não esperar',
        }
    elif stage == 'MARKUP_MATURE':
        return {
            'mode': 'dca',
            'lump_sum_pct': 0,
            'dca_pct': 100,
            'dca_weeks': 4,
            'dca_intervals': 4,
            'note': '100% DCA gradual por 4 semanas — trend mature, espera dips',
        }
    elif stage in ('EXTENDED', 'DISTRIBUTION'):
        return {
            'mode': 'wait',
            'lump_sum_pct': 0,
            'dca_pct': 0,
            'dca_weeks': 0,
            'dca_intervals': 0,
            'note': '⚠ WAIT — setup esticado, espera correção/reset',
        }
    elif stage == 'MARKDOWN':
        return {
            'mode': 'wait',
            'lump_sum_pct': 0,
            'dca_pct': 0,
            'dca_weeks': 0,
            'dca_intervals': 0,
            'note': '⚠ WAIT — bear trend, espera reversão (CHoCH bull HTF)',
        }
    else:  # CHOP
        return {
            'mode': 'dca',
            'lump_sum_pct': 0,
            'dca_pct': 100,
            'dca_weeks': 8,
            'dca_intervals': 8,
            'note': 'CHOP — DCA muito gradual (8 semanas) ou ignora',
        }


def compute_sector_rotation(matrix_rows: list[dict]) -> dict:
    """Detect sector rotation: força relativa entre sectores.
    
    Para cada sector, calcula:
      - avg composite score
      - count de coins em ACCUMULATION/EARLY (bullish setups)
      - count de coins em EXTENDED/MARKDOWN (bearish/avoid)
      - signal: OVERWEIGHT / NEUTRAL / UNDERWEIGHT
    
    Args:
        matrix_rows: rows do decision matrix
    
    Returns:
        {
            'rotation_signal': 'L1 → DeFi' or similar,
            'sectors': [
                {sector, avg_score, bullish_count, extended_count, signal, top_picks},
                ...
            ]
        }
    """
    sectors_data = {}
    
    for row in matrix_rows:
        symbol = row.get('symbol', '').replace('USDT', '')
        sector = get_sector(symbol)
        
        if sector not in sectors_data:
            sectors_data[sector] = {
                'sector': sector,
                'rows': [],
                'composite_sum': 0,
                'bullish_count': 0,
                'extended_count': 0,
                'count': 0,
            }
        
        s = sectors_data[sector]
        s['rows'].append(row)
        s['composite_sum'] += row.get('composite', 0)
        s['count'] += 1
        
        stage_1d = row.get('stage_1d', {}).get('stage', '')
        stage_1w = (row.get('stage_1w') or {}).get('stage', '')
        
        if stage_1d in ('ACCUMULATION', 'MARKUP_EARLY') or stage_1w in ('ACCUMULATION', 'MARKUP_EARLY'):
            s['bullish_count'] += 1
        if stage_1d in ('EXTENDED', 'MARKDOWN') or stage_1w in ('EXTENDED', 'MARKDOWN'):
            s['extended_count'] += 1
    
    # Compute signal per sector
    sectors_list = []
    for sector, data in sectors_data.items():
        avg_score = data['composite_sum'] / data['count'] if data['count'] > 0 else 0
        bullish_pct = data['bullish_count'] / data['count'] * 100 if data['count'] > 0 else 0
        extended_pct = data['extended_count'] / data['count'] * 100 if data['count'] > 0 else 0
        
        # Signal logic
        if avg_score >= 5 or bullish_pct >= 50:
            signal = 'OVERWEIGHT'
        elif avg_score <= -3 or extended_pct >= 50:
            signal = 'UNDERWEIGHT'
        else:
            signal = 'NEUTRAL'
        
        # Top picks: as 3 melhores composite scores do sector
        top_picks = sorted(data['rows'], key=lambda r: r.get('composite', 0), reverse=True)[:3]
        top_picks_simple = [
            {
                'symbol': p['symbol'],
                'composite': p['composite'],
                'tier': p['tier'],
                'action': p['action'],
            }
            for p in top_picks
        ]
        
        sectors_list.append({
            'sector': sector,
            'count': data['count'],
            'avg_score': round(avg_score, 2),
            'bullish_count': data['bullish_count'],
            'bullish_pct': round(bullish_pct, 1),
            'extended_count': data['extended_count'],
            'extended_pct': round(extended_pct, 1),
            'signal': signal,
            'top_picks': top_picks_simple,
        })
    
    # Sort by avg_score DESC
    sectors_list.sort(key=lambda s: s['avg_score'], reverse=True)
    
    # Rotation signal: top sector vs bottom sector
    rotation_signal = None
    if len(sectors_list) >= 2:
        top = sectors_list[0]
        bottom = sectors_list[-1]
        if top['signal'] == 'OVERWEIGHT' and bottom['signal'] == 'UNDERWEIGHT':
            rotation_signal = f'{bottom["sector"]} → {top["sector"]}'
    
    return {
        'rotation_signal': rotation_signal,
        'sectors': sectors_list,
    }


def compute_strategy_recommendations(
    matrix_rows: list[dict],
    portfolio_usd: float,
    profile: str = 'aggressive',
) -> dict:
    """Compute full strategy recommendations: top picks + allocation + DCA.
    
    Args:
        matrix_rows: full decision matrix
        portfolio_usd: portfolio total
        profile: risk profile
    
    Returns:
        {
            'top_picks': [
                {symbol, tier, alloc_pct, alloc_usd, dca, sl_tp, reasons},
                ...
            ],
            'sector_rotation': {...},
            'profile': 'aggressive',
        }
    """
    from app.services.risk_model import PROFILES
    
    p = PROFILES[profile]
    tier_alloc = p['tier_alloc']
    tier_order = {'S': 5, 'A': 4, 'B': 3, 'C': 2, 'D': 1}
    min_tier_value = tier_order.get(p['min_tier'], 3)
    
    # Filter eligible rows (tier >= min, action != AVOID)
    eligible = [
        r for r in matrix_rows
        if tier_order.get(r['tier'], 0) >= min_tier_value
        and r.get('action') not in ('AVOID', 'WATCH')
    ]
    
    # Sort by composite DESC
    eligible.sort(key=lambda r: r['composite'], reverse=True)
    
    # Build top picks
    top_picks = []
    total_alloc = 0
    
    for row in eligible:
        tier = row['tier']
        alloc_pct = tier_alloc.get(tier, 0)
        if alloc_pct == 0:
            continue
        
        # Cap if total exceeds max_exposure
        if total_alloc + alloc_pct > p['max_exposure']:
            alloc_pct = max(0, p['max_exposure'] - total_alloc)
            if alloc_pct < 0.01:  # too small
                continue
        
        total_alloc += alloc_pct
        alloc_usd = portfolio_usd * alloc_pct
        
        # DCA strategy
        stage_for_dca = row['stage_1d']['stage']
        dca = compute_dca_schedule(stage_for_dca, row['stage_1d']['score'])
        
        top_picks.append({
            'symbol': row['symbol'],
            'sector': get_sector(row['symbol']),
            'tier': tier,
            'composite': row['composite'],
            'action': row['action'],
            'stage_1d': row['stage_1d']['stage'],
            'stage_1w': (row.get('stage_1w') or {}).get('stage'),
            'alloc_pct': round(alloc_pct * 100, 2),
            'alloc_usd': round(alloc_usd, 2),
            'lump_sum_usd': round(alloc_usd * dca['lump_sum_pct'] / 100, 2),
            'dca_total_usd': round(alloc_usd * dca['dca_pct'] / 100, 2),
            'dca_weekly_usd': round(alloc_usd * dca['dca_pct'] / 100 / dca['dca_intervals'], 2) if dca['dca_intervals'] > 0 else 0,
            'dca_mode': dca['mode'],
            'dca_weeks': dca['dca_weeks'],
            'dca_note': dca['note'],
        })
        
        # Stop after we hit max_exposure
        if total_alloc >= p['max_exposure']:
            break
    
    # Sector rotation
    sector_data = compute_sector_rotation(matrix_rows)
    
    return {
        'profile': profile,
        'portfolio_usd': portfolio_usd,
        'total_alloc_pct': round(total_alloc * 100, 2),
        'remaining_cash_pct': round((1 - total_alloc) * 100, 2),
        'remaining_cash_usd': round(portfolio_usd * (1 - total_alloc), 2),
        'top_picks': top_picks,
        'sector_rotation': sector_data,
    }
