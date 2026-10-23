"""Milestone 5: adaptive signal controller — priority + bounded green
extension off Milestone 4's density scores.

Reuses FixedTimerController's exact phase skeleton (NS_GREEN -> NS_YELLOW ->
ALL_RED_A -> EW_GREEN -> EW_YELLOW -> ALL_RED_B) rather than re-deriving
signal-safety logic. The only thing that becomes adaptive is *how long a
green phase lasts* — yellow and all-red clearance durations are always the
same fixed values FixedTimerController uses, never shortened or skipped.
"""

from decision_engine.density import road_density_score
from simulation.config import ALL_RED_CLEARANCE_S, YELLOW_DURATION_S
from simulation.controllers.base_controller import SignalControllerBase
from simulation.controllers.fixed_timer_controller import (
    _LIGHT_BY_PHASE,
    _NEXT_PHASE,
    EW_GROUP,
    NS_GROUP,
    Phase,
)
from simulation.entities.intersection import Intersection

MIN_GREEN_S = 8.0
MAX_GREEN_S = 45.0
EXTENSION_THRESHOLD = 1.1  # active group must out-score the waiting group by this factor to keep extending

_FIXED_DURATIONS = {
    Phase.NS_YELLOW: YELLOW_DURATION_S,
    Phase.ALL_RED_A: ALL_RED_CLEARANCE_S,
    Phase.EW_YELLOW: YELLOW_DURATION_S,
    Phase.ALL_RED_B: ALL_RED_CLEARANCE_S,
}
_GREEN_GROUP = {Phase.NS_GREEN: NS_GROUP, Phase.EW_GREEN: EW_GROUP}
_WAITING_GROUP = {Phase.NS_GREEN: EW_GROUP, Phase.EW_GREEN: NS_GROUP}


class AdaptiveController(SignalControllerBase):
    """Extends green time for the currently-active direction while its
    density score meaningfully exceeds the waiting direction's, bounded by
    a hard [min_green_s, max_green_s] window so no direction can be
    starved or hogged indefinitely regardless of density readings.
    """

    def __init__(
        self,
        min_green_s: float = MIN_GREEN_S,
        max_green_s: float = MAX_GREEN_S,
        extension_threshold: float = EXTENSION_THRESHOLD,
    ):
        self.phase = Phase.NS_GREEN
        self._elapsed_in_phase = 0.0
        self._apply_phase_lights_pending = True
        self.min_green_s = min_green_s
        self.max_green_s = max_green_s
        self.extension_threshold = extension_threshold

    def update(self, intersection: Intersection, dt: float) -> None:
        if self._apply_phase_lights_pending:
            self._apply_lights(intersection)
            self._apply_phase_lights_pending = False

        self._elapsed_in_phase += dt

        if self._should_end_phase(intersection):
            self.phase = _NEXT_PHASE[self.phase]
            self._elapsed_in_phase = 0.0
            self._apply_lights(intersection)

    def _should_end_phase(self, intersection: Intersection) -> bool:
        if self.phase not in _GREEN_GROUP:
            return self._elapsed_in_phase >= _FIXED_DURATIONS[self.phase]

        if self._elapsed_in_phase >= self.max_green_s:
            return True
        if self._elapsed_in_phase < self.min_green_s:
            return False

        active_score = self._group_density(intersection, _GREEN_GROUP[self.phase])
        waiting_score = self._group_density(intersection, _WAITING_GROUP[self.phase])
        return active_score <= waiting_score * self.extension_threshold

    @staticmethod
    def _group_density(intersection: Intersection, group) -> float:
        return sum(road_density_score(intersection.roads[name]) for name in group)

    def _apply_lights(self, intersection: Intersection) -> None:
        for road_name, light_state in _LIGHT_BY_PHASE[self.phase].items():
            intersection.set_light_state(road_name, light_state)

    def current_phase_name(self) -> str:
        return self.phase.name

    def resync(self, intersection: Intersection) -> None:
        self._apply_lights(intersection)

    def resume_from_all_red(self, intersection: Intersection, served_roads) -> None:
        self.phase = Phase.EW_GREEN if set(served_roads) & set(NS_GROUP) else Phase.NS_GREEN
        self._elapsed_in_phase = 0.0
        self._apply_phase_lights_pending = False
        self._apply_lights(intersection)
