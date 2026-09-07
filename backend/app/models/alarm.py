# alarm.py — Alarm model
# Students set alarms to get notified when a venue becomes free.

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class Alarm(Base):
    __tablename__ = "alarms"

    id = Column(Integer, primary_key=True, index=True)
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    note = Column(String, nullable=True)
    triggered = Column(Boolean, default=False, nullable=False)
    triggered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    venue = relationship("Venue")
    user = relationship("User")

    def __repr__(self):
        return f"<Alarm user={self.user_id} venue={self.venue_id} triggered={self.triggered}>"
