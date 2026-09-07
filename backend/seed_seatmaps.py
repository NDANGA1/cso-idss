# seed_seatmaps.py
# Seeds seat maps with placeholder ROI data for testing.

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from app.db.database import SessionLocal
from app.models.venue import Venue
from app.models.seatmap import SeatMap
from app.services.seatmap_service import generate_layout

db = SessionLocal()

venues = db.query(Venue).all()
created = 0
skipped = 0

for venue in venues:
    existing = db.query(SeatMap).filter(SeatMap.venue_id == venue.id).first()
    if existing:
        skipped += 1
        continue

    layout = generate_layout(venue)
    sm = SeatMap(
        venue_id=venue.id,
        rows=layout["rows"],
        cols=layout["cols"],
        total_seats=layout["total_seats"],
        layout_json=layout,
        states_json=None,
        data_source="MOCK",
    )
    db.add(sm)
    created += 1

db.commit()
db.close()

print(f"[OK] Seeded {created} seat maps, skipped {skipped} existing")
