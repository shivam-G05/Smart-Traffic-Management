from decision_engine.density import (
    DENSITY_WEIGHTS,
    MOVING_MULTIPLIER,
    QUEUED_MULTIPLIER,
    lane_density_score,
    road_density_breakdown,
    road_density_score,
)
from simulation.config import RoadName, VehicleType
from simulation.entities.lane import Lane
from simulation.entities.road import Road
from simulation.entities.vehicle import Vehicle


def test_empty_lane_has_zero_density():
    lane = Lane(lane_index=0)
    assert lane_density_score(lane) == 0.0


def test_queued_vehicle_weighs_more_than_moving_vehicle():
    queued_lane = Lane(lane_index=0)
    queued_lane.spawn(Vehicle(vehicle_type=VehicleType.CAR, lane_index=0, position_m=50.0, speed_mps=0.0))

    moving_lane = Lane(lane_index=0)
    moving_lane.spawn(Vehicle(vehicle_type=VehicleType.CAR, lane_index=0, position_m=50.0, speed_mps=10.0))

    queued_score = lane_density_score(queued_lane)
    moving_score = lane_density_score(moving_lane)

    assert queued_score == DENSITY_WEIGHTS[VehicleType.CAR] * QUEUED_MULTIPLIER
    assert moving_score == DENSITY_WEIGHTS[VehicleType.CAR] * MOVING_MULTIPLIER
    assert queued_score > moving_score


def test_ambulance_outweighs_several_queued_cars():
    lane = Lane(lane_index=0)
    for _ in range(5):
        lane.spawn(Vehicle(vehicle_type=VehicleType.CAR, lane_index=0, position_m=50.0, speed_mps=0.0))
    cars_score = lane_density_score(lane)

    ambulance_lane = Lane(lane_index=0)
    ambulance_lane.spawn(Vehicle(vehicle_type=VehicleType.AMBULANCE, lane_index=0, position_m=50.0, speed_mps=0.0))
    ambulance_score = lane_density_score(ambulance_lane)

    assert ambulance_score > cars_score


def test_road_score_equals_sum_of_lane_scores():
    road = Road(RoadName.NORTH, spawn_rate_per_s=0.0)
    road.lanes[0].spawn(Vehicle(vehicle_type=VehicleType.CAR, lane_index=0, position_m=50.0, speed_mps=0.0))
    road.lanes[1].spawn(Vehicle(vehicle_type=VehicleType.BUS, lane_index=1, position_m=50.0, speed_mps=0.0))

    expected = sum(lane_density_score(lane) for lane in road.lanes)
    assert road_density_score(road) == expected
    assert road_density_score(road) > 0.0


def test_breakdown_itemizes_exactly_the_road_score():
    road = Road(RoadName.NORTH, spawn_rate_per_s=0.0)
    road.lanes[0].spawn(Vehicle(vehicle_type=VehicleType.CAR, lane_index=0, position_m=150.0, speed_mps=0.0))
    road.lanes[0].spawn(Vehicle(vehicle_type=VehicleType.CAR, lane_index=0, position_m=140.0, speed_mps=0.0))
    road.lanes[1].spawn(Vehicle(vehicle_type=VehicleType.BUS, lane_index=1, position_m=120.0, speed_mps=9.0))

    rows = road_density_breakdown(road)
    by_key = {(r["type"], r["state"]): r for r in rows}

    assert by_key[("car", "queued")]["count"] == 2
    assert by_key[("bus", "moving")]["contribution"] == DENSITY_WEIGHTS[VehicleType.BUS] * MOVING_MULTIPLIER
    assert abs(sum(r["contribution"] for r in rows) - road_density_score(road)) < 1e-6
