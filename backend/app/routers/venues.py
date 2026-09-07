# routers/venues.py
# REST endpoints for venues — CRUD + live occupancy + updates from camera.

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.db.database import get_db
from app.models.venue import Venue
from app.models.user import User
from app.schemas.venue import VenueCreate, VenueOut, VenueStateOut, OccupancyUpdateIn
from app.services.occupancy_engine import OccupancyEngine, update_venue_occupancy
from app.core.deps import get_current_user, require_admin

router = APIRouter(prefix="/venues", tags=["venues"])

DAYS = {"MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"}

# ── Hero endpoint ────────────────────────────────────────────────────────────

@router.get("/live", response_model=List[dict])
async def get_live_venues(db: Session = Depends(get_db)):
    return OccupancyEngine.get_all_venues_state(db)

@router.get("/summary")
async def get_summary(db: Session = Depends(get_db)):
    """Dashboard summary: total, available, occupied counts + avg availability."""
    return OccupancyEngine.get_summary_stats(db)

# ── Search ───────────────────────────────────────────────────────────────────

@router.get("/search")
async def search_venues(
    db: Session = Depends(get_db),
    available_now: bool = False,
    day: Optional[str] = Query(None, description="e.g. MONDAY"),
    time: Optional[str] = Query(None, description="e.g. 14:00"),
    min_capacity: Optional[int] = None,
    min_availability: Optional[float] = None,
    status: Optional[str] = Query(None, description="GREEN or RED"),
):
    """
    Smart search. All filters are optional and combinable.
    - available_now: only GREEN venues right now
    - day + time: check availability at a hypothetical day/time
    - min_capacity: minimum seat count
    - min_availability: minimum availability percentage (0-100)
    - status: GREEN or RED
    """
    # Hypothetical time search
    if day and time:
        day = day.upper()
        if day not in DAYS:
            raise HTTPException(400, f"Invalid day. Use one of: {DAYS}")
        try:
            hour, minute = map(int, time.split(":"))
        except ValueError:
            raise HTTPException(400, "Time must be in HH:MM format")

        from datetime import datetime as dt, date
        check_dt = dt.combine(date.today(), __import__("datetime").time(hour, minute))
        venues = db.query(Venue).all()
        # Override weekday for hypothetical check
        original_now = datetime.now
        results = []
        for v in venues:
            # Manually compute state at hypothetical day+time
            from app.services.occupancy_engine import OccupancyEngine as OE
            from app.models.booking import Booking
            from datetime import time as t
            check_time = t(hour, minute)
            booking = db.query(Booking).filter(
                Booking.venue_id == v.id,
                Booking.day_of_week == day,
                Booking.status == "ACTIVE",
                Booking.start_time <= check_time,
                Booking.end_time > check_time,
            ).first()
            current_occ = v.current_occupancy or 0
            cap = v.capacity or 1
            state = "RED" if booking or current_occ >= cap else "GREEN"
            free = 0 if state == "RED" else max(0, cap - current_occ)
            pct = 0.0 if state == "RED" else round(free / cap * 100, 1)
            entry = {
                "venue_id": v.id,
                "venue_name": v.name,
                "availability_state": state,
                "availability_percentage": pct,
                "free_seats": free,
                "capacity": cap,
                "data_mode": v.data_mode,
            }
            results.append(entry)
    else:
        results = OccupancyEngine.get_all_venues_state(db)

    # Apply filters
    filtered = []
    for s in results:
        if available_now and s["availability_state"] != "GREEN":
            continue
        if status and s["availability_state"] != status.upper():
            continue
        if min_capacity and s["capacity"] < min_capacity:
            continue
        if min_availability is not None and s["availability_percentage"] < min_availability:
            continue
        filtered.append(s)

    return {"total": len(filtered), "results": filtered}

# ── Individual venue ─────────────────────────────────────────────────────────

@router.get("/{venue_id}/live")
async def get_venue_live(venue_id: int, db: Session = Depends(get_db)):
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(404, "Venue not found")
    return OccupancyEngine.compute_state(db, venue)

@router.get("/{venue_id}/schedule")
async def get_venue_schedule(
    venue_id: int,
    day: Optional[str] = Query(None, description="Day of week e.g. MONDAY"),
    db: Session = Depends(get_db),
):
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(404, "Venue not found")
    if not day:
        day = datetime.now().strftime("%A").upper()
    return {
        "venue_id": venue_id,
        "venue_name": venue.name,
        "day": day.upper(),
        "schedule": OccupancyEngine.get_venue_schedule(db, venue_id, day),
    }

@router.get("/{venue_id}/forecast")
async def get_venue_forecast(
    venue_id: int,
    day: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Hourly availability forecast for a venue."""
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(404, "Venue not found")
    if not day:
        day = datetime.now().strftime("%A").upper()
    return {
        "venue_id": venue_id,
        "venue_name": venue.name,
        "day": day.upper(),
        "forecast": OccupancyEngine.forecast_day(db, venue, day),
    }

# ── Camera / occupancy update ────────────────────────────────────────────────

@router.post("/{venue_id}/occupancy")
async def update_occupancy(
    venue_id: int,
    payload: OccupancyUpdateIn,
    db: Session = Depends(get_db),
):
    """
    Receive occupancy count from camera or manual source.
    No auth required — camera systems call this directly.
    In production, restrict to camera IP range via middleware.
    """
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(404, "Venue not found")
    if payload.new_occupancy < 0:
        raise HTTPException(400, "Occupancy cannot be negative")

    # Update data_mode when camera provides data
    if payload.source == "CAMERA" and venue.data_mode != "LIVE":
        venue.data_mode = "LIVE"

    result = update_venue_occupancy(db, venue, payload.new_occupancy, payload.source)
    return {"message": "Occupancy updated", "state": result}

# ── Admin CRUD ───────────────────────────────────────────────────────────────

@router.get("/", response_model=List[dict])
async def list_venues(db: Session = Depends(get_db)):
    venues = db.query(Venue).all()
    return [{"id": v.id, "name": v.name, "capacity": v.capacity, "data_mode": v.data_mode} for v in venues]

@router.post("/", response_model=VenueOut, status_code=201)
async def create_venue(
    payload: VenueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    existing = db.query(Venue).filter(Venue.name == payload.name).first()
    if existing:
        raise HTTPException(400, "Venue name already exists")
    venue = Venue(**payload.model_dump())
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue

@router.delete("/{venue_id}", status_code=204)
async def delete_venue(
    venue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(404, "Venue not found")
    db.delete(venue)
    db.commit()

# ── Simulation endpoint (dev/demo) ────────────────────────────────────────────

@router.post("/simulate/occupancy")
async def simulate_occupancy(
    venue_name: str,
    new_occupancy: int,
    db: Session = Depends(get_db),
):
    """Simulate a camera update by venue name — for demos."""
    venue = db.query(Venue).filter(Venue.name == venue_name).first()
    if not venue:
        raise HTTPException(404, "Venue not found")
    if new_occupancy < 0:
        raise HTTPException(400, "Occupancy cannot be negative")
    result = update_venue_occupancy(db, venue, new_occupancy)
    return {"message": f"Simulated update for {venue_name}", "state": result}
