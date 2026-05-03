"""Risk-Based Position Sizing — Kelly Criterion inspired.

Fund principle: Position size = function of risk, NOT tier.

Formula:
  Risk_USD = portfolio_USD × risk_per_trade%
  Position_Size = Risk_USD / Risk_Per_Unit
  
Where:
  Risk_Per_Unit = (entry - SL) × share_count
  
Exemplo:
  Portfolio: $100,000
  Risk per trade: 2% = $2,000
  
  Setup A: Entry $50,000, SL $49,000, ATR=1%
    Risk_Per_Unit = $1,000
    Position = $2,000 / $1,000 = 2 shares = $100,000 exposure (⚠️ too much!)
    → Limited to max_exposure (50%) = $50,000 = 1 share
  
  Setup B: Entry $40, SL $38, ATR=5%
    Risk_Per_Unit = $2
    Position = $2,000 / $2 = 1,000 shares = $40,000 exposure (✓ good)
"""
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class RiskProfile:
    """Risk parameters for portfolio."""
    portfolio_usd: float
    risk_per_trade: float = 0.02  # 2%
    max_exposure_pct: float = 0.50  # Max 50% in single position
    max_positions: int = 20
    min_position_usd: float = 500  # Minimum position size
    kelly_fraction: float = 0.25  # Use 25% of Kelly (conservative)
    max_per_sector: float = 0.30  # 30% max in sector
    max_per_symbol: float = 0.15  # 15% max in single symbol


def calculate_position_size(
    entry_price: float,
    sl_price: float,
    portfolio_usd: float,
    risk_per_trade: float = 0.02,
    max_exposure_pct: float = 0.50,
    min_position_usd: float = 500,
    tier: str = 'C',
) -> tuple[float, float, list[str]]:
    """Calculate position size based on risk.
    
    Args:
        entry_price: Entry price per unit
        sl_price: Stop loss price
        portfolio_usd: Total portfolio
        risk_per_trade: % of portfolio to risk
        max_exposure_pct: Max % of portfolio in this position
        min_position_usd: Minimum position value
        tier: For context (not limiting)
    
    Returns:
        (position_usd, position_units, reasons)
    """
    reasons = []
    
    # Risk per unit (absolute)
    risk_per_unit = abs(entry_price - sl_price)
    if risk_per_unit <= 0:
        reasons.append('⚠ Invalid SL (not below entry)')
        return 0, 0, reasons
    
    # Risk dollar amount
    risk_usd = portfolio_usd * risk_per_trade
    reasons.append(f'Risk: ${risk_usd:.0f} ({risk_per_trade*100:.1f}% of ${portfolio_usd:.0f})')
    
    # Position size (units)
    units = risk_usd / risk_per_unit
    exposure = units * entry_price
    
    # Apply exposure cap
    max_exposure_usd = portfolio_usd * max_exposure_pct
    if exposure > max_exposure_usd:
        units = max_exposure_usd / entry_price
        exposure = max_exposure_usd
        reasons.append(f'⚠️ Capped at {max_exposure_pct*100:.0f}% exposure (${max_exposure_usd:.0f})')
    
    # Apply minimum position
    if exposure < min_position_usd:
        reasons.append(f'⚠️ Below minimum (${min_position_usd})')
        return 0, 0, reasons
    
    reasons.append(f'Position: ${exposure:.0f} ({exposure/portfolio_usd*100:.1f}% portfolio)')
    reasons.append(f'Units: {units:.4f}')
    
    return exposure, units, reasons


def apply_kelly_criterion(
    win_rate: float,
    avg_win_r: float,
    avg_loss_r: float,
    kelly_fraction: float = 0.25,
) -> float:
    """Calculate Kelly % position size (conservative: fraction of Kelly).
    
    Kelly % = (win_rate × avg_win - loss_rate × avg_loss) / avg_win
    
    Args:
        win_rate: % of trades that win (0-1)
        avg_win_r: Average win in R-multiples
        avg_loss_r: Average loss in R-multiples (positive)
        kelly_fraction: Use this fraction of Kelly (default 25%)
    
    Returns:
        Position size fraction (0-1)
    """
    if win_rate <= 0 or win_rate >= 1 or avg_win_r <= 0 or avg_loss_r <= 0:
        return 0.02  # Default 2%
    
    loss_rate = 1 - win_rate
    kelly_pct = (win_rate * avg_win_r - loss_rate * avg_loss_r) / avg_win_r
    kelly_pct = max(0.01, min(0.25, kelly_pct))  # Bound to 1%-25%
    
    return kelly_pct * kelly_fraction


@dataclass
class PositionSizing:
    """Portfolio position sizing engine."""
    
    profile: RiskProfile
    
    def size_positions(
        self,
        rows: list[dict],
    ) -> list[dict]:
        """Size all positions according to risk profile.
        
        Updates rows with position_size_usd, position_units, sizing_reasons.
        """
        # Track exposure by sector + symbol
        exposure_by_sector = {}
        exposure_by_symbol = {}
        total_exposure = 0
        
        for row in rows:
            sector = row.get('sector', 'Unknown')
            symbol = row.get('symbol', '?')
            price = row.get('price', 0)
            stops = row.get('stops', {})
            tier = row.get('tier', 'C')
            
            if not price or not stops:
                row['position_size_usd'] = 0
                row['position_units'] = 0
                row['sizing_reasons'] = ['No price/stops data']
                continue
            
            sl = stops.get('sl', price * 0.98)
            
            # Base sizing
            exposure, units, reasons = calculate_position_size(
                price,
                sl,
                self.profile.portfolio_usd,
                risk_per_trade=self.profile.risk_per_trade,
                max_exposure_pct=self.profile.max_exposure_pct,
                min_position_usd=self.profile.min_position_usd,
                tier=tier,
            )
            
            # Check sector limit
            sector_exposure = exposure_by_sector.get(sector, 0)
            max_sector_usd = self.profile.portfolio_usd * self.profile.max_per_sector
            if sector_exposure + exposure > max_sector_usd:
                available = max_sector_usd - sector_exposure
                if available > self.profile.min_position_usd:
                    exposure = available
                    units = exposure / price
                    reasons.append(f'⚠️ Capped by sector max ({self.profile.max_per_sector*100:.0f}%)')
                else:
                    exposure = 0
                    units = 0
                    reasons.append(f'❌ Sector limit reached')
            
            # Check symbol limit
            max_symbol_usd = self.profile.portfolio_usd * self.profile.max_per_symbol
            if exposure > max_symbol_usd:
                exposure = max_symbol_usd
                units = exposure / price
                reasons.append(f'⚠️ Capped by symbol max ({self.profile.max_per_symbol*100:.0f}%)')
            
            # Update tracking
            if exposure > 0:
                exposure_by_sector[sector] = sector_exposure + exposure
                exposure_by_symbol[symbol] = exposure
                total_exposure += exposure
                
                if total_exposure > self.profile.portfolio_usd:
                    # Reduce this position pro-rata
                    reduction = total_exposure - self.profile.portfolio_usd
                    exposure = max(0, exposure - reduction)
                    units = exposure / price if price else 0
                    total_exposure -= reduction
                    reasons.append(f'⚠️ Portfolio cap — reduced by ${reduction:.0f}')
            
            row['position_size_usd'] = exposure
            row['position_units'] = units
            row['sizing_reasons'] = reasons
            row['sector_exposure'] = exposure_by_sector.get(sector, 0)
        
        return rows
