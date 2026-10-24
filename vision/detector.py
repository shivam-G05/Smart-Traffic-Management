"""OpenCV Haar Cascade vehicle detector.

Important honesty note: a single generic Haar cascade (cars.xml) is a
binary vehicle / not-vehicle detector — it localizes vehicle-shaped regions
with a bounding box and a rough confidence score, it does not classify
vehicle type. Per-detection "type" labels shown on the dashboard come from
matching each detection back to the nearest ground-truth simulated vehicle
(see pipeline.py) purely for display — a real deployment would need either
several per-class cascades or a small classifier stage on top of each crop
to get type. That limitation is real, not simulation-specific, and is
exactly why later CV pipelines (this project's natural next step beyond
Milestone 2) move to single-stage multi-class detectors instead.
"""

from dataclasses import dataclass

import cv2
import numpy as np

from vision.config import (
    CASCADE_PATH,
    DETECT_MIN_NEIGHBORS,
    DETECT_MIN_SIZE_PX,
    DETECT_SCALE_FACTOR,
    UPSCALE_FACTOR,
)


@dataclass(frozen=True)
class Detection:
    x: int
    y: int
    w: int
    h: int
    confidence: float

    def to_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "confidence": round(self.confidence, 3),
        }


class HaarVehicleDetector:
    def __init__(
        self,
        cascade_path=CASCADE_PATH,
        upscale_factor: float = UPSCALE_FACTOR,
        equalize: bool = True,
        min_neighbors: int = DETECT_MIN_NEIGHBORS,
    ):
        # The keyword arguments exist for the ablation in
        # scripts/vision_eval.py; the live pipeline uses the defaults.
        self._cascade = cv2.CascadeClassifier(str(cascade_path))
        if self._cascade.empty():
            raise RuntimeError(f"Failed to load Haar cascade from {cascade_path}")
        self.upscale_factor = upscale_factor
        self.equalize = equalize
        self.min_neighbors = min_neighbors

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        if self.equalize:
            gray = cv2.equalizeHist(gray)

        # The cascade's own training window (20x20) is close to or larger
        # than our rendered vehicles at native resolution, so it can barely
        # ever fire. Upscaling before detection — then mapping boxes back
        # down — gives it a realistic chance without inflating frame/JPEG
        # size for anything else that consumes the raw frame.
        upscaled = cv2.resize(gray, None, fx=self.upscale_factor, fy=self.upscale_factor)

        rects, _reject_levels, level_weights = self._cascade.detectMultiScale3(
            upscaled,
            scaleFactor=DETECT_SCALE_FACTOR,
            minNeighbors=self.min_neighbors,
            minSize=DETECT_MIN_SIZE_PX,
            outputRejectLevels=True,
        )

        detections = []
        for (x, y, w, h), weight in zip(rects, level_weights):
            # `weight` is the cascade's final-stage decision margin, not a
            # calibrated probability — its scale is specific to this cascade
            # and was found empirically. Treated as a relative confidence,
            # clipped to [0, 1].
            confidence = float(min(1.0, max(0.0, weight / 2.0)))
            detections.append(
                Detection(
                    int(x / self.upscale_factor),
                    int(y / self.upscale_factor),
                    int(w / self.upscale_factor),
                    int(h / self.upscale_factor),
                    confidence,
                )
            )
        return detections
