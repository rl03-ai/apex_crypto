"""Fund Mode Pipeline — Simplified: sector allocation + phase weighting + risk sizing + phase strength."""
import logging
from app.services.fund_mode.regime_weighting import apply_phase_weighting
from app.services.fund_mode.sector_allocation import apply_sector_allocation
from app.services.fund_mode.risk_based_sizing import PositionSizing, RiskProfile
from app.services.fund_mode.correlation_tracking import CorrelationTracker
from app.services.phase_strength_detector import apply_phase_strength

log = logging.getLogger(__name__)


class FundModePipeline:
    """Institutional fund mode: phase-based + sector-first + risk-sized."""
    
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
    
    def process(self, rows: list[dict]) -> tuple[list[dict], dict]:
        """Full fund-mode pipeline.
        
        Steps:
          1. Apply phase-based weighting (ACCUM ×1.5, MANIP ×1.0, DIST ×0.3)
          2. Apply correlation penalties (flag >0.80 correlations)
          3. Sector-first allocation
          4. Risk-based position sizing
          5. Final ranking
        """
        if not rows:
            return [], {}
        
        log.info(f'Fund Mode: Processing {len(rows)} symbols, ${self.portfolio_usd} portfolio')
        
        # Step 1: Phase weighting
        log.info('Step 1: Phase weighting (ACCUM ×1.5, MANIP ×1.0, DIST ×0.3)')
        rows = [apply_phase_weighting(row) for row in rows]
        
        # Step 1.5: Phase strength analysis (new!)
        log.info('Step 1.5: Phase strength analysis (transition warnings)')
        rows = [apply_phase_strength(row) for row in rows]
        
        # Step 2: Correlation penalties
        log.info('Step 2: Correlation penalties (>0.80 flags)')
        rows = CorrelationTracker.apply_correlation_penalties(rows, max_correlation=0.80)
        
        # Step 3: Sector allocation (top-down)
        log.info('Step 3: Sector allocation (12 sectors, max 30% per sector)')
        rows, sector_summary = apply_sector_allocation(
            rows,
            max_sector_exposure=self.risk_profile.max_per_sector,
            max_positions=self.risk_profile.max_positions,
        )
        
        # Step 4: Risk-based position sizing
        log.info('Step 4: Risk-based sizing (2% risk per trade)')
        rows = self.position_sizer.size_positions(rows)
        
        # Step 5: Filter valid positions + sort by position size
        rows = [r for r in rows if r.get('position_size_usd', 0) > 0]
        rows.sort(key=lambda r: r.get('position_size_usd', 0), reverse=True)
        
        # Summary
        total_exposure = sum(r.get('position_size_usd', 0) for r in rows)
        
        # Count by phase
        phase_counts = {
            'ACUMULACAO': sum(1 for r in rows if r.get('phase') == 'ACUMULACAO'),
            'MANIPULACAO': sum(1 for r in rows if r.get('phase') == 'MANIPULACAO'),
            'DISTRIBUICAO': sum(1 for r in rows if r.get('phase') == 'DISTRIBUICAO'),
            'CHOP': sum(1 for r in rows if r.get('phase') == 'CHOP'),
        }
        
        summary = {
            'pipeline': 'fund_mode_simplified',
            'input_count': len(rows),
            'output_count': len(rows),
            'total_exposure_usd': round(total_exposure, 2),
            'total_exposure_pct': round(total_exposure / self.portfolio_usd * 100, 1),
            'phase_distribution': phase_counts,
            'sector_summary': sector_summary,
        }
        
        return rows, summary
