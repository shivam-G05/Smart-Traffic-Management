from dataclasses import dataclass, field
from itertools import count

from simulation.config import VEHICLE_PROFILES, VehicleType

_id_counter = count(1)


@dataclass
class Vehicle:
    vehicle_type: VehicleType
    lane_index: int
    position_m: float = 0.0
    speed_mps: float = 0.0
    id: int = field(default_factory=lambda: next(_id_counter))
    exited: bool = False

    @property
    def profile(self):
        return VEHICLE_PROFILES[self.vehicle_type]

    @property
    def is_emergency(self) -> bool:
        return self.profile.is_emergency

    def to_state(self) -> dict:
        return {
            "id": self.id,
            "type": self.vehicle_type.value,
            "lane": self.lane_index,
            "position": round(self.position_m, 2),
            "speed": round(self.speed_mps, 2),
            "emergency": self.is_emergency,
        }
