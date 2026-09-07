# routers/bookings.py
# All booking-related endpoints go here.

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date

from app.db.database import get_db
from app.models.booking import Booking
from app.models.venue import Venue
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingOut
from app.core.deps import get_current_user, require_lecturer_or_above, require_timetabler_or_admin

router = APIRouter(prefix="/bookings", tags=["bookings"])

DAYS = {"MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"}

ONE_TIME_ROLES = {"LECTURER", "IFMSO"}
RECURRING_ROLES = {"TIMETABLER", "ADMIN"}

def _effective_status(b: Booking) -> str:
    if b.status != "ACTIVE":
        return b.status
    if b.booking_date:
        end_dt = datetime.combine(b.booking_date, b.end_time)
        if end_dt < datetime.now():
            return "COMPLETED"
    return "ACTIVE"

def _booking_to_dict(b: Booking) -> dict:
    return {
        "id": b.id,
        "venue_id": b.venue_id,
        "venue_name": b.venue.name if b.venue else None,
        "holder_name": b.user.name if b.user else None,
        "course_code": b.course_code,
        "course_name": b.course_name,
        "booking_type": b.booking_type,
        "booking_date": b.booking_date.isoformat() if b.booking_date else None,
        "is_recurring": b.booking_date is None,
        "day_of_week": b.day_of_week,
        "start_time": b.start_time.strftime("%H:%M") if b.start_time else None,
        "end_time": b.end_time.strftime("%H:%M") if b.end_time else None,
        "status": _effective_status(b),
        "source": b.source,
    }

@router.get("/my", response_model=List[dict])
async def my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_lecturer_or_above),
):
    """Return the calling user's own bookings, newest first."""
    bookings = (
        db.query(Booking)
        .filter(Booking.user_id == current_user.id)
        .order_by(Booking.booking_date.desc().nullslast(), Booking.start_time)
        .all()
    )
    return [_booking_to_dict(b) for b in bookings]

@router.get("/", response_model=List[dict])
async def list_bookings(
    day: Optional[str] = Query(None),
    venue_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Booking)
    if day:
        q = q.filter(Booking.day_of_week == day.upper())
    if venue_id:
        q = q.filter(Booking.venue_id == venue_id)
    if status:
        q = q.filter(Booking.status == status.upper())
    bookings = q.order_by(Booking.day_of_week, Booking.start_time).all()
    return [_booking_to_dict(b) for b in bookings]

@router.get("/active", response_model=List[dict])
async def active_bookings(db: Session = Depends(get_db)):
    """Bookings active right now (today, current time window)."""
    from sqlalchemy import or_, and_
    now = datetime.now()
    today_name = now.strftime("%A").upper()
    today_date = date.today()
    current_time = now.time()
    bookings = (
        db.query(Booking)
        .filter(
            Booking.status == "ACTIVE",
            Booking.day_of_week == today_name,
            Booking.start_time <= current_time,
            Booking.end_time > current_time,
            or_(
                Booking.booking_date == None,
                Booking.booking_date == today_date,
            ),
        )
        .all()
    )
    return [_booking_to_dict(b) for b in bookings]

@router.post("/", response_model=dict, status_code=201)
async def create_booking(
    payload: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_lecturer_or_above),
):
    """
    Create a booking.

    - LECTURER / IFMSO: must supply booking_date (one-time, auto-expires after end_time).
    - TIMETABLER / ADMIN: can omit booking_date for a recurring weekly slot, or
      supply booking_date for a one-off manual override.
    """
    role = current_user.role

    # Enforce one-time-only for lecturers and IFMSO
    if role in ONE_TIME_ROLES and not payload.booking_date:
        raise HTTPException(
            400,
            "LECTURER and IFMSO bookings must include a specific booking_date. "
            "Only TIMETABLER / ADMIN can create recurring bookings."
        )

    # Timetablers cannot accidentally create a one-time booking without knowing it
    # (they can, but the UI makes it explicit — no server restriction needed)

    day = payload.day_of_week.upper()
    if day not in DAYS:
        raise HTTPException(400, f"Invalid day. Use one of: {DAYS}")

    venue = db.query(Venue).filter(Venue.id == payload.venue_id).first()
    if not venue:
        raise HTTPException(404, "Venue not found")

    # Conflict check — scope by booking_date for one-time, or day for recurring
    from sqlalchemy import or_, and_
    if payload.booking_date:
        date_clause = or_(
            and_(Booking.booking_date == None, Booking.day_of_week == day),
            Booking.booking_date == payload.booking_date,
        )
    else:
        # Recurring: conflicts with any recurring on same day OR any one-time on any future date on that day
        date_clause = Booking.day_of_week == day

    conflict = (
        db.query(Booking)
        .filter(
            Booking.venue_id == payload.venue_id,
            Booking.status == "ACTIVE",
            Booking.start_time < payload.end_time,
            Booking.end_time > payload.start_time,
            date_clause,
        )
        .first()
    )
    if conflict:
        raise HTTPException(
            409,
            f"Time conflict: {conflict.course_name or conflict.course_code or 'existing booking'} "
            f"({conflict.start_time.strftime('%H:%M')}–{conflict.end_time.strftime('%H:%M')})"
        )

    # Determine booking_type from role if not explicitly set
    btype = payload.booking_type
    if btype == "MANUAL":
        if role == "TIMETABLER":
            btype = "TIMETABLE" if not payload.booking_date else "MANUAL"
        elif role in ("LECTURER", "IFMSO"):
            btype = "MANUAL"

    booking = Booking(
        venue_id=payload.venue_id,
        user_id=current_user.id,
        course_code=payload.course_code,
        course_name=payload.course_name,
        booking_type=btype,
        booking_date=payload.booking_date,
        day_of_week=day,
        start_time=payload.start_time,
        end_time=payload.end_time,
        status="ACTIVE",
        source="MANUAL",
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return _booking_to_dict(booking)

@router.delete("/{booking_id}", status_code=204)
async def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_lecturer_or_above),
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(404, "Booking not found")

    # Lecturers and IFMSO can only cancel their own; admin/timetabler can cancel any
    if current_user.role in ONE_TIME_ROLES and booking.user_id != current_user.id:
        raise HTTPException(403, "You can only cancel your own bookings")

    booking.status = "CANCELLED"
    db.commit()

@router.get("/all", response_model=List[dict])
async def all_bookings(
    day: Optional[str] = Query(None),
    venue_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_timetabler_or_admin),
):
    """All bookings — admin/timetabler only. Filterable by day, venue, status, search."""
    q = db.query(Booking)
    if day:
        q = q.filter(Booking.day_of_week == day.upper())
    if venue_id:
        q = q.filter(Booking.venue_id == venue_id)
    if status:
        q = q.filter(Booking.status == status.upper())
    bookings = q.order_by(Booking.day_of_week, Booking.start_time).all()
    results = [_booking_to_dict(b) for b in bookings]
    if search:
        s = search.lower()
        results = [b for b in results if s in (b.get('venue_name') or '').lower()
                   or s in (b.get('course_name') or '').lower()
                   or s in (b.get('course_code') or '').lower()
                   or s in (b.get('holder_name') or '').lower()]
    return results
