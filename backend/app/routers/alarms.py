# routers/alarms.py
# Alarm CRUD — students can set alarms and get notified when a venue frees up.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.db.database import get_db
from app.models.alarm import Alarm
from app.models.venue import Venue
from app.models.user import User
from app.schemas.alarm import AlarmCreate, AlarmOut
from app.core.deps import get_current_user
from app.services.occupancy_engine import OccupancyEngine

router = APIRouter(prefix="/alarms", tags=["alarms"])

def _alarm_to_dict(a: Alarm) -> dict:
    return {
        "id": a.id,
        "venue_id": a.venue_id,
        "venue_name": a.venue.name if a.venue else None,
        "note": a.note,
        "triggered": a.triggered,
        "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }

@router.get("/", response_model=List[dict])
async def list_my_alarms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alarms = db.query(Alarm).filter(Alarm.user_id == current_user.id).order_by(Alarm.created_at.desc()).all()

    # Auto-trigger any pending alarm whose venue is currently GREEN.
    # This catches timetable-based transitions (booking end_time passes naturally)
    # which are never detected by update_venue_occupancy().
    changed = False
    for alarm in alarms:
        if not alarm.triggered and alarm.venue:
            state = OccupancyEngine.compute_state(db, alarm.venue)
            if state["availability_state"] == "GREEN":
                alarm.triggered = True
                alarm.triggered_at = datetime.now()
                changed = True
    if changed:
        db.commit()

    return [_alarm_to_dict(a) for a in alarms]

@router.post("/", response_model=dict, status_code=201)
async def create_alarm(
    payload: AlarmCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    venue = db.query(Venue).filter(Venue.id == payload.venue_id).first()
    if not venue:
        raise HTTPException(404, "Venue not found")

    # Prevent duplicate active alarms for same user+venue
    existing = db.query(Alarm).filter(
        Alarm.user_id == current_user.id,
        Alarm.venue_id == payload.venue_id,
        Alarm.triggered == False,
    ).first()
    if existing:
        raise HTTPException(409, "You already have an active alarm for this venue")

    alarm = Alarm(
        venue_id=payload.venue_id,
        user_id=current_user.id,
        note=payload.note,
        triggered=False,
    )
    db.add(alarm)
    db.commit()
    db.refresh(alarm)
    return _alarm_to_dict(alarm)

@router.delete("/{alarm_id}", status_code=204)
async def delete_alarm(
    alarm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alarm = db.query(Alarm).filter(Alarm.id == alarm_id, Alarm.user_id == current_user.id).first()
    if not alarm:
        raise HTTPException(404, "Alarm not found")
    db.delete(alarm)
    db.commit()

@router.get("/pending-count", response_model=dict)
async def pending_alarm_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = db.query(Alarm).filter(
        Alarm.user_id == current_user.id,
        Alarm.triggered == False,
    ).count()
    return {"pending": count}
