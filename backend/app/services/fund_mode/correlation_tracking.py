"""Correlation Tracking — Monitor portfolio coherence.

Fund principle: If 2 positions correlate >0.80, they're functionally the same bet.
Reduce position or skip one.

Correlation categories:
  >0.90: Identical behavior (almost never buy together)
  0.80-0.90: Highly correlated (caution)
  0.60-0.80: Correlated (acceptable with reason)
  <0.60: Diversifying (good)
  <0: Hedging (great)
"""
import logging
from collections import defaultdict

log = logging.getLogger(__name__)


class CorrelationTracker:
    """Track correlations between positions."""
    
    # Hardcoded correlation matrix (updated monthly in real fund)
    # Based on historical BTC/ETH relationship + sector groups
    DEFAULT_CORRELATIONS = {
        # Bitcoin group
        ('BTC', 'WBTC'): 0.99,
        ('BTC', 'CBBTC'): 0.98,
        
        # Ethereum group
        ('ETH', 'STETH'): 0.95,
        ('ETH', 'WSTETH'): 0.94,
        
        # BTC vs ETH
        ('BTC', 'ETH'): 0.80,
        
        # L1s (correlate with ETH ~0.70)
        ('SOL', 'ADA'): 0.72,
        ('SOL', 'AVAX'): 0.70,
        ('ADA', 'AVAX'): 0.68,
        
        # DeFi (high correlation with ETH)
        ('UNI', 'AAVE'): 0.85,
        ('AAVE', 'COMPOUND'): 0.82,
        ('UNI', 'ETH'): 0.78,
        
        # Memes (lower correlation, more volatile)
        ('DOGE', 'SHIB'): 0.65,
        ('PEPE', 'WIF'): 0.55,
        ('DOGE', 'BTC'): 0.70,
        
        # AI (emerging, lower correlation)
        ('FET', 'RENDER'): 0.50,
        ('FET', 'ETH'): 0.45,
    }
    
    @staticmethod
    def get_correlation(sym1: str, sym2: str) -> float:
        """Get correlation between 2 symbols (0-1)."""
        # Normalize symbols
        s1, s2 = sym1.replace('USDT', ''), sym2.replace('USDT', '')
        if s1 == s2:
            return 1.0
        
        # Lookup (order doesn't matter)
        key = tuple(sorted([s1, s2]))
        corr = CorrelationTracker.DEFAULT_CORRELATIONS.get(key)
        
        if corr is not None:
            return corr
        
        # Fallback: if both in same sector, assume 0.70
        from app.services.fund_mode.sector_allocation import get_sector
        if get_sector(s1) == get_sector(s2):
            return 0.70
        
        # Different sectors: low correlation
        return 0.30
    
    @staticmethod
    def flag_correlated_pairs(rows: list[dict], max_correlation: float = 0.80) -> dict:
        """Flag pairs with correlation > threshold.
        
        Returns:
            {(sym1, sym2): correlation, ...}
        """
        flagged = {}
        
        for i, row1 in enumerate(rows):
            sym1 = row1.get('symbol', '').replace('USDT', '')
            for row2 in rows[i+1:]:
                sym2 = row2.get('symbol', '').replace('USDT', '')
                corr = CorrelationTracker.get_correlation(sym1, sym2)
                
                if corr > max_correlation:
                    flagged[(sym1, sym2)] = corr
        
        return flagged
    
    @staticmethod
    def apply_correlation_penalties(
        rows: list[dict],
        max_correlation: float = 0.80,
    ) -> list[dict]:
        """Apply correlation penalties to scores.
        
        If symbol has high correlation with others in portfolio:
        - Reduce score by (correlation - 0.80) × 5 points
        """
        # First pass: identify all correlations
        corr_map = defaultdict(list)
        for i, row1 in enumerate(rows):
            sym1 = row1.get('symbol', '').replace('USDT', '')
            for row2 in rows[i+1:]:
                sym2 = row2.get('symbol', '').replace('USDT', '')
                corr = CorrelationTracker.get_correlation(sym1, sym2)
                
                if corr > max_correlation:
                    corr_map[sym1].append((sym2, corr))
                    corr_map[sym2].append((sym1, corr))
        
        # Second pass: apply penalties
        for row in rows:
            sym = row.get('symbol', '').replace('USDT', '')
            corr_list = corr_map.get(sym, [])
            
            if corr_list:
                # Average correlation excess
                avg_excess = sum(c - max_correlation for _, c in corr_list) / len(corr_list)
                penalty = avg_excess * 5  # Scale to score points
                
                original = row.get('composite', 0)
                row['composite'] = max(-99, original - penalty)
                row['correlation_penalty'] = penalty
                row['correlation_conflicts'] = [s for s, _ in corr_list]
        
        return rows
