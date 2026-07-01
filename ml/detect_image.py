"""Annotate a single image with the trained garbage detector.

Runs YOLOv8-seg on one image and writes a copy with boxes + masks + labels
drawn -- the still-image version of the README demo.

Usage:
    .venv/bin/python -m ml.detect_image path/to/photo.jpg
    .venv/bin/python -m ml.detect_image photo.jpg -o out.jpg --conf 0.25 --imgsz 416
"""
import argparse
from pathlib import Path

import cv2
from ultralytics import YOLO


def annotate_image(
    src: str, weights: str = "ml/weights/best.pt",
    conf: float = 0.25, imgsz: int = 416, out: str | None = None,
) -> tuple[str, list[tuple[str, float]]]:
    if not Path(src).exists():
        raise SystemExit(f"image not found: {src}")
    if not Path(weights).exists():
        raise SystemExit(f"weights not found: {weights} (run from the repo root)")

    model = YOLO(weights)
    device = "cpu"
    try:
        import torch
        if torch.backends.mps.is_available():
            device = "mps"
        elif torch.cuda.is_available():
            device = "cuda"
    except Exception:
        pass
    res = model.predict(src, conf=conf, imgsz=imgsz, device=device, verbose=False)[0]
    annotated = res.plot()  # boxes + segmentation masks + labels
    dets = [(res.names[int(b.cls)], round(float(b.conf), 2)) for b in res.boxes]

    out = out or str(Path(src).with_name(f"{Path(src).stem}_detected.jpg"))
    cv2.imwrite(out, annotated)
    return out, dets


def main() -> None:
    ap = argparse.ArgumentParser(description="Annotate one image with garbage detections")
    ap.add_argument("image", help="path to the input image")
    ap.add_argument("-o", "--out", default=None, help="output path (default: <name>_detected.jpg)")
    ap.add_argument("--weights", default="ml/weights/best.pt")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--imgsz", type=int, default=416, help="model was trained at 416")
    args = ap.parse_args()

    out, dets = annotate_image(args.image, args.weights, args.conf, args.imgsz, args.out)
    if dets:
        print("detections:", ", ".join(f"{c} {p}" for c, p in dets))
    else:
        print("no objects detected above conf threshold")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
