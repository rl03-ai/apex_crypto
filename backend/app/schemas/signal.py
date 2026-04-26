from datetime import datetime

from pydantic import BaseModel


class SignalOut(BaseModel):
    id: str
    symbol: str
    coin_id: str | None
    interval: str
    direction: str
    setup_type: str
    score: int
    signal_label: str
    price: float
    sl: float | None
    tp: float | None
    title: str
    description: str
    is_active: bool
    detected_at: datetime
    expires_at: datetime | None

    model_config = {'from_attributes': True}
