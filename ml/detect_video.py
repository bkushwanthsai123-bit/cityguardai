"""Annotate a video with the trained garbage detector.

Runs YOLOv8-seg on sampled frames of a video and writes an annotated animated
GIF (boxes + masks + labels drawn) -- the video version of the README demo.
Optionally also writes an mp4 for native players.

Usage:
    .venv/bin/python -m ml.detect_video clip.mp4
    .venv/bin/python -m ml.detect_video clip.mp4 -o out.gif --fps 10 --width 640
    .venv/bin/python -m ml.detect_video clip.mp4 --mp4 --imgsz 416 --conf 0.25

Notes:
- The model was trained at imgsz=416; that's the default here for crisp boxes.
- Long videos are frame-sampled (--stride / auto) and capped (--max-frames) to
  keep the GIF a reasonable size.
"""
import argparse
from pathlib import Path

import cv2
from PIL import Image
from ultralytics import YOLO


def pick_device() -> str:
    """Fastest available device: mps (Apple GPU) > cuda > cpu."""
    try:
        import torch

        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def main() -> None:
    ap = argparse.ArgumentParser(description="Annotate a video with garbage detections")
    ap.add_argument("video", help="path to the input video")
    ap.add_argument("-o", "--out", default=None, help="output GIF path (default: <name>_detected.gif)")
    ap.add_argument("--weights", default="ml/weights/best.pt")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--imgsz", type=int, default=416, help="model was trained at 416")
    ap.add_argument("--stride", type=int, default=None, help="process every Nth frame (auto from fps if unset)")
    ap.add_argument("--max-frames", type=int, default=200, help="cap on frames written")
    ap.add_argument("--width", type=int, default=640, help="downscale output width")
    ap.add_argument("--fps", type=int, default=10, help="GIF playback fps")
    ap.add_argument("--mp4", action="store_true", help="also write an mp4v .mp4 alongside the GIF")
    args = ap.parse_args()

    if not Path(args.video).exists():
        raise SystemExit(f"video not found: {args.video}")
    if not Path(args.weights).exists():
        raise SystemExit(f"weights not found: {args.weights} (run from the repo root)")

    model = YOLO(args.weights)
    device = pick_device()
    print(f"device: {device}")
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise SystemExit(f"could not open video: {args.video}")

    src_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    stride = args.stride or (max(1, round(src_fps / args.fps)) if src_fps > 0 else 3)

    pil_frames: list[Image.Image] = []
    mp4_writer = None
    class_counts: dict[str, int] = {}
    frames_with_garbage = 0
    idx = 0
    capped = False
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % stride == 0:
                if len(pil_frames) >= args.max_frames:
                    capped = True
                    break
                res = model.predict(frame, conf=args.conf, imgsz=args.imgsz, device=device, verbose=False)[0]
                if len(res.boxes):
                    frames_with_garbage += 1
                    for b in res.boxes:
                        name = res.names[int(b.cls)]
                        class_counts[name] = class_counts.get(name, 0) + 1
                annotated_bgr = res.plot()
                h, w = annotated_bgr.shape[:2]
                if w > args.width:
                    annotated_bgr = cv2.resize(annotated_bgr, (args.width, round(h * args.width / w)))
                if args.mp4:
                    if mp4_writer is None:
                        oh, ow = annotated_bgr.shape[:2]
                        mp4_path = str(Path(args.video).with_name(f"{Path(args.video).stem}_detected.mp4"))
                        mp4_writer = cv2.VideoWriter(
                            mp4_path, cv2.VideoWriter_fourcc(*"mp4v"), args.fps, (ow, oh)
                        )
                    mp4_writer.write(annotated_bgr)
                pil_frames.append(Image.fromarray(cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB)))
            idx += 1
    finally:
        cap.release()
        if mp4_writer is not None:
            mp4_writer.release()

    if not pil_frames:
        raise SystemExit("no frames decoded from video")

    out = args.out or str(Path(args.video).with_name(f"{Path(args.video).stem}_detected.gif"))
    pil_frames[0].save(
        out, format="GIF", save_all=True, append_images=pil_frames[1:],
        loop=0, duration=int(1000 / max(args.fps, 1)), optimize=True, disposal=2,
    )

    summary = ", ".join(f"{c}:{n}" for c, n in sorted(class_counts.items())) or "none"
    print(f"processed {len(pil_frames)} frame(s) (stride {stride}, src {src_fps:.1f}fps), "
          f"{frames_with_garbage} with garbage" + (" [capped]" if capped else ""))
    print(f"detections by class: {summary}")
    print(f"wrote {out}")
    if args.mp4:
        print(f"wrote {Path(args.video).with_name(Path(args.video).stem + '_detected.mp4')}")


if __name__ == "__main__":
    main()
