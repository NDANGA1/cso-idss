# export_model.py
# Exports YOLOv8 models from PyTorch to ONNX format.
# I only need to run this once to prepare the model files.

import argparse, os, ssl, shutil, sys

p = argparse.ArgumentParser()
p.add_argument("--size", default="s", choices=["n", "s", "m"],
               help="Model size: n=nano(6MB) s=small(22MB) m=medium(50MB)")
p.add_argument("--pose", action="store_true",
               help="Export yolov8s-pose.onnx for keypoint-based seated person detection")
args = p.parse_args()

if args.pose:
    args.size = "s"  # pose uses s-size weights

HERE      = os.path.dirname(os.path.abspath(__file__))
model_name = f"yolov8{args.size}-pose" if args.pose else f"yolov8{args.size}"
DEST       = os.path.join(HERE, f"{model_name}.onnx")

if os.path.exists(DEST):
    print(f"[ok] Model already exists: {DEST} ({os.path.getsize(DEST)//1024} KB)")
    sys.exit(0)

# Patch SSL to bypass certificate revocation issues on some Windows machines
_orig_ctx = ssl.create_default_context
def _no_verify(*a, **kw):
    ctx = _orig_ctx(*a, **kw)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx
ssl.create_default_context = _no_verify

import requests, urllib3
urllib3.disable_warnings()

PT_FILE = os.path.join(HERE, "..", f"{model_name}.pt")
PT_URL  = f"https://github.com/ultralytics/assets/releases/download/v8.4.0/{model_name}.pt"

# Download .pt if needed
if not os.path.exists(PT_FILE):
    print(f"[*] Downloading yolov8n.pt (~6 MB)...")
    r = requests.get(PT_URL, verify=False, stream=True, timeout=120)
    r.raise_for_status()
    with open(PT_FILE, "wb") as f:
        downloaded = 0
        for chunk in r.iter_content(8192):
            f.write(chunk)
            downloaded += len(chunk)
            print(f"\r    {downloaded//1024} KB", end="", flush=True)
    print()
    print(f"[ok] yolov8n.pt — {os.path.getsize(PT_FILE)//1024} KB")
else:
    print(f"[ok] yolov8n.pt already present")

# Export to ONNX
print("[*] Exporting to ONNX (opset 12) — takes ~60s...")
from ultralytics import YOLO
import glob

os.chdir(os.path.join(HERE, ".."))  # run from backend/
model = YOLO(f"{model_name}.pt")
model.export(format="onnx", imgsz=640, opset=12, simplify=True)

candidates = [f for f in glob.glob("**/*.onnx", recursive=True)
              if "venv" not in f and f != DEST]
if candidates:
    shutil.move(candidates[0], DEST)
    print(f"[ok] Model ready: {DEST} ({os.path.getsize(DEST)//1024} KB)")
else:
    print("[error] Could not find exported ONNX file")
    sys.exit(1)
