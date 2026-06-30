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
    ) -> None:
        self.model_path = model_path or settings.MODEL_PATH
        self.conf_threshold = (
            conf_threshold if conf_threshold is not None else settings.CONF_THRESHOLD
        )
        self.model = None
        self.using_fallback = False

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
        logger.info("YOLO model loaded from %r (fallback=%s)", weights, self.using_fallback)
        return self

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

    def detect(self, image_bytes: bytes) -> DetectionResult:
        """Run detection on raw image bytes and return a DetectionResult."""
        if self.model is None:
            raise RuntimeError("Detector model is not loaded; call load() first.")

        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_w, img_h = image.size

        start = time.perf_counter()
        results = self.model.predict(
            source=image, conf=self.conf_threshold, verbose=False
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
