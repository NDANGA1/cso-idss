# routers/seatmap.py
# Endpoints for saving/getting seat layouts and updating seat states from camera.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Tuple
from pydantic import BaseModel

from app.db.database import get_db
from app.models.seatmap import SeatMap
from app.models.venue import Venue
from app.models.user import User
from app.core.deps import get_current_user, require_admin
from app.services.seatmap_service import (
    get_seatmap_with_states,
    update_states_from_camera,
    save_layout,
)

router = APIRouter(prefix="/venues", tags=["seatmap"])

class SeatStateIn(BaseModel):
    id: str
    occupied: bool
    confidence: float = 1.0

class StatesPayload(BaseModel):
    states: List[SeatStateIn]

class CalibrationPayload(BaseModel):
    top_left: Tuple[float, float]
    top_right: Tuple[float, float]
    bottom_left: Tuple[float, float]
    bottom_right: Tuple[float, float]
    rows: int
    cols: int
    frame_width: int
    frame_height: int
    aisle_after_col: Optional[int] = None

@router.get("/{venue_id}/seatmap")
async def get_seatmap(venue_id: int, db: Session = Depends(get_db)):
    """
    Live seat map for a venue.
    Returns layout + per-seat occupied/empty states.
    data_source: MOCK until CCTV inference loop runs.
    """
    result = get_seatmap_with_states(db, venue_id)
    if result is None:
        raise HTTPException(404, "No seat map found for this venue")
    return result

@router.post("/{venue_id}/seatmap/states", status_code=200)
async def update_seat_states(
    venue_id: int,
    payload: StatesPayload,
    db: Session = Depends(get_db),
):
    """
    Called by the YOLOv8n inference loop with real per-seat occupancy.
    No auth required — camera system posts directly (restrict by IP in production).
    Automatically:
      - saves states to seat_maps.states_json
      - sets data_source = CAMERA
      - updates venue.current_occupancy so dashboard/search/live-venues reflect reality
    """
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(404, "Venue not found")
    ok = update_states_from_camera(db, venue_id, [s.model_dump() for s in payload.states])
    if not ok:
        raise HTTPException(404, "No seat map found for this venue")
    return {"message": "Seat states updated", "count": len(payload.states)}

@router.post("/{venue_id}/seatmap/calibrate", status_code=200)
async def calibrate_seatmap(
    venue_id: int,
    payload: CalibrationPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Admin calibration endpoint.

    Takes 4 corner pixel coordinates of the seating area in the camera frame
    and auto-generates all seat ROI bounding boxes via bilinear interpolation.
    Variable rows/cols fully supported — just pass the actual count.

    Returns the generated layout for preview before saving.
    Call POST /venues/{id}/seatmap/layout to persist after previewing.
    """
    from camera.calibrate_utils import build_layout_from_calibration
    layout = build_layout_from_calibration(
        top_left=payload.top_left,
        top_right=payload.top_right,
        bottom_left=payload.bottom_left,
        bottom_right=payload.bottom_right,
        rows=payload.rows,
        cols=payload.cols,
        frame_width=payload.frame_width,
        frame_height=payload.frame_height,
        aisle_after_col=payload.aisle_after_col,
    )
    # Auto-save (admin can still call /layout to override)
    save_layout(db, venue_id, layout)
    return {
        "message": f"Calibrated {layout['total_seats']} seat ROIs from 4-corner input",
        "layout": layout,
    }

@router.post("/{venue_id}/seatmap/layout", status_code=200)
async def update_layout(
    venue_id: int,
    layout: dict,
    db: Session = Depends(get_db),
):
    """Save a seat layout from calibration tool or admin."""
    ok = save_layout(db, venue_id, layout)
    if not ok:
        raise HTTPException(404, "No seat map found for this venue")
    return {"message": "Layout saved"}
