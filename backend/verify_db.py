# verify_db.py — quick sanity check on DB contents

import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env')
from app.db.database import SessionLocal
from app.models.booking import Booking
from app.models.venue import Venue

db = SessionLocal()
print('=== VENUES ===')
for v in db.query(Venue).all():
    cnt = db.query(Booking).filter(Booking.venue_id == v.id).count()
    print(f'  {v.name:<12} cap={v.capacity}  bookings={cnt}  mode={v.data_mode}')

print(f'\nTotal venues: {db.query(Venue).count()}')
print(f'Total bookings: {db.query(Booking).count()}')

print('\n=== MONDAY BOOKINGS (first 15) ===')
for b in db.query(Booking).filter(Booking.day_of_week == 'MONDAY').order_by(Booking.start_time).limit(15).all():
    code = b.course_code or '(no code)'
    print(f'  {b.venue.name:<12} {str(b.start_time)[:5]}-{str(b.end_time)[:5]}  {code}')

db.close()
