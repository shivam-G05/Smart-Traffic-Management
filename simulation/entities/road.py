import random
from collections import deque

from simulation.config import (
    INTERSECTION_EXIT_POS_M,
    LANES_PER_ROAD,
    SAFE_FOLLOWING_GAP_M,
    VEHICLE_PROFILES,
    RoadName,
    VehicleType,
)
from simulation.entities.lane import Lane, safe_following_speed
from simulation.entities.traffic_light import TrafficLight
from simulation.entities.vehicle import Vehicle

_VEHICLE_TYPES = list(VEHICLE_PROFILES.keys())
_SPAWN_WEIGHTS = [VEHICLE_PROFILES[t].spawn_weight for t in _VEHICLE_TYPES]


class Road:
    def __init__(
        self,
        name: RoadName,
        spawn_rate_per_s: float,
        rng: random.Random | None = None,
        entry_backlog: bool = False,
        insert_at_speed: bool = False,
        reaction_time_s: float = 0.0,
    ):
        self.name = name
        self.reaction_time_s = reaction_time_s  # see lane.safe_following_speed
        self.lanes = [Lane(i, reaction_time_s=reaction_time_s) for i in range(LANES_PER_ROAD)]
        self.light = TrafficLight()
        self.spawn_rate_per_s = spawn_rate_per_s
        self._spawn_accumulator = 0.0
        # Defaults to the global `random` module (unseeded, today's
        # behavior). Milestone 9 passes a shared random.Random(seed)
        # instance so two engines can be compared against identical
        # vehicle-arrival sequences.
        self._rng = rng if rng is not None else random
        # entry_backlog=False (default, the live dashboard and the paper's
        # experiments) drops an arrival whose lane entry is still occupied.
        # Above capacity that hides the overload: demand silently vanishes
        # instead of queueing. With entry_backlog=True a blocked arrival
        # waits off-map in arrival order and enters as soon as a lane has
        # room, so unserved demand, spillback and entry delay are measurable.
        # Its vehicle type is drawn on arrival, not on entry, so two runs
        # with the same seed see identical arrivals whatever the controller.
        self.entry_backlog = entry_backlog
        # insert_at_speed=False (default) puts a new vehicle on the road at
        # rest. A vehicle then has to accelerate ~12 m before the next can
        # enter, which caps entry at roughly 2 vehicles per 3 s per approach
        # — below what the signal can discharge, so above capacity the road
        # entry, not the junction, would be the bottleneck. With True a
        # vehicle enters at the fastest speed from which it can still stop
        # behind the vehicle ahead (like SUMO's departSpeed="max").
        self.insert_at_speed = insert_at_speed
        self._clock_s = 0.0
        self._backlog: deque[tuple[VehicleType, float]] = deque()  # (type, arrival time)

    def maybe_spawn(self, dt: float) -> None:
        self._clock_s += dt
        self._spawn_accumulator += self.spawn_rate_per_s * dt
        while self._spawn_accumulator >= 1.0:
            self._spawn_accumulator -= 1.0
            if self.entry_backlog:
                self._backlog.append((self._draw_vehicle_type(), self._clock_s))
            else:
                self._spawn_vehicle()
        if self.entry_backlog:
            self._admit_backlog()

    def _draw_vehicle_type(self) -> VehicleType:
        return self._rng.choices(_VEHICLE_TYPES, weights=_SPAWN_WEIGHTS, k=1)[0]

    @staticmethod
    def _entry_clear(lane: Lane) -> bool:
        if not lane.vehicles:
            return True
        last = lane.vehicles[-1]
        return last.position_m - last.profile.length_m >= SAFE_FOLLOWING_GAP_M

    def _admit_backlog(self) -> None:
        while self._backlog:
            free = [lane for lane in self.lanes if self._entry_clear(lane)]
            if not free:
                return
            lane = min(free, key=lambda l: l.vehicle_count())
            vehicle_type, arrived_at = self._backlog.popleft()
            vehicle = Vehicle(
                vehicle_type=vehicle_type,
                lane_index=lane.lane_index,
                entry_wait_s=self._clock_s - arrived_at,
            )
            self._set_entry_speed(vehicle, lane)
            lane.spawn(vehicle)

    def _set_entry_speed(self, vehicle: Vehicle, lane: Lane) -> None:
        if not self.insert_at_speed:
            return
        profile = vehicle.profile
        speed = profile.max_speed_mps
        if lane.vehicles:
            # Same Gipps-style bound Lane applies every step: no faster than
            # still lets it stop MIN_VEHICLE_GAP_M behind the leader even if
            # the leader brakes as hard as it can.
            leader = lane.vehicles[-1]
            gap = leader.position_m - leader.profile.length_m
            speed = min(speed, safe_following_speed(gap, leader.speed_mps, leader.profile.deceleration_mps2,
                                                    profile.deceleration_mps2, self.reaction_time_s))
        vehicle.speed_mps = speed

    @property
    def backlog_count(self) -> int:
        """Arrivals still waiting to enter (always 0 without entry_backlog)."""
        return len(self._backlog)

    def backlog_waits_s(self) -> list[float]:
        """How long each vehicle still in the backlog has waited so far."""
        return [self._clock_s - arrived_at for _, arrived_at in self._backlog]

    def _spawn_vehicle(self) -> None:
        lane = min(self.lanes, key=lambda l: l.vehicle_count())
        if lane.vehicles:
            last = lane.vehicles[-1]
            # Measure clearance to the last vehicle's *rear*, not its nose —
            # a 10m bus whose nose had passed 6m still covered the spawn
            # point, so new vehicles used to appear inside it.
            if last.position_m - last.profile.length_m < SAFE_FOLLOWING_GAP_M:
                return  # spawn point still occupied, skip this arrival
        vehicle_type: VehicleType = self._rng.choices(_VEHICLE_TYPES, weights=_SPAWN_WEIGHTS, k=1)[0]
        vehicle = Vehicle(vehicle_type=vehicle_type, lane_index=lane.lane_index)
        self._set_entry_speed(vehicle, lane)
        lane.spawn(vehicle)

    def update(self, dt: float) -> None:
        self.light.tick(dt)
        for lane in self.lanes:
            lane.update(dt, self.light.state)

    def total_queue_length(self) -> int:
        return sum(lane.queue_length() for lane in self.lanes)

    def total_vehicle_count(self) -> int:
        return sum(lane.vehicle_count() for lane in self.lanes)

    def has_emergency_vehicle(self) -> bool:
        """An emergency vehicle that still has to get through this junction.
        Once it has crossed INTERSECTION_EXIT_POS_M it no longer needs a
        green, even though it stays on the map until ROAD_LENGTH_M — counting
        it until then would hold every other road at red for no reason."""
        return any(
            v.is_emergency and v.position_m < INTERSECTION_EXIT_POS_M
            for lane in self.lanes
            for v in lane.vehicles
            if not v.exited
        )

    def total_exited(self) -> int:
        return sum(lane.total_exited for lane in self.lanes)

    def total_wait_time_s(self) -> float:
        return sum(lane.total_wait_time_s for lane in self.lanes)

    def to_state(self) -> dict:
        return {
            "name": self.name.value,
            "light": self.light.to_state(),
            "queue_length": self.total_queue_length(),
            "vehicle_count": self.total_vehicle_count(),
            "has_emergency_vehicle": self.has_emergency_vehicle(),
            "total_exited": self.total_exited(),
            "total_wait_time_s": round(self.total_wait_time_s(), 2),
            "lanes": [lane.to_state() for lane in self.lanes],
        }
