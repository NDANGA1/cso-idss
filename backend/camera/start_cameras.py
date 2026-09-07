# start_cameras.py
# Launches inference for all cameras defined in cameras.json.
# I spawn a thread per camera so they all run in parallel.

import argparse, json, os, subprocess, sys, signal, time

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "cameras.json")
INFERENCE = os.path.join(HERE, "inference.py")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--api", default=None, help="Override backend API URL")
    p.add_argument("--show", action="store_true", help="Show live video windows")
    p.add_argument("--interval", type=int, default=None)
    p.add_argument("--confidence", type=float, default=None)
    args = p.parse_args()

    with open(CONFIG) as f:
        config = json.load(f)

    defaults = config["defaults"]
    api      = args.api or defaults["api"]
    interval = args.interval or defaults["interval_seconds"]
    conf     = args.confidence or defaults["confidence"]
    model    = os.path.join(HERE, os.path.basename(defaults["model"]))

    active = [c for c in config["cameras"] if c["active"] and c["rtsp"]]
    if not active:
        print("[warn] No active cameras in cameras.json. Add an RTSP URL and set active=true.")
        sys.exit(0)

    procs = []
    for cam in active:
        cmd = [
            sys.executable, INFERENCE,
            "--venue_id", str(cam["venue_id"]),
            "--rtsp", cam["rtsp"],
            "--api", api,
            "--interval", str(interval),
            "--confidence", str(conf),
            "--model", model,
        ]
        if args.show:
            cmd.append("--show")

        print(f"[start] venue {cam['venue_name']} (id={cam['venue_id']})  {cam['rtsp'][:60]}...")
        proc = subprocess.Popen(cmd)
        procs.append((cam["venue_name"], proc))

    print(f"\n[ok] {len(procs)} camera(s) running. Press Ctrl+C to stop all.\n")

    def stop_all(sig=None, frame=None):
        print("\n[stop] Stopping all cameras...")
        for name, proc in procs:
            proc.terminate()
            print(f"  stopped venue {name}")
        sys.exit(0)

    signal.signal(signal.SIGINT, stop_all)
    signal.signal(signal.SIGTERM, stop_all)

    # Wait — if any process dies unexpectedly, report it
    while True:
        for name, proc in procs:
            if proc.poll() is not None:
                print(f"[warn] Camera for venue {name} exited (code {proc.returncode}). Restarting...")
                # Find config entry and relaunch
                cam = next(c for c in active if c["venue_name"] == name)
                cmd = [
                    sys.executable, INFERENCE,
                    "--venue_id", str(cam["venue_id"]),
                    "--rtsp", cam["rtsp"],
                    "--api", api,
                    "--interval", str(interval),
                    "--confidence", str(conf),
                    "--model", model,
                ]
                if args.show:
                    cmd.append("--show")
                new_proc = subprocess.Popen(cmd)
                # Replace in list
                idx = next(i for i, (n, _) in enumerate(procs) if n == name)
                procs[idx] = (name, new_proc)
        time.sleep(5)

if __name__ == "__main__":
    main()
