import pytest

from analytics.alerts import HighTrafficAlert
from analytics.collector import AnalyticsCollector, classify_congestion
from analytics.config import CONGESTION_HIGH_MIN, CONGESTION_LOW_MAX


class _FakeRunner:
    """Minimal stand-in for SimulationRunner — AnalyticsCollector only ever
    reads .latest_state, so this is all it needs (and all Milestone 9's
    shadow runner reuse needs to keep working)."""

    def __init__(self):
        self.latest_state: dict = {}

    def set_state(self, sim_time: float, **roads) -> None:
        self.latest_state = {"sim_time": sim_time, "roads": roads}


def _road(density_score=0.0, queue_length=0, total_exited=0, total_wait_time_s=0.0):
    return {
        "density_score": density_score,
        "queue_length": queue_length,
        "total_exited": total_exited,
        "total_wait_time_s": total_wait_time_s,
    }


def test_classify_congestion_thresholds():
    assert classify_congestion(0.0) == "low"
    assert classify_congestion(CONGESTION_LOW_MAX) == "low"
    assert classify_congestion((CONGESTION_LOW_MAX + CONGESTION_HIGH_MIN) / 2) == "medium"
    assert classify_congestion(CONGESTION_HIGH_MIN) == "medium"
    assert classify_congestion(CONGESTION_HIGH_MIN + 0.01) == "high"


def test_sample_computes_throughput_and_avg_wait_delta():
    runner = _FakeRunner()
    collector = AnalyticsCollector(runner, sample_hz=1.0, history_len=10)

    runner.set_state(1.0, north=_road(total_exited=0, total_wait_time_s=0.0))
    collector.sample()

    runner.set_state(2.0, north=_road(total_exited=3, total_wait_time_s=15.0))
    collector.sample()

    latest = collector.history("north")[-1]
    assert latest["throughput_delta"] == 3
    assert latest["avg_wait_time_s"] == pytest.approx(5.0)


def test_sample_never_divides_by_zero_departures():
    runner = _FakeRunner()
    collector = AnalyticsCollector(runner)

    runner.set_state(1.0, north=_road(total_exited=5, total_wait_time_s=10.0))
    collector.sample()
    runner.set_state(2.0, north=_road(total_exited=5, total_wait_time_s=10.0))  # no new departures
    collector.sample()

    latest = collector.history("north")[-1]
    assert latest["throughput_delta"] == 0
    assert latest["avg_wait_time_s"] is None


def test_history_respects_maxlen():
    runner = _FakeRunner()
    collector = AnalyticsCollector(runner, history_len=3)
    for i in range(10):
        runner.set_state(float(i), north=_road(total_exited=i, total_wait_time_s=float(i)))
        collector.sample()
    assert len(collector.history("north")) == 3


def test_summary_sane_at_zero_throughput():
    runner = _FakeRunner()
    collector = AnalyticsCollector(runner)
    runner.set_state(1.0, north=_road(density_score=2.0), south=_road(density_score=20.0))

    summary = collector.summary()
    assert summary["roads"]["north"]["avg_wait_time_s"] is None
    assert summary["roads"]["south"]["congestion_level"] == "high"
    assert summary["overall"]["total_exited"] == 0
    assert summary["overall"]["avg_wait_time_s"] is None


def test_high_traffic_alert_turns_on_immediately_and_holds_through_brief_dips():
    alert = HighTrafficAlert(threshold=6.0, hold_s=3.0)
    assert alert.update("north", 5.0, 0.0) is False
    assert alert.update("north", 6.5, 1.0) is True   # above threshold: on at once
    assert alert.update("north", 5.5, 2.0) is True   # dipped 1s ago: still held
    assert alert.update("north", 6.2, 2.5) is True   # back above: hold restarts
    assert alert.update("north", 4.0, 5.4) is True   # 2.9s below: still held
    assert alert.update("north", 4.0, 5.6) is False  # 3.1s below: clears


def test_high_traffic_alert_is_tracked_per_road():
    alert = HighTrafficAlert(threshold=6.0, hold_s=3.0)
    assert alert.update("north", 7.0, 0.0) is True
    assert alert.update("south", 1.0, 0.0) is False
