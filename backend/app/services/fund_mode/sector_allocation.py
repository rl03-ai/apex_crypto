"""Sector Allocation Module — Top-down allocation (sector first, then symbol).

Fund allocation flow:
  1. Detect sector of each asset
  2. Aggregate scores by sector
  3. Rank sectors by strength (weighted score)
  4. Allocate % per sector (with diversification limits)
  5. Within sector, pick top symbols

Sector map (simplified):
  Bitcoin: BTC
  Ethereum: ETH, STETH, WSTETH, CBBTC
  L1: SOL, ADA, AVAX, POLKA, NEAR
  L2: OP, ARB, STRK, MANTA
  DeFi: UNI, AAVE, COMPOUND, CURVE, LIDO, MAKER
  AI: FET, RENDER, AGIX
  Memes: DOGE, SHIB, PEPE, WIF
  Gaming: AXS, SAND, ENJ, FLOW
  Oracle: LINK, BAND, PYTH, TELLOR
  Storage: FIL, AR, STORJ
  RWA: ONDO, TBX, PAXG
  Privacy: MONERO, ZCASH
  NFT: BLUR, LOOKS
"""
import logging
from collections import defaultdict

log = logging.getLogger(__name__)


SECTOR_MAP = {
    'Bitcoin': {'BTC', 'WBTC', 'CBBTC'},
    'Ethereum': {'ETH', 'STETH', 'WSTETH'},
    'L1': {'SOL', 'ADA', 'AVAX', 'DOT', 'NEAR', 'ATOM', 'APTOS', 'SUI'},
    'L2': {'OP', 'ARB', 'STRK', 'MANTA', 'SCROLL'},
    'DeFi': {'UNI', 'AAVE', 'COMPOUND', 'CURVE', 'LIDO', 'MAKER', 'GMX', 'DYDX'},
    'AI': {'FET', 'RENDER', 'AGIX', 'TAO', 'NMT', 'ARKM'},
    'Memes': {'DOGE', 'SHIB', 'PEPE', 'WIF', 'BONK', 'FLOKI'},
    'Gaming': {'AXS', 'SAND', 'ENJ', 'FLOW', 'GALA', 'IMX'},
    'Oracle': {'LINK', 'BAND', 'PYTH', 'API3'},
    'Storage': {'FIL', 'AR', 'STORJ'},
    'RWA': {'ONDO', 'PAXG', 'IBIT', 'GBTC'},
    'Privacy': {'MONERO', 'ZCASH', 'RAILGUN'},
    'NFT': {'BLUR', 'LOOKS'},
}


def get_sector(symbol: str) -> str | None:
    """Return sector for symbol, or None if unknown."""
    sym = symbol.replace('USDT', '').upper()
    for sector, symbols in SECTOR_MAP.items():
        if sym in symbols:
            return sector
    return None


def aggregate_by_sector(rows: list[dict]) -> dict[str, list[dict]]:
    """Group rows by sector, maintaining order."""
    by_sector = defaultdict(list)
    for row in rows:
        sym = row.get('symbol', '').replace('USDT', '')
        sector = get_sector(sym)
        if sector:
            by_sector[sector].append(row)
        else:
            # Unknown sector — treat as own sector
            by_sector[f'_unknown_{sym}'].append(row)
    
    # Sort within each sector by composite score desc
    for sector in by_sector:
        by_sector[sector].sort(key=lambda r: r.get('composite', 0), reverse=True)
    
    return dict(by_sector)


def rank_sectors(by_sector: dict[str, list[dict]]) -> list[tuple[str, float, int]]:
    """Rank sectors by weighted score (avg of top 3 in sector).
    
    Returns:
        [(sector, weighted_avg_score, position_count), ...]
    """
    sector_scores = []
    
    for sector, rows in by_sector.items():
        if not rows:
            continue
        
        # Weighted average: top 3 assets, weighted by position
        top_3 = sorted(rows, key=lambda r: r.get('composite', 0), reverse=True)[:3]
        avg_score = sum(r.get('composite', 0) for r in top_3) / len(top_3) if top_3 else 0
        
        # Count assets with action BUY+
        buy_count = sum(1 for r in rows if r.get('action') in ('STRONG BUY', 'BUY'))
        
        sector_scores.append((sector, avg_score, buy_count))
    
    # Sort by weighted score desc
    sector_scores.sort(key=lambda x: (x[1], x[2]), reverse=True)
    
    return sector_scores


def allocate_sector_limits(
    sector_rankings: list[tuple[str, float, int]],
    max_sector_exposure: float = 0.30,
    max_positions: int = 20,
) -> dict[str, float]:
    """Allocate % exposure per sector.
    
    Args:
        sector_rankings: List of (sector, score, count)
        max_sector_exposure: Max % in single sector (default 30%)
        max_positions: Max symbols across all sectors
    
    Returns:
        {sector: allocation_pct}
    """
    if not sector_rankings:
        return {}
    
    total_score = sum(score for _, score, _ in sector_rankings)
    if total_score <= 0:
        # Fallback: equal weight
        n_sectors = len(sector_rankings)
        return {sector: 1.0 / n_sectors for sector, _, _ in sector_rankings}
    
    # Proportional allocation, capped at max_sector_exposure
    allocations = {}
    for sector, score, _ in sector_rankings:
        prop = score / total_score
        capped = min(prop, max_sector_exposure)
        allocations[sector] = capped
    
    # Renormalize to 1.0
    total_alloc = sum(allocations.values())
    if total_alloc > 0:
        allocations = {s: (a / total_alloc) for s, a in allocations.items()}
    
    return allocations


def apply_sector_allocation(
    rows: list[dict],
    max_sector_exposure: float = 0.30,
    max_positions: int = 20,
) -> tuple[list[dict], dict]:
    """Apply sector-first allocation to matrix rows.
    
    Returns:
        (updated_rows, allocation_summary)
    """
    by_sector = aggregate_by_sector(rows)
    sector_rankings = rank_sectors(by_sector)
    sector_allocs = allocate_sector_limits(
        sector_rankings,
        max_sector_exposure=max_sector_exposure,
        max_positions=max_positions,
    )
    
    # Update rows with sector + allocation info
    for row in rows:
        sym = row.get('symbol', '').replace('USDT', '')
        sector = get_sector(sym)
        row['sector'] = sector or 'Unknown'
        row['sector_allocation'] = sector_allocs.get(sector or 'Unknown', 0)
    
    # Rank within sectors by composite, pick top N per sector
    final_rows = []
    sector_position_count = defaultdict(int)
    
    for sector in sorted(by_sector.keys(), 
                        key=lambda s: sector_allocs.get(s, 0), reverse=True):
        rows_in_sector = sorted(
            by_sector[sector],
            key=lambda r: r.get('composite', 0),
            reverse=True
        )
        
        # Limit by allocation (rough: if sector 20%, pick top 20% of max_positions)
        sector_alloc = sector_allocs.get(sector, 0)
        max_in_sector = max(1, int(max_positions * sector_alloc + 0.5))
        
        for row in rows_in_sector[:max_in_sector]:
            final_rows.append(row)
            sector_position_count[sector] += 1
    
    summary = {
        'sector_rankings': sector_rankings,
        'sector_allocations': sector_allocs,
        'sector_position_count': dict(sector_position_count),
    }
    
    return final_rows, summary
