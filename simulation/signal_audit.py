"""Signal change-interval auditor.

Observes an intersection once per tick (after the tick has been applied) and
records every violation of the rules any controller must obey:

- conflicting_green: North/South and East/West green at the same time
- green_to_red:      a light skips yellow
- yellow_to_green:   a yellow light turns green again
- short_yellow:      yellow shown for less than yellow_s
- short_clearance:   a direction turns green before the other direction has
                     been fully red for clearance_s

Used by the test suite and by offline experiments, so both measure safety
with exactly the same definition.
"""

from collections import Counter

from simulation.config import ALL_RED_CLEARANCE_S, YELLOW_DURATION_S, LightState
from simulation.controllers.fixed_timer_controller import EW_GROUP, NS_GROUP
from simulation.entities.intersection import Intersection

_GROUPS = {"ns": NS_GROUP, "ew": EW_GROUP}


class SignalAudit:
    def __init__(
        self,
        intersection: Intersection,
        dt: float,
        yellow_s: float = YELLOW_DURATION_S,
        clearance_s: float = ALL_RED_CLEARANCE_S,
    ):
        self.roads = intersection.roads
        self.dt = dt
        self.yellow_s = yellow_s
        self.clearance_s = clearance_s
        self.tick = 0
        self.counts: Counter = Counter()
        self.first_violations: list[tuple[str, str, float]] = []
        self._prev = {name: road.light.state for name, road in self.roads.items()}
        self._yellow_ticks = {name: 0 for name in self.roads}
        self._last_not_red_tick = {"ns": None, "ew": None}

    def _flag(self, kind: str, road_name) -> None:
        self.counts[kind] += 1
        if len(self.first_violations) < 20:
            self.first_violations.append((kind, getattr(road_name, "value", road_name), self.tick * self.dt))

    def observe(self) -> None:
        self.tick += 1
        tolerance = self.dt / 2

        green = {g: any(self.roads[r].light.state == LightState.GREEN for r in members) for g, members in _GROUPS.items()}
        if green["ns"] and green["ew"]:
            self._flag("conflicting_green", "all")

        for name, road in self.roads.items():
            state, prev = road.light.state, self._prev[name]
            if prev == LightState.GREEN and state == LightState.RED:
                self._flag("green_to_red", name)
            if prev == LightState.YELLOW and state == LightState.GREEN:
                self._flag("yellow_to_green", name)

            if state == LightState.YELLOW:
                self._yellow_ticks[name] += 1
            elif prev == LightState.YELLOW:
                if self._yellow_ticks[name] * self.dt < self.yellow_s - tolerance:
                    self._flag("short_yellow", name)
                self._yellow_ticks[name] = 0

            if state == LightState.GREEN and prev != LightState.GREEN:
                other = "ew" if name in NS_GROUP else "ns"
                last = self._last_not_red_tick[other]
                if last is not None and (self.tick - last - 1) * self.dt < self.clearance_s - tolerance:
                    self._flag("short_clearance", name)
            self._prev[name] = state

        for group, members in _GROUPS.items():
            if any(self.roads[r].light.state != LightState.RED for r in members):
                self._last_not_red_tick[group] = self.tick

    @property
    def total_violations(self) -> int:
        return sum(self.counts.values())
