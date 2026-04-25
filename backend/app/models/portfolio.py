"""Portfolio, Position e PositionLot para crypto.

Diferenças vs apex_unified (equities):
  - Position referencia coin_id (CoinGecko) em vez de asset_id (DB FK)
  - Sem asset table — preço actual vai buscar ao CoinGecko no momento do refresh
  - Adicionado campo exchange (Binance, Coinbase, etc.)
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Portfolio(Base):
    __tablename__ = 'portfolios'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String)
    base_currency: Mapped[str] = mapped_column(String, default='USD')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Position(Base):
    __tablename__ = 'positions'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id: Mapped[str] = mapped_column(ForeignKey('portfolios.id', ondelete='CASCADE'), index=True)

    # Identificação da moeda — sem FK, usa CoinGecko directamente
    coin_id: Mapped[str] = mapped_column(String, index=True)    # ex: 'bitcoin'
    symbol: Mapped[str] = mapped_column(String, default='')     # ex: 'BTC'
    name: Mapped[str] = mapped_column(String, default='')       # ex: 'Bitcoin'

    status: Mapped[str] = mapped_column(String, default='open')  # open | closed
    first_buy_date: Mapped[date] = mapped_column(Date)
    avg_cost: Mapped[float] = mapped_column(Float)               # USD por unidade
    quantity: Mapped[float] = mapped_column(Float)
    invested_amount: Mapped[float] = mapped_column(Float)        # avg_cost * quantity

    # Cache do último refresh (não é fonte de verdade — recalculado no refresh)
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Contexto de investimento
    exchange: Mapped[str | None] = mapped_column(String, nullable=True)   # ex: 'Binance'
    horizon: Mapped[str | None] = mapped_column(String, nullable=True)    # short | swing | long
    thesis: Mapped[str | None] = mapped_column(String, nullable=True)
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PositionLot(Base):
    """Registo de cada compra (lot) — permite calcular avg cost correctamente."""
    __tablename__ = 'position_lots'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    position_id: Mapped[str] = mapped_column(ForeignKey('positions.id', ondelete='CASCADE'), index=True)
    lot_date: Mapped[date] = mapped_column(Date)
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)      # preço de compra em USD
    fees: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
