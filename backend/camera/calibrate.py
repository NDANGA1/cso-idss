# calibrate.py
# I use this to draw seat ROI boxes on a live camera frame.
# Click and drag to mark each seat, press S to save to the backend.
# The coordinates get normalised to 0-1 so they're resolution-independent.

import argparse, json, requests, sys
import cv2
import numpy as np

drawing = False
start_x = start_y = 0
current_box = None
boxes = []
frame_orig = None
frame_display = None
seat_labels = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

def mouse_cb(event, x, y, flags, param):
    global drawing, start_x, start_y, current_box, frame_display

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        start_x, start_y = x, y

    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        frame_display = frame_orig.copy()
        _draw_existing(frame_display)
        cv2.rectangle(frame_display, (start_x, start_y), (x, y), (0, 200, 255), 2)

    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        x1, y1 = min(start_x, x), min(start_y, y)
        x2, y2 = max(start_x, x), max(start_y, y)
        if abs(x2-x1) > 10 and abs(y2-y1) > 10:
            boxes.append((x1, y1, x2, y2))
        frame_display = frame_orig.copy()
        _draw_existing(frame_display)

def _draw_existing(img):
    h, w = img.shape[:2]
    for i, (x1,y1,x2,y2) in enumerate(boxes):
        row_i = i // 10
        col_i = i % 10
        label = f"{seat_labels[row_i % len(seat_labels)]}{col_i+1}"
        cv2.rectangle(img, (x1,y1), (x2,y2), (0,255,100), 2)
        cv2.putText(img, label, (x1+4, y1+16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,100), 1)
    cv2.putText(img, f"Seats defined: {len(boxes)}  |  R=undo  S=save  Q=quit",
                (10, img.shape[0]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)

def build_layout(frame_w, frame_h):
    seats = []
    rows = max(1, len(boxes) // 10 + (1 if len(boxes) % 10 else 0))
    cols = min(10, len(boxes))
    for i, (x1,y1,x2,y2) in enumerate(boxes):
        row_i = i // 10
        col_i = i % 10
        label = f"{seat_labels[row_i % len(seat_labels)]}{col_i+1}"
        seats.append({
            "id": label,
            "row": row_i,
            "col": col_i,
            "row_label": seat_labels[row_i % len(seat_labels)],
            "col_label": str(col_i+1),
            "roi": {
                "x": round(x1/frame_w, 4),
                "y": round(y1/frame_h, 4),
                "w": round((x2-x1)/frame_w, 4),
                "h": round((y2-y1)/frame_h, 4),
            }
        })
    return {
        "rows": rows,
        "cols": cols,
        "total_seats": len(seats),
        "aisle_after_col": cols // 2,
        "seats": seats,
    }

def save_layout(venue_id, layout, api, token=None):
    try:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        r = requests.post(
            f"{api}/venues/{venue_id}/seatmap/layout",
            json=layout,
            headers=headers,
            timeout=10,
        )
        if r.ok:
            print(f"[ok] Layout saved — {layout['total_seats']} seats for venue {venue_id}")
        else:
            print(f"[error] API returned {r.status_code}: {r.text[:120]}")
    except Exception as e:
        print(f"[error] Could not reach API: {e}")
        # Save locally as fallback
        fname = f"venue_{venue_id}_layout.json"
        with open(fname, "w") as f:
            json.dump(layout, f, indent=2)
        print(f"[fallback] Layout saved locally to {fname}")

def main():
    global frame_orig, frame_display

    p = argparse.ArgumentParser()
    p.add_argument("--venue_id", type=int, required=True)
    p.add_argument("--rtsp", type=str, required=True)
    p.add_argument("--api", type=str, default="http://localhost:8001")
    p.add_argument("--token", type=str, default=None, help="Admin JWT token for API auth")
    p.add_argument("--snapshot", type=str, default=None, help="Use existing image instead of camera")
    args = p.parse_args()

    if args.snapshot:
        frame_orig = cv2.imread(args.snapshot)
    else:
        print(f"[*] Connecting to camera...")
        cap = cv2.VideoCapture(args.rtsp, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            print("[error] Cannot connect to camera")
            sys.exit(1)
        ret, frame_orig = cap.read()
        cap.release()
        if not ret:
            print("[error] Could not grab frame")
            sys.exit(1)

    h, w = frame_orig.shape[:2]
    frame_display = frame_orig.copy()
    print(f"[ok] Frame: {w}x{h}")
    print("[*] Draw ROI boxes around each seat. R=undo, S=save, Q=quit")

    cv2.namedWindow("Calibration")
    cv2.setMouseCallback("Calibration", mouse_cb)

    while True:
        cv2.imshow("Calibration", frame_display)
        key = cv2.waitKey(20) & 0xFF

        if key == ord('r') and boxes:
            boxes.pop()
            frame_display = frame_orig.copy()
            _draw_existing(frame_display)

        elif key == ord('s'):
            if not boxes:
                print("[warn] No boxes drawn yet")
                continue
            layout = build_layout(w, h)
            save_layout(args.venue_id, layout, args.api, args.token)
            break

        elif key == ord('q'):
            print("Quit without saving.")
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
