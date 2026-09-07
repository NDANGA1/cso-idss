# migrate_add_booking_date.py
# I added the booking_date column later to support one-time bookings.
# This script runs the migration on an existing DB.

import psycopg
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:Jane2003@localhost:5432/cso_idss")
# Convert SQLAlchemy URL to plain psycopg connstring
conn_str = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")

with psycopg.connect(conn_str) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'bookings' AND column_name = 'booking_date'
        """)
        exists = cur.fetchone()
        if exists:
            print("[OK] booking_date column already exists — nothing to do")
        else:
            cur.execute("ALTER TABLE bookings ADD COLUMN booking_date DATE")
            cur.execute("CREATE INDEX IF NOT EXISTS ix_bookings_booking_date ON bookings(booking_date)")
            conn.commit()
            print("[OK] Added booking_date column and index to bookings table")
