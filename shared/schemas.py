"""Pydantic DTOs shared between the simulation engine and the API/WebSocket
layer. Kept separate from simulation/entities so the simulation package has
no framework dependency (pydantic) and stays reusable outside a web context.
"""

from pydantic import BaseModel


class VehicleState(BaseModel):
    id: int
    type: str
    length: float
    lane: int
    position: float
    speed: float
    emergency: bool


class LaneState(BaseModel):
    lane_index: int
    queue_length: int
    vehicle_count: int
    density_score: float
    vehicles: list[VehicleState]


class TrafficLightState(BaseModel):
    state: str
    time_in_state: float


class DensityContribution(BaseModel):
    type: str
    state: str  # "queued" | "moving"
    count: int
    weight: float
    multiplier: float
    contribution: float


class RoadState(BaseModel):
    name: str
    light: TrafficLightState
    queue_length: int
    vehicle_count: int
    density_score: float
    congestion_level: str  # "low" | "medium" | "high"
    high_traffic_alert: bool  # congestion "high", held on briefly to avoid flicker
    density_breakdown: list[DensityContribution]
    has_emergency_vehicle: bool
    total_exited: int
    total_wait_time_s: float
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
    is_emergency: bool


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
    vision_emergency_detected: bool


class VisionSnapshot(BaseModel):
    sim_time: float
    roads: dict[str, RoadVisionFrame]
