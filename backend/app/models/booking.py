# booking.py — Booking model
# Handles timetable bookings and manual bookings.
# booking_date=NULL means it's a recurring timetable entry.

from sqlalchemy import Column, Integer, String, Enum as SQLEnum, ForeignKey, Time, Date
from sqlalchemy.orm import relationship
from app.db.base import Base

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)

    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)   # nullable as per your request

    # Course information
    course_code = Column(String, nullable=True)      # e.g. "CSE3204"
    course_name = Column(String, nullable=True)      # e.g. "Database Systems"

    booking_type = Column(
        SQLEnum('TIMETABLE', 'MANUAL', 'IFMSO', 'OVERRIDE', 'BLOCKED', name="booking_type"),
        nullable=False,
        default='TIMETABLE'
    )

    # NULL = recurring weekly (timetabler); set = one-time on that specific date (lecturer/ifmso)
    booking_date = Column(Date, nullable=True, index=True)

    # Core timetable fields
    day_of_week = Column(
        SQLEnum('MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 
                'SATURDAY', 'SUNDAY', name="day_of_week"),
        nullable=False
    )
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    status = Column(
        SQLEnum('ACTIVE', 'COMPLETED', 'CANCELLED', name="booking_status"),
        nullable=False,
        default='ACTIVE'
    )

    source = Column(
        SQLEnum('TIMETABLE_PDF', 'MANUAL', 'SYSTEM', name="booking_source"),
        nullable=False,
        default='TIMETABLE_PDF'
    )

    # Relationships
    venue = relationship("Venue", back_populates="bookings")
    user = relationship("User")

    def __repr__(self):
        return f"<Booking {self.course_code or self.course_name} | {self.day_of_week} {self.start_time}-{self.end_time} | {self.booking_type}>"