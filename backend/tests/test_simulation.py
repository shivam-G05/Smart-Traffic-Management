import random

import pytest

from simulation.config import LightState, RoadName, VehicleType
from simulation.controllers.fixed_timer_controller import EW_GROUP, NS_GROUP, FixedTimerController
from simulation.engine import SimulationEngine
from simulation.entities.intersection import Intersection
from simulation.entities.road import Road
from simulation.entities.vehicle import Vehicle


def test_road_spawns_vehicles_over_time():
    road = Road(RoadName.NORTH, spawn_rate_per_s=5.0)
    for _ in range(100):
        road.maybe_spawn(dt=0.05)
    assert road.total_vehicle_count() > 0


def test_vehicle_moves_forward_on_green():
    road = Road(RoadName.NORTH, spawn_rate_per_s=0.0)
    road.light.set_state(LightState.GREEN)
    road._spawn_vehicle()
    vehicle = road.lanes[0].vehicles[0]
    start_position = vehicle.position_m
    for _ in range(200):
        road.update(dt=0.05)
    assert vehicle.position_m > start_position


def test_vehicle_stops_at_red_light():
    road = Road(RoadName.NORTH, spawn_rate_per_s=0.0)
    road.light.set_state(LightState.RED)
    road._spawn_vehicle()
    for _ in range(400):
        road.update(dt=0.05)
    vehicle = road.lanes[0].vehicles[0]
    assert vehicle.position_m < 200.0 + 1.0


def test_total_exited_and_wait_time_accumulate_as_vehicles_cross():
    road = Road(RoadName.NORTH, spawn_rate_per_s=0.0)
    road.light.set_state(LightState.GREEN)
    road._spawn_vehicle()
    assert road.total_exited() == 0

    for _ in range(1000):  # long enough for a car to cross ROAD_LENGTH_M at max speed
        road.update(dt=0.05)

    assert road.total_exited() == 1
    assert road.total_wait_time_s() >= 0.0


def test_queued_time_only_accrues_while_stopped_at_a_red_light():
    road = Road(RoadName.NORTH, spawn_rate_per_s=0.0)
    road.light.set_state(LightState.RED)
    road._spawn_vehicle()
    vehicle = road.lanes[0].vehicles[0]
    for _ in range(100):  # 5s stopped at red
        road.update(dt=0.05)
    queued_after_red = vehicle.queued_time_s
    assert queued_after_red > 0.0

    road.light.set_state(LightState.GREEN)
    for _ in range(1000):  # long enough to clear the intersection
        road.update(dt=0.05)

    # Once it's crossed (exited), no further queued time accrues beyond
    # whatever it accumulated while genuinely stopped at the red light.
    assert road.total_wait_time_s() == pytest.approx(queued_after_red, abs=0.2)


def test_seeded_engines_produce_identical_vehicle_arrivals():
    engine_a = SimulationEngine(controller=FixedTimerController(), seed=42)
    engine_b = SimulationEngine(controller=FixedTimerController(), seed=42)

    for _ in range(1000):
        engine_a.tick(dt=0.05)
        engine_b.tick(dt=0.05)
        assert (
            engine_a.intersection.total_vehicles_active()
            == engine_b.intersection.total_vehicles_active()
        )


def test_unseeded_engines_default_to_todays_behavior():
    # seed=None must not raise and must still produce a usable simulation —
    # this is the exact default every pre-Milestone-9 call site relies on.
    engine = SimulationEngine()
    for _ in range(100):
        engine.tick(dt=0.05)
    assert engine.sim_time_s == pytest.approx(5.0)


def test_vehicles_never_overlap_or_pass_through_each_other():
    # Regression: the old car-following rule only reacted within 8m, but a
    # car at full speed needs ~22m to stop, so followers drove into and
    # through stopped queues (worst measured overlap was 14.75m). Heavy
    # demand against a long red is exactly the case that used to break.
    road = Road(RoadName.NORTH, spawn_rate_per_s=1.0, rng=random.Random(1))
    road.light.set_state(LightState.RED)
    dt = 0.05
    for tick in range(int(240 / dt)):
        if tick == int(120 / dt):
            road.light.set_state(LightState.GREEN)
        road.maybe_spawn(dt)
        road.update(dt)
        for lane in road.lanes:
            for leader, follower in zip(lane.vehicles, lane.vehicles[1:]):
                gap = leader.position_m - leader.profile.length_m - follower.position_m
                assert gap >= -1e-9


def test_emergency_flag_clears_once_vehicle_is_through_the_junction():
    road = Road(RoadName.NORTH, spawn_rate_per_s=0.0)
    ambulance = Vehicle(vehicle_type=VehicleType.AMBULANCE, lane_index=0, position_m=150.0)
    road.lanes[0].spawn(ambulance)
    assert road.has_emergency_vehicle()

    ambulance.position_m = 230.0  # past INTERSECTION_EXIT_POS_M, still on the map
    assert not road.has_emergency_vehicle()


def test_fixed_timer_never_grants_conflicting_greens():
    intersection = Intersection()
    controller = FixedTimerController()
    for _ in range(2000):
        controller.update(intersection, dt=0.05)
        ns_green = any(intersection.roads[r].light.state == LightState.GREEN for r in NS_GROUP)
        ew_green = any(intersection.roads[r].light.state == LightState.GREEN for r in EW_GROUP)
        assert not (ns_green and ew_green)


def test_fixed_timer_eventually_greens_every_road():
    intersection = Intersection()
    controller = FixedTimerController()
    seen_green: set[RoadName] = set()
    for _ in range(2000):
        controller.update(intersection, dt=0.05)
        for name, road in intersection.roads.items():
            if road.light.state == LightState.GREEN:
                seen_green.add(name)
    assert seen_green == set(RoadName)


def test_engine_state_serializes_all_roads():
    engine = SimulationEngine()
    for _ in range(50):
        engine.tick(dt=0.05)
    state = engine.to_state()
    assert set(state["roads"].keys()) == {r.value for r in RoadName}
    assert "active_phase" in state
