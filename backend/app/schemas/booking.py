from pydantic import BaseModel, model_validator
from typing import Optional
from datetime import time, date

class BookingCreate(BaseModel):
    venue_id: int
    course_code: Optional[str] = None
    course_name: Optional[str] = None
    booking_type: str = "MANUAL"
    # One-time bookings: provide booking_date, day_of_week is auto-derived
    # Recurring bookings (timetabler only): leave booking_date None, provide day_of_week
    booking_date: Optional[date] = None
    day_of_week: Optional[str] = None
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def derive_day(self):
        if self.booking_date and not self.day_of_week:
            self.day_of_week = self.booking_date.strftime("%A").upper()
        if not self.booking_date and not self.day_of_week:
            raise ValueError("Provide either booking_date (one-time) or day_of_week (recurring)")
        return self

class BookingOut(BaseModel):
    id: int
    venue_id: int
    venue_name: Optional[str] = None
    holder_name: Optional[str] = None
    course_code: Optional[str] = None
    course_name: Optional[str] = None
    booking_type: str
    booking_date: Optional[date] = None
    day_of_week: str
    start_time: str
    end_time: str
    status: str
    source: str

    model_config = {"from_attributes": True}
