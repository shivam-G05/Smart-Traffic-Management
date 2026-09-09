import base64

import numpy as np
import pytest

from vision.camera import ground_truth_boxes, render_road_frame
from vision.config import FRAME_HEIGHT_PX, FRAME_WIDTH_PX
from vision.detector import HaarVehicleDetector
from vision.pipeline import analyze_road
from vision.tracker import ByteTracker

SAMPLE_ROAD_STATE = {
    "lanes": [
        {
            "lane_index": 0,
            "vehicles": [
                {"id": 1, "type": "car", "position": 195},
                {"id": 2, "type": "bus", "position": 170},
                {"id": 3, "type": "car", "position": 100},  # out of camera view
            ],
        },
        {
            "lane_index": 1,
            "vehicles": [{"id": 4, "type": "ambulance", "position": 185}],
        },
    ]
}

EMPTY_ROAD_STATE = {"lanes": [{"lane_index": 0, "vehicles": []}, {"lane_index": 1, "vehicles": []}]}


def test_render_road_frame_shape_and_dtype():
    frame = render_road_frame(SAMPLE_ROAD_STATE, seed=1)
    assert frame.shape == (FRAME_HEIGHT_PX, FRAME_WIDTH_PX, 3)
    assert frame.dtype == np.uint8


def test_render_road_frame_is_deterministic_for_a_fixed_seed():
    a = render_road_frame(SAMPLE_ROAD_STATE, seed=5)
    b = render_road_frame(SAMPLE_ROAD_STATE, seed=5)
    assert np.array_equal(a, b)


def test_ground_truth_boxes_excludes_vehicles_outside_camera_view():
    boxes = ground_truth_boxes(SAMPLE_ROAD_STATE)
    ids = {b["id"] for b in boxes}
    assert ids == {1, 2, 4}  # vehicle 3 is beyond VIEW_DISTANCE_M from the stop line


def test_ground_truth_boxes_empty_when_no_vehicles():
    assert ground_truth_boxes(EMPTY_ROAD_STATE) == []


@pytest.fixture(scope="module")
def detector():
    return HaarVehicleDetector()


def test_detector_loads_and_returns_a_list(detector):
    frame = render_road_frame(SAMPLE_ROAD_STATE, seed=2)
    detections = detector.detect(frame)
    assert isinstance(detections, list)
    for det in detections:
        assert 0.0 <= det.confidence <= 1.0
        assert det.w > 0 and det.h > 0


def test_detector_on_empty_road_rarely_explodes_with_detections(detector):
    frame = render_road_frame(EMPTY_ROAD_STATE, seed=3)
    detections = detector.detect(frame)
    assert len(detections) < 10


def test_analyze_road_returns_expected_shape(detector):
    result = analyze_road(
        "north", SAMPLE_ROAD_STATE, detector, ByteTracker(), dt=0.5, seed=9
    )
    assert result["road"] == "north"
    assert result["ground_truth_count"] == 3
    assert result["detected_count"] == len(result["detections"])
    for det in result["detections"]:
        assert "matched" in det and "confidence" in det and "track_id" in det
    assert result["precision"] is None or 0.0 <= result["precision"] <= 1.0
    assert result["recall"] is None or 0.0 <= result["recall"] <= 1.0
    assert result["active_tracks"] >= 0
    assert result["unique_vehicles_tracked"] >= 0

    jpeg_bytes = base64.b64decode(result["frame_jpeg_base64"])
    assert jpeg_bytes[:2] == b"\xff\xd8"  # JPEG magic bytes


def test_analyze_road_on_empty_road_has_no_ground_truth(detector):
    result = analyze_road(
        "south", EMPTY_ROAD_STATE, detector, ByteTracker(), dt=0.5, seed=11
    )
    assert result["ground_truth_count"] == 0
    assert result["recall"] is None
    # A false-positive detection on an empty scene can still spawn a track
    # (the Haar cascade's known noise, see vision/detector.py) — the
    # field just needs to be a sane non-negative count, not necessarily 0.
    assert result["unique_vehicles_tracked"] >= 0
