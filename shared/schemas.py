"""Pydantic DTOs shared between the simulation engine and the API/WebSocket
layer. Kept separate from simulation/entities so the simulation package has
no framework dependency (pydantic) and stays reusable outside a web context.
"""

from pydantic import BaseModel


class VehicleState(BaseModel):
    id: int
    type: str
    lane: int
    position: float
    speed: float
    emergency: bool


class LaneState(BaseModel):
    lane_index: int
    queue_length: int
    vehicle_count: int
    vehicles: list[VehicleState]


class TrafficLightState(BaseModel):
    state: str
    time_in_state: float


class RoadState(BaseModel):
    name: str
    light: TrafficLightState
    queue_length: int
    vehicle_count: int
    has_emergency_vehicle: bool
    lanes: list[LaneState]


class IntersectionSnapshot(BaseModel):
    sim_time: float
    active_phase: str
    controller: str
    total_active_vehicles: int
    roads: dict[str, RoadState]
