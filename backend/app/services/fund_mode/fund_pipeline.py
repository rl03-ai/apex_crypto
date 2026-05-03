"""Fund Mode Pipeline — Orquestra regime weighting, sector allocation, risk sizing, correlation."""
import logging
from app.services.fund_mode.regime_weighting import RegimeWeighting, apply_regime_to_matrix_row
from app.services.fund_mode.sector_allocation import apply_sector_allocation, get_sector
from app.services.fund_mode.risk_based_sizing import PositionSizing, RiskProfile
from app.services.fund_mode.correlation_tracking import CorrelationTracker

log = logging.getLogger(__name__)


class FundModePipeline:
    """End-to-end fund-mode processing."""
    
    def __init__(self, portfolio_usd: float = 100000):
        self.portfolio_usd = portfolio_usd
        self.risk_profile = RiskProfile(
            portfolio_usd=portfolio_usd,
            risk_per_trade=0.02,  # 2% per trade
            max_exposure_pct=0.50,
            max_positions=20,
            max_per_sector=0.30,
            max_per_symbol=0.15,
        )
        self.position_sizer = PositionSizing(self.risk_profile)
    
    def process_matrix(self, rows: list[dict]) -> tuple[list[dict], dict]:
        """Full fund-mode pipeline for matrix rows.
        
        Steps:
          1. Apply regime weighting (HTF trend modifies scores)
          2. Apply correlation penalties
          3. Sector-first allocation
          4. Risk-based position sizing
          5. Final ranking
        
        Returns:
            (processed_rows, summary)
        """
        if not rows:
            return [], {}
        
        log.info(f'Fund Mode: Processing {len(rows)} symbols')
        
        # Step 1: Regime weighting
        log.info('Step 1: Regime weighting')
        rows = [apply_regime_to_matrix_row(row) for row in rows]
        
        # Step 2: Correlation penalties
        log.info('Step 2: Correlation penalties')
        rows = CorrelationTracker.apply_correlation_penalties(rows, max_correlation=0.80)
        
        # Step 3: Sector allocation (top-down)
        log.info('Step 3: Sector allocation')
        rows, sector_summary = apply_sector_allocation(
            rows,
            max_sector_exposure=self.risk_profile.max_per_sector,
            max_positions=self.risk_profile.max_positions,
        )
        
        # Step 4: Risk-based position sizing
        log.info('Step 4: Risk-based sizing')
        rows = self.position_sizer.size_positions(rows)
        
        # Step 5: Filter valid positions
        rows = [r for r in rows if r.get('position_size_usd', 0) > 0]
        
        # Final sort by position size
        rows.sort(key=lambda r: r.get('position_size_usd', 0), reverse=True)
        
        # Summary
        total_exposure = sum(r.get('position_size_usd', 0) for r in rows)
        summary = {
            'pipeline': 'fund_mode',
            'input_count': len(rows),
            'output_count': len(rows),
            'total_exposure_usd': total_exposure,
            'total_exposure_pct': total_exposure / self.portfolio_usd * 100,
            'sector_summary': sector_summary,
            'positions': [
                {
                    'symbol': r.get('symbol'),
                    'sector': r.get('sector'),
                    'position_usd': r.get('position_size_usd', 0),
                    'units': r.get('position_units', 0),
                    'score': r.get('composite', 0),
                    'tier': r.get('tier'),
                }
                for r in rows
            ],
        }
        
        return rows, summary
