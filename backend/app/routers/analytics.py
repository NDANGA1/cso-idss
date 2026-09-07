# routers/analytics.py
# Analytics endpoints — occupancy trends, peak hours, busiest venues etc.

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from app.db.database import get_db
from app.models.venue import Venue
from app.models.booking import Booking
from app.services.occupancy_engine import OccupancyEngine
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])

DAYS_ORDER = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]

# ── Occupancy readings endpoints ─────────────────────────────────────────────

@router.post("/snapshot", status_code=200)
async def take_snapshot(db: Session = Depends(get_db)):
    written = analytics_service.snapshot_all_venues(db)
    return {"message": "Snapshot taken", "written": written}

@router.get("/daily")
async def get_daily(db: Session = Depends(get_db)):
    """Hourly campus occupancy avg for today."""
    return {"data": analytics_service.daily_hourly(db)}

@router.get("/weekly")
async def get_weekly(db: Session = Depends(get_db)):
    """Daily campus occupancy avg for the last 7 days."""
    return {"data": analytics_service.weekly_daily(db)}

@router.get("/venues/occupancy")
async def get_venue_comparison(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """Per-venue avg / peak / min occupancy over last N days."""
    return {"data": analytics_service.venue_comparison(db, days=days)}

@router.get("/distribution")
async def get_distribution(
    days: int = Query(1, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """State distribution (GREEN/FULL/RED) for pie chart."""
    return analytics_service.state_distribution(db, days=days)

@router.get("/insights")
async def get_insights(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """Peak hour, peak day, busiest/quietest venue over last N days."""
    return analytics_service.peak_insights(db, days=days)

@router.get("/overview")
async def campus_overview(db: Session = Depends(get_db)):
    """
    High-level campus utilisation for the Admin Analytics page.
    Returns per-venue utilisation % and campus-wide totals.
    """
    venues = db.query(Venue).all()
    states = [OccupancyEngine.compute_state(db, v) for v in venues]

    total = len(states)
    green_count = sum(1 for s in states if s["availability_state"] == "GREEN")
    red_count = total - green_count
    avg_pct = round(sum(s["availability_percentage"] for s in states) / total, 1) if total else 0

    rankings = sorted(states, key=lambda s: s["availability_percentage"])

    return {
        "summary": {
            "total_venues": total,
            "available": green_count,
            "occupied": red_count,
            "campus_availability_percentage": avg_pct,
        },
        "venues": [
            {
                "venue_id": s["venue_id"],
                "venue_name": s["venue_name"],
                "availability_state": s["availability_state"],
                "availability_percentage": s["availability_percentage"],
                "capacity": s["capacity"],
                "current_occupancy": s["current_occupancy"],
                "data_mode": s["data_mode"],
            }
            for s in states
        ],
        "most_utilised": [
            {"venue_name": s["venue_name"], "availability_percentage": s["availability_percentage"]}
            for s in rankings[:3]
        ],
        "most_available": [
            {"venue_name": s["venue_name"], "availability_percentage": s["availability_percentage"]}
            for s in reversed(rankings[-3:])
        ],
    }

@router.get("/bookings-by-day")
async def bookings_by_day(db: Session = Depends(get_db)):
    """Count of active bookings per day of week — for trend chart."""
    rows = (
        db.query(Booking.day_of_week, func.count(Booking.id).label("count"))
        .filter(Booking.status == "ACTIVE")
        .group_by(Booking.day_of_week)
        .all()
    )
    day_map = {r.day_of_week: r.count for r in rows}
    return [{"day": d, "bookings": day_map.get(d, 0)} for d in DAYS_ORDER]

@router.get("/venue/{venue_id}/utilisation")
async def venue_utilisation(venue_id: int, db: Session = Depends(get_db)):
    """Scheduled usage hours per day for one venue."""
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        from fastapi import HTTPException
        raise HTTPException(404, "Venue not found")

    result = []
    for day in DAYS_ORDER:
        bookings = (
            db.query(Booking)
            .filter(
                Booking.venue_id == venue_id,
                Booking.day_of_week == day,
                Booking.status == "ACTIVE",
            )
            .all()
        )
        total_minutes = sum(
            (b.end_time.hour * 60 + b.end_time.minute) - (b.start_time.hour * 60 + b.start_time.minute)
            for b in bookings
        )
        result.append({"day": day, "scheduled_hours": round(total_minutes / 60, 1), "booking_count": len(bookings)})

    return {"venue_id": venue_id, "venue_name": venue.name, "utilisation": result}
