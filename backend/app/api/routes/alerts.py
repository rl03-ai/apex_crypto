"""Alertas do sistema.

GET  /alerts           → lista não lidos (+ todos com ?all=true)
POST /alerts/{id}/read → marcar como lido
POST /alerts/read-all  → marcar todos como lidos
DELETE /alerts/{id}    → eliminar
"""
from fastapi import APIRouter, Query, Response

from app.api.deps import CurrentUser, DBSession
from app.models.alert import Alert
from app.schemas.alert import AlertOut

router = APIRouter()


@router.get('', response_model=list[AlertOut])
def list_alerts(
    current_user: CurrentUser,
    db: DBSession,
    all: bool = Query(False, description='Incluir alertas já lidos'),
    limit: int = Query(50, le=200),
) -> list[Alert]:
    q = db.query(Alert).filter(Alert.user_id == current_user.id)
    if not all:
        q = q.filter(Alert.is_read == False)  # noqa: E712
    return q.order_by(Alert.created_at.desc()).limit(limit).all()


@router.post('/{alert_id}/read', response_model=AlertOut)
def mark_read(alert_id: str, current_user: CurrentUser, db: DBSession) -> Alert:
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.user_id == current_user.id).first()
    if not alert:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail='Alerta não encontrado')
    alert.is_read = True
    db.commit()
    db.refresh(alert)
    return alert


@router.post('/read-all')
def mark_all_read(current_user: CurrentUser, db: DBSession) -> dict:
    updated = (
        db.query(Alert)
        .filter(Alert.user_id == current_user.id, Alert.is_read == False)  # noqa: E712
        .update({'is_read': True})
    )
    db.commit()
    return {'marked_read': updated}


@router.delete('/{alert_id}')
def delete_alert(alert_id: str, current_user: CurrentUser, db: DBSession) -> None:
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.user_id == current_user.id).first()
    if not alert:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail='Alerta não encontrado')
    db.delete(alert)
    db.commit()
