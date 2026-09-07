# inference.py — camera-based people detection pipeline
# I spent a lot of time on this. It loads YOLO ONNX models and runs
# detection on RTSP camera frames. I added CLAHE preprocessing,
# TTA (test-time augmentation), pose detection and temporal smoothing
# to get the best possible count accuracy on cheap cameras.
# Run: python camera/inference.py --venue_id 60 --rtsp "rtsp://..."

import argparse, time, requests, sys, os, warnings, collections
import cv2
import numpy as np

warnings.filterwarnings("ignore")

HERE        = os.path.dirname(os.path.abspath(__file__))
MODEL_M     = os.path.join(HERE, "yolov8m.onnx")    # best
MODEL_S     = os.path.join(HERE, "yolov8s.onnx")    # good
MODEL_N     = os.path.join(HERE, "yolov8n.onnx")    # fallback
MODEL_POSE  = os.path.join(HERE, "yolov8s-pose.onnx")  # pose keypoints
INPUT_W, INPUT_H = 640, 640

CONF        = 0.25
NMS_IOU     = 0.35
FRAMES      = 2       # 2 frames × 2 (TTA) = 4 passes — fast enough on CPU
SMOOTH_K    = 5
ROI_OVERLAP = 0.30

# COCO keypoint indices for pose model
KP_NOSE, KP_L_SHOULDER, KP_R_SHOULDER = 0, 5, 6
KP_L_HIP, KP_R_HIP = 11, 12

# ─── Preprocessing ────────────────────────────────────────────────────────────

def preprocess(frame):
    """CLAHE contrast enhancement + unsharp-mask sharpening."""
    lab  = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l     = clahe.apply(l)
    enhanced = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)

    # Unsharp mask — sharpen blurry RTSP frames
    blur   = cv2.GaussianBlur(enhanced, (0, 0), 3)
    sharp  = cv2.addWeighted(enhanced, 1.5, blur, -0.5, 0)
    return sharp

# ─── Detection backends ───────────────────────────────────────────────────────

class UltralyticsDetector:
    """YOLOv8 via ultralytics — handles NMS internally."""
    def __init__(self, model_path):
        from ultralytics import YOLO
        self.model = YOLO(model_path, task="detect")
        sz = os.path.getsize(model_path) // (1024*1024)
        print(f"[ok] YOLOv8 via ultralytics — {os.path.basename(model_path)} ({sz} MB)")

    def detect(self, frame):
        results = self.model(frame, classes=[0], conf=CONF, iou=NMS_IOU, verbose=False)
        boxes   = results[0].boxes.xyxy.cpu().numpy() if results[0].boxes else np.empty((0, 4))
        return boxes

    def annotate(self, frame, boxes, label=""):
        for idx, b in enumerate(boxes.astype(int), start=1):
            cv2.rectangle(frame, (b[0], b[1]), (b[2], b[3]), (0, 255, 80), 2)
            lbl = f"PERSON {idx}"
            (tw, th), _ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(frame, (b[0], b[1]-th-6), (b[0]+tw+4, b[1]), (0, 255, 80), -1)
            cv2.putText(frame, lbl, (b[0]+2, b[1]-4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
        if label:
            cv2.putText(frame, label, (10, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        return frame

class ONNXDetector:
    """YOLOv8 via OpenCV DNN — fallback."""
    def __init__(self, model_path):
        self.net = cv2.dnn.readNetFromONNX(model_path)
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        sz = os.path.getsize(model_path) // (1024*1024)
        print(f"[ok] YOLOv8 via OpenCV DNN — {os.path.basename(model_path)} ({sz} MB)")

    def detect(self, frame):
        h, w   = frame.shape[:2]
        scale  = min(INPUT_W / w, INPUT_H / h)
        nw, nh = int(w * scale), int(h * scale)
        resized = cv2.resize(frame, (nw, nh))
        pad = np.full((INPUT_H, INPUT_W, 3), 114, dtype=np.uint8)
        pad[:nh, :nw] = resized
        blob = cv2.dnn.blobFromImage(pad, 1/255.0, (INPUT_W, INPUT_H), swapRB=True)

        self.net.setInput(blob)
        out = self.net.forward(self.net.getUnconnectedOutLayersNames())[0][0].T

        boxes_raw, scores_raw = [], []
        for row in out:
            score = float(row[4])
            if score < CONF:
                continue
            cx, cy, bw, bh = row[:4]
            x1 = max(0, (cx - bw/2) / scale)
            y1 = max(0, (cy - bh/2) / scale)
            x2 = min(w, (cx + bw/2) / scale)
            y2 = min(h, (cy + bh/2) / scale)
            boxes_raw.append([x1, y1, x2-x1, y2-y1])
            scores_raw.append(score)

        if not boxes_raw:
            return np.empty((0, 4))

        indices = cv2.dnn.NMSBoxes(boxes_raw, scores_raw, CONF, NMS_IOU)
        result  = []
        for i in (indices.flatten() if len(indices) else []):
            x, y, bw, bh = boxes_raw[i]
            result.append([x, y, x+bw, y+bh])
        return np.array(result)

    def annotate(self, frame, boxes, label=""):
        for b in boxes.astype(int):
            cv2.rectangle(frame, (b[0], b[1]), (b[2], b[3]), (0, 200, 255), 2)
        if label:
            cv2.putText(frame, label, (10, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        return frame

class PoseDetector:
    """
    YOLOv8-pose — detects people via body keypoints.
    Great for overhead/angled cameras where body shape is unclear.
    A 'person' is confirmed when shoulder OR hip keypoints are visible
    with sufficient confidence (works even if head is not visible).
    """
    def __init__(self):
        from ultralytics import YOLO
        self.model = YOLO(MODEL_POSE, task="pose")
        sz = os.path.getsize(MODEL_POSE) // (1024*1024)
        print(f"[ok] YOLOv8-pose loaded — {os.path.basename(MODEL_POSE)} ({sz} MB)")

    def detect(self, frame):
        """Return bounding boxes of people confirmed by keypoint visibility."""
        results = self.model(frame, conf=CONF, verbose=False)
        boxes   = []
        if not results or results[0].keypoints is None:
            return np.empty((0, 4))

        kp_data = results[0].keypoints.data.cpu().numpy()   # (N, 17, 3) x,y,conf
        det_boxes = results[0].boxes.xyxy.cpu().numpy() if results[0].boxes else np.empty((0,4))

        for i, kps in enumerate(kp_data):
            # Check if any of: shoulders, hips have confidence > 0.3
            key_kps = [KP_L_SHOULDER, KP_R_SHOULDER, KP_L_HIP, KP_R_HIP]
            visible = sum(1 for k in key_kps if kps[k, 2] > 0.3)
            if visible >= 1 and i < len(det_boxes):
                boxes.append(det_boxes[i])

        return np.array(boxes) if boxes else np.empty((0, 4))

    def annotate(self, frame, boxes, label=""):
        for b in boxes.astype(int):
            cv2.rectangle(frame, (b[0], b[1]), (b[2], b[3]), (255, 100, 0), 2)
            cv2.putText(frame, "pose", (b[0], b[1]-5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 100, 0), 1)
        if label:
            cv2.putText(frame, label, (10, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        return frame

def ensemble_boxes(boxes_list):
    """Merge boxes from multiple detectors, deduplicate with NMS."""
    if not any(len(b) for b in boxes_list):
        return np.empty((0, 4))
    all_boxes = np.vstack([b for b in boxes_list if len(b)])
    rects  = [[float(b[0]), float(b[1]), float(b[2]-b[0]), float(b[3]-b[1])] for b in all_boxes]
    scores = [1.0] * len(rects)
    idx    = cv2.dnn.NMSBoxes(rects, scores, CONF, NMS_IOU)
    if not len(idx):
        return np.empty((0, 4))
    return all_boxes[idx.flatten()]

def load_detector(force_backend=None):
    # Pick best available detection model
    for path in [MODEL_M, MODEL_S, MODEL_N]:
        if os.path.exists(path):
            model_path = path
            break
    else:
        print(f"[error] No model found. Run:  python camera/export_model.py")
        sys.exit(1)

    print(f"[*] Detection model: {os.path.basename(model_path)}")

    if force_backend == "onnx":
        return ONNXDetector(model_path), None

    try:
        det = UltralyticsDetector(model_path)
    except Exception as e:
        print(f"[warn] ultralytics failed ({e}), falling back to OpenCV DNN")
        det = ONNXDetector(model_path)

    # Load pose model if available
    pose = None
    if os.path.exists(MODEL_POSE):
        try:
            pose = PoseDetector()
        except Exception as e:
            print(f"[warn] Pose model failed to load ({e}) — skipping")
    else:
        print(f"[info] yolov8s-pose.onnx not found — pose detection disabled")
        print(f"[hint] Run: python camera/export_model.py --pose  to enable it")

    return det, pose

# ─── Test-time augmentation ───────────────────────────────────────────────────

def detect_with_tta(detector, pose, frame):
    """
    Run detection + pose on original AND flipped frame.
    Ensemble all results through NMS.
    """
    processed = preprocess(frame)
    flipped   = cv2.flip(processed, 1)
    w         = frame.shape[1]

    box_sets = []

    # Detection model — original + flip
    b_orig = detector.detect(processed)
    b_flip = detector.detect(flipped)
    if len(b_flip):
        b_flip_m = b_flip.copy()
        b_flip_m[:, 0] = w - b_flip[:, 2]
        b_flip_m[:, 2] = w - b_flip[:, 0]
        box_sets.append(b_flip_m)
    box_sets.append(b_orig)

    # Pose model — original + flip
    if pose:
        p_orig = pose.detect(processed)
        p_flip = pose.detect(flipped)
        if len(p_flip):
            p_flip_m = p_flip.copy()
            p_flip_m[:, 0] = w - p_flip[:, 2]
            p_flip_m[:, 2] = w - p_flip[:, 0]
            box_sets.append(p_flip_m)
        box_sets.append(p_orig)

    return ensemble_boxes(box_sets)

# ─── Multi-frame sampling ─────────────────────────────────────────────────────

def detect_multi_frame(detector, pose, cap, rtsp_url, n=FRAMES):
    """Grab n frames, run full pipeline on each, return frame with most detections."""
    best_boxes = np.empty((0, 4))
    best_frame = None

    for _ in range(n):
        cap, frame = get_frame(cap, rtsp_url)
        if frame is None:
            continue
        boxes = detect_with_tta(detector, pose, frame)
        if len(boxes) >= len(best_boxes):
            best_boxes = boxes
            best_frame = frame

    return cap, best_frame, best_boxes

# ─── Camera helpers ───────────────────────────────────────────────────────────

def _make_cap(rtsp_url):
    """Open RTSP with TCP transport + timeout (avoids Windows UDP hang)."""
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|timeout;10000000"
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap

def open_camera(rtsp_url):
    print(f"[*] Connecting to {rtsp_url} (TCP transport)...")
    cap = _make_cap(rtsp_url)
    if not cap.isOpened():
        print(f"[error] Cannot connect to {rtsp_url}")
        sys.exit(1)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[ok] Camera connected — {w}x{h}")
    return cap

def get_frame(cap, rtsp_url, max_retries=5):
    for attempt in range(max_retries):
        ret, frame = cap.read()
        if ret and frame is not None:
            return cap, frame
        print(f"[warn] Frame read failed (attempt {attempt+1}/{max_retries}), reconnecting...")
        cap.release()
        time.sleep(3)
        cap = _make_cap(rtsp_url)
    return cap, None

# ─── ROI helpers ──────────────────────────────────────────────────────────────

def box_roi_iou(box, roi, fw, fh):
    """Return IoU between detection box and seat ROI."""
    rx1, ry1 = roi["x"] * fw,              roi["y"] * fh
    rx2, ry2 = (roi["x"]+roi["w"]) * fw,   (roi["y"]+roi["h"]) * fh
    bx1, by1, bx2, by2 = box

    ix1, iy1 = max(bx1, rx1), max(by1, ry1)
    ix2, iy2 = min(bx2, rx2), min(by2, ry2)
    iw, ih   = max(0, ix2-ix1), max(0, iy2-iy1)
    inter    = iw * ih
    if inter == 0:
        return 0.0
    union = (bx2-bx1)*(by2-by1) + (rx2-rx1)*(ry2-ry1) - inter
    return inter / union if union else 0.0

def box_in_roi(box, roi, fw, fh):
    """True if box centre is in ROI OR overlap >= ROI_OVERLAP."""
    # Centre-point check
    cx = (box[0] + box[2]) / 2
    cy = (box[1] + box[3]) / 2
    rx, ry = roi["x"] * fw, roi["y"] * fh
    rw, rh = roi["w"] * fw, roi["h"] * fh
    if rx <= cx <= rx+rw and ry <= cy <= ry+rh:
        return True
    # Overlap check
    return box_roi_iou(box, roi, fw, fh) >= ROI_OVERLAP

def load_roi(venue_id, api):
    try:
        r = requests.get(f"{api}/venues/{venue_id}/seatmap", timeout=5)
        if r.ok:
            data  = r.json()
            seats = data.get("seats") or data.get("layout_json", {}).get("seats", [])
            if seats:
                print(f"[ok] {len(seats)} seat ROIs loaded for venue {venue_id}")
            return seats
    except Exception as e:
        print(f"[warn] Could not fetch seat ROIs: {e}")
    print("[info] No seat ROIs — counting people in full frame")
    return []

# ─── API ──────────────────────────────────────────────────────────────────────

def post_occupancy(api, venue_id, occupied, total):
    try:
        r = requests.post(
            f"{api}/venues/{venue_id}/occupancy",
            json={"new_occupancy": occupied, "source": "CAMERA"},
            timeout=5,
        )
        if r.ok:
            print(f"[ok] venue {venue_id} → {occupied}/{total} occupied")
        else:
            print(f"[warn] API {r.status_code}: {r.text[:80]}")
    except Exception as e:
        print(f"[warn] POST failed: {e}")

def post_seat_states(api, venue_id, seat_states):
    try:
        requests.post(
            f"{api}/venues/{venue_id}/seatmap/states",
            json={"states": seat_states, "source": "CAMERA"},
            timeout=5,
        )
    except Exception as e:
        print(f"[warn] seat states POST failed: {e}")

# ─── Main loop ────────────────────────────────────────────────────────────────

def run(venue_id, rtsp_url, api, interval, show, backend):
    print()
    print(f"  ╔══════════════════════════════════════════════╗")
    print(f"  ║   CSO-IDSS Camera Inference — ENHANCED       ║")
    print(f"  ╠══════════════════════════════════════════════╣")
    print(f"  ║  Venue    : {venue_id:<32} ║")
    print(f"  ║  RTSP     : ...{rtsp_url[-29:]:<29} ║")
    print(f"  ║  Conf     : {CONF}  NMS IoU: {NMS_IOU}  Frames: {FRAMES}{'':9}║")
    print(f"  ║  TTA      : ON   CLAHE: ON   Smooth: {SMOOTH_K} readings {'':4}║")
    print(f"  ║  BG sub   : MOG2 (secondary signal){'':10}║")
    print(f"  ╚══════════════════════════════════════════════╝")
    print()

    detector, pose = load_detector(backend)
    cap      = open_camera(rtsp_url)
    seats    = load_roi(venue_id, api)
    total_seats = len(seats) or 30

    # Background subtractor — secondary signal
    bg_sub = cv2.createBackgroundSubtractorMOG2(
        history=200, varThreshold=40, detectShadows=False
    )

    # Temporal smoothing buffer
    count_history = collections.deque(maxlen=SMOOTH_K)

    last_run = 0
    boxes    = np.empty((0, 4))
    last_frame = None

    while True:
        cap, frame = get_frame(cap, rtsp_url)
        if frame is None:
            print("[error] Lost feed. Reconnecting in 10s...")
            time.sleep(10)
            cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
            continue

        # Feed background subtractor on every frame (builds model continuously)
        bg_sub.apply(frame)

        now = time.time()
        if now - last_run >= interval:
            last_run = now

            # ── 1. Multi-frame + TTA + preprocessing ──────────────────────
            cap, best_frame, boxes = detect_multi_frame(detector, pose, cap, rtsp_url)
            if best_frame is None:
                best_frame = frame

            h, w = best_frame.shape[:2]

            # ── 2. Background subtraction occupancy estimate ───────────────
            fg_mask  = bg_sub.apply(best_frame, learningRate=0)
            fg_clean = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN,
                                         np.ones((5,5), np.uint8))
            contours, _ = cv2.findContours(fg_clean, cv2.RETR_EXTERNAL,
                                            cv2.CHAIN_APPROX_SIMPLE)
            bg_blobs = sum(1 for c in contours if cv2.contourArea(c) > 800)

            # ── 3. Count per seat ROI (or full frame) ─────────────────────
            if seats:
                seat_states, yolo_count = [], 0
                for seat in seats:
                    in_seat = any(box_in_roi(b, seat["roi"], w, h) for b in boxes)
                    yolo_count += int(in_seat)
                    seat_states.append({
                        "id": seat["id"],
                        "occupied": in_seat,
                        "confidence": 0.9 if in_seat else 0.95,
                    })

                # If YOLO sees more people than ROI matches, trust YOLO count
                # (happens when a person sits outside a calibrated ROI)
                occupied_raw = max(yolo_count, len(boxes))
                if bg_blobs > occupied_raw * 1.5 and bg_blobs <= total_seats:
                    occupied_raw = max(yolo_count, int((yolo_count + bg_blobs) / 2))

                post_seat_states(api, venue_id, seat_states)
            else:
                occupied_raw = len(boxes)
                if bg_blobs > occupied_raw * 1.5:
                    occupied_raw = max(occupied_raw, int((occupied_raw + bg_blobs) / 2))

            # ── 4. Temporal smoothing ─────────────────────────────────────
            count_history.append(occupied_raw)
            occupied = int(np.median(list(count_history)))

            post_occupancy(api, venue_id, occupied, total_seats)
            last_frame = best_frame

        if show and last_frame is not None:
            vis = last_frame.copy()
            # Draw YOLO boxes — labelled PERSON 1, PERSON 2, …
            for idx, b in enumerate(boxes.astype(int), start=1):
                cv2.rectangle(vis, (b[0], b[1]), (b[2], b[3]), (0, 255, 80), 2)
                label_text = f"PERSON {idx}"
                (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                cv2.rectangle(vis, (b[0], b[1]-th-6), (b[0]+tw+4, b[1]), (0, 255, 80), -1)
                cv2.putText(vis, label_text, (b[0]+2, b[1]-4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
            # Draw seat ROIs
            if seats:
                h_vis, w_vis = vis.shape[:2]
                for seat in seats:
                    if not seat.get("roi"):
                        continue
                    rx = int(seat["roi"]["x"] * w_vis)
                    ry = int(seat["roi"]["y"] * h_vis)
                    rw = int(seat["roi"]["w"] * w_vis)
                    rh = int(seat["roi"]["h"] * h_vis)
                    color = (0, 80, 255)
                    cv2.rectangle(vis, (rx, ry), (rx+rw, ry+rh), color, 1)
                    cv2.putText(vis, seat["id"], (rx+2, ry+10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)
            # HUD
            label = (f"YOLO:{len(boxes)} BG:{bg_blobs} "
                     f"RAW:{count_history[-1] if count_history else 0} "
                     f"SMOOTH:{int(np.median(list(count_history))) if count_history else 0}"
                     f"/{total_seats}  Q=quit")
            cv2.putText(vis, label, (8, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)
            cv2.imshow(f"CSO-IDSS Venue {venue_id}", vis)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        else:
            time.sleep(0.05)

    cap.release()
    if show:
        cv2.destroyAllWindows()

def main():
    p = argparse.ArgumentParser(description="CSO-IDSS Camera Inference — Enhanced")
    p.add_argument("--venue_id",   type=int,   required=True)
    p.add_argument("--rtsp",       type=str,   required=True)
    p.add_argument("--api",        type=str,   default="http://localhost:8001")
    p.add_argument("--interval",   type=int,   default=5)
    p.add_argument("--show",       action="store_true")
    p.add_argument("--backend",    type=str,   default=None, choices=["onnx"])
    args = p.parse_args()
    run(args.venue_id, args.rtsp, args.api, args.interval, args.show, args.backend)

if __name__ == "__main__":
    main()
