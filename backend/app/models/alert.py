"""Alertas do sistema gerados por jobs ou por triggers de watchlist."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Alert(Base):
    __tablename__ = 'alerts'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)

    alert_type: Mapped[str] = mapped_column(String)    # price_above | price_below | score_above | system
    severity: Mapped[str] = mapped_column(String, default='info')  # info | warning | critical

    coin_id: Mapped[str | None] = mapped_column(String, nullable=True)    # moeda relacionada (pode ser None para alertas de sistema)
    title: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(String)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
