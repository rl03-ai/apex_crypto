"""Watchlist — moedas favoritas do utilizador.

Cada linha guarda o coin_id do CoinGecko (ex: 'bitcoin', 'ethereum').
Sem FK para tabela de assets — os dados live vêm sempre do CoinGecko.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WatchlistEntry(Base):
    __tablename__ = 'watchlist'
    __table_args__ = (UniqueConstraint('user_id', 'coin_id', name='uq_watchlist_user_coin'),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    coin_id: Mapped[str] = mapped_column(String, index=True)       # ex: 'bitcoin'
    symbol: Mapped[str] = mapped_column(String, default='')        # ex: 'BTC' — cache cosmético
    name: Mapped[str] = mapped_column(String, default='')          # ex: 'Bitcoin'
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    # Alertas de preço simples
    alert_price_above: Mapped[float | None] = mapped_column(nullable=True)
    alert_price_below: Mapped[float | None] = mapped_column(nullable=True)
    alert_score_above: Mapped[float | None] = mapped_column(nullable=True)

    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
