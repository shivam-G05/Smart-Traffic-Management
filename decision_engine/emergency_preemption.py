"""Milestone 6: emergency vehicle preemption.

Wraps any SignalControllerBase and forces/extends green for a road with an
active emergency vehicle. Uses simulation ground truth
(Road.has_emergency_vehicle()) exclusively — never the vision pipeline's
detection, whose recall is documented (Milestones 2-3) as genuinely poor.
Making signal safety depend on the Haar cascade's detection rate would be
actively dangerous; the vision-side "would the camera have caught this"
flag (vision/pipeline.py's is_emergency/vision_emergency_detected) stays a
separate, display-only honesty indicator.

State machine. Every transition obeys the same change-interval rules as
the normal signal plan: a green light always shows yellow for the full
yellow_s before it turns red, and every approach stays red for clearance_s
before a conflicting direction is given green — on the way in AND on the
way back out.

    NORMAL --(emergency detected)--> FORCE_YELLOW --> CLEARING (all-red)
      --> PREEMPT_GREEN --(cleared or max_hold_s)--> RELEASE_YELLOW
      --> RELEASE_CLEARING (all-red) --> inner.resume_from_all_red() --> NORMAL

Taking over mid-interval: a light the inner controller had already turned
yellow keeps the rest of its yellow time, and an all-red already in
progress only runs for its remaining clearance. If the emergency road's
direction is already green, that green is simply held (no clearance).

PREEMPT_GREEN gives green to the emergency road's whole direction (e.g.
North AND South), matching the normal phase plan — so the non-conflicting
partner road is never flipped straight from green to red.

A green that has been showing for less than min_green_s is never cut short
by a preemption. That keeps drivers from seeing a green that lasts a single
tick, and it bounds starvation: a vehicle still stuck after max_hold_s
cannot re-trigger preemption until the cross direction has had at least
min_green_s of green. If two directions have emergency vehicles, the one
that already has green is served first; otherwise requests are served one
at a time, never interrupting a preemption in progress.
"""

from enum import Enum, auto

from simulation.config import ALL_RED_CLEARANCE_S, YELLOW_DURATION_S, LightState, RoadName
from simulation.controllers.base_controller import SignalControllerBase
from simulation.controllers.fixed_timer_controller import EW_GROUP, NS_GROUP
from simulation.entities.intersection import Intersection

MAX_HOLD_S = 20.0
MIN_GREEN_BEFORE_PREEMPT_S = 5.0


class _State(Enum):
    NORMAL = auto()
    FORCE_YELLOW = auto()
    CLEARING = auto()
    PREEMPT_GREEN = auto()
    RELEASE_YELLOW = auto()
    RELEASE_CLEARING = auto()


def _group_of(road_name: RoadName) -> tuple[RoadName, ...]:
    return NS_GROUP if road_name in NS_GROUP else EW_GROUP


class EmergencyPreemptionController(SignalControllerBase):
    def __init__(
        self,
        inner: SignalControllerBase,
        clearance_s: float = ALL_RED_CLEARANCE_S,
        yellow_s: float = YELLOW_DURATION_S,
        max_hold_s: float = MAX_HOLD_S,
        min_green_s: float = MIN_GREEN_BEFORE_PREEMPT_S,
        on_event=None,
    ):
        self.inner = inner
        self.clearance_s = clearance_s
        self.yellow_s = yellow_s
        self.max_hold_s = max_hold_s
        self.min_green_s = min_green_s
        # Optional sync callback(sim_time, event_type, phase_name, road_name)
        # -> None, fired at preemption start/end — Milestone 8 wires this to
        # an async DB write (see backend/app/event_recorder.py). Kept as a
        # plain callback here so decision_engine/ never has to import
        # database/ or asyncio scheduling concerns.
        self.on_event = on_event
        self._state = _State.NORMAL
        self._target_road: RoadName | None = None
        self._elapsed = 0.0
        self._wait_s = 0.0  # how long the current timed state (yellow / all-red) must last
        # Mirrors the engine's own sim_time_s: this controller's update() is
        # called with the same dt every tick the engine ticks, so summing it
        # here tracks sim_time accurately without needing a reference to
        # the engine itself.
        self._sim_time_s = 0.0

    def _emit(self, event_type: str, road_name: str | None) -> None:
        if self.on_event is not None:
            self.on_event(self._sim_time_s, event_type, self.current_phase_name(), road_name)

    def update(self, intersection: Intersection, dt: float) -> None:
        self._sim_time_s += dt

        if self._state == _State.NORMAL:
            emergency_road = self._pick_emergency_road(intersection)
            if emergency_road is not None:
                self._begin_preemption(intersection, emergency_road)
            else:
                self.inner.update(intersection, dt)
            return

        self._elapsed += dt

        if self._state == _State.PREEMPT_GREEN:
            if not self._target_group_has_emergency(intersection) or self._elapsed >= self.max_hold_s:
                self._enter_release_yellow(intersection)
        elif self._elapsed >= self._wait_s:
            if self._state == _State.FORCE_YELLOW:
                self._enter_clearing(intersection, self.clearance_s)
            elif self._state == _State.CLEARING:
                self._enter_preempt_green(intersection)
            elif self._state == _State.RELEASE_YELLOW:
                self._enter_release_clearing(intersection)
            elif self._state == _State.RELEASE_CLEARING:
                self._end_preemption(intersection)

    def _pick_emergency_road(self, intersection: Intersection) -> RoadName | None:
        candidates = [name for name, road in intersection.roads.items() if road.has_emergency_vehicle()]
        if not candidates:
            return None
        # Holding a green that is already showing needs no clearance and
        # interrupts nobody, so serve that approach first.
        for name in candidates:
            if intersection.roads[name].light.state == LightState.GREEN:
                return name
        # Otherwise some other direction's green would be cut: only allowed
        # once that green has been showing for at least min_green_s.
        for road in intersection.roads.values():
            if road.light.state == LightState.GREEN and road.light.time_in_state_s < self.min_green_s:
                return None
        return candidates[0]

    def _target_group_has_emergency(self, intersection: Intersection) -> bool:
        return any(intersection.roads[name].has_emergency_vehicle() for name in _group_of(self._target_road))

    def _begin_preemption(self, intersection: Intersection, road_name: RoadName) -> None:
        self._target_road = road_name
        self._emit("EMERGENCY_PREEMPTION_START", road_name.value)
        lights = {name: road.light for name, road in intersection.roads.items()}

        if lights[road_name].state == LightState.GREEN:
            # Only one direction can ever be green, so the conflicting
            # approaches are already red — just hold this green.
            self._enter_preempt_green(intersection)
            return

        yellow_remaining_s = 0.0
        for name, light in lights.items():
            if light.state == LightState.GREEN:
                intersection.set_light_state(name, LightState.YELLOW)
                yellow_remaining_s = max(yellow_remaining_s, self.yellow_s)
            elif light.state == LightState.YELLOW:
                yellow_remaining_s = max(yellow_remaining_s, self.yellow_s - light.time_in_state_s)

        if yellow_remaining_s > 0.0:
            self._elapsed = 0.0
            self._wait_s = yellow_remaining_s
            self._state = _State.FORCE_YELLOW
        elif all(light.state == LightState.RED for light in lights.values()):
            # All-red already under way: it began when the last light turned red.
            all_red_for_s = min(light.time_in_state_s for light in lights.values())
            self._enter_clearing(intersection, self.clearance_s - all_red_for_s)
        else:
            self._enter_clearing(intersection, self.clearance_s)

    def _enter_clearing(self, intersection: Intersection, wait_s: float) -> None:
        for name in intersection.roads:
            intersection.set_light_state(name, LightState.RED)
        self._elapsed = 0.0
        self._wait_s = max(0.0, wait_s)
        self._state = _State.CLEARING
        if self._wait_s == 0.0:
            self._enter_preempt_green(intersection)

    def _enter_preempt_green(self, intersection: Intersection) -> None:
        group = _group_of(self._target_road)
        for name in intersection.roads:
            intersection.set_light_state(name, LightState.GREEN if name in group else LightState.RED)
        self._elapsed = 0.0
        self._state = _State.PREEMPT_GREEN

    def _enter_release_yellow(self, intersection: Intersection) -> None:
        for name in _group_of(self._target_road):
            intersection.set_light_state(name, LightState.YELLOW)
        self._elapsed = 0.0
        self._wait_s = self.yellow_s
        self._state = _State.RELEASE_YELLOW

    def _enter_release_clearing(self, intersection: Intersection) -> None:
        for name in intersection.roads:
            intersection.set_light_state(name, LightState.RED)
        self._elapsed = 0.0
        self._wait_s = self.clearance_s
        self._state = _State.RELEASE_CLEARING

    def _end_preemption(self, intersection: Intersection) -> None:
        served = _group_of(self._target_road)
        ended_road = self._target_road.value
        self._state = _State.NORMAL
        self._target_road = None
        self._elapsed = 0.0
        # Every approach has now been red for the full clearance interval,
        # so the inner controller can start a fresh green for the direction
        # that was held.
        self.inner.resume_from_all_red(intersection, served)
        self._emit("EMERGENCY_PREEMPTION_END", ended_road)

    def current_phase_name(self) -> str:
        if self._state == _State.NORMAL:
            return self.inner.current_phase_name()
        road = self._target_road.value if self._target_road is not None else "?"
        return f"EMERGENCY_{self._state.name}_{road}"

    def describe(self) -> str:
        return f"EmergencyPreemptionController({self.inner.describe()})"
