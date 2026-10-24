"""Comparison controllers for the experiments (reviewer request: compare
against stronger baselines and existing approaches).

Each one re-implements the *control strategy* of a published approach in
this simulator — they are not the original systems, and like this
project's own controllers they read exact vehicle states (ideal sensing).
All of them subclass AdaptiveController and replace only
_green_ready_to_end(): the phase sequence, 3 s yellow, 1 s all-red and the
8-45 s green bounds are shared, so every baseline keeps the same change
intervals and the same 50 s maximum red, and the comparison isolates the
switching decision itself.

The optimized fixed-time baseline is FixedTimerController with a green
from decision_engine/webster.py, not a class here.
"""

from decision_engine.adaptive_controller import _GREEN_GROUP, _WAITING_GROUP, AdaptiveController
from decision_engine.density import road_density_score
from simulation.config import STOP_LINE_POS_M
from simulation.entities.intersection import Intersection

# Same values as analytics/config.py's congestion thresholds (decision_engine
# may not import analytics/, so they are repeated rather than shared).
LEVEL_LOW_MAX = 3.0
LEVEL_HIGH_MIN = 6.0
LEVEL_GREEN_S = {"low": 10.0, "medium": 20.0, "high": 30.0}


def _vehicles_before_stop_line(intersection: Intersection, group) -> int:
    return sum(
        1
        for name in group
        for lane in intersection.roads[name].lanes
        for vehicle in lane.vehicles
        if vehicle.position_m < STOP_LINE_POS_M
    )


class ActuatedController(AdaptiveController):
    """Classic fully-actuated control: past the minimum, a green ends as
    soon as the served direction gaps out (no vehicle within the 10 m
    stop-line zone) and the other direction has a vehicle waiting; no
    density score. Paired with AdaptiveController(hold_while_discharging=
    True) it shows what the density comparison adds beyond actuation."""

    def __init__(self, **kwargs):
        super().__init__(hold_while_discharging=True, **kwargs)

    def _green_ready_to_end(self, intersection: Intersection) -> bool:
        if self._still_discharging(intersection, _GREEN_GROUP[self.phase]):
            return False
        return _vehicles_before_stop_line(intersection, _WAITING_GROUP[self.phase]) > 0

    def describe(self) -> str:
        return "ActuatedController"


class MaxPressureController(AdaptiveController):
    """Max-pressure control (Varaiya, 2013) for an isolated junction: a
    phase's pressure is the number of vehicles upstream of its stop lines
    minus those downstream; with free exits the downstream term is zero.
    Past the minimum green the controller switches as soon as the waiting
    phase's pressure exceeds the served one's. The 45 s maximum is kept so
    the comparison runs under the same maximum-red bound."""

    def _green_ready_to_end(self, intersection: Intersection) -> bool:
        served = _vehicles_before_stop_line(intersection, _GREEN_GROUP[self.phase])
        waiting = _vehicles_before_stop_line(intersection, _WAITING_GROUP[self.phase])
        return waiting > served

    def describe(self) -> str:
        return "MaxPressureController"


class DensityLevelController(AdaptiveController):
    """Three-level density control, in the style of Nsofwa and Tembo's
    density-based system: when a green starts, the served direction's
    density is classed low / medium / high (busiest road of the direction,
    same 3.0 / 6.0 thresholds as the dashboard) and the green is set to
    10 / 20 / 30 s; it is not revised during the green."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._target_green_s = LEVEL_GREEN_S["medium"]

    def _apply_lights(self, intersection: Intersection) -> None:
        super()._apply_lights(intersection)
        if self.phase in _GREEN_GROUP:
            score = max(road_density_score(intersection.roads[name]) for name in _GREEN_GROUP[self.phase])
            level = "low" if score <= LEVEL_LOW_MAX else "high" if score > LEVEL_HIGH_MIN else "medium"
            self._target_green_s = LEVEL_GREEN_S[level]

    def _green_ready_to_end(self, intersection: Intersection) -> bool:
        return self._elapsed_in_phase >= self._target_green_s

    def describe(self) -> str:
        return "DensityLevelController"
