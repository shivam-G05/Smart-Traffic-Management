from app.comparison import build_comparison_snapshot
from simulation.engine import SimulationEngine
from simulation.controllers.fixed_timer_controller import FixedTimerController


class _FakeCollector:
    def __init__(self, overall: dict, roads: dict | None = None):
        self._summary = {"roads": roads or {}, "overall": overall}

    def summary(self) -> dict:
        return self._summary


def test_delta_computed_when_both_sides_have_throughput():
    primary = _FakeCollector({"total_exited": 10, "avg_wait_time_s": 8.0})
    shadow = _FakeCollector({"total_exited": 14, "avg_wait_time_s": 5.0})

    result = build_comparison_snapshot(primary, shadow, "fixed", "adaptive")

    assert result["primary"]["controller_type"] == "fixed"
    assert result["shadow"]["controller_type"] == "adaptive"
    assert result["delta"]["throughput"] == 4
    assert result["delta"]["avg_wait_time_s"] == -3.0


def test_delta_is_none_when_either_side_has_zero_throughput():
    primary = _FakeCollector({"total_exited": 0, "avg_wait_time_s": None})
    shadow = _FakeCollector({"total_exited": 5, "avg_wait_time_s": 4.0})

    result = build_comparison_snapshot(primary, shadow, "fixed", "adaptive")

    assert result["delta"]["avg_wait_time_s"] is None
    assert result["delta"]["throughput"] == 5


def test_same_seed_produces_identical_arrivals_before_controllers_can_diverge():
    engine_fixed = SimulationEngine(controller=FixedTimerController(), seed=7)
    engine_adaptive = SimulationEngine(controller=FixedTimerController(), seed=7)

    # A single tick, before either controller's own timing logic has had a
    # chance to diverge anything — arrivals must still match exactly.
    engine_fixed.tick(dt=0.05)
    engine_adaptive.tick(dt=0.05)

    assert (
        engine_fixed.intersection.total_vehicles_active()
        == engine_adaptive.intersection.total_vehicles_active()
    )
