"""Watchlist — moedas favoritas do utilizador.

GET  /watchlist           → lista todas
POST /watchlist           → adicionar moeda
GET  /watchlist/{id}      → detalhe
PUT  /watchlist/{id}      → editar alertas/notas
DELETE /watchlist/{id}    → remover
GET  /watchlist/enriched  → lista com dados live do CoinGecko
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DBSession
from app.models.watchlist import WatchlistEntry
from app.schemas.watchlist import WatchlistAdd, WatchlistOut, WatchlistUpdate

router = APIRouter()


@router.get('', response_model=list[WatchlistOut])
def list_watchlist(current_user: CurrentUser, db: DBSession) -> list[WatchlistEntry]:
    return (
        db.query(WatchlistEntry)
        .filter(WatchlistEntry.user_id == current_user.id)
        .order_by(WatchlistEntry.added_at.desc())
        .all()
    )


@router.post('', response_model=WatchlistOut, status_code=201)
def add_to_watchlist(payload: WatchlistAdd, current_user: CurrentUser, db: DBSession) -> WatchlistEntry:
    existing = (
        db.query(WatchlistEntry)
        .filter(WatchlistEntry.user_id == current_user.id, WatchlistEntry.coin_id == payload.coin_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail='Moeda já está na watchlist')

    entry = WatchlistEntry(
        user_id=current_user.id,
        coin_id=payload.coin_id,
        symbol=payload.symbol.upper(),
        name=payload.name,
        notes=payload.notes,
        alert_price_above=payload.alert_price_above,
        alert_price_below=payload.alert_price_below,
        alert_score_above=payload.alert_score_above,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get('/enriched')
async def list_watchlist_enriched(current_user: CurrentUser, db: DBSession) -> list[dict]:
    """Devolve watchlist com dados live do CoinGecko (preço, score, etc.)."""
    from app.services.coingecko import fetch_markets_by_ids
    from app.services.scoring import crypto_score, reasons

    entries = (
        db.query(WatchlistEntry)
        .filter(WatchlistEntry.user_id == current_user.id)
        .all()
    )
    if not entries:
        return []

    coin_ids = [e.coin_id for e in entries]
    markets = await fetch_markets_by_ids(coin_ids)
    markets_map = {m['id']: m for m in markets}

    result = []
    for entry in entries:
        raw = markets_map.get(entry.coin_id, {})
        score = crypto_score(raw) if raw else {}
        result.append({
            'watchlist_id': entry.id,
            'coin_id': entry.coin_id,
            'symbol': entry.symbol,
            'name': entry.name,
            'notes': entry.notes,
            'alert_price_above': entry.alert_price_above,
            'alert_price_below': entry.alert_price_below,
            'alert_score_above': entry.alert_score_above,
            'added_at': entry.added_at.isoformat(),
            # live data
            'price': raw.get('current_price'),
            'change_24h': raw.get('price_change_percentage_24h'),
            'change_7d': raw.get('price_change_percentage_7d_in_currency'),
            'market_cap': raw.get('market_cap'),
            **score,
            'why_selected': reasons(raw, score) if raw else [],
        })
    return result


@router.get('/{entry_id}', response_model=WatchlistOut)
def get_entry(entry_id: str, current_user: CurrentUser, db: DBSession) -> WatchlistEntry:
    entry = _get_or_404(entry_id, current_user.id, db)
    return entry


@router.put('/{entry_id}', response_model=WatchlistOut)
def update_entry(
    entry_id: str, payload: WatchlistUpdate, current_user: CurrentUser, db: DBSession
) -> WatchlistEntry:
    entry = _get_or_404(entry_id, current_user.id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete('/{entry_id}', status_code=204)
def remove_entry(entry_id: str, current_user: CurrentUser, db: DBSession) -> None:
    entry = _get_or_404(entry_id, current_user.id, db)
    db.delete(entry)
    db.commit()


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_or_404(entry_id: str, user_id: str, db: Session) -> WatchlistEntry:
    entry = (
        db.query(WatchlistEntry)
        .filter(WatchlistEntry.id == entry_id, WatchlistEntry.user_id == user_id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail='Entrada de watchlist não encontrada')
    return entry
