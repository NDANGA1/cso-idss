# main.py — CSO-IDSS FastAPI entry point
# I set up all the routers here and configure middleware.
# I also start the background scheduler and backfill thread on startup.
# Run with: uvicorn app.main:app --reload --port 8001

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn
import os
from sqlalchemy import text

from app.db.database import get_db, engine
from app.db.base import Base

# Routers
from app.routers.auth import router as auth_router
from app.routers.venues import router as venues_router
from app.routers.bookings import router as bookings_router
from app.routers.alarms import router as alarms_router
from app.routers.analytics import router as analytics_router
from app.routers.timetable import router as timetable_router
from app.routers.seatmap import router as seatmap_router
from app.routers.forecast import router as forecast_router

load_dotenv()

app = FastAPI(
    title="CSO-IDSS",
    description="AI-Based Real-Time Campus Space Occupation & Intelligent Decision Support System — IFM",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(venues_router)
app.include_router(bookings_router)
app.include_router(alarms_router)
app.include_router(analytics_router)
app.include_router(timetable_router)
app.include_router(seatmap_router)
app.include_router(forecast_router)

@app.get("/calendar/period", tags=["calendar"])
def get_academic_period():
    from datetime import date
    from app.core.academic_calendar import is_teaching_active, academic_period_label
    today = date.today()
    return {
        "date": today.isoformat(),
        "period": academic_period_label(today),
        "timetable_active": is_teaching_active(today),
        "is_break": not is_teaching_active(today),
    }

@app.on_event("startup")
async def create_tables():
    from app.models.venue import Venue
    from app.models.user import User
    from app.models.booking import Booking
    from app.models.alarm import Alarm
    from app.models.seatmap import SeatMap
    from app.models.reading import OccupancyReading
    Base.metadata.create_all(bind=engine)
    print("[OK] Tables created/verified")
    from app.services.forecast_service import warm_up
    warm_up()
    _backfill_on_startup()
    _start_snapshot_scheduler()

def _backfill_on_startup():
    """Fill any gaps in the last 7 days of readings — runs once in background on every startup."""
    import threading
    from app.services.analytics_service import backfill_readings
    from app.db.database import SessionLocal

    def _run():
        try:
            db = SessionLocal()
            written = backfill_readings(db, days=7)
            db.close()
            print(f"[startup] backfill complete — {written} new readings inserted")
        except Exception as e:
            print(f"[startup] backfill error: {e}")

    threading.Thread(target=_run, daemon=True).start()

def _start_snapshot_scheduler():
    """Take an occupancy snapshot every 15 min so analytics history never goes stale."""
    import threading
    from app.services.analytics_service import snapshot_all_venues
    from app.db.database import SessionLocal

    def _loop():
        import time
        while True:
            time.sleep(15 * 60)   # 15 minutes
            try:
                db = SessionLocal()
                count = snapshot_all_venues(db)
                db.close()
                print(f"[scheduler] snapshot written — {count} venues")
            except Exception as e:
                print(f"[scheduler] snapshot error: {e}")

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    print("[OK] Snapshot scheduler started (every 15 min)")

@app.get("/")
async def root():
    return {
        "message": "CSO-IDSS Backend v0.2.0",
        "status": "healthy",
        "docs": "/docs",
    }

@app.get("/health")
async def health_check():
    db_status = "not configured"
    if engine:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_status = "connected"
        except Exception as e:
            db_status = f"failed: {str(e)[:80]}"
    return {"status": "ok", "database": db_status}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
