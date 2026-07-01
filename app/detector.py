"""YOLOv8 garbage detector wrapper."""

from __future__ import annotations

import io
import logging
import time
from pathlib import Path

from .config import settings
from .schemas import Detection, DetectionResult

logger = logging.getLogger(__name__)

# Fixed class index order — must match the detection model and ml/dataset.yaml.
CLASS_NAMES = ["Glass", "Metal", "Paper", "Plastic", "Waste"]

_FALLBACK_WEIGHTS = "yolov8n.pt"


class Detector:
    """Loads a YOLO model once and runs inference on image bytes."""

    def __init__(
        self,
        model_path: str | None = None,
        conf_threshold: float | None = None,
        imgsz: int | None = None,
    ) -> None:
        self.model_path = model_path or settings.MODEL_PATH
        self.conf_threshold = (
            conf_threshold if conf_threshold is not None else settings.CONF_THRESHOLD
        )
        self.imgsz = imgsz if imgsz is not None else settings.IMGSZ
        self.model = None
        self.using_fallback = False
        self.device = "cpu"  # resolved in load() to mps/cuda when available

    def load(self) -> "Detector":
        """Warm-load the YOLO model.

        If the configured weights are missing, fall back to ultralytics
        'yolov8n.pt' so the app still boots (logged as a warning).
        """
        from ultralytics import YOLO  # imported lazily to keep module importable

        weights = self.model_path
        if not Path(weights).is_file():
            logger.warning(
                "MODEL_PATH weights not found at %r; falling back to %r",
                weights,
                _FALLBACK_WEIGHTS,
            )
            weights = _FALLBACK_WEIGHTS
            self.using_fallback = True

        self.model = YOLO(weights)
        self.device = self._pick_device()
        logger.info(
            "YOLO model loaded from %r (fallback=%s, device=%s)",
            weights, self.using_fallback, self.device,
        )
        return self

    @staticmethod
    def _pick_device() -> str:
        """Pick the fastest available inference device (mps > cuda > cpu).

        Ultralytics does not auto-select Apple's MPS backend; doing so here
        gives a ~3-4x speedup on Apple Silicon (notably for video).
        """
        try:
            import torch

            if torch.backends.mps.is_available():
                return "mps"
            if torch.cuda.is_available():
                return "cuda"
        except Exception:  # noqa: BLE001 - torch missing/broken -> cpu
            pass
        return "cpu"

    @property
    def loaded(self) -> bool:
        """Whether a model instance is loaded."""
        return self.model is not None

    def _class_name(self, cls_id: int) -> str:
        """Resolve a class id to a contract class name.

        Trusts the loaded model's names; for the project model these match
        CLASS_NAMES. For the generic fallback model, names are best-effort.
        """
        names = getattr(self.model, "names", None)
        if isinstance(names, dict) and cls_id in names:
            return str(names[cls_id])
        if 0 <= cls_id < len(CLASS_NAMES):
            return CLASS_NAMES[cls_id]
        return str(cls_id)

    def detect(
        self, image_bytes: bytes, imgsz: int | None = None
    ) -> DetectionResult:
        """Run detection on raw image bytes and return a DetectionResult.

        ``imgsz`` overrides the configured inference size for this call only;
        higher values recover more small objects at the cost of latency.
        """
        if self.model is None:
            raise RuntimeError("Detector model is not loaded; call load() first.")

        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_w, img_h = image.size

        start = time.perf_counter()
        results = self.model.predict(
            source=image,
            conf=self.conf_threshold,
            imgsz=imgsz if imgsz is not None else self.imgsz,
            device=self.device,
            verbose=False,
        )
        inference_ms = (time.perf_counter() - start) * 1000.0

        detections: list[Detection] = []
        area = float(img_w * img_h) or 1.0
        for res in results:
            boxes = getattr(res, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
                conf = float(box.conf[0].item())
                cls_id = int(box.cls[0].item())
                bw = max(0.0, x2 - x1)
                bh = max(0.0, y2 - y1)
                detections.append(
                    Detection(
                        class_name=self._class_name(cls_id),
                        confidence=conf,
                        bbox=[x1, y1, x2, y2],
                        area_fraction=(bw * bh) / area,
                    )
                )

        return DetectionResult(
            detections=detections,
            image_width=img_w,
            image_height=img_h,
            inference_ms=inference_ms,
        )

    def annotate(
        self, image_bytes: bytes, imgsz: int | None = None
    ) -> bytes:
        """Run detection and return the image with boxes/masks/labels drawn.

        Returns JPEG-encoded bytes. Uses the same conf/imgsz as ``detect`` so
        the drawn boxes match the persisted incident.
        """
        if self.model is None:
            raise RuntimeError("Detector model is not loaded; call load() first.")

        import cv2
        import numpy as np
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        # Downscale huge photos before drawing: res.plot() renders masks at the
        # source resolution, so a multi-megapixel image with many detections can
        # blow up memory ("Invalid buffer size"). Display-only, so this is safe.
        max_side = 1600
        if max(image.size) > max_side:
            image.thumbnail((max_side, max_side))
        results = self.model.predict(
            source=image,
            conf=self.conf_threshold,
            imgsz=imgsz if imgsz is not None else self.imgsz,
            device=self.device,
            verbose=False,
        )
        # res.plot() returns a BGR ndarray with boxes + segmentation masks.
        annotated_bgr = results[0].plot()
        ok, buf = cv2.imencode(".jpg", annotated_bgr)
        if not ok:
            raise RuntimeError("failed to JPEG-encode the annotated image")
        return np.asarray(buf).tobytes()

    def annotate_video(
        self,
        video_path: str,
        imgsz: int | None = None,
        stride: int | None = None,
        max_frames: int = 200,
        out_width: int = 640,
        gif_fps: int = 10,
        video_imgsz: int = 640,
    ) -> tuple[bytes, dict]:
        """Detect on sampled video frames and return an annotated animated GIF.

        Frames are sampled at ``stride`` (auto-derived from source fps toward
        ``gif_fps`` when None), each run through the model and drawn with
        ``res.plot()`` (boxes + segmentation masks), downscaled to ``out_width``,
        and encoded as a looping GIF.

        Per-frame inference defaults to ``video_imgsz`` (640) rather than the
        configured ``self.imgsz`` (often 1280): running the heavy size on every
        frame makes GIFs of real videos take minutes on CPU. 640 is ~5x faster
        and visually equivalent for the preview. Pass ``imgsz`` to override.

        Returns ``(gif_bytes, summary)`` where summary reports how many frames
        were processed, how many contained garbage, per-class counts, and whether
        the ``max_frames`` cap was hit (so nothing is silently truncated).
        """
        if self.model is None:
            raise RuntimeError("Detector model is not loaded; call load() first.")

        import cv2
        from PIL import Image

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"could not open video: {video_path}")

        src_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if stride is None:
            # sample down to ~gif_fps; e.g. 30fps source -> every 3rd frame
            stride = max(1, round(src_fps / gif_fps)) if src_fps > 0 else 3

        pil_frames: list[Image.Image] = []
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
                    if len(pil_frames) >= max_frames:
                        capped = True
                        break
                    # Downscale large frames (e.g. 4K) before predict/plot to
                    # avoid the full-res mask-render memory blowup.
                    fh, fw = frame.shape[:2]
                    if fw > 1600:
                        frame = cv2.resize(frame, (1600, round(fh * 1600 / fw)))
                    res = self.model.predict(
                        source=frame,
                        conf=self.conf_threshold,
                        imgsz=imgsz if imgsz is not None else video_imgsz,
                        device=self.device,
                        verbose=False,
                    )[0]
                    boxes = getattr(res, "boxes", None)
                    if boxes is not None and len(boxes):
                        frames_with_garbage += 1
                        for b in boxes:
                            name = self._class_name(int(b.cls[0].item()))
                            class_counts[name] = class_counts.get(name, 0) + 1
                    annotated_bgr = res.plot()
                    annotated_rgb = cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB)
                    h, w = annotated_rgb.shape[:2]
                    if w > out_width:
                        annotated_rgb = cv2.resize(
                            annotated_rgb, (out_width, round(h * out_width / w))
                        )
                    pil_frames.append(Image.fromarray(annotated_rgb))
                idx += 1
        finally:
            cap.release()

        if not pil_frames:
            raise RuntimeError("no frames decoded from video")

        buf = io.BytesIO()
        pil_frames[0].save(
            buf,
            format="GIF",
            save_all=True,
            append_images=pil_frames[1:],
            loop=0,
            duration=int(1000 / max(gif_fps, 1)),
            optimize=True,
            disposal=2,
        )

        summary = {
            "source_frames": total,
            "source_fps": round(src_fps, 2),
            "stride": stride,
            "frames_processed": len(pil_frames),
            "frames_with_garbage": frames_with_garbage,
            "class_counts": class_counts,
            "capped_at_max_frames": capped,
            "max_frames": max_frames,
        }
        return buf.getvalue(), summary
