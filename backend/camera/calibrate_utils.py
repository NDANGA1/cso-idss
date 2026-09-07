# calibrate_utils.py — helper functions for the ROI calibration tool

from typing import List, Tuple, Dict, Any

Point = Tuple[float, float]   # (x, y) in pixels OR fractions

def _lerp(a: Point, b: Point, t: float) -> Point:
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))

def bilinear_point(tl: Point, tr: Point, bl: Point, br: Point,
                   u: float, v: float) -> Point:
    """
    Map (u, v) in [0,1]² to a pixel position inside the quadrilateral
    defined by the 4 corners.
      u = 0 → left edge,  u = 1 → right edge
      v = 0 → top edge,   v = 1 → bottom edge
    """
    top = _lerp(tl, tr, u)
    bot = _lerp(bl, br, u)
    return _lerp(top, bot, v)

def generate_rois_from_corners(
    top_left: Point,
    top_right: Point,
    bottom_left: Point,
    bottom_right: Point,
    rows: int,
    cols: int,
    frame_width: int,
    frame_height: int,
    seat_margin: float = 0.35,   # fraction of cell size to shrink for the seat box
) -> List[Dict[str, Any]]:
    """
    Given 4 corners of the seating area (in pixels) and the grid size,
    return a list of seat dicts each containing:
      id, row, col, row_label, col_label,
      roi: {x, y, w, h}  ← all as fractions of frame (0-1)

    seat_margin: how much to shrink each cell to make the seat box.
      0.0 = seat fills entire cell, 0.35 = seat takes 65% of cell (recommended).

    Call with frame_width / frame_height from the camera snapshot resolution.
    ROIs stored as fractions so they are resolution-independent.
    """
    seats = []
    for r in range(rows):
        for c in range(cols):
            # Normalised position of the cell centre
            u_center = (c + 0.5) / cols
            v_center = (r + 0.5) / rows

            # Cell corners (normalised)
            u0, u1 = c / cols, (c + 1) / cols
            v0, v1 = r / rows, (r + 1) / rows

            # Map all 4 cell corners through bilinear interpolation
            tl_px = bilinear_point(top_left, top_right, bottom_left, bottom_right, u0, v0)
            tr_px = bilinear_point(top_left, top_right, bottom_left, bottom_right, u1, v0)
            bl_px = bilinear_point(top_left, top_right, bottom_left, bottom_right, u0, v1)
            br_px = bilinear_point(top_left, top_right, bottom_left, bottom_right, u1, v1)

            # Bounding box of the 4 corners
            xs = [tl_px[0], tr_px[0], bl_px[0], br_px[0]]
            ys = [tl_px[1], tr_px[1], bl_px[1], br_px[1]]
            cell_x = min(xs)
            cell_y = min(ys)
            cell_w = max(xs) - cell_x
            cell_h = max(ys) - cell_y

            # Shrink by seat_margin
            pad_x = cell_w * seat_margin / 2
            pad_y = cell_h * seat_margin / 2
            seat_x = cell_x + pad_x
            seat_y = cell_y + pad_y
            seat_w = cell_w - 2 * pad_x
            seat_h = cell_h - 2 * pad_y

            # Convert to frame fractions
            roi = {
                "x": round(seat_x / frame_width, 4),
                "y": round(seat_y / frame_height, 4),
                "w": round(seat_w / frame_width, 4),
                "h": round(seat_h / frame_height, 4),
            }

            # Row label: A, B, C … AA, AB …
            row_label = _row_label(r)
            col_label = str(c + 1)

            seats.append({
                "id": f"{row_label}{col_label}",
                "row": r,
                "col": c,
                "row_label": row_label,
                "col_label": col_label,
                "roi": roi,
            })

    return seats

def build_layout_from_calibration(
    top_left: Point,
    top_right: Point,
    bottom_left: Point,
    bottom_right: Point,
    rows: int,
    cols: int,
    frame_width: int,
    frame_height: int,
    aisle_after_col: int = None,
) -> Dict[str, Any]:
    """
    Full layout_json ready to save to seat_maps.layout_json.
    This is what the calibration endpoint calls.
    """
    seats = generate_rois_from_corners(
        top_left, top_right, bottom_left, bottom_right,
        rows, cols, frame_width, frame_height,
    )
    return {
        "rows": rows,
        "cols": cols,
        "total_seats": len(seats),
        "aisle_after_col": aisle_after_col,
        "calibrated": True,          # flag: ROIs are real, not estimated
        "frame_width": frame_width,
        "frame_height": frame_height,
        "corners": {                  # stored so re-calibration can show the original points
            "top_left": top_left,
            "top_right": top_right,
            "bottom_left": bottom_left,
            "bottom_right": bottom_right,
        },
        "seats": seats,
    }

def _row_label(row_idx: int) -> str:
    label = ""
    n = row_idx
    while True:
        label = chr(ord("A") + n % 26) + label
        n = n // 26 - 1
        if n < 0:
            break
    return label

# ── ROI overlap check (used by inference loop) ───────────────────────────────

def point_in_roi(px: float, py: float, roi: Dict, fw: int, fh: int) -> bool:
    """Does pixel (px, py) fall inside this ROI?"""
    x = roi["x"] * fw
    y = roi["y"] * fh
    w = roi["w"] * fw
    h = roi["h"] * fh
    return x <= px <= x + w and y <= py <= y + h

def bbox_overlaps_roi(
    det_x1: float, det_y1: float, det_x2: float, det_y2: float,
    roi: Dict, fw: int, fh: int,
    iou_threshold: float = 0.15,
) -> bool:
    """
    Does a YOLO detection bounding box overlap a seat ROI enough to
    count as occupied?  Uses Intersection-over-Union (IoU).
    Lower threshold (0.15) catches partial overlaps (person edge clips seat).
    """
    rx1 = roi["x"] * fw
    ry1 = roi["y"] * fh
    rx2 = rx1 + roi["w"] * fw
    ry2 = ry1 + roi["h"] * fh

    inter_x1 = max(det_x1, rx1)
    inter_y1 = max(det_y1, ry1)
    inter_x2 = min(det_x2, rx2)
    inter_y2 = min(det_y2, ry2)

    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return False

    inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    roi_area = (rx2 - rx1) * (ry2 - ry1)

    return (inter_area / roi_area) >= iou_threshold
