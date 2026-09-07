from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class VenueBase(BaseModel):
    name: str
    capacity: int
    total_seats: int
    data_mode: str = "SIMULATED"

class VenueCreate(VenueBase):
    pass

class VenueUpdate(BaseModel):
    name: Optional[str] = None
    capacity: Optional[int] = None
    total_seats: Optional[int] = None
    data_mode: Optional[str] = None

class VenueOut(VenueBase):
    id: int
    current_occupancy: int
    last_updated: Optional[datetime]

    model_config = {"from_attributes": True}

class VenueStateOut(BaseModel):
    venue_id: int
    venue_name: str
    availability_state: str          # GREEN | RED
    availability_reason: str
    availability_percentage: float
    availability_level: str          # HIGH | MEDIUM | LOW
    current_occupancy: int
    capacity: int
    free_seats: int
    current_holder: Optional[str]
    expected_free_time: Optional[str]
    last_updated: Optional[datetime]
    data_mode: str

class OccupancyUpdateIn(BaseModel):
    new_occupancy: int
    source: str = "CAMERA"           # CAMERA | MANUAL
    confidence: Optional[float] = None
