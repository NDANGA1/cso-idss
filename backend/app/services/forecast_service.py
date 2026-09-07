# forecast_service.py
# I implemented a forecast using historical occupancy readings.
# It groups readings by hour and day-of-week, then averages them.
# Nothing fancy — just averages work well enough for this project.

import threading
from datetime import datetime, date, timedelta, time as dt_time
from typing import List, Dict, Any, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.models.reading import OccupancyReading
from app.models.venue import Venue
from app.models.booking import Booking

# ── Module-level model cache ──────────────────────────────────────────────────
_model = None
_model_lock = threading.Lock()
_model_trained_at: Optional[datetime] = None
_MIN_ROWS = 50

# ── Booking pre-loader (one query, in-memory lookup) ─────────────────────────

def _load_booking_slots(db: Session) -> Set[Tuple[int, int, int]]:
    """
    Return a set of (venue_id, day_of_week_int, hour) tuples covering every
    booked slot across all ACTIVE recurring bookings.
    day_of_week_int: 0=Mon … 6=Sun (Python weekday convention).
    """
    DAY_MAP = {
        "MONDAY": 0, "TUESDAY": 1, "WEDNESDAY": 2, "THURSDAY": 3,
        "FRIDAY": 4, "SATURDAY": 5, "SUNDAY": 6,
    }
    bookings = db.query(
        Booking.venue_id, Booking.day_of_week,
        Booking.start_time, Booking.end_time,
    ).filter(Booking.status == "ACTIVE").all()

    booked: Set[Tuple[int, int, int]] = set()
    for b in bookings:
        dow = DAY_MAP.get(b.day_of_week, -1)
        if dow < 0:
            continue
        start_h = b.start_time.hour
        end_h = b.end_time.hour + (1 if b.end_time.minute > 0 else 0)
        for h in range(start_h, end_h):
            booked.add((b.venue_id, dow, h))
    return booked

def _is_booked(slots: Set[Tuple[int, int, int]], venue_id: int, dt: datetime) -> bool:
    return (venue_id, dt.weekday(), dt.hour) in slots

# ── Model training ────────────────────────────────────────────────────────────

def _train(db: Session):
    import warnings
    from sklearn.ensemble import RandomForestRegressor
    rows = db.query(OccupancyReading).all()
    if len(rows) < _MIN_ROWS:
        return None
    X = [
        [r.recorded_at.hour, r.recorded_at.weekday(),
         1 if r.recorded_at.weekday() >= 5 else 0,
         r.venue_id, 1 if r.booking_active else 0]
        for r in rows
    ]
    y = [r.occupancy_pct for r in rows]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = RandomForestRegressor(
            n_estimators=80, max_depth=10, min_samples_leaf=6,
            n_jobs=1, random_state=42,   # n_jobs=1 avoids parallel.delayed warnings
        )
        model.fit(X, y)
    return model

def _train_in_background(db_factory):
    """Train in a daemon thread so uvicorn stays responsive during startup."""
    global _model, _model_trained_at
    try:
        from app.db.database import SessionLocal
        db = db_factory()
        m = _train(db)
        db.close()
        with _model_lock:
            _model = m
            _model_trained_at = datetime.now()
        print("[forecast] Model ready.")
    except Exception as e:
        print(f"[forecast] Training failed: {e}")

def warm_up():
    """Call once from main.py startup event — trains in background thread."""
    from app.db.database import SessionLocal
    t = threading.Thread(target=_train_in_background, args=(SessionLocal,), daemon=True)
    t.start()

def get_model(db: Session):
    global _model, _model_trained_at
    with _model_lock:
        if _model is None and _model_trained_at is None:
            # Synchronous fallback only if warm_up() was never called
            _model = _train(db)
            _model_trained_at = datetime.now()
    return _model

def retrain(db: Session):
    global _model, _model_trained_at
    with _model_lock:
        _model = _train(db)
        _model_trained_at = datetime.now()
    return _model_trained_at

def _predict_batch(model, X_batch: List[List]) -> List[float]:
    """Predict a whole batch at once; fallback heuristic if model not ready."""
    if model and X_batch:
        import numpy as np
        pcts = model.predict(np.array(X_batch))
        return [max(0.0, float(p)) for p in pcts]
    # Heuristic fallback
    return [
        70.0 if row[4] == 1 else (10.0 if (row[0] < 8 or row[0] >= 20) else 35.0)
        for row in X_batch
    ]

# ── Public forecast functions ─────────────────────────────────────────────────

def campus_next_24h(db: Session) -> List[Dict]:
    """Predicted campus avg occupancy % for each of the next 24 hours."""
    model = get_model(db)
    venues = db.query(Venue.id).all()
    venue_ids = [v.id for v in venues]
    slots = _load_booking_slots(db)
    now = datetime.now().replace(minute=0, second=0, microsecond=0)

    hours = [now + timedelta(hours=h + 1) for h in range(24)]
    # Build full batch: 24 hours × N venues
    X_batch, meta = [], []
    for slot in hours:
        for vid in venue_ids:
            booked = _is_booked(slots, vid, slot)
            X_batch.append([slot.hour, slot.weekday(), 1 if slot.weekday() >= 5 else 0, vid, 1 if booked else 0])
            meta.append(slot)

    pcts = _predict_batch(model, X_batch)

    # Average per hour
    results = []
    n = len(venue_ids)
    for i, slot in enumerate(hours):
        avg = sum(pcts[i * n:(i + 1) * n]) / n if n else 0.0
        results.append({
            "slot_dt": slot.isoformat(),
            "hour_label": slot.strftime("%H:00"),
            "predicted_pct": round(avg, 1),
        })
    return results

def campus_next_7_days(db: Session) -> List[Dict]:
    """Predicted campus avg % for each of the next 7 days (08:00–19:00 window)."""
    model = get_model(db)
    venues = db.query(Venue.id).all()
    venue_ids = [v.id for v in venues]
    slots = _load_booking_slots(db)
    today = date.today()
    DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    HOURS = list(range(8, 20))

    results = []
    for d in range(1, 8):
        target = today + timedelta(days=d)
        X_batch = []
        for h in HOURS:
            slot = datetime.combine(target, dt_time(h))
            for vid in venue_ids:
                booked = _is_booked(slots, vid, slot)
                X_batch.append([h, target.weekday(), 1 if target.weekday() >= 5 else 0, vid, 1 if booked else 0])

        pcts = _predict_batch(model, X_batch)
        avg = sum(pcts) / len(pcts) if pcts else 0.0
        results.append({
            "date": target.isoformat(),
            "day_label": DOW[target.weekday()],
            "predicted_pct": round(avg, 1),
        })
    return results

def venue_forecast_24h(db: Session, venue_id: int) -> List[Dict]:
    """Next 24-hour forecast for a single venue."""
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        return []
    model = get_model(db)
    slots = _load_booking_slots(db)
    now = datetime.now().replace(minute=0, second=0, microsecond=0)

    hours = [now + timedelta(hours=h + 1) for h in range(24)]
    X_batch = []
    booked_flags = []
    for slot in hours:
        booked = _is_booked(slots, venue_id, slot)
        booked_flags.append(booked)
        X_batch.append([slot.hour, slot.weekday(), 1 if slot.weekday() >= 5 else 0, venue_id, 1 if booked else 0])

    pcts = _predict_batch(model, X_batch)
    return [
        {
            "slot_dt": hours[i].isoformat(),
            "hour_label": hours[i].strftime("%H:00"),
            "predicted_pct": round(pcts[i], 1),
            "booking_active": booked_flags[i],
        }
        for i in range(24)
    ]

def peak_predictions(db: Session) -> Dict:
    """Busiest predicted hour, day, and venue for the next 7 days."""
    model = get_model(db)
    venues = db.query(Venue.id, Venue.name).all()
    venue_ids = [v.id for v in venues]
    venue_names = {v.id: v.name for v in venues}
    slots = _load_booking_slots(db)
    today = date.today()
    DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    # Build full batch: 7 days × 24 hours × N venues
    X_batch, slot_meta = [], []   # meta = (day_idx, hour, venue_id)
    for d in range(1, 8):
        target = today + timedelta(days=d)
        for h in range(24):
            slot_dt = datetime.combine(target, dt_time(h))
            for vid in venue_ids:
                booked = _is_booked(slots, vid, slot_dt)
                X_batch.append([h, target.weekday(), 1 if target.weekday() >= 5 else 0, vid, 1 if booked else 0])
                slot_meta.append((d, target, h, vid))

    if not X_batch:
        return {
            "busiest_hour": None, "busiest_hour_pct": None,
            "busiest_day": None, "busiest_day_pct": None,
            "busiest_venue_tomorrow": None, "busiest_venue_tomorrow_pct": None,
            "quietest_venue_tomorrow": None, "quietest_venue_tomorrow_pct": None,
            "model_trained_at": None, "model_ready": False,
            "error": "No venue data available yet",
        }

    pcts = _predict_batch(model, X_batch)

    # Aggregate
    hour_sums: Dict[Tuple, list] = {}   # (day, hour) → [pcts]
    day_sums: Dict[int, list] = {}      # day_idx → [pcts]
    venue_day1_sums: Dict[int, list] = {}  # venue_id → [pcts] for day 1 08-19

    for i, (d, target, h, vid) in enumerate(slot_meta):
        key_hour = (target, h)
        hour_sums.setdefault(key_hour, []).append(pcts[i])
        day_sums.setdefault(d, []).append(pcts[i])
        if d == 1 and 8 <= h < 20:
            venue_day1_sums.setdefault(vid, []).append(pcts[i])

    # Best hour
    best_hour_key = max(hour_sums, key=lambda k: sum(hour_sums[k]) / len(hour_sums[k]))
    best_hour_avg = sum(hour_sums[best_hour_key]) / len(hour_sums[best_hour_key])
    best_hour_dt = datetime.combine(best_hour_key[0], dt_time(best_hour_key[1]))
    best_hour_label = f"{DOW[best_hour_dt.weekday()]} {best_hour_key[1]:02d}:00"

    # Best day
    best_day_idx = max(day_sums, key=lambda k: sum(day_sums[k]) / len(day_sums[k]))
    best_day_avg = sum(day_sums[best_day_idx]) / len(day_sums[best_day_idx])
    target_day = today + timedelta(days=best_day_idx)
    best_day_label = f"{DOW[target_day.weekday()]} {target_day.strftime('%d/%m')}"

    # Venue rankings for tomorrow
    venue_avgs = sorted(
        [(vid, sum(v) / len(v)) for vid, v in venue_day1_sums.items()],
        key=lambda x: x[1], reverse=True,
    )

    return {
        "busiest_hour": best_hour_label,
        "busiest_hour_pct": round(best_hour_avg, 1),
        "busiest_day": best_day_label,
        "busiest_day_pct": round(best_day_avg, 1),
        "busiest_venue_tomorrow": venue_names.get(venue_avgs[0][0]) if venue_avgs else None,
        "busiest_venue_tomorrow_pct": round(venue_avgs[0][1], 1) if venue_avgs else None,
        "quietest_venue_tomorrow": venue_names.get(venue_avgs[-1][0]) if venue_avgs else None,
        "quietest_venue_tomorrow_pct": round(venue_avgs[-1][1], 1) if venue_avgs else None,
        "model_trained_at": _model_trained_at.isoformat() if _model_trained_at else None,
        "model_ready": model is not None,
    }

def model_info(db: Session) -> Dict:
    model = get_model(db)
    row_count = db.query(OccupancyReading).count()
    return {
        "model_ready": model is not None,
        "model_trained_at": _model_trained_at.isoformat() if _model_trained_at else None,
        "training_rows": row_count,
        "algorithm": "RandomForestRegressor",
        "features": ["hour_of_day", "day_of_week", "is_weekend", "venue_id", "booking_active"],
        "target": "occupancy_pct",
        "note": "Re-trains at startup. Call POST /forecast/retrain to refresh after new data.",
    }
