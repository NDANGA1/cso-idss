# seatmap.py — SeatMap model
# I store the seat ROI layout as JSON here.
# layout_json has normalised coordinates (0-1) so they work at any resolution.

from sqlalchemy import Column, Integer, String, Enum as SQLEnum, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class SeatMap(Base):
    __tablename__ = "seat_maps"

    id = Column(Integer, primary_key=True, index=True)
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=False, unique=True)

    rows = Column(Integer, nullable=False)
    cols = Column(Integer, nullable=False)
    total_seats = Column(Integer, nullable=False)

    layout_json = Column(JSON, nullable=False)   # seat definitions + ROI bounding boxes
    states_json = Column(JSON, nullable=True)    # current per-seat states (null until first update)

    data_source = Column(
        SQLEnum("MOCK", "CAMERA", name="seatmap_source"),
        nullable=False,
        default="MOCK",
    )

    last_updated = Column(DateTime(timezone=True), onupdate=func.now(), default=func.now())

    venue = relationship("Venue")
