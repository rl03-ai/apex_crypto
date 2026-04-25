from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, computed_field, model_validator


class PortfolioCreate(BaseModel):
    name: str
    base_currency: str = 'USD'


class PortfolioOut(BaseModel):
    id: str
    name: str
    base_currency: str
    created_at: datetime

    model_config = {'from_attributes': True}


# ── Position ─────────────────────────────────────────────────────────────────

class PositionCreate(BaseModel):
    portfolio_id: str
    coin_id: str
    symbol: str = ''
    name: str = ''
    first_buy_date: date
    avg_cost: float
    quantity: float
    exchange: str | None = None
    horizon: str | None = None     # short | swing | long
    thesis: str | None = None
    target_price: float | None = None
    stop_loss: float | None = None

    @model_validator(mode='after')
    def compute_invested(self) -> PositionCreate:
        # invested_amount calculado automaticamente se não vier no payload
        return self

    @property
    def invested_amount(self) -> float:
        return round(self.avg_cost * self.quantity, 2)


class PositionUpdate(BaseModel):
    exchange: str | None = None
    horizon: str | None = None
    thesis: str | None = None
    target_price: float | None = None
    stop_loss: float | None = None
    status: str | None = None   # open | closed


class PositionOut(BaseModel):
    id: str
    portfolio_id: str
    coin_id: str
    symbol: str
    name: str
    status: str
    first_buy_date: date
    avg_cost: float
    quantity: float
    invested_amount: float
    current_price: float | None
    current_value: float | None
    pnl: float | None
    pnl_pct: float | None
    last_refreshed_at: datetime | None
    exchange: str | None
    horizon: str | None
    thesis: str | None
    target_price: float | None
    stop_loss: float | None
    created_at: datetime

    model_config = {'from_attributes': True}


# ── PositionLot ───────────────────────────────────────────────────────────────

class LotCreate(BaseModel):
    lot_date: date
    quantity: float
    price: float
    fees: float = 0.0
    notes: str | None = None


class LotOut(BaseModel):
    id: str
    position_id: str
    lot_date: date
    quantity: float
    price: float
    fees: float
    notes: str | None
    created_at: datetime

    model_config = {'from_attributes': True}


# ── Portfolio Summary ─────────────────────────────────────────────────────────

class PortfolioSummary(BaseModel):
    portfolio: PortfolioOut
    positions: list[PositionOut]
    total_invested: float
    total_value: float
    total_pnl: float
    total_pnl_pct: float
