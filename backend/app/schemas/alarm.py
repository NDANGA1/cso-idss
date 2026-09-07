from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AlarmCreate(BaseModel):
    venue_id: int
    Optional[str] = None

class AlarmOut(BaseModel):
    id: int
    venue_id: int
    venue_name: Optional[str]
    Optional[str]
    triggered: bool
    triggered_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}
