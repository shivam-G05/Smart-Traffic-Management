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


class VehicleDetection(BaseModel):
    x: int
    y: int
    w: int
    h: int
    confidence: float
    matched: bool
    matched_type: str | None
    track_id: int | None


class RoadVisionFrame(BaseModel):
    road: str
    frame_jpeg_base64: str
    detections: list[VehicleDetection]
    ground_truth_count: int
    detected_count: int
    precision: float | None
    recall: float | None
    active_tracks: int
    unique_vehicles_tracked: int


class VisionSnapshot(BaseModel):
    sim_time: float
    roads: dict[str, RoadVisionFrame]
