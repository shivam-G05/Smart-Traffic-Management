from vision.detector import Detection
from vision.tracker import ByteTracker, KalmanBoxTracker


def _det(x, y, confidence=0.3, w=20, h=20):
    return Detection(x=x, y=y, w=w, h=h, confidence=confidence)


def test_track_id_persists_across_frames_for_same_moving_vehicle():
    tracker = ByteTracker()
    ids_seen = []
    for i in range(5):
        visible = tracker.update([_det(50 + i * 3, 50)], dt=1.0)
        ids_seen.append([t.id for t in visible])

    # First tick: not yet confirmed (min_hits=2), so nothing visible yet.
    assert ids_seen[0] == []
    # From the second tick on, the same single track id is returned every time.
    confirmed_ids = {i for tick in ids_seen[1:] for i in tick}
    assert len(confirmed_ids) == 1
    assert all(tick == ids_seen[1] for tick in ids_seen[1:])


def test_two_well_separated_vehicles_get_distinct_ids():
    tracker = ByteTracker()
    for _ in range(2):
        visible = tracker.update([_det(50, 50), _det(150, 150)], dt=1.0)
    ids = {t.id for t in visible}
    assert len(ids) == 2


def test_track_removed_after_max_age_without_detection():
    tracker = ByteTracker(max_age=2)
    tracker.update([_det(50, 50)], dt=1.0)
    tracker.update([_det(51, 50)], dt=1.0)  # now confirmed
    assert tracker.tracks and tracker.tracks[0].confirmed

    for _ in range(3):
        tracker.update([], dt=1.0)  # no detections at all

    assert tracker.tracks == []


def test_reappearing_vehicle_at_new_location_gets_a_new_id():
    tracker = ByteTracker(max_age=1)
    tracker.update([_det(50, 50)], dt=1.0)
    visible = tracker.update([_det(51, 50)], dt=1.0)
    original_id = visible[0].id

    # Vehicle leaves the frame long enough for its track to be dropped.
    tracker.update([], dt=1.0)
    tracker.update([], dt=1.0)
    assert tracker.tracks == []

    # A vehicle reappears far from where the old one was.
    tracker.update([_det(150, 150)], dt=1.0)
    visible = tracker.update([_det(151, 150)], dt=1.0)
    new_id = visible[0].id

    assert new_id != original_id


def test_low_confidence_detection_sustains_an_existing_confirmed_track():
    tracker = ByteTracker()
    tracker.update([_det(50, 50, confidence=0.3)], dt=1.0)
    visible = tracker.update([_det(52, 50, confidence=0.3)], dt=1.0)
    confirmed_id = visible[0].id

    # Only a weak detection appears near the same spot this tick.
    visible = tracker.update([_det(54, 50, confidence=0.02)], dt=1.0)

    assert len(visible) == 1
    assert visible[0].id == confirmed_id


def test_low_confidence_detection_never_spawns_a_new_track():
    tracker = ByteTracker()
    tracker.update([_det(50, 50, confidence=0.02)], dt=1.0)
    tracker.update([_det(52, 50, confidence=0.02)], dt=1.0)
    visible = tracker.update([_det(54, 50, confidence=0.02)], dt=1.0)

    assert visible == []
    assert tracker.total_tracks_created == 0


def test_total_tracks_created_counts_unique_vehicles_not_frames():
    tracker = ByteTracker()
    for i in range(10):
        tracker.update([_det(50 + i * 2, 50)], dt=1.0)

    assert tracker.total_tracks_created == 1


def test_kalman_filter_converges_toward_constant_velocity_motion():
    kf = KalmanBoxTracker(cx=0.0, cy=0.0)
    true_x = 0.0
    for _ in range(20):
        kf.predict(dt=1.0)
        true_x += 5.0
        kf.update(cx=true_x, cy=0.0)

    kf.predict(dt=1.0)
    predicted_x, _ = kf.center
    assert abs(predicted_x - (true_x + 5.0)) < 2.0


def test_single_stage_tracker_ignores_low_confidence_detections():
    two_stage, single = ByteTracker(min_hits=1), ByteTracker(min_hits=1, two_stage=False)
    strong, weak = Detection(10, 10, 10, 10, 0.9), Detection(11, 10, 10, 10, 0.01)
    for tracker in (two_stage, single):
        tracker.update([strong], dt=0.5)
    assert two_stage.update([weak], dt=0.5)          # weak detection sustains the track
    assert not single.update([weak], dt=0.5)         # dropped: no match this frame


def test_tracker_without_motion_model_matches_against_the_last_box():
    tracker = ByteTracker(min_hits=1, predict_motion=False)
    tracker.update([Detection(10, 10, 10, 10, 0.9)], dt=0.5)
    (track,) = tracker.update([Detection(12, 10, 10, 10, 0.9)], dt=0.5)
    assert track.bbox == (12, 10, 10, 10)
