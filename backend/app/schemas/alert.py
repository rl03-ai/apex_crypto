from datetime import datetime

from pydantic import BaseModel


class AlertOut(BaseModel):
    id: str
    alert_type: str
    severity: str
    coin_id: str | None
    title: str
    message: str
    is_read: bool
    created_at: datetime

    model_config = {'from_attributes': True}
