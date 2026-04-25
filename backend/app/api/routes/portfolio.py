"""Portfolio routes.

GET    /portfolios                               → lista portfolios do user
POST   /portfolios                               → criar portfolio
GET    /portfolios/{id}                          → sumário com P&L calculado
DELETE /portfolios/{id}                          → eliminar

GET    /portfolios/{id}/positions                → posições da carteira
POST   /portfolios/{id}/positions                → abrir posição
GET    /portfolios/{id}/positions/{pos_id}       → detalhe posição
PUT    /portfolios/{id}/positions/{pos_id}       → editar tese / meta / stop
DELETE /portfolios/{id}/positions/{pos_id}       → fechar / eliminar

POST   /portfolios/{id}/positions/{pos_id}/lots  → adicionar lot de compra
POST   /portfolios/{id}/refresh                  → atualiza preços live do CoinGecko
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DBSession
from app.models.portfolio import Portfolio, Position, PositionLot
from app.schemas.portfolio import (
    LotCreate,
    LotOut,
    PortfolioCreate,
    PortfolioOut,
    PortfolioSummary,
    PositionCreate,
    PositionOut,
    PositionUpdate,
)

router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
# PORTFOLIOS
# ══════════════════════════════════════════════════════════════════════════════

@router.get('', response_model=list[PortfolioOut])
def list_portfolios(current_user: CurrentUser, db: DBSession) -> list[Portfolio]:
    return db.query(Portfolio).filter(Portfolio.user_id == current_user.id).all()


@router.post('', response_model=PortfolioOut, status_code=201)
def create_portfolio(payload: PortfolioCreate, current_user: CurrentUser, db: DBSession) -> Portfolio:
    portfolio = Portfolio(user_id=current_user.id, name=payload.name, base_currency=payload.base_currency)
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return portfolio


@router.get('/{portfolio_id}', response_model=PortfolioSummary)
def get_portfolio(portfolio_id: str, current_user: CurrentUser, db: DBSession) -> dict:
    portfolio = _portfolio_or_404(portfolio_id, current_user.id, db)
    positions = db.query(Position).filter(Position.portfolio_id == portfolio_id, Position.status == 'open').all()

    total_invested = sum(p.invested_amount for p in positions)
    total_value = sum(p.current_value or p.invested_amount for p in positions)
    total_pnl = total_value - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0.0

    return {
        'portfolio': portfolio,
        'positions': positions,
        'total_invested': round(total_invested, 2),
        'total_value': round(total_value, 2),
        'total_pnl': round(total_pnl, 2),
        'total_pnl_pct': round(total_pnl_pct, 2),
    }


@router.delete('/{portfolio_id}')
def delete_portfolio(portfolio_id: str, current_user: CurrentUser, db: DBSession) -> None:
    portfolio = _portfolio_or_404(portfolio_id, current_user.id, db)
    db.delete(portfolio)
    db.commit()


# ══════════════════════════════════════════════════════════════════════════════
# POSITIONS
# ══════════════════════════════════════════════════════════════════════════════

@router.get('/{portfolio_id}/positions', response_model=list[PositionOut])
def list_positions(portfolio_id: str, current_user: CurrentUser, db: DBSession) -> list[Position]:
    _portfolio_or_404(portfolio_id, current_user.id, db)
    return db.query(Position).filter(Position.portfolio_id == portfolio_id).all()


@router.post('/{portfolio_id}/positions', response_model=PositionOut, status_code=201)
def open_position(
    portfolio_id: str, payload: PositionCreate, current_user: CurrentUser, db: DBSession
) -> Position:
    _portfolio_or_404(portfolio_id, current_user.id, db)

    # Verificar se já existe posição aberta para esta moeda neste portfolio
    existing = (
        db.query(Position)
        .filter(
            Position.portfolio_id == portfolio_id,
            Position.coin_id == payload.coin_id,
            Position.status == 'open',
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f'Já existe posição aberta para {payload.coin_id} neste portfolio. '
                   'Adiciona um lot ou edita a posição existente.',
        )

    position = Position(
        portfolio_id=portfolio_id,
        coin_id=payload.coin_id,
        symbol=payload.symbol.upper() if payload.symbol else '',
        name=payload.name,
        first_buy_date=payload.first_buy_date,
        avg_cost=payload.avg_cost,
        quantity=payload.quantity,
        invested_amount=round(payload.avg_cost * payload.quantity, 2),
        exchange=payload.exchange,
        horizon=payload.horizon,
        thesis=payload.thesis,
        target_price=payload.target_price,
        stop_loss=payload.stop_loss,
    )
    db.add(position)
    db.flush()

    # Criar o primeiro lot automaticamente
    lot = PositionLot(
        position_id=position.id,
        lot_date=payload.first_buy_date,
        quantity=payload.quantity,
        price=payload.avg_cost,
    )
    db.add(lot)
    db.commit()
    db.refresh(position)
    return position


@router.get('/{portfolio_id}/positions/{position_id}', response_model=PositionOut)
def get_position(
    portfolio_id: str, position_id: str, current_user: CurrentUser, db: DBSession
) -> Position:
    _portfolio_or_404(portfolio_id, current_user.id, db)
    return _position_or_404(position_id, portfolio_id, db)


@router.put('/{portfolio_id}/positions/{position_id}', response_model=PositionOut)
def update_position(
    portfolio_id: str,
    position_id: str,
    payload: PositionUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> Position:
    _portfolio_or_404(portfolio_id, current_user.id, db)
    position = _position_or_404(position_id, portfolio_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(position, field, value)
    db.commit()
    db.refresh(position)
    return position


@router.delete('/{portfolio_id}/positions/{position_id}')
def delete_position(
    portfolio_id: str, position_id: str, current_user: CurrentUser, db: DBSession
) -> None:
    _portfolio_or_404(portfolio_id, current_user.id, db)
    position = _position_or_404(position_id, portfolio_id, db)
    db.delete(position)
    db.commit()


# ══════════════════════════════════════════════════════════════════════════════
# LOTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get('/{portfolio_id}/positions/{position_id}/lots', response_model=list[LotOut])
def list_lots(
    portfolio_id: str, position_id: str, current_user: CurrentUser, db: DBSession
) -> list[PositionLot]:
    _portfolio_or_404(portfolio_id, current_user.id, db)
    _position_or_404(position_id, portfolio_id, db)
    return db.query(PositionLot).filter(PositionLot.position_id == position_id).order_by(PositionLot.lot_date).all()


@router.post('/{portfolio_id}/positions/{position_id}/lots', response_model=LotOut, status_code=201)
def add_lot(
    portfolio_id: str,
    position_id: str,
    payload: LotCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> PositionLot:
    """Adiciona um lot de compra e recalcula avg_cost + quantity + invested_amount."""
    _portfolio_or_404(portfolio_id, current_user.id, db)
    position = _position_or_404(position_id, portfolio_id, db)

    lot = PositionLot(
        position_id=position_id,
        lot_date=payload.lot_date,
        quantity=payload.quantity,
        price=payload.price,
        fees=payload.fees,
        notes=payload.notes,
    )
    db.add(lot)
    db.flush()

    # Recalcular avg_cost com todos os lots (inclui o novo)
    all_lots = db.query(PositionLot).filter(PositionLot.position_id == position_id).all()
    total_qty = sum(l.quantity for l in all_lots)
    total_cost = sum(l.quantity * l.price + l.fees for l in all_lots)
    position.quantity = round(total_qty, 8)
    position.avg_cost = round(total_cost / total_qty, 8) if total_qty else position.avg_cost
    position.invested_amount = round(total_cost, 2)

    db.commit()
    db.refresh(lot)
    return lot


# ══════════════════════════════════════════════════════════════════════════════
# REFRESH — atualiza preços live do CoinGecko
# ══════════════════════════════════════════════════════════════════════════════

@router.post('/{portfolio_id}/refresh')
async def refresh_portfolio(portfolio_id: str, current_user: CurrentUser, db: DBSession) -> dict:
    """Busca preços actuais no CoinGecko e recalcula P&L de todas as posições abertas."""
    from app.services.coingecko import fetch_markets_by_ids

    _portfolio_or_404(portfolio_id, current_user.id, db)
    positions = (
        db.query(Position)
        .filter(Position.portfolio_id == portfolio_id, Position.status == 'open')
        .all()
    )
    if not positions:
        return {'refreshed': 0, 'positions': []}

    coin_ids = list({p.coin_id for p in positions})
    markets = await fetch_markets_by_ids(coin_ids)
    price_map = {m['id']: m.get('current_price') for m in markets}

    now = datetime.now(timezone.utc)
    results = []
    for pos in positions:
        price = price_map.get(pos.coin_id)
        if price is None:
            results.append({'coin_id': pos.coin_id, 'status': 'no_price'})
            continue

        pos.current_price = price
        pos.current_value = round(price * pos.quantity, 2)
        pos.pnl = round(pos.current_value - pos.invested_amount, 2)
        pos.pnl_pct = round(pos.pnl / pos.invested_amount * 100, 2) if pos.invested_amount else 0.0
        pos.last_refreshed_at = now
        results.append({
            'coin_id': pos.coin_id,
            'symbol': pos.symbol,
            'price': price,
            'current_value': pos.current_value,
            'pnl': pos.pnl,
            'pnl_pct': pos.pnl_pct,
            'status': 'ok',
        })

    db.commit()
    return {'refreshed': len([r for r in results if r['status'] == 'ok']), 'positions': results}


# ══════════════════════════════════════════════════════════════════════════════
# helpers internos
# ══════════════════════════════════════════════════════════════════════════════

def _portfolio_or_404(portfolio_id: str, user_id: str, db: Session) -> Portfolio:
    p = db.query(Portfolio).filter(Portfolio.id == portfolio_id, Portfolio.user_id == user_id).first()
    if not p:
        raise HTTPException(status_code=404, detail='Portfolio não encontrado')
    return p


def _position_or_404(position_id: str, portfolio_id: str, db: Session) -> Position:
    p = db.query(Position).filter(Position.id == position_id, Position.portfolio_id == portfolio_id).first()
    if not p:
        raise HTTPException(status_code=404, detail='Posição não encontrada')
    return p
