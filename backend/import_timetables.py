# import_timetables.py
# Script to import a batch of timetable PDFs into the system.

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Add backend root to path
sys.path.insert(0, os.path.dirname(__file__))

TIMETABLE_FOLDER = r"C:\Users\JANE KAYANGE\Desktop\FYP PRAYGOD\TIMETABLES"

def main():
    from app.db.database import SessionLocal, engine
    from app.db.base import Base
    from app.models.venue import Venue
    from app.models.user import User
    from app.models.booking import Booking
    from app.models.alarm import Alarm
    from app.services.timetable_parser import parse_timetable_pdf

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        files = [f for f in os.listdir(TIMETABLE_FOLDER) if not f.endswith(".tmp")]
        if not files:
            print(f"No files found in {TIMETABLE_FOLDER}")
            return

        print(f"Found {len(files)} file(s) in {TIMETABLE_FOLDER}\n")

        total_created = 0
        total_skipped = 0

        for fname in sorted(files):
            fpath = os.path.join(TIMETABLE_FOLDER, fname)
            print(f"Processing: {fname}")
            try:
                result = parse_timetable_pdf(fpath, db, filename=fname)
                print(f"  [OK] Created: {result['bookings_created']}  Skipped: {result['bookings_skipped']}  Pages: {result['pages_processed']}")
                if result['errors']:
                    for err in result['errors']:
                        print(f"  [WARN] {err}")
                total_created += result['bookings_created']
                total_skipped += result['bookings_skipped']
            except Exception as e:
                print(f"  [ERR] {e}")

        print(f"\nImport complete.")
        print(f"   Total bookings created : {total_created}")
        print(f"   Total bookings skipped : {total_skipped}")
        print(f"   Total venues in DB     : {db.query(Venue).count()}")
        print(f"   Total bookings in DB   : {db.query(Booking).count()}")

    finally:
        db.close()

if __name__ == "__main__":
    main()
