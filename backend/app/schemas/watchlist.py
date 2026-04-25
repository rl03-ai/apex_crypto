from datetime import datetime

from pydantic import BaseModel


class WatchlistAdd(BaseModel):
    coin_id: str
    symbol: str = ''
    name: str = ''
    notes: str | None = None
    alert_price_above: float | None = None
    alert_price_below: float | None = None
    alert_score_above: float | None = None


class WatchlistUpdate(BaseModel):
    notes: str | None = None
    alert_price_above: float | None = None
    alert_price_below: float | None = None
    alert_score_above: float | None = None


class WatchlistOut(BaseModel):
    id: str
    coin_id: str
    symbol: str
    name: str
    notes: str | None
    alert_price_above: float | None
    alert_price_below: float | None
    alert_score_above: float | None
    added_at: datetime

    model_config = {'from_attributes': True}
