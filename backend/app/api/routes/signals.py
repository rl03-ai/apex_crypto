"""Endpoints de sinais.

GET /signals                      → todos os sinais activos
GET /signals?direction=long&min_score=8
GET /signals/coin/{coin_id}       → análise on-demand do InstDash para uma moeda
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, DBSession
from app.models.signal import Signal
from app.schemas.signal import SignalOut

router = APIRouter()


@router.get('', response_model=list[SignalOut])
def list_signals(
    current_user: CurrentUser,
    db: DBSession,
    direction: str | None = Query(None, description="'long' | 'short' | 'exit'"),
    min_score: int | None = Query(None, description='Filtra sinais com |score| >= min_score'),
    interval: str | None = Query(None, description='1d | 4h | 1w'),
    only_active: bool = Query(True),
    limit: int = Query(50, le=200),
) -> list[Signal]:
    q = db.query(Signal)
    if only_active:
        q = q.filter(Signal.is_active == True)  # noqa: E712
    if direction:
        q = q.filter(Signal.direction == direction)
    if interval:
        q = q.filter(Signal.interval == interval)
    if min_score is not None:
        # |score| >= min_score
        q = q.filter((Signal.score >= min_score) | (Signal.score <= -min_score))
    return q.order_by(Signal.detected_at.desc()).limit(limit).all()


@router.get('/coin/{coin_id}')
async def analyse_coin(coin_id: str, current_user: CurrentUser,
                        interval: str = Query('1d', description='1d | 4h | 1w'),
                        htf: str = Query('1w')) -> dict:
    """Análise on-demand do InstDash para uma moeda específica.

    Não persiste sinais — só devolve a análise actual.
    """
    from app.services.binance import coingecko_id_to_binance_symbol
    from app.services.instdash import analyse_symbol

    symbol = coingecko_id_to_binance_symbol(coin_id)
    if not symbol:
        # Tentar como símbolo Binance directo (ex: 'BTCUSDT')
        if coin_id.upper().endswith('USDT'):
            symbol = coin_id.upper()
        else:
            symbol = f'{coin_id.upper()}USDT'

    result = await analyse_symbol(symbol, interval=interval, htf_interval=htf)
    if not result:
        raise HTTPException(404, f'Sem dados InstDash para {symbol}. Pode não estar listado na Binance ou ter pouco histórico.')
    return result
