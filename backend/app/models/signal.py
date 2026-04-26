"""Sinal detectado — output dos detectores ou do webhook InstDash."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Signal(Base):
    __tablename__ = 'signals'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Identificação
    symbol: Mapped[str]    = mapped_column(String, index=True)         # ex 'BTCUSDT'
    coin_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)  # ex 'bitcoin' (opcional)
    interval: Mapped[str]  = mapped_column(String, default='1d')       # 1d, 4h, 1w

    # Tipo do sinal
    direction: Mapped[str] = mapped_column(String)                     # 'long' | 'short' | 'exit'
    setup_type: Mapped[str] = mapped_column(String)                    # 'long_valid', 'short_valid', 'choch_bull',
                                                                       # 'bos_bear', 'sweep_high', 'pnl_exit', etc.

    # Score e contexto (snapshot)
    score: Mapped[int] = mapped_column(Integer, default=0)             # -16 a +16
    signal_label: Mapped[str] = mapped_column(String, default='Neutro')  # 'FORTE ALTA', 'Alta', etc.

    price: Mapped[float] = mapped_column(Float)
    sl: Mapped[float | None] = mapped_column(Float, nullable=True)
    tp: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Texto explicativo do sinal (para a UI)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default='')

    # Snapshot completo (JSON) para auditoria/debug
    snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Estado
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
