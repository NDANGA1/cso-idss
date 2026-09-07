# occupancy_engine.py
# This is the core of my system — I call it the OccupancyEngine.
# It computes the real-time availability state for every venue.
# I took a lot of care with the booking date logic here because
# timetable bookings shouldn't count during holiday breaks.

from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session
from app.models.venue import Venue
from app.models.booking import Booking
from app.core.academic_calendar import is_teaching_active, academic_period_label

class OccupancyEngine:
    @staticmethod
    def _date_filter(check_day: str, check_date: date, teaching_active: bool = True):
        """
        Match bookings for the given day.
        - During teaching periods: recurring (timetable) + one-time system bookings both count.
        - During breaks/holidays: only one-time system bookings (booking_date IS SET) count.
          Recurring timetable bookings are suppressed — there are no classes during breaks.
        """
        if teaching_active:
            return and_(
                Booking.day_of_week == check_day,
                or_(
                    Booking.booking_date == None,        # recurring timetable
                    Booking.booking_date == check_date,  # one-time today
                ),
            )
        else:
            # Break / holiday: only count deliberate one-time bookings
            return and_(
                Booking.day_of_week == check_day,
                Booking.booking_date == check_date,
            )

    @staticmethod
    def _active_booking_now(db: Session, venue_id: int, check_day: str, check_time, check_date: date = None) -> Optional[Booking]:
        """Find a booking that is active at the given day+time."""
        check_date = check_date or date.today()
        teaching = is_teaching_active(check_date)
        return (
            db.query(Booking)
            .filter(
                Booking.venue_id == venue_id,
                Booking.status == "ACTIVE",
                Booking.start_time <= check_time,
                Booking.end_time > check_time,
                OccupancyEngine._date_filter(check_day, check_date, teaching),
            )
            .first()
        )

    @staticmethod
    def _next_booking(db: Session, venue_id: int, check_day: str, check_time, check_date: date = None) -> Optional[Booking]:
        """Find the next upcoming booking today after check_time."""
        check_date = check_date or date.today()
        teaching = is_teaching_active(check_date)
        return (
            db.query(Booking)
            .filter(
                Booking.venue_id == venue_id,
                Booking.status == "ACTIVE",
                Booking.start_time > check_time,
                OccupancyEngine._date_filter(check_day, check_date, teaching),
            )
            .order_by(Booking.start_time)
            .first()
        )

    @staticmethod
    def compute_state(db: Session, venue: Venue, at: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Compute full availability state for a venue.
        Pass `at` to compute for a hypothetical future time (forecasting).
        """
        now = at or datetime.now()
        today_weekday = now.strftime("%A").upper()
        current_time = now.time()
        today_date = now.date()
        teaching = is_teaching_active(today_date)

        active_booking = OccupancyEngine._active_booking_now(
            db, venue.id, today_weekday, current_time
        )
        next_booking = OccupancyEngine._next_booking(
            db, venue.id, today_weekday, current_time
        )

        current_occupancy = venue.current_occupancy or 0
        capacity = venue.capacity or 1

        # ── Step 1: booking-based state ─────────────────────────────────────────
        if active_booking:
            booking_state = "RED"
            reason = active_booking.booking_type
            holder = active_booking.user.name if active_booking.user else active_booking.course_name or "Scheduled"
            expected_free = datetime.combine(now.date(), active_booking.end_time)
            course_info = {
                "course_code": active_booking.course_code,
                "course_name": active_booking.course_name,
            }
        else:
            booking_state = "GREEN"
            reason = "AVAILABLE"
            holder = None
            expected_free = None
            course_info = {}

        # ── Step 2: physical occupancy from seatmap (primary truth for numbers) ──
        physical_occupied = None
        physical_free = None
        physical_occupancy_pct = None
        physical_data_source = None
        try:
            from app.models.seatmap import SeatMap
            import random as _rng
            sm = db.query(SeatMap).filter(SeatMap.venue_id == venue.id).first()
            if sm and sm.total_seats and sm.total_seats > 0:
                if sm.data_source == "MOCK":
                    # Prefer the value already written by seatmap_service (GET /seatmap
                    # updates venue.current_occupancy including overcrowding above capacity).
                    # Fall back to reproducing the same scenario seed if not yet set.
                    if venue.current_occupancy is not None and venue.current_occupancy > 0:
                        physical_occupied = venue.current_occupancy
                    else:
                        is_booked = booking_state == "RED"
                        bucket = int(datetime.now().timestamp() // 60)
                        seed_rng = _rng.Random(venue.id * 10000 + bucket)
                        scenario = seed_rng.random()
                        if is_booked:
                            if scenario < 0.70:
                                ratio = seed_rng.uniform(0.65, 0.85)
                            elif scenario < 0.90:
                                ratio = seed_rng.uniform(0.88, 1.00)
                            else:
                                ratio = seed_rng.uniform(1.02, 1.20)
                        else:
                            if scenario < 0.75:
                                ratio = seed_rng.uniform(0.03, 0.15)
                            elif scenario < 0.90:
                                ratio = seed_rng.uniform(0.55, 0.82)
                            else:
                                ratio = seed_rng.uniform(0.92, 1.10)
                        physical_occupied = round(sm.total_seats * ratio)
                else:
                    states = sm.states_json or []
                    physical_occupied = sum(1 for s in states if s.get("occupied"))
                # physical_free counts only actual seats (can't be negative even if overcrowded)
                physical_free = max(0, sm.total_seats - physical_occupied)
                physical_occupancy_pct = round(physical_occupied / sm.total_seats * 100, 1)
                physical_data_source = sm.data_source
        except Exception:
            pass

        # ── Step 3: derive final state and seat numbers ──────────────────────────
        effective_occupied = physical_occupied if physical_occupied is not None else current_occupancy
        is_overcrowded = effective_occupied > capacity

        if booking_state == "RED":
            # Booked by timetable/staff — always RED regardless of physical count.
            # Overcrowding is shown via is_overcrowded/overcrowding_count but label stays BOOKED.
            state = "RED"
            free_seats = max(0, capacity - effective_occupied)
            availability_percentage = 0.0
        else:
            # No booking. Physically full → FULL (distinct from RED/booked).
            if effective_occupied >= capacity:
                state = "FULL"
                reason = "OVERCROWDED" if is_overcrowded else "FULL_CAPACITY"
                free_seats = 0
                availability_percentage = 0.0
            else:
                state = "GREEN"
                free_seats = max(0, capacity - effective_occupied)
                availability_percentage = round((free_seats / capacity) * 100, 1)

        # Update current_occupancy to reflect physical reality
        current_occupancy = effective_occupied

        if availability_percentage >= 70:
            level = "HIGH"
        elif availability_percentage >= 30:
            level = "MEDIUM"
        else:
            level = "LOW"

        next_booking_info = None
        if next_booking:
            next_booking_info = {
                "start_time": next_booking.start_time.strftime("%H:%M"),
                "end_time": next_booking.end_time.strftime("%H:%M"),
                "course_name": next_booking.course_name,
                "holder": next_booking.user.name if next_booking.user else None,
            }

        return {
            "venue_id": venue.id,
            "venue_name": venue.name,
            "availability_state": state,
            "availability_reason": reason,
            "availability_percentage": availability_percentage,
            "availability_level": level,
            "current_occupancy": current_occupancy,
            "capacity": capacity,
            "free_seats": free_seats,
            "current_holder": holder,
            "expected_free_time": expected_free.isoformat() if expected_free else None,
            "last_updated": venue.last_updated,
            "data_mode": venue.data_mode,
            "next_booking": next_booking_info,
            "is_overcrowded": is_overcrowded,
            "overcrowding_count": max(0, effective_occupied - capacity) if is_overcrowded else 0,
            "physical_occupied_seats": physical_occupied,
            "physical_free_seats": physical_free,
            "physical_occupancy_pct": physical_occupancy_pct,
            "physical_data_source": physical_data_source,
            "academic_period": academic_period_label(today_date),
            "timetable_active": teaching,
            **course_info,
        }

    @staticmethod
    def get_all_venues_state(db: Session) -> List[Dict]:
        """Returns live state of all venues."""
        venues = db.query(Venue).all()
        return [OccupancyEngine.compute_state(db, v) for v in venues]

    @staticmethod
    def get_summary_stats(db: Session) -> Dict[str, Any]:
        """Campus-wide summary for the dashboard."""
        states = OccupancyEngine.get_all_venues_state(db)
        total = len(states)
        green = sum(1 for s in states if s["availability_state"] == "GREEN")
        red = sum(1 for s in states if s["availability_state"] == "RED")
        full = sum(1 for s in states if s["availability_state"] == "FULL")
        occupied = red + full   # both booked and physically full are "not available"
        avg_availability = round(
            sum(s["availability_percentage"] for s in states) / total, 1
        ) if total else 0

        return {
            "total_venues": total,
            "available": green,
            "occupied": occupied,
            "booked": red,
            "full": full,
            "availability_percentage": avg_availability,
        }

    @staticmethod
    def get_venue_schedule(db: Session, venue_id: int, day: str, check_date: date = None) -> List[Dict]:
        """Return all bookings for a venue on a given day (recurring + today's one-time)."""
        check_date = check_date or date.today()
        teaching = is_teaching_active(check_date)
        bookings = (
            db.query(Booking)
            .filter(
                Booking.venue_id == venue_id,
                Booking.status == "ACTIVE",
                OccupancyEngine._date_filter(day.upper(), check_date, teaching),
            )
            .order_by(Booking.start_time)
            .all()
        )
        return [
            {
                "start_time": b.start_time.strftime("%H:%M"),
                "end_time": b.end_time.strftime("%H:%M"),
                "course_code": b.course_code,
                "course_name": b.course_name,
                "session_type": b.booking_type,
                "lecturer": b.user.name if b.user else None,
                "booking_date": b.booking_date.isoformat() if b.booking_date else None,
                "is_recurring": b.booking_date is None,
            }
            for b in bookings
        ]

    @staticmethod
    def forecast_day(db: Session, venue: Venue, day: str, check_date: date = None) -> List[Dict]:
        """
        Return hourly availability forecast for a venue on a given day.
        Combines timetable bookings with current physical occupancy.
        During breaks, timetable bookings are suppressed.
        """
        check_date = check_date or date.today()
        teaching = is_teaching_active(check_date)
        slots = []
        for hour in range(6, 22):   # 06:00 – 21:00
            from datetime import time as t
            check_time = t(hour, 0)
            booking = (
                db.query(Booking)
                .filter(
                    Booking.venue_id == venue.id,
                    Booking.status == "ACTIVE",
                    Booking.start_time <= check_time,
                    Booking.end_time > check_time,
                    OccupancyEngine._date_filter(day.upper(), check_date, teaching),
                )
                .first()
            )
            if booking:
                state = "RED"
                pct = 0.0
            else:
                state = "GREEN"
                pct = 100.0
            slots.append({
                "hour": f"{hour:02d}:00",
                "state": state,
                "availability_percentage": pct,
            })
        return slots

def update_venue_occupancy(db: Session, venue: Venue, new_occupancy: int, source: str = "MANUAL"):
    """Update physical count, fire alarm check, return new state."""
    old_state = "RED" if (venue.current_occupancy or 0) >= (venue.capacity or 1) else "GREEN"

    venue.current_occupancy = new_occupancy
    db.commit()
    db.refresh(venue)

    new_state_data = OccupancyEngine.compute_state(db, venue)

    # RED → GREEN transition: trigger pending alarms
    if old_state == "RED" and new_state_data["availability_state"] == "GREEN":
        _trigger_alarms(db, venue.id)

    return new_state_data

def _trigger_alarms(db: Session, venue_id: int):
    """Mark pending alarms as triggered when venue goes GREEN."""
    from app.models.alarm import Alarm
    from datetime import datetime
    pending = db.query(Alarm).filter(
        Alarm.venue_id == venue_id,
        Alarm.triggered == False
    ).all()
    for alarm in pending:
        alarm.triggered = True
        alarm.triggered_at = datetime.now()
    if pending:
        db.commit()
