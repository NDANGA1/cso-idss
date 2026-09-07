# seed_readings.py
# Seeds occupancy readings so the analytics page has some data to show.

import sys, os, random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal
from app.models.reading import OccupancyReading
from app.models.venue import Venue
from app.models.booking import Booking
from app.db.base import Base
from app.db.database import engine  # noqa: F401 – needed for create_all

Base.metadata.create_all(bind=engine)

db = SessionLocal()

existing = db.query(OccupancyReading).count()
if existing > 0:
    print(f"[SKIP] occupancy_readings already has {existing} rows. Delete them first to re-seed.")
    db.close()
    sys.exit(0)

venues = db.query(Venue).all()
print(f"Seeding readings for {len(venues)} venues over 7 days (every 15 min)...")

# Pre-load ALL bookings into memory — avoids ~36k round-trips to Railway
DAY_MAP = {"MONDAY":0,"TUESDAY":1,"WEDNESDAY":2,"THURSDAY":3,"FRIDAY":4,"SATURDAY":5,"SUNDAY":6}
booked_slots: set = set()  # (venue_id, dow_int, hour)
for b in db.query(Booking).filter(Booking.status == "ACTIVE").all():
    dow = DAY_MAP.get(b.day_of_week, -1)
    if dow < 0:
        continue
    start_h = b.start_time.hour
    end_h = b.end_time.hour + (1 if b.end_time.minute > 0 else 0)
    for h in range(start_h, end_h):
        booked_slots.add((b.venue_id, dow, h))

print(f"  Loaded {len(booked_slots)} booked slots into memory")

INTERVAL_MIN = 15
now = datetime.now().replace(second=0, microsecond=0)
start = now - timedelta(days=7)

rows = []
dt = start
while dt <= now:
    slot_bucket = int(dt.timestamp() // 60)

    for venue in venues:
        is_booked = (venue.id, dt.weekday(), dt.hour) in booked_slots
        total = venue.capacity or 60

        rng = random.Random(venue.id * 10000 + slot_bucket)
        scenario = rng.random()

        if is_booked:
            if scenario < 0.70:
                ratio = rng.uniform(0.65, 0.85)
            elif scenario < 0.90:
                ratio = rng.uniform(0.88, 1.00)
            else:
                ratio = rng.uniform(1.02, 1.20)
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

        if occupied >= total:
            state = "RED" if is_booked else "FULL"
        elif is_booked:
            state = "RED"
        else:
            state = "GREEN"

        rows.append(OccupancyReading(
            venue_id=venue.id,
            recorded_at=dt,
            occupied_count=occupied,
            total_seats=total,
            occupancy_pct=pct,
            availability_state=state,
            data_source="MOCK",
            booking_active=is_booked,
        ))

    dt += timedelta(minutes=INTERVAL_MIN)

    if len(rows) >= 5000:
        db.bulk_save_objects(rows)
        db.commit()
        print(f"  {len(rows)} rows written up to {dt.strftime('%Y-%m-%d %H:%M')}...")
        rows = []

if rows:
    db.bulk_save_objects(rows)
    db.commit()

total_rows = db.query(OccupancyReading).count()
print(f"[OK] Seeded {total_rows} occupancy readings.")
db.close()
