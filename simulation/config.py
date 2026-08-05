"""Static simulation constants and per-vehicle-type physical profiles."""

from dataclasses import dataclass
from enum import Enum


class VehicleType(str, Enum):
    CAR = "car"
    MOTORCYCLE = "motorcycle"
    BUS = "bus"
    TRUCK = "truck"
    AUTO = "auto"
    AMBULANCE = "ambulance"
    FIRE_TRUCK = "fire_truck"


class RoadName(str, Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


class LightState(str, Enum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"


@dataclass(frozen=True)
class VehicleProfile:
    length_m: float
    max_speed_mps: float
    acceleration_mps2: float
    deceleration_mps2: float
    is_emergency: bool
    spawn_weight: float  # relative likelihood of this type spawning


VEHICLE_PROFILES: dict[VehicleType, VehicleProfile] = {
    VehicleType.CAR: VehicleProfile(4.5, 14.0, 2.5, 4.5, False, 55),
    VehicleType.MOTORCYCLE: VehicleProfile(2.0, 15.0, 3.5, 5.0, False, 25),
    VehicleType.AUTO: VehicleProfile(3.2, 11.0, 2.0, 4.0, False, 10),
    VehicleType.BUS: VehicleProfile(10.0, 10.0, 1.2, 3.0, False, 5),
    VehicleType.TRUCK: VehicleProfile(9.0, 9.0, 1.0, 2.8, False, 4),
    VehicleType.AMBULANCE: VehicleProfile(5.5, 16.0, 3.0, 5.0, True, 0.5),
    VehicleType.FIRE_TRUCK: VehicleProfile(10.5, 12.0, 1.5, 3.5, True, 0.5),
}

# --- Road geometry (all distances in metres, 1D position along the road) ---
ROAD_LENGTH_M = 260.0          # spawn point -> despawn point
STOP_LINE_POS_M = 200.0        # where vehicles must stop on red/yellow
INTERSECTION_EXIT_POS_M = 218.0  # far edge of the intersection box
LANES_PER_ROAD = 2

SAFE_FOLLOWING_GAP_M = 8.0
MIN_VEHICLE_GAP_M = 2.0

# --- Signal timing (fixed-timer baseline, seconds) ---
FIXED_GREEN_DURATION_S = 20.0
YELLOW_DURATION_S = 3.0
ALL_RED_CLEARANCE_S = 1.0

# --- Spawn ---
BASE_SPAWN_RATE_PER_S = 0.35   # baseline mean arrivals/sec per road (Poisson)
SPAWN_RATE_JITTER = 0.9        # applied per-road periodically to create asymmetry

# --- Simulation loop ---
TICK_HZ = 20
BROADCAST_HZ = 10
