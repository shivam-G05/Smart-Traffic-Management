from enum import Enum, auto

from simulation.config import (
    ALL_RED_CLEARANCE_S,
    FIXED_GREEN_DURATION_S,
    YELLOW_DURATION_S,
    LightState,
    RoadName,
)
from simulation.controllers.base_controller import SignalControllerBase
from simulation.entities.intersection import Intersection

NS_GROUP = (RoadName.NORTH, RoadName.SOUTH)
EW_GROUP = (RoadName.EAST, RoadName.WEST)


class Phase(Enum):
    NS_GREEN = auto()
    NS_YELLOW = auto()
    ALL_RED_A = auto()
    EW_GREEN = auto()
    EW_YELLOW = auto()
    ALL_RED_B = auto()


_PHASE_DURATIONS = {
    Phase.NS_GREEN: FIXED_GREEN_DURATION_S,
    Phase.NS_YELLOW: YELLOW_DURATION_S,
    Phase.ALL_RED_A: ALL_RED_CLEARANCE_S,
    Phase.EW_GREEN: FIXED_GREEN_DURATION_S,
    Phase.EW_YELLOW: YELLOW_DURATION_S,
    Phase.ALL_RED_B: ALL_RED_CLEARANCE_S,
}
_NEXT_PHASE = {
    Phase.NS_GREEN: Phase.NS_YELLOW,
    Phase.NS_YELLOW: Phase.ALL_RED_A,
    Phase.ALL_RED_A: Phase.EW_GREEN,
    Phase.EW_GREEN: Phase.EW_YELLOW,
    Phase.EW_YELLOW: Phase.ALL_RED_B,
    Phase.ALL_RED_B: Phase.NS_GREEN,
}
_LIGHT_BY_PHASE = {
    Phase.NS_GREEN: {**{r: LightState.GREEN for r in NS_GROUP}, **{r: LightState.RED for r in EW_GROUP}},
    Phase.NS_YELLOW: {**{r: LightState.YELLOW for r in NS_GROUP}, **{r: LightState.RED for r in EW_GROUP}},
    Phase.ALL_RED_A: {r: LightState.RED for r in RoadName},
    Phase.EW_GREEN: {**{r: LightState.GREEN for r in EW_GROUP}, **{r: LightState.RED for r in NS_GROUP}},
    Phase.EW_YELLOW: {**{r: LightState.YELLOW for r in EW_GROUP}, **{r: LightState.RED for r in NS_GROUP}},
    Phase.ALL_RED_B: {r: LightState.RED for r in RoadName},
}


class FixedTimerController(SignalControllerBase):
    """Baseline strategy: equal, fixed-duration green time per phase,
    regardless of actual traffic density. Serves as the comparison
    baseline for the adaptive controller introduced in a later milestone.
    """

    def __init__(self):
        self.phase = Phase.NS_GREEN
        self._elapsed_in_phase = 0.0
        self._apply_phase_lights_pending = True

    def update(self, intersection: Intersection, dt: float) -> None:
        if self._apply_phase_lights_pending:
            self._apply_lights(intersection)
            self._apply_phase_lights_pending = False

        self._elapsed_in_phase += dt
        if self._elapsed_in_phase >= _PHASE_DURATIONS[self.phase]:
            self.phase = _NEXT_PHASE[self.phase]
            self._elapsed_in_phase = 0.0
            self._apply_lights(intersection)

    def _apply_lights(self, intersection: Intersection) -> None:
        for road_name, light_state in _LIGHT_BY_PHASE[self.phase].items():
            intersection.set_light_state(road_name, light_state)

    def current_phase_name(self) -> str:
        return self.phase.name
