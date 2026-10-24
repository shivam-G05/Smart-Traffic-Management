"""Milestone 5: adaptive signal controller — priority + bounded green
extension off Milestone 4's density scores.

Reuses FixedTimerController's exact phase skeleton (NS_GREEN -> NS_YELLOW ->
ALL_RED_A -> EW_GREEN -> EW_YELLOW -> ALL_RED_B) rather than re-deriving
signal-safety logic. The only thing that becomes adaptive is *how long a
green phase lasts* — yellow and all-red clearance durations are always the
same fixed values FixedTimerController uses, never shortened or skipped.
"""

from decision_engine.density import road_density_score
from simulation.config import ALL_RED_CLEARANCE_S, STOP_LINE_POS_M, YELLOW_DURATION_S
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

# Discharge hold (optional, see AdaptiveController): a green is "still
# discharging" while any vehicle on the served approaches is within this
# distance upstream of the stop line — in effect a stop-line presence
# detector. A saturated queue moving off keeps a vehicle within ~2 car
# lengths of the line continuously; free-flowing arrivals cross 10 m in
# under a second, so the green gaps out between them. Chosen from 10/15/20/
# 30 m on a tuning seed (1000) kept apart from the evaluation seeds: larger
# zones held greens too long at 0.8-1.0x capacity (e.g. 30 m: 15.9 s delay
# vs 10.6 s at 1.0x, preemption off).
DISCHARGE_ZONE_M = 10.0

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
        hold_while_discharging: bool = False,
        discharge_zone_m: float = DISCHARGE_ZONE_M,
    ):
        """hold_while_discharging=False is the controller the paper
        evaluates. Measured above capacity (scripts/oversaturation.py) it
        loses ~9% of capacity: once both directions are saturated, the
        stopped queue on red (weight 1.5 per vehicle) soon outweighs the
        vehicles moving through on green (0.5), so greens end at ~11 s and
        every phase change spends 4 s on yellow and all-red. With True, a
        green past its minimum also needs the served direction to have
        gapped out — no vehicle within discharge_zone_m of its stop line —
        before it can end, so a saturated queue keeps its green (up to
        max_green_s) while a cleared one still hands over early.
        """
        self.phase = Phase.NS_GREEN
        self._elapsed_in_phase = 0.0
        self._apply_phase_lights_pending = True
        self.min_green_s = min_green_s
        self.max_green_s = max_green_s
        self.extension_threshold = extension_threshold
        self.hold_while_discharging = hold_while_discharging
        self.discharge_zone_m = discharge_zone_m

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
        if self.hold_while_discharging and self._still_discharging(intersection, _GREEN_GROUP[self.phase]):
            return False

        active_score = self._group_density(intersection, _GREEN_GROUP[self.phase])
        waiting_score = self._group_density(intersection, _WAITING_GROUP[self.phase])
        return active_score <= waiting_score * self.extension_threshold

    @staticmethod
    def _group_density(intersection: Intersection, group) -> float:
        return sum(road_density_score(intersection.roads[name]) for name in group)

    def _still_discharging(self, intersection: Intersection, group) -> bool:
        zone_start = STOP_LINE_POS_M - self.discharge_zone_m
        return any(
            zone_start <= vehicle.position_m < STOP_LINE_POS_M
            for name in group
            for lane in intersection.roads[name].lanes
            for vehicle in lane.vehicles
        )

    def _apply_lights(self, intersection: Intersection) -> None:
        for road_name, light_state in _LIGHT_BY_PHASE[self.phase].items():
            intersection.set_light_state(road_name, light_state)

    def current_phase_name(self) -> str:
        return self.phase.name

    def describe(self) -> str:
        return "AdaptiveController(discharge hold)" if self.hold_while_discharging else "AdaptiveController"

    def resync(self, intersection: Intersection) -> None:
        self._apply_lights(intersection)

    def resume_from_all_red(self, intersection: Intersection, served_roads) -> None:
        self.phase = Phase.EW_GREEN if set(served_roads) & set(NS_GROUP) else Phase.NS_GREEN
        self._elapsed_in_phase = 0.0
        self._apply_phase_lights_pending = False
        self._apply_lights(intersection)
