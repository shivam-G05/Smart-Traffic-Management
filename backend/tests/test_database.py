import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import app
from database import writer
from database.models import SimulationRun
from database.session import Database


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def db():
    database = Database("sqlite+aiosqlite:///:memory:")
    _run(database.init())
    yield database
    _run(database.dispose())


def _sample_state(**road_overrides) -> dict:
    road = {
        "queue_length": 2,
        "vehicle_count": 3,
        "density_score": 4.5,
        "light": {"state": "green"},
        "has_emergency_vehicle": False,
        "total_exited": 1,
        "total_wait_time_s": 3.2,
    }
    road.update(road_overrides)
    return {"sim_time": 12.5, "roads": {"north": road}}


def test_create_run_and_persist_sample_round_trip(db):
    run_id = _run(writer.create_run(db.session_factory, controller_type="fixed"))
    assert run_id > 0

    _run(writer.persist_sample(db.session_factory, run_id, _sample_state()))

    rows = _run(writer.fetch_road_snapshot_rows(db.session_factory, run_id))
    assert len(rows) == 1
    assert rows[0]["road_name"] == "north"
    assert rows[0]["density_score"] == 4.5
    assert rows[0]["total_wait_time_s"] == 3.2


def test_persist_event_round_trip(db):
    run_id = _run(writer.create_run(db.session_factory, controller_type="adaptive"))
    _run(
        writer.persist_event(
            db.session_factory,
            run_id,
            sim_time=5.0,
            event_type="EMERGENCY_PREEMPTION_START",
            phase_name="EMERGENCY_FORCE_YELLOW_west",
            road_name="west",
        )
    )

    events = _run(writer.fetch_signal_events(db.session_factory, run_id))
    assert len(events) == 1
    assert events[0]["event_type"] == "EMERGENCY_PREEMPTION_START"
    assert events[0]["road_name"] == "west"


def test_end_run_sets_ended_at(db):
    run_id = _run(writer.create_run(db.session_factory, controller_type="fixed"))

    async def _get_run():
        async with db.session_factory() as session:
            return await session.get(SimulationRun, run_id)

    assert _run(_get_run()).ended_at is None
    _run(writer.end_run(db.session_factory, run_id))
    assert _run(_get_run()).ended_at is not None


def test_reports_export_endpoint_json_and_csv_are_well_formed():
    with TestClient(app) as client:
        json_response = client.get("/api/reports/export?format=json")
        csv_response = client.get("/api/reports/export?format=csv")

    assert json_response.status_code == 200
    body = json_response.json()
    assert "run_id" in body
    assert "road_snapshots" in body
    assert "signal_events" in body

    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    header = csv_response.text.strip().splitlines()[0].split(",")
    assert header == [
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
