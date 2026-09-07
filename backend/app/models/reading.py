# reading.py — OccupancyReading model
# Every time I take an occupancy snapshot it gets saved here.
# This is what feeds the analytics charts.

from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime, ForeignKey
from app.db.base import Base

class OccupancyReading(Base):
    __tablename__ = "occupancy_readings"

    id               = Column(Integer, primary_key=True, index=True)
    venue_id         = Column(Integer, ForeignKey("venues.id"), nullable=False, index=True)
    recorded_at      = Column(DateTime, nullable=False, default=datetime.now, index=True)
    occupied_count   = Column(Integer, nullable=False)   # may exceed total_seats (overcrowding)
    total_seats      = Column(Integer, nullable=False)
    occupancy_pct    = Column(Float,   nullable=False)   # occupied_count / total_seats * 100
    availability_state = Column(String(10), nullable=False)   # GREEN | FULL | RED
    data_source      = Column(String(10), nullable=False, default="MOCK")  # MOCK | CAMERA
    booking_active   = Column(Boolean, nullable=False, default=False)
