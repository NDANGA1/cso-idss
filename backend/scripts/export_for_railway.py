# scripts/export_for_railway.py
# Dumps the DB for deployment to Railway.

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.db.database import get_db
from app.models.venue import Venue
from app.models.booking import Booking
from app.models.seatmap import SeatMap

def sql_val(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    # string — escape single quotes
    return "'" + str(v).replace("'", "''") + "'"

def main():
    db = next(get_db())

    venues = db.query(Venue).order_by(Venue.id).all()
    bookings = db.query(Booking).order_by(Booking.id).all()
    seatmaps = db.query(SeatMap).order_by(SeatMap.id).all()

    lines = []
    lines.append("-- CSO-IDSS seed data export")
    lines.append("-- Run this in Railway's PostgreSQL console\n")

    # ── Venues ────────────────────────────────────────────────────────────────
    lines.append("-- VENUES")
    lines.append("TRUNCATE venues RESTART IDENTITY CASCADE;\n")
    for v in venues:
        lines.append(
            f"INSERT INTO venues (id, name, capacity, total_seats, current_occupancy, data_mode) VALUES "
            f"({sql_val(v.id)}, {sql_val(v.name)}, {sql_val(v.capacity)}, "
            f"{sql_val(v.total_seats)}, {sql_val(v.current_occupancy)}, {sql_val(v.data_mode)});"
        )
    lines.append(f"SELECT setval('venues_id_seq', {max(v.id for v in venues)});\n")

    # ── Bookings ──────────────────────────────────────────────────────────────
    lines.append("-- BOOKINGS")
    lines.append("TRUNCATE bookings RESTART IDENTITY CASCADE;\n")
    for b in bookings:
        lines.append(
            f"INSERT INTO bookings (id, venue_id, course_code, course_name, booking_type, booking_date, "
            f"day_of_week, start_time, end_time, status, source) VALUES "
            f"({sql_val(b.id)}, {sql_val(b.venue_id)}, {sql_val(b.course_code)}, {sql_val(b.course_name)}, "
            f"{sql_val(b.booking_type)}, {sql_val(b.booking_date)}, {sql_val(b.day_of_week)}, "
            f"{sql_val(b.start_time)}, {sql_val(b.end_time)}, {sql_val(b.status)}, {sql_val(b.source)});"
        )
    if bookings:
        lines.append(f"SELECT setval('bookings_id_seq', {max(b.id for b in bookings)});\n")

    # ── Seatmaps ──────────────────────────────────────────────────────────────
    if seatmaps:
        lines.append("-- SEATMAPS")
        lines.append("TRUNCATE seat_maps RESTART IDENTITY CASCADE;\n")
        import json
        for s in seatmaps:
            lines.append(
                f"INSERT INTO seat_maps (id, venue_id, rows, cols, total_seats, layout_json, states_json, data_source) VALUES "
                f"({sql_val(s.id)}, {sql_val(s.venue_id)}, {sql_val(s.rows)}, {sql_val(s.cols)}, "
                f"{sql_val(s.total_seats)}, {sql_val(json.dumps(s.layout_json))}, "
                f"{sql_val(json.dumps(s.states_json) if s.states_json else None)}, {sql_val(s.data_source)});"
            )
        if seatmaps:
            lines.append(f"SELECT setval('seat_maps_id_seq', {max(s.id for s in seatmaps)});\n")

    lines.append("-- Done. Now run seed_readings.py on Railway to generate occupancy history.")

    print("\n".join(lines))
    sys.stderr.write(f"\nExported: {len(venues)} venues, {len(bookings)} bookings, {len(seatmaps)} seatmaps\n")

if __name__ == "__main__":
    main()
