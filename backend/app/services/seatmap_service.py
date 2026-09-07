# seatmap_service.py
# I wrote this to handle saving/loading seat maps and updating
# seat states from the camera inference output.

import math
import random
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.models.seatmap import SeatMap
from app.models.venue import Venue
from app.services.occupancy_engine import OccupancyEngine

# ── Layout generation ────────────────────────────────────────────────────────

def _grid_dims(capacity: int):
    """Return (rows, cols) for a roughly rectangular grid."""
    cols = math.ceil(math.sqrt(capacity * 1.4))   # slightly wider than tall
    rows = math.ceil(capacity / cols)
    return rows, cols

def _row_label(row_idx: int) -> str:
    """0→A, 1→B, …, 25→Z, 26→AA …"""
    label = ""
    n = row_idx
    while True:
        label = chr(ord("A") + n % 26) + label
        n = n // 26 - 1
        if n < 0:
            break
    return label

def generate_layout(venue: Venue) -> Dict[str, Any]:
    """
    Build a layout_json for a venue from its capacity.
    ROI bounding boxes are evenly distributed across a simulated camera frame.
    When the calibration tool runs on a real camera snapshot, it overwrites
    these ROIs with actual pixel-accurate positions.
    """
    capacity = venue.capacity or 30
    rows, cols = _grid_dims(capacity)
    total = min(rows * cols, capacity)

    aisle_after = cols // 2 if cols > 4 else None

    # Camera frame is divided into a grid — seats fill the middle 80% of frame
    margin_x, margin_y = 0.05, 0.10
    usable_w = 0.90
    usable_h = 0.80
    seat_w = usable_w / (cols + (1 if aisle_after else 0)) * 0.85
    seat_h = usable_h / rows * 0.75

    seats = []
    seat_count = 0
    for r in range(rows):
        for c in range(cols):
            if seat_count >= total:
                break
            row_label = _row_label(r)
            col_label = str(c + 1)

            # x offset: add aisle gap after aisle_after column
            aisle_gap = (seat_w * 1.5) if (aisle_after and c >= aisle_after) else 0
            x = margin_x + c * (usable_w / cols) + aisle_gap
            y = margin_y + r * (usable_h / rows)

            seats.append({
                "id": f"{row_label}{col_label}",
                "row": r,
                "col": c,
                "row_label": row_label,
                "col_label": col_label,
                "roi": {
                    "x": round(x, 4),
                    "y": round(y, 4),
                    "w": round(seat_w, 4),
                    "h": round(seat_h, 4),
                },
            })
            seat_count += 1

    return {
        "rows": rows,
        "cols": cols,
        "total_seats": seat_count,
        "aisle_after_col": aisle_after,
        "seats": seats,
    }

# ── Mock state generation ────────────────────────────────────────────────────

def generate_mock_states(db: Session, seatmap: SeatMap) -> List[Dict]:
    """
    Produce realistic per-seat states that swing dynamically over time.
    Seed changes every 60s so polls show live drift. A scenario roll
    determines the occupancy band first, allowing venues to organically
    crowded up, go overcrowded, or stay quiet.
    """
    venue = db.query(Venue).filter(Venue.id == seatmap.venue_id).first()
    if not venue:
        return []

    seats = seatmap.layout_json.get("seats", [])
    total = len(seats)
    if total == 0:
        return []

    bucket = int(datetime.now().timestamp() // 60)
    rng = random.Random(seatmap.venue_id * 10000 + bucket)

    # Check if venue is currently booked (use booking_state only, not physical)
    from app.services.occupancy_engine import OccupancyEngine
    from app.models.booking import Booking
    from datetime import datetime as dt
    now = dt.now()
    day = now.strftime("%A").upper()
    check_time = now.time()
    from sqlalchemy import or_, and_
    from app.models.booking import Booking
    from datetime import date
    today = date.today()
    active = db.query(Booking).filter(
        Booking.venue_id == venue.id,
        Booking.status == "ACTIVE",
        Booking.start_time <= check_time,
        Booking.end_time > check_time,
        Booking.day_of_week == day,
        or_(Booking.booking_date == None, Booking.booking_date == today),
    ).first()
    is_booked = active is not None

    scenario = rng.random()   # 0.0–1.0, unique per venue+bucket

    if is_booked:
        # Booked room — class in session
        if scenario < 0.70:
            ratio = rng.uniform(0.65, 0.85)   # normal class
        elif scenario < 0.90:
            ratio = rng.uniform(0.88, 1.00)   # packed class
        else:
            ratio = rng.uniform(1.02, 1.20)   # overcrowded — people standing/extra
    else:
        # Unbooked room
        if scenario < 0.75:
            ratio = rng.uniform(0.03, 0.15)   # quiet — few lingering people
        elif scenario < 0.90:
            ratio = rng.uniform(0.55, 0.82)   # spontaneous gathering / study group
        else:
            ratio = rng.uniform(0.92, 1.10)   # unexpectedly overfull → FULL_CAPACITY

    # physical_count can exceed total seats (standing people, overcrowding)
    physical_count = round(total * ratio)

    # Seat states: mark seats occupied up to total; excess = standing people
    seated_occupied = min(physical_count, total)
    occupied_ids = set(rng.sample([s["id"] for s in seats], seated_occupied))

    states = [
        {
            "id": s["id"],
            "occupied": s["id"] in occupied_ids,
            "confidence": round(rng.uniform(0.82, 0.98), 2) if s["id"] in occupied_ids
                          else round(rng.uniform(0.88, 0.99), 2),
        }
        for s in seats
    ]

    # Store the real physical count (may exceed total seats) in venue so
    # OccupancyEngine can report actual overcrowding
    if venue.current_occupancy != physical_count:
        venue.current_occupancy = physical_count
        db.commit()

    return states

# ── Public API ───────────────────────────────────────────────────────────────

def get_seatmap_with_states(db: Session, venue_id: int) -> Dict[str, Any] | None:
    """
    Return the seat map with current states.
    For MOCK source: regenerate states on every call.
    For CAMERA source: return stored states (inference loop keeps them fresh).
    """
    sm = db.query(SeatMap).filter(SeatMap.venue_id == venue_id).first()
    if not sm:
        return None

    if sm.data_source == "MOCK":
        states = generate_mock_states(db, sm)
    else:
        states = sm.states_json or []

    # Merge states into layout
    state_map = {s["id"]: s for s in states}
    seats_with_state = []
    for seat in sm.layout_json.get("seats", []):
        s = state_map.get(seat["id"], {"id": seat["id"], "occupied": False, "confidence": 1.0})
        seats_with_state.append({**seat, "occupied": s["occupied"], "confidence": s["confidence"]})

    occupied = sum(1 for s in seats_with_state if s["occupied"])

    return {
        "venue_id": venue_id,
        "rows": sm.rows,
        "cols": sm.cols,
        "total_seats": sm.total_seats,
        "occupied_seats": occupied,
        "free_seats": sm.total_seats - occupied,
        "occupancy_percentage": round(occupied / sm.total_seats * 100, 1) if sm.total_seats else 0,
        "aisle_after_col": sm.layout_json.get("aisle_after_col"),
        "seats": seats_with_state,
        "data_source": sm.data_source,
        "last_updated": sm.last_updated.isoformat() if sm.last_updated else None,
    }

def update_states_from_camera(db: Session, venue_id: int, states: List[Dict]) -> bool:
    """
    Called by the inference loop with real per-seat states.
    Also updates venue.current_occupancy so OccupancyEngine propagates
    the real count to dashboard, live venues, search, and alarms.
    """
    sm = db.query(SeatMap).filter(SeatMap.venue_id == venue_id).first()
    if not sm:
        return False
    sm.states_json = states
    sm.data_source = "CAMERA"
    sm.last_updated = datetime.now()

    occupied_count = sum(1 for s in states if s.get("occupied"))
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if venue:
        venue.current_occupancy = occupied_count
        venue.data_mode = "LIVE"

    db.commit()

    # Write an occupancy reading so analytics accumulate camera data
    if venue:
        from app.services.analytics_service import record_reading
        from app.services.occupancy_engine import OccupancyEngine
        state = OccupancyEngine.compute_state(db, venue)
        record_reading(
            db=db,
            venue_id=venue_id,
            occupied_count=occupied_count,
            total_seats=sm.total_seats or venue.capacity,
            availability_state=state["availability_state"],
            data_source="CAMERA",
            booking_active=state["availability_state"] == "RED",
            rate_limit_minutes=0,   # always record camera data
        )

    return True

def save_layout(db: Session, venue_id: int, layout: Dict) -> bool:
    """Called by calibration tool to save ROI bounding boxes."""
    sm = db.query(SeatMap).filter(SeatMap.venue_id == venue_id).first()
    if not sm:
        return False
    sm.layout_json = layout
    sm.rows = layout.get("rows", sm.rows)
    sm.cols = layout.get("cols", sm.cols)
    sm.total_seats = layout.get("total_seats", sm.total_seats)
    db.commit()
    return True
