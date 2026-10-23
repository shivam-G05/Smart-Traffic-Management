import csv
import io

from fastapi import APIRouter, Request
from fastapi.responses import Response

from analytics.config import CONGESTION_HIGH_MIN, CONGESTION_LOW_MAX, HIGH_TRAFFIC_ALERT_HOLD_S
from database import writer
from decision_engine.adaptive_controller import EXTENSION_THRESHOLD, MAX_GREEN_S, MIN_GREEN_S
from decision_engine.density import DENSITY_WEIGHTS, MOVING_MULTIPLIER, QUEUED_MULTIPLIER
from decision_engine.emergency_preemption import MAX_HOLD_S, MIN_GREEN_BEFORE_PREEMPT_S
from simulation.config import (
    ALL_RED_CLEARANCE_S,
    BASE_SPAWN_RATE_PER_S,
    FIXED_GREEN_DURATION_S,
    QUEUED_SPEED_MPS,
    YELLOW_DURATION_S,
)
from vision.config import TRACK_MAX_AGE, TRACK_MIN_HITS

router = APIRouter(prefix="/api")

_EXPORT_FIELDNAMES = [
    "sim_time",
    "road_name",
    "queue_length",
    "vehicle_count",
    "density_score",
    "light_state",
    "has_emergency_vehicle",
    "total_exited",
    "total_wait_time_s",
]


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/intersection/state")
async def intersection_state(request: Request):
    runner = request.app.state.simulation_runner
    return runner.latest_state


@router.get("/vision/latest")
async def vision_latest(request: Request):
    runner = request.app.state.vision_runner
    return runner.latest_snapshot


@router.get("/analytics/history/{road}")
async def analytics_history(road: str, request: Request):
    collector = request.app.state.analytics_collector
    return {"road": road, "history": collector.history(road)}


@router.get("/analytics/summary")
async def analytics_summary(request: Request):
    collector = request.app.state.analytics_collector
    return collector.summary()


@router.get("/reports/export")
async def reports_export(request: Request, run_id: int | None = None, format: str = "json"):
    database = request.app.state.database
    target_run_id = run_id if run_id is not None else request.app.state.run_id

    snapshot_rows = await writer.fetch_road_snapshot_rows(database.session_factory, target_run_id)
    event_rows = await writer.fetch_signal_events(database.session_factory, target_run_id)

    if format == "csv":
        buffer = io.StringIO()
        csv_writer = csv.DictWriter(buffer, fieldnames=_EXPORT_FIELDNAMES)
        csv_writer.writeheader()
        csv_writer.writerows(snapshot_rows)
        return Response(content=buffer.getvalue(), media_type="text/csv")

    return {"run_id": target_run_id, "road_snapshots": snapshot_rows, "signal_events": event_rows}


@router.get("/comparison/latest")
async def comparison_latest(request: Request):
    return request.app.state.latest_comparison


@router.get("/explain")
async def explain():
    """Every constant the dashboard's numbers are computed from, read from
    the modules that actually use them — so the "How it works" view shows
    the live values rather than hand-copied ones that could drift."""
    return {
        "density": {
            "weights": {t.value: w for t, w in DENSITY_WEIGHTS.items()},
            "queued_multiplier": QUEUED_MULTIPLIER,
            "moving_multiplier": MOVING_MULTIPLIER,
            "queued_speed_mps": QUEUED_SPEED_MPS,
        },
        "congestion": {
            "low_max": CONGESTION_LOW_MAX,
            "high_min": CONGESTION_HIGH_MIN,
            "alert_hold_s": HIGH_TRAFFIC_ALERT_HOLD_S,
        },
        "fixed_timer": {
            "green_s": FIXED_GREEN_DURATION_S,
            "yellow_s": YELLOW_DURATION_S,
            "all_red_s": ALL_RED_CLEARANCE_S,
        },
        "adaptive": {
            "min_green_s": MIN_GREEN_S,
            "max_green_s": MAX_GREEN_S,
            "extension_threshold": EXTENSION_THRESHOLD,
        },
        "emergency": {"max_hold_s": MAX_HOLD_S, "min_green_before_preempt_s": MIN_GREEN_BEFORE_PREEMPT_S},
        "tracking": {"min_hits": TRACK_MIN_HITS, "max_age_frames": TRACK_MAX_AGE},
        "demand": {"base_spawn_rate_per_s": BASE_SPAWN_RATE_PER_S},
    }


@router.get("/signals/status")
async def signals_status(request: Request):
    runner = request.app.state.simulation_runner
    state = runner.latest_state
    if not state:
        return {"active_phase": None, "roads": {}}
    return {
        "active_phase": state.get("active_phase"),
        "controller": state.get("controller"),
        "roads": {
            name: {
                "light": road["light"]["state"],
                "queue_length": road["queue_length"],
                "density_score": road["density_score"],
                "has_emergency_vehicle": road["has_emergency_vehicle"],
            }
            for name, road in state.get("roads", {}).items()
        },
    }
