"""Endpoints de sinais.

GET /signals                      → todos os sinais activos
GET /signals?direction=long&min_score=8
GET /signals/coin/{coin_id}       → análise on-demand do InstDash para uma moeda
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import DBSession
from app.models.signal import Signal
from app.schemas.signal import SignalOut

router = APIRouter()


@router.get('', response_model=list[SignalOut])
def list_signals(
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
async def analyse_coin(coin_id: str,
                        interval: str = Query('1d', description='1d | 4h | 1w'),
                        htf: str = Query('1w')) -> dict:
    """Análise on-demand do InstDash para uma moeda específica.

    Não persiste sinais — só devolve a análise actual.
    """
    from app.services.binance import resolve_binance_symbol
    from app.services.coingecko import fetch_coin_detail
    from app.services.instdash import analyse_symbol

    try:
        # Estratégia 1: tratar input directo se for já BTCUSDT
        if coin_id.upper().endswith('USDT'):
            symbol = coin_id.upper()
        else:
            # Estratégia 2: resolver via CoinGecko symbol → Binance pair
            detail = await fetch_coin_detail(coin_id)
            cg_symbol = (detail.get('symbol') or '').upper() if detail else None
            symbol = await resolve_binance_symbol(coin_id, fallback_symbol=cg_symbol)

        if not symbol:
            raise HTTPException(
                404,
                f'{coin_id!r} não está disponível na Binance. O InstDash usa apenas pares Binance USDT.',
            )

        result = await analyse_symbol(symbol, interval=interval, htf_interval=htf)
        if not result:
            raise HTTPException(
                503,
                f'Sem dados InstDash para {symbol}. Possíveis causas: histórico insuficiente, moeda não listada na Binance, ou rate-limit. Tenta de novo em 1 minuto.',
            )
        return result

    except HTTPException:
        # HTTPExceptions já têm status code apropriado — propaga
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception('analyse_coin %s falhou: %s', coin_id, e)
        raise HTTPException(
            500,
            f'Erro interno ao analisar {coin_id!r}. Detalhes nos logs do servidor.',
        )
