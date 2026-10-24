"""ByteTrack-style multi-object tracker.

Gives every detected vehicle a persistent ID across frames instead of
treating each broadcast tick's detections as anonymous, so the dashboard
can show stable identities and a genuine cumulative "vehicles counted"
figure rather than re-summing per-frame noise.

Two ideas borrowed from ByteTrack (Zhang et al., 2022), adapted to our
detector's much noisier confidence range (see TRACK_HIGH_CONF_THRESHOLD in
vision/config.py):

1. A constant-velocity Kalman filter predicts where each track *should* be
   before matching, so a vehicle that moved meaningfully between broadcast
   ticks (0.5s apart, not real video frame-rate) still matches by
   predicted position rather than only raw IoU against its last box.
2. Two-stage association: match high-confidence detections to tracks
   first, then try matching *low*-confidence detections against whatever
   tracks are still unmatched, instead of discarding weak detections
   outright. A weak detection is still evidence a known vehicle is still
   there. Low-confidence detections are never allowed to spawn brand new
   tracks, though — only a confident detection earns a new identity.
"""

from dataclasses import dataclass, field
from itertools import count

import numpy as np
from scipy.optimize import linear_sum_assignment

from vision.config import (
    TRACK_HIGH_CONF_THRESHOLD,
    TRACK_MATCH_IOU_THRESHOLD,
    TRACK_MAX_AGE,
    TRACK_MIN_HITS,
)
from vision.detector import Detection

_track_id_counter = count(1)

BBox = tuple[int, int, int, int]


class KalmanBoxTracker:
    """Constant-velocity Kalman filter over a box's center (cx, cy).

    Width/height are not filtered, just carried over from whichever
    detection last matched — a reasonable simplification given our boxes
    are small and roughly constant-size per vehicle type, and it keeps the
    filter small enough to reason about directly.
    """

    def __init__(self, cx: float, cy: float):
        self.x = np.array([cx, cy, 0.0, 0.0])  # state: [cx, cy, vx, vy]
        self.P = np.eye(4) * 10.0  # state covariance
        self.Q = np.diag([1.0, 1.0, 4.0, 4.0])  # process noise
        self.R = np.eye(2) * 4.0  # measurement noise
        self.H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=float)

    def predict(self, dt: float) -> None:
        F = np.array(
            [
                [1, 0, dt, 0],
                [0, 1, 0, dt],
                [0, 0, 1, 0],
                [0, 0, 0, 1],
            ]
        )
        self.x = F @ self.x
        self.P = F @ self.P @ F.T + self.Q

    def update(self, cx: float, cy: float) -> None:
        z = np.array([cx, cy])
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(4) - K @ self.H) @ self.P

    @property
    def center(self) -> tuple[float, float]:
        return float(self.x[0]), float(self.x[1])


@dataclass(eq=False)  # identity equality/hash — a Track is never value-equal to another
class Track:
    kf: KalmanBoxTracker
    bbox: BBox  # x, y, w, h of the last detection that matched this track
    id: int = field(default_factory=lambda: next(_track_id_counter))
    hits: int = 1
    time_since_update: int = 0
    confirmed: bool = False

    def predicted_box(self) -> tuple[float, float, int, int]:
        cx, cy = self.kf.center
        w, h = self.bbox[2], self.bbox[3]
        return cx - w / 2, cy - h / 2, w, h

    def to_dict(self) -> dict:
        x, y, w, h = self.bbox
        return {"id": self.id, "x": x, "y": y, "w": w, "h": h}


def _iou(box_a: tuple[float, float, int, int], box_b: BBox) -> float:
    ax0, ay0, aw, ah = box_a
    bx0, by0, bw, bh = box_b
    ax1, ay1 = ax0 + aw, ay0 + ah
    bx1, by1 = bx0 + bw, by0 + bh

    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    if inter <= 0:
        return 0.0

    area_a = aw * ah
    area_b = bw * bh
    return inter / (area_a + area_b - inter)


class ByteTracker:
    """Owns every active track for one camera across successive calls to
    update(). Construct one instance per road and keep it alive for the
    life of the process — it is the persistent state that makes tracking
    possible at all.
    """

    def __init__(
        self,
        high_conf_threshold: float = TRACK_HIGH_CONF_THRESHOLD,
        match_iou_threshold: float = TRACK_MATCH_IOU_THRESHOLD,
        max_age: int = TRACK_MAX_AGE,
        min_hits: int = TRACK_MIN_HITS,
        two_stage: bool = True,
        predict_motion: bool = True,
    ):
        # two_stage=False drops low-confidence detections instead of using
        # them in a second matching pass (a SORT-style single stage);
        # predict_motion=False matches against each track's last box
        # instead of its Kalman prediction. Both exist for the tracker
        # ablation in scripts/vision_eval.py; the live pipeline uses neither.
        self.two_stage = two_stage
        self.predict_motion = predict_motion
        self.high_conf_threshold = high_conf_threshold
        self.match_iou_threshold = match_iou_threshold
        self.max_age = max_age
        self.min_hits = min_hits
        self.tracks: list[Track] = []
        self.total_tracks_created = 0

    def update(self, detections: list[Detection], dt: float) -> list[Track]:
        """Advances every track by dt, associates this tick's detections,
        and returns the tracks that are confirmed *and* visible this tick.
        """
        if self.predict_motion:
            for track in self.tracks:
                track.kf.predict(dt)

        high = [d for d in detections if d.confidence >= self.high_conf_threshold]
        low = [d for d in detections if d.confidence < self.high_conf_threshold] if self.two_stage else []

        all_indices = list(range(len(self.tracks)))
        matched_high, unmatched_track_idx, unmatched_high = self._match(
            self.tracks, all_indices, high
        )
        remaining_tracks = [self.tracks[i] for i in unmatched_track_idx]
        matched_low, _remaining_unmatched, _unmatched_low = self._match(
            remaining_tracks, list(range(len(remaining_tracks))), low
        )

        matched_this_tick: set[int] = set()
        for track_idx, det in matched_high:
            self._apply_match(self.tracks[track_idx], det)
            matched_this_tick.add(id(self.tracks[track_idx]))
        for local_idx, det in matched_low:
            self._apply_match(remaining_tracks[local_idx], det)
            matched_this_tick.add(id(remaining_tracks[local_idx]))

        for track in self.tracks:
            if id(track) not in matched_this_tick:
                track.time_since_update += 1

        for det in unmatched_high:
            self._spawn_track(det)

        self.tracks = [t for t in self.tracks if t.time_since_update <= self.max_age]

        return [t for t in self.tracks if t.confirmed and t.time_since_update == 0]

    def _match(
        self,
        tracks: list[Track],
        track_indices: list[int],
        detections: list[Detection],
    ) -> tuple[list[tuple[int, Detection]], list[int], list[Detection]]:
        if not track_indices or not detections:
            return [], track_indices, list(detections)

        cost = np.ones((len(track_indices), len(detections)))
        for row, ti in enumerate(track_indices):
            predicted = tracks[ti].predicted_box() if self.predict_motion else tracks[ti].bbox
            for col, det in enumerate(detections):
                cost[row, col] = 1.0 - _iou(predicted, (det.x, det.y, det.w, det.h))

        row_idx, col_idx = linear_sum_assignment(cost)

        matches: list[tuple[int, Detection]] = []
        matched_rows: set[int] = set()
        matched_cols: set[int] = set()
        max_cost = 1.0 - self.match_iou_threshold
        for r, c in zip(row_idx, col_idx):
            if cost[r, c] <= max_cost:
                matches.append((track_indices[r], detections[c]))
                matched_rows.add(r)
                matched_cols.add(c)

        unmatched_tracks = [ti for i, ti in enumerate(track_indices) if i not in matched_rows]
        unmatched_dets = [d for i, d in enumerate(detections) if i not in matched_cols]
        return matches, unmatched_tracks, unmatched_dets

    def _apply_match(self, track: Track, det: Detection) -> None:
        cx, cy = det.x + det.w / 2, det.y + det.h / 2
        track.kf.update(cx, cy)
        track.bbox = (det.x, det.y, det.w, det.h)
        track.hits += 1
        track.time_since_update = 0
        if track.hits >= self.min_hits:
            track.confirmed = True

    def _spawn_track(self, det: Detection) -> None:
        cx, cy = det.x + det.w / 2, det.y + det.h / 2
        track = Track(kf=KalmanBoxTracker(cx, cy), bbox=(det.x, det.y, det.w, det.h))
        track.confirmed = self.min_hits <= 1
        self.tracks.append(track)
        self.total_tracks_created += 1
