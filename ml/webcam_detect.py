"""Live webcam garbage detection.

Opens your Mac's camera, runs the trained YOLOv8 model on every frame, and
draws bounding boxes + labels in real time -- the live version of the README
demo. Press 'q' (or Esc) in the window to quit; 's' saves the current frame.

Usage:
    .venv/bin/python -m ml.webcam_detect                 # defaults
    .venv/bin/python -m ml.webcam_detect --cam 0 --conf 0.35 --imgsz 640
    .venv/bin/python -m ml.webcam_detect --weights ml/weights/best.pt

Note (macOS): the first run pops a camera-permission prompt for your
terminal app -- click Allow, then re-run. Must be run from YOUR terminal
(not a background process) so the window appears and the prompt shows.
"""
import argparse
import time
from pathlib import Path

import cv2
from ultralytics import YOLO


def main() -> None:
    ap = argparse.ArgumentParser(description="Live webcam garbage detection")
    ap.add_argument("--weights", default="ml/weights/best.pt", help="YOLOv8 .pt weights")
    ap.add_argument("--cam", type=int, default=0, help="camera index (0 = default)")
    ap.add_argument("--conf", type=float, default=0.25, help="confidence threshold")
    ap.add_argument("--imgsz", type=int, default=416, help="inference size (model trained at 416)")
    args = ap.parse_args()

    if not Path(args.weights).exists():
        raise SystemExit(f"weights not found: {args.weights} (run from the repo root)")

    print(f"loading model: {args.weights}")
    model = YOLO(args.weights)
    device = "cpu"
    try:
        import torch
        if torch.backends.mps.is_available():
            device = "mps"
        elif torch.cuda.is_available():
            device = "cuda"
    except Exception:
        pass
    print(f"classes: {model.names} | device: {device}")

    cap = cv2.VideoCapture(args.cam)
    if not cap.isOpened():
        raise SystemExit(
            f"could not open camera {args.cam}. On macOS, grant camera access "
            "to your terminal in System Settings > Privacy & Security > Camera."
        )

    win = "Garbage Detection (q=quit, s=save)"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    saves = 0
    prev = time.time()
    fps = 0.0

    while True:
        ok, frame = cap.read()
        if not ok:
            print("no frame from camera; exiting")
            break

        # stream=False, single frame; verbose off to keep the console quiet
        res = model.predict(frame, conf=args.conf, imgsz=args.imgsz, device=device, verbose=False)[0]
        annotated = res.plot()  # frame with boxes + labels drawn by ultralytics

        now = time.time()
        fps = 0.9 * fps + 0.1 * (1.0 / max(now - prev, 1e-6))
        prev = now
        n = len(res.boxes)
        cv2.putText(annotated, f"{fps:4.1f} FPS  |  {n} object(s)", (12, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        cv2.imshow(win, annotated)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):  # q or Esc
            break
        if key == ord("s"):
            out = f"webcam_capture_{saves}.jpg"
            cv2.imwrite(out, annotated)
            print(f"saved {out}")
            saves += 1

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
