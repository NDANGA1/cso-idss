# analytics_service.py
# All the analytics logic lives here — peak hours, utilisation rates,
# busiest venues, trend data for the charts. I also do backfilling here
# so the analytics page isn't empty on a fresh install.

from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy import func, extract, text
from sqlalchemy.orm import Session

from app.models.reading import OccupancyReading
from app.models.venue import Venue

# ── Writing ──────────────────────────────────────────────────────────────────

def record_reading(
    db: Session,
    venue_id: int,
    occupied_count: int,
    total_seats: int,
    availability_state: str,
    data_source: str = "MOCK",
    booking_active: bool = False,
    rate_limit_minutes: int = 4,
) -> bool:
    """
    Write one occupancy reading. Returns False if rate-limited (too recent).
    Pass rate_limit_minutes=0 to always write (used by camera inference).
    """
    if rate_limit_minutes > 0:
        cutoff = datetime.now() - timedelta(minutes=rate_limit_minutes)
        recent = db.query(OccupancyReading).filter(
            OccupancyReading.venue_id == venue_id,
            OccupancyReading.recorded_at >= cutoff,
        ).first()
        if recent:
            return False

    pct = round(occupied_count / total_seats * 100, 1) if total_seats else 0.0
    row = OccupancyReading(
        venue_id=venue_id,
        recorded_at=datetime.now(),
        occupied_count=occupied_count,
        total_seats=total_seats,
        occupancy_pct=pct,
        availability_state=availability_state,
        data_source=data_source,
        booking_active=booking_active,
    )
    db.add(row)
    db.commit()
    return True

def snapshot_all_venues(db: Session) -> int:
    """
    Record the current state of every venue. Called from POST /analytics/snapshot.
    Returns count of rows actually written (some may be rate-limited).
    """
    from app.services.occupancy_engine import OccupancyEngine
    venues = db.query(Venue).all()
    written = 0
    for venue in venues:
        state = OccupancyEngine.compute_state(db, venue)
        ok = record_reading(
            db=db,
            venue_id=venue.id,
            occupied_count=state["current_occupancy"] or 0,
            total_seats=state["capacity"],
            availability_state=state["availability_state"],
            data_source=state.get("physical_data_source") or "MOCK",
            booking_active=state["availability_state"] == "RED",
            rate_limit_minutes=4,
        )
        if ok:
            written += 1
    return written

def backfill_readings(db: Session, days: int = 7) -> int:
    """
    Fill any gaps in occupancy_readings for the last `days` days.
    Generates one reading per 15-min slot per venue only for slots that have
    no existing row — so it's safe to call on every startup without duplicating.
    Uses the same deterministic mock scenario as seed_readings.py.
    """
    import random
    from app.models.booking import Booking

    # Pre-load booking slots into memory
    DAY_MAP = {"MONDAY":0,"TUESDAY":1,"WEDNESDAY":2,"THURSDAY":3,"FRIDAY":4,"SATURDAY":5,"SUNDAY":6}
    booked_slots: set = set()
    for b in db.query(Booking).filter(Booking.status == "ACTIVE").all():
        dow = DAY_MAP.get(b.day_of_week, -1)
        if dow < 0:
            continue
        for h in range(b.start_time.hour, b.end_time.hour + (1 if b.end_time.minute > 0 else 0)):
            booked_slots.add((b.venue_id, dow, h))

    venues = db.query(Venue).all()
    if not venues:
        return 0

    now = datetime.now().replace(second=0, microsecond=0)
    start = (now - timedelta(days=days)).replace(hour=0, minute=0)

    # Find existing timestamps per venue to avoid inserting duplicates
    from app.models.reading import OccupancyReading as OR
    existing = set(
        db.query(OR.venue_id, OR.recorded_at)
        .filter(OR.recorded_at >= start)
        .all()
    )

    rows, written = [], 0
    dt = start
    while dt <= now:
        slot_bucket = int(dt.timestamp() // 60)
        for venue in venues:
            if (venue.id, dt) in existing:
                continue
            is_booked = (venue.id, dt.weekday(), dt.hour) in booked_slots
            total = venue.capacity or 60
            rng = random.Random(venue.id * 10000 + slot_bucket)
            scenario = rng.random()
            if is_booked:
                ratio = rng.uniform(0.65,0.85) if scenario<0.70 else rng.uniform(0.88,1.00) if scenario<0.90 else rng.uniform(1.02,1.20)
            else:
                if not (8 <= dt.hour < 20):
                    ratio = rng.uniform(0.00, 0.05)
                elif scenario < 0.75:
                    ratio = rng.uniform(0.03, 0.15)
                elif scenario < 0.90:
                    ratio = rng.uniform(0.55, 0.82)
                else:
                    ratio = rng.uniform(0.92, 1.10)
            occupied = round(total * ratio)
            pct = round(occupied / total * 100, 1)
            state = "RED" if is_booked else ("FULL" if occupied >= total else "GREEN")
            rows.append(OR(
                venue_id=venue.id, recorded_at=dt,
                occupied_count=occupied, total_seats=total,
                occupancy_pct=pct, availability_state=state,
                data_source="MOCK", booking_active=is_booked,
            ))
            written += 1
            if len(rows) >= 5000:
                db.bulk_save_objects(rows); db.commit(); rows = []
        dt += timedelta(minutes=15)

    if rows:
        db.bulk_save_objects(rows); db.commit()
    return written

# ── Reading / aggregation ─────────────────────────────────────────────────────

def daily_hourly(db: Session, date=None) -> List[Dict]:
    """
    Average occupancy % per hour for a given date (default today).
    Returns 24 slots; hours with no data get occupancy_pct=None.
    """
    target = date or datetime.now().date()
    rows = (
        db.query(
            extract("hour", OccupancyReading.recorded_at).label("hour"),
            func.avg(OccupancyReading.occupancy_pct).label("avg_pct"),
            func.avg(OccupancyReading.occupied_count).label("avg_count"),
            func.count(OccupancyReading.id).label("samples"),
        )
        .filter(func.date(OccupancyReading.recorded_at) == target)
        .group_by("hour")
        .order_by("hour")
        .all()
    )
    row_map = {int(r.hour): r for r in rows}
    return [
        {
            "hour": h,
            "label": f"{h:02d}:00",
            "avg_occupancy_pct": round(row_map[h].avg_pct, 1) if h in row_map else None,
            "avg_occupied": round(row_map[h].avg_count) if h in row_map else None,
            "samples": row_map[h].samples if h in row_map else 0,
        }
        for h in range(24)
    ]

def weekly_daily(db: Session) -> List[Dict]:
    """
    Average occupancy % per calendar day for the last 7 days.
    """
    cutoff = datetime.now() - timedelta(days=7)
    rows = (
        db.query(
            func.date(OccupancyReading.recorded_at).label("day"),
            func.avg(OccupancyReading.occupancy_pct).label("avg_pct"),
            func.avg(OccupancyReading.occupied_count).label("avg_count"),
            func.count(OccupancyReading.id).label("samples"),
        )
        .filter(OccupancyReading.recorded_at >= cutoff)
        .group_by("day")
        .order_by("day")
        .all()
    )
    DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return [
        {
            "date": str(r.day),
            "label": DAY_NAMES[r.day.weekday()] if hasattr(r.day, "weekday") else str(r.day),
            "avg_occupancy_pct": round(r.avg_pct, 1),
            "avg_occupied": round(r.avg_count),
            "samples": r.samples,
        }
        for r in rows
    ]

def venue_comparison(db: Session, days: int = 7) -> List[Dict]:
    """
    Per-venue average, peak, and min occupancy over the last N days.
    Returns sorted by avg desc.
    """
    cutoff = datetime.now() - timedelta(days=days)
    rows = (
        db.query(
            OccupancyReading.venue_id,
            func.avg(OccupancyReading.occupancy_pct).label("avg_pct"),
            func.max(OccupancyReading.occupancy_pct).label("peak_pct"),
            func.min(OccupancyReading.occupancy_pct).label("min_pct"),
            func.count(OccupancyReading.id).label("samples"),
        )
        .filter(OccupancyReading.recorded_at >= cutoff)
        .group_by(OccupancyReading.venue_id)
        .order_by(func.avg(OccupancyReading.occupancy_pct).desc())
        .all()
    )
    venue_names = {v.id: v.name for v in db.query(Venue).all()}
    return [
        {
            "venue_id": r.venue_id,
            "venue_name": venue_names.get(r.venue_id, f"Venue {r.venue_id}"),
            "avg_occupancy_pct": round(r.avg_pct, 1),
            "peak_occupancy_pct": round(r.peak_pct, 1),
            "min_occupancy_pct": round(r.min_pct, 1),
            "samples": r.samples,
        }
        for r in rows
    ]

def state_distribution(db: Session, days: int = 1) -> Dict:
    """
    Count of readings per availability_state over last N days.
    Used for pie chart.
    """
    cutoff = datetime.now() - timedelta(days=days)
    rows = (
        db.query(
            OccupancyReading.availability_state,
            func.count(OccupancyReading.id).label("count"),
        )
        .filter(OccupancyReading.recorded_at >= cutoff)
        .group_by(OccupancyReading.availability_state)
        .all()
    )
    total = sum(r.count for r in rows) or 1
    result = {r.availability_state: r.count for r in rows}
    return {
        "GREEN": result.get("GREEN", 0),
        "FULL": result.get("FULL", 0),
        "RED": result.get("RED", 0),
        "total": total,
        "green_pct": round(result.get("GREEN", 0) / total * 100, 1),
        "full_pct": round(result.get("FULL", 0) / total * 100, 1),
        "red_pct": round(result.get("RED", 0) / total * 100, 1),
    }

def peak_insights(db: Session, days: int = 7) -> Dict:
    """Peak hour, peak day, busiest venue, quietest venue over last N days."""
    cutoff = datetime.now() - timedelta(days=days)

    # Peak hour
    hour_row = (
        db.query(
            extract("hour", OccupancyReading.recorded_at).label("hour"),
            func.avg(OccupancyReading.occupancy_pct).label("avg_pct"),
        )
        .filter(OccupancyReading.recorded_at >= cutoff)
        .group_by("hour")
        .order_by(func.avg(OccupancyReading.occupancy_pct).desc())
        .first()
    )

    # Peak day-of-week
    dow_row = (
        db.query(
            extract("dow", OccupancyReading.recorded_at).label("dow"),
            func.avg(OccupancyReading.occupancy_pct).label("avg_pct"),
        )
        .filter(OccupancyReading.recorded_at >= cutoff)
        .group_by("dow")
        .order_by(func.avg(OccupancyReading.occupancy_pct).desc())
        .first()
    )

    venue_names = {v.id: v.name for v in db.query(Venue).all()}
    DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

    # Busiest / quietest venue
    venue_rows = (
        db.query(
            OccupancyReading.venue_id,
            func.avg(OccupancyReading.occupancy_pct).label("avg_pct"),
        )
        .filter(OccupancyReading.recorded_at >= cutoff)
        .group_by(OccupancyReading.venue_id)
        .order_by(func.avg(OccupancyReading.occupancy_pct).desc())
        .all()
    )

    return {
        "peak_hour": f"{int(hour_row.hour):02d}:00" if hour_row else None,
        "peak_hour_pct": round(hour_row.avg_pct, 1) if hour_row else None,
        "peak_day": DOW[int(dow_row.dow)] if dow_row else None,
        "peak_day_pct": round(dow_row.avg_pct, 1) if dow_row else None,
        "busiest_venue": venue_names.get(venue_rows[0].venue_id) if venue_rows else None,
        "busiest_pct": round(venue_rows[0].avg_pct, 1) if venue_rows else None,
        "quietest_venue": venue_names.get(venue_rows[-1].venue_id) if venue_rows else None,
        "quietest_pct": round(venue_rows[-1].avg_pct, 1) if venue_rows else None,
    }
