# venue.py — SQLAlchemy model for Venue
# Stores all the venue info like capacity, current occupancy and data mode.

from sqlalchemy import Column, Integer, String, Enum as SQLEnum, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class Venue(Base):
    __tablename__ = "venues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)

    capacity = Column(Integer, nullable=False, default=50)
    total_seats = Column(Integer, nullable=False, default=50)

    # Physical state (updated by camera / simulation)
    current_occupancy = Column(Integer, default=0)

    # Supporting fields
    data_mode = Column(
        SQLEnum('LIVE', 'SIMULATED', 'TIMETABLE_ONLY', name="data_mode"),
        nullable=False,
        default='SIMULATED'
    )

    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    bookings = relationship("Booking", back_populates="venue")