# routers/forecast.py
# Returns forecasted occupancy for a venue across the day.

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services import forecast_service

router = APIRouter(prefix="/forecast", tags=["forecast"])

@router.get("/campus/24h")
async def campus_24h(db: Session = Depends(get_db)):
    return {"data": forecast_service.campus_next_24h(db)}

@router.get("/campus/7days")
async def campus_7days(db: Session = Depends(get_db)):
    """Predicted campus avg occupancy % for each of the next 7 days."""
    return {"data": forecast_service.campus_next_7_days(db)}

@router.get("/venue/{venue_id}/24h")
async def venue_24h(venue_id: int, db: Session = Depends(get_db)):
    """Predicted occupancy % for a single venue over the next 24 hours."""
    data = forecast_service.venue_forecast_24h(db, venue_id)
    if not data:
        from fastapi import HTTPException
        raise HTTPException(404, "Venue not found")
    return {"venue_id": venue_id, "data": data}

@router.get("/peaks")
async def peaks(db: Session = Depends(get_db)):
    """Busiest predicted hour, day, and venue for the next 7 days."""
    return forecast_service.peak_predictions(db)

@router.get("/model/info")
async def model_info(db: Session = Depends(get_db)):
    """Model metadata — algorithm, training rows, features."""
    return forecast_service.model_info(db)

@router.post("/retrain", status_code=200)
async def retrain(db: Session = Depends(get_db)):
    """Force model retrain on latest occupancy_readings data."""
    trained_at = forecast_service.retrain(db)
    return {"message": "Model retrained", "trained_at": trained_at.isoformat() if trained_at else None}
