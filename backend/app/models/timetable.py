# timetable.py — TimetableEntry model
# I parse timetable PDFs and store entries here.

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.db.base import Base

class TimetableEntry(Base):
    __tablename__ = "timetable_entries"

    id = Column(Integer, primary_key=True, index=True)
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Lecturer

    course_code = Column(String, nullable=False)
    course_name = Column(String, nullable=True)
    day_of_week = Column(String, nullable=False)  # "Monday", "Tuesday"
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)

    # Relationship
    venue = relationship("Venue")
    lecturer = relationship("User")

    def __repr__(self):
        return f"<Timetable {self.course_code} in {self.venue.name}>"