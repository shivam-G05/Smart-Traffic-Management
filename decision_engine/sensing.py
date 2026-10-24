"""Imperfect sensing for the controllers (reviewer request: address the gap
between the ideal simulator sensing used for control and the weak vision
pipeline).

Every controller normally reads exact vehicle states. SensedController
wraps one so that it instead sees the junction through a SensorModel:
- a camera's field of view (vehicles within view_m before the stop line);
- a refresh rate (the view only updates every refresh_s, so it lags);
- missed detections (each vehicle is seen with probability recall on each
  refresh, independently);
- no vehicle classes, as with a single Haar cascade (every vehicle reported
  as a car, weight 1);
- phantom detections at fixed spots in view, as the Haar cascade's static
  background false positives (each present with probability
  phantom_presence on each refresh, reported as a stopped car).

The controller's own signal commands still go to the real junction, and
emergency preemption (which wraps the sensed controller) keeps reading the
true emergency flags: this models density sensing only.
"""

import random
from dataclasses import dataclass

from simulation.config import STOP_LINE_POS_M, VehicleType
from simulation.controllers.base_controller import SignalControllerBase
from simulation.entities.intersection import Intersection


@dataclass(frozen=True)
class SensorModel:
    recall: float = 1.0
    view_m: float = 60.0
    refresh_s: float = 0.5
    class_blind: bool = True
    phantoms_per_approach: int = 0
    phantom_presence: float = 1.0
    seed: int = 0


@dataclass
class _Seen:
    """What the sensor reports about one vehicle (or phantom)."""
    vehicle_type: VehicleType
    position_m: float
    speed_mps: float


class _PerceivedLane:
    def __init__(self):
        self.vehicles: list[_Seen] = []


class _PerceivedRoad:
    def __init__(self, real_road, n_lanes: int):
        self._real = real_road
        self.name = real_road.name
        self.light = real_road.light  # the controller's own signal state is known exactly
        self.lanes = [_PerceivedLane() for _ in range(n_lanes)]

    def has_emergency_vehicle(self) -> bool:
        return self._real.has_emergency_vehicle()


class PerceivedIntersection:
    """What a controller sees: perceived vehicles; commands go to the real junction."""

    def __init__(self, real: Intersection):
        self._real = real
        self.roads = {name: _PerceivedRoad(road, len(road.lanes)) for name, road in real.roads.items()}

    def set_light_state(self, road_name, state) -> None:
        self._real.set_light_state(road_name, state)


class SensedController(SignalControllerBase):
    def __init__(self, inner: SignalControllerBase, sensor: SensorModel):
        self.inner = inner
        self.sensor = sensor
        self._rng = random.Random(sensor.seed)
        self._view: PerceivedIntersection | None = None
        self._since_refresh = 0.0
        self._phantoms: dict = {}

    def _refresh(self, intersection: Intersection) -> None:
        s = self.sensor
        if self._view is None:
            self._view = PerceivedIntersection(intersection)
            # Fixed phantom spots per lane, chosen once (static background).
            for name, road in intersection.roads.items():
                for lane_index in range(len(road.lanes)):
                    self._phantoms[(name, lane_index)] = [
                        STOP_LINE_POS_M - self._rng.uniform(0, s.view_m)
                        for _ in range(s.phantoms_per_approach // len(road.lanes)
                                       + (lane_index < s.phantoms_per_approach % len(road.lanes)))
                    ]
        for name, road in intersection.roads.items():
            seen_road = self._view.roads[name]
            for lane_index, lane in enumerate(road.lanes):
                seen = []
                for v in lane.vehicles:
                    if not (STOP_LINE_POS_M - s.view_m <= v.position_m < STOP_LINE_POS_M):
                        continue
                    if s.recall < 1.0 and self._rng.random() >= s.recall:
                        continue
                    seen.append(_Seen(VehicleType.CAR if s.class_blind else v.vehicle_type, v.position_m, v.speed_mps))
                for position in self._phantoms[(name, lane_index)]:
                    if self._rng.random() < s.phantom_presence:
                        seen.append(_Seen(VehicleType.CAR, position, 0.0))
                seen.sort(key=lambda x: -x.position_m)
                seen_road.lanes[lane_index].vehicles = seen

    def update(self, intersection: Intersection, dt: float) -> None:
        self._since_refresh += dt
        if self._view is None or self._since_refresh >= self.sensor.refresh_s - 1e-9:
            self._refresh(intersection)
            self._since_refresh = 0.0
        self.inner.update(self._view, dt)

    def current_phase_name(self) -> str:
        return self.inner.current_phase_name()

    def describe(self) -> str:
        return f"Sensed({self.inner.describe()})"

    def resync(self, intersection: Intersection) -> None:
        self.inner.resync(intersection)

    def resume_from_all_red(self, intersection: Intersection, served_roads) -> None:
        self.inner.resume_from_all_red(intersection, served_roads)
