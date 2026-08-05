"""Wires camera + detector together for one road and adds the honesty
layer: matching each raw detection back to ground truth (for type labels
and precision/recall), and drawing the annotated frame for the dashboard.
"""

import base64

import cv2

from vision.camera import encode_jpeg, ground_truth_boxes, render_road_frame
from vision.config import MATCH_PADDING_PX
from vision.detector import Detection, HaarVehicleDetector

_DETECTION_BOX_COLOR = (0, 210, 0)
_FALSE_POSITIVE_COLOR = (0, 140, 255)
_GROUND_TRUTH_COLOR = (90, 90, 90)


def _contains_center(gt: dict, cx: float, cy: float) -> bool:
    x0, y0 = gt["x"] - MATCH_PADDING_PX, gt["y"] - MATCH_PADDING_PX
    x1, y1 = gt["x"] + gt["w"] + MATCH_PADDING_PX, gt["y"] + gt["h"] + MATCH_PADDING_PX
    return x0 <= cx <= x1 and y0 <= cy <= y1


def _match_detections(detections: list[Detection], gt_boxes: list[dict]) -> tuple[list[dict], set[int]]:
    matched_gt_ids: set[int] = set()
    results = []
    for det in detections:
        cx, cy = det.x + det.w / 2, det.y + det.h / 2
        matching_gts = [gt for gt in gt_boxes if _contains_center(gt, cx, cy)]
        best_gt = min(
            matching_gts,
            key=lambda gt: (gt["x"] + gt["w"] / 2 - cx) ** 2 + (gt["y"] + gt["h"] / 2 - cy) ** 2,
            default=None,
        )

        if best_gt is not None:
            matched_gt_ids.add(best_gt["id"])

        results.append(
            {
                **det.to_dict(),
                "matched": best_gt is not None,
                "matched_type": best_gt["type"] if best_gt is not None else None,
            }
        )
    return results, matched_gt_ids


def analyze_road(road_name: str, road_state: dict, detector: HaarVehicleDetector, seed=None) -> dict:
    frame = render_road_frame(road_state, seed=seed)
    gt_boxes = ground_truth_boxes(road_state)
    raw_detections = detector.detect(frame)
    labeled_detections, matched_gt_ids = _match_detections(raw_detections, gt_boxes)

    annotated = frame.copy()
    for gt in gt_boxes:
        cv2.rectangle(
            annotated, (gt["x"], gt["y"]), (gt["x"] + gt["w"], gt["y"] + gt["h"]),
            _GROUND_TRUTH_COLOR, thickness=1,
        )
    for det in labeled_detections:
        color = _DETECTION_BOX_COLOR if det["matched"] else _FALSE_POSITIVE_COLOR
        x, y, w, h = det["x"], det["y"], det["w"], det["h"]
        cv2.rectangle(annotated, (x, y), (x + w, y + h), color, thickness=1)
        label = f"{det['confidence']:.2f}"
        cv2.putText(
            annotated, label, (x, max(0, y - 3)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.32, color, 1, cv2.LINE_AA,
        )

    ground_truth_count = len(gt_boxes)
    detected_count = len(labeled_detections)
    recall = (len(matched_gt_ids) / ground_truth_count) if ground_truth_count else None
    precision = (
        sum(1 for d in labeled_detections if d["matched"]) / detected_count
        if detected_count
        else None
    )

    return {
        "road": road_name,
        "frame_jpeg_base64": base64.b64encode(encode_jpeg(annotated)).decode("ascii"),
        "detections": labeled_detections,
        "ground_truth_count": ground_truth_count,
        "detected_count": detected_count,
        "precision": round(precision, 2) if precision is not None else None,
        "recall": round(recall, 2) if recall is not None else None,
    }
