"""Weighted traffic density scoring per lane/road.

Combines vehicle count, queue state, and vehicle-type weight into a single
"density score" — the input Milestone 5's adaptive controller uses to decide
green-light duration. Kept out of `simulation/` deliberately: these weights
are a decision-engine concern (tunable independently of vehicle physics),
not a simulation fact, so `simulation/config.py`/`VehicleProfile` stay
decision-agnostic.

Queued vehicles weigh more than moving ones — a vehicle stopped at the line
is exactly the "needs green" pressure this score exists to capture, while a
vehicle still approaching at speed will likely clear on its own.
"""

from collections.abc import Mapping

from simulation.config import VehicleType
from simulation.entities.intersection import Intersection
from simulation.entities.lane import Lane
from simulation.entities.road import Road
from simulation.entities.vehicle import Vehicle

DENSITY_WEIGHTS: dict[VehicleType, float] = {
    VehicleType.CAR: 1.0,
    VehicleType.MOTORCYCLE: 0.5,
    VehicleType.AUTO: 0.8,
    VehicleType.BUS: 3.0,
    VehicleType.TRUCK: 2.5,
    VehicleType.AMBULANCE: 6.0,
    VehicleType.FIRE_TRUCK: 6.0,
}

QUEUED_MULTIPLIER = 1.5
MOVING_MULTIPLIER = 0.5


def vehicle_density_weight(vehicle: Vehicle) -> float:
    return DENSITY_WEIGHTS[vehicle.vehicle_type]


# The optional weights/multiplier arguments below exist for the ablation
# experiments (scripts/ablation.py), which re-run the controller with
# different scoring; every caller in the live system uses the defaults.

def lane_density_score(
    lane: Lane,
    weights: Mapping[VehicleType, float] = DENSITY_WEIGHTS,
    queued_multiplier: float = QUEUED_MULTIPLIER,
    moving_multiplier: float = MOVING_MULTIPLIER,
) -> float:
    score = 0.0
    for vehicle in lane.vehicles:
        weight = weights[vehicle.vehicle_type]
        score += weight * (queued_multiplier if Lane._is_queued(vehicle) else moving_multiplier)
    return score


def road_density_score(
    road: Road,
    weights: Mapping[VehicleType, float] = DENSITY_WEIGHTS,
    queued_multiplier: float = QUEUED_MULTIPLIER,
    moving_multiplier: float = MOVING_MULTIPLIER,
) -> float:
    return sum(lane_density_score(lane, weights, queued_multiplier, moving_multiplier) for lane in road.lanes)


def compute_intersection_density(intersection: Intersection) -> dict[str, dict]:
    """Returns {road_name: {"road_score": float, "lane_scores": [float, ...]}}."""
    result = {}
    for name, road in intersection.roads.items():
        lane_scores = [lane_density_score(lane) for lane in road.lanes]
        result[name.value] = {"road_score": sum(lane_scores), "lane_scores": lane_scores}
    return result


def road_density_breakdown(road: Road) -> list[dict]:
    """The same formula as road_density_score, itemized per (vehicle type,
    queued/moving) group, so the dashboard can show exactly how a road's
    score was produced. Contributions sum to road_density_score(road)."""
    groups: dict[tuple[VehicleType, bool], int] = {}
    for lane in road.lanes:
        for vehicle in lane.vehicles:
            key = (vehicle.vehicle_type, Lane._is_queued(vehicle))
            groups[key] = groups.get(key, 0) + 1

    rows = []
    for (vehicle_type, queued), count in groups.items():
        weight = DENSITY_WEIGHTS[vehicle_type]
        multiplier = QUEUED_MULTIPLIER if queued else MOVING_MULTIPLIER
        rows.append(
            {
                "type": vehicle_type.value,
                "state": "queued" if queued else "moving",
                "count": count,
                "weight": weight,
                "multiplier": multiplier,
                "contribution": round(count * weight * multiplier, 2),
            }
        )
    rows.sort(key=lambda r: r["contribution"], reverse=True)
    return rows
