"""Synthesizes a virtual CCTV frame for one road's approach to the stop
line, from the same state dict the WebSocket dashboard already consumes.

This stands in for a real frame grab. It is deliberately rendered with
visible edges/gradients (dark body, lighter windshield band) rather than
flat silhouettes, since the Haar cascade in detector.py was trained on
photographs and relies on those intensity-gradient patterns — flat color
blocks give it almost nothing to key on.
"""

import random

import cv2
import numpy as np

from simulation.config import STOP_LINE_POS_M
from vision.config import (
    FRAME_HEIGHT_PX,
    FRAME_WIDTH_PX,
    LANE_WIDTH_PX,
    LANES_PER_ROAD,
    PX_PER_M,
    VIEW_DISTANCE_M,
)

_BODY_COLOR = {
    "car": (150, 90, 40),
    "motorcycle": (120, 120, 120),
    "auto": (70, 150, 90),
    "bus": (30, 140, 200),
    "truck": (60, 100, 200),
    "ambulance": (230, 230, 230),
    "fire_truck": (40, 40, 200),
}
_DEFAULT_LENGTH_PX = {
    "car": 18,
    "motorcycle": 10,
    "auto": 15,
    "bus": 34,
    "truck": 32,
    "ambulance": 20,
    "fire_truck": 36,
}


def _draw_vehicle(frame: np.ndarray, cx: float, cy: float, vehicle_type: str) -> None:
    body_color = _BODY_COLOR.get(vehicle_type, _BODY_COLOR["car"])
    length_px = _DEFAULT_LENGTH_PX.get(vehicle_type, 18)
    width_px = max(14, min(LANE_WIDTH_PX - 12, int(length_px * 0.85)))

    x0, y0 = int(cx - width_px / 2), int(cy - length_px / 2)
    x1, y1 = int(cx + width_px / 2), int(cy + length_px / 2)
    if x1 <= 0 or y1 <= 0 or x0 >= frame.shape[1] or y0 >= frame.shape[0]:
        return

    cv2.rectangle(frame, (x0, y0), (x1, y1), body_color, thickness=-1)

    windshield_h = max(2, length_px // 3)
    wx0, wy0 = x0 + 2, y0 + 2
    wx1, wy1 = x1 - 2, y0 + windshield_h
    if wx1 > wx0 and wy1 > wy0:
        cv2.rectangle(frame, (wx0, wy0), (wx1, wy1), (210, 210, 210), thickness=-1)

    cv2.rectangle(frame, (x0, y0), (x1, y1), (15, 15, 15), thickness=1)


def _road_background(rng: random.Random) -> np.ndarray:
    frame = np.full((FRAME_HEIGHT_PX, FRAME_WIDTH_PX, 3), 60, dtype=np.uint8)
    noise = np.array(
        [[rng.randint(-6, 6) for _ in range(FRAME_WIDTH_PX)] for _ in range(FRAME_HEIGHT_PX)],
        dtype=np.int16,
    )
    frame = np.clip(frame.astype(np.int16) + noise[:, :, None], 0, 255).astype(np.uint8)

    center_x = FRAME_WIDTH_PX // 2
    lane_span = LANE_WIDTH_PX * LANES_PER_ROAD
    for lane_index in range(LANES_PER_ROAD + 1):
        x = center_x - lane_span // 2 + lane_index * LANE_WIDTH_PX
        dash = (x == center_x - lane_span // 2 or x == center_x + lane_span // 2)
        color = (200, 200, 200) if dash else (120, 120, 90)
        for y in range(0, FRAME_HEIGHT_PX, 14):
            cv2.line(frame, (x, y), (x, min(y + 8, FRAME_HEIGHT_PX)), color, 1)

    cv2.rectangle(frame, (0, 0), (FRAME_WIDTH_PX - 1, 2), (235, 235, 235), thickness=-1)
    return frame


def _visible_vehicle_layout(road_state: dict):
    """Yields (vehicle_dict, center_x_px, center_y_px, width_px, height_px)
    for every vehicle currently within the camera's field of view. This is
    the single source of truth for vehicle placement, shared by the frame
    renderer and by ground_truth_boxes() so the two can never drift apart.
    """
    center_x = FRAME_WIDTH_PX // 2
    lane_span = LANE_WIDTH_PX * LANES_PER_ROAD
    lanes_left_edge = center_x - lane_span // 2

    for lane in road_state["lanes"]:
        lane_index = lane["lane_index"]
        lane_center_x = lanes_left_edge + lane_index * LANE_WIDTH_PX + LANE_WIDTH_PX / 2
        for vehicle in lane["vehicles"]:
            distance_from_stop_line = STOP_LINE_POS_M - vehicle["position"]
            if not (0 <= distance_from_stop_line <= VIEW_DISTANCE_M):
                continue
            cy = distance_from_stop_line * PX_PER_M
            length_px = _DEFAULT_LENGTH_PX.get(vehicle["type"], 18)
            width_px = max(14, min(LANE_WIDTH_PX - 12, int(length_px * 0.85)))
            yield vehicle, lane_center_x, cy, width_px, length_px


def render_road_frame(road_state: dict, seed: int | None = None) -> np.ndarray:
    """Renders a BGR uint8 frame (H, W, 3) of one road's approach, showing
    vehicles within VIEW_DISTANCE_M of the stop line. Vehicles further back
    than that are simply out of the camera's field of view, same as a real
    fixed CCTV camera would be.
    """
    rng = random.Random(seed)
    frame = _road_background(rng)

    for vehicle, cx, cy, _w, _h in _visible_vehicle_layout(road_state):
        _draw_vehicle(frame, cx, cy, vehicle["type"])

    return frame


def ground_truth_boxes(road_state: dict) -> list[dict]:
    """Bounding boxes for every currently-visible vehicle, in the same pixel
    space render_road_frame() draws into. Used only for the honesty metrics
    (precision/recall) and detection-to-type labeling in pipeline.py — never
    fed back into the detector itself.
    """
    boxes = []
    for vehicle, cx, cy, w, h in _visible_vehicle_layout(road_state):
        boxes.append(
            {
                "id": vehicle["id"],
                "type": vehicle["type"],
                "x": int(cx - w / 2),
                "y": int(cy - h / 2),
                "w": w,
                "h": h,
            }
        )
    return boxes


def encode_jpeg(frame: np.ndarray, quality: int = 80) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("Failed to JPEG-encode frame")
    return buf.tobytes()
