#!/usr/bin/env python3
"""Train the Smart City waste detector (YOLOv8-seg, 5 classes).

Mirrors the standard ultralytics flow: load a pretrained YOLOv8, fine-tune on
the 5-class waste dataset (Glass, Metal, Paper, Plastic, Waste), validate, and
copy the best weights to ml/weights/best.pt for the API to serve.

Usage:
    python -m ml.train --data ml/dataset.yaml --model yolov8n-seg.pt --epochs 40
    python -m ml.train --data <path>/data.yaml --imgsz 416 --device mps

The dataset is a YOLOv8 segmentation export (train/valid/test with images+labels).
Auto-selects the fastest device (mps/cuda/cpu) unless --device is given.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def pick_device() -> str:
    try:
        import torch

        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "0"
    except Exception:
        pass
    return "cpu"


def main() -> None:
    ap = argparse.ArgumentParser(description="Train YOLOv8-seg waste detector")
    ap.add_argument("--data", default="ml/dataset.yaml", help="dataset YAML")
    ap.add_argument("--model", default="yolov8n-seg.pt", help="pretrained base")
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--imgsz", type=int, default=416, help="matches deployed model")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--patience", type=int, default=10, help="early-stop patience")
    ap.add_argument("--device", default=None, help="mps/cuda/cpu (auto if unset)")
    ap.add_argument("--name", default="waste_seg", help="run name under ml/runs")
    ap.add_argument("--deploy", action="store_true",
                    help="copy best.pt to ml/weights/best.pt after training")
    args = ap.parse_args()

    from ultralytics import YOLO

    device = args.device or pick_device()
    print(f"training {args.model} on {args.data} | device={device} | "
          f"epochs={args.epochs} imgsz={args.imgsz}")

    model = YOLO(args.model)
    model.train(
        data=args.data, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
        patience=args.patience, device=device, project="ml/runs", name=args.name,
        exist_ok=True, seed=42,
    )
    # Validate on the test split for held-out metrics.
    metrics = model.val(data=args.data, split="test", imgsz=args.imgsz, device=device)
    print("test mAP50:", round(float(metrics.box.map50), 4),
          "| mAP50-95:", round(float(metrics.box.map), 4))

    best = Path("ml/runs") / args.name / "weights" / "best.pt"
    print(f"best weights: {best}")
    if args.deploy and best.is_file():
        dst = Path("ml/weights/best.pt")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(best, dst)
        print(f"deployed -> {dst}")


if __name__ == "__main__":
    main()
