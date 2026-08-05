from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_websocket_receives_simulation_snapshot():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/simulation") as websocket:
            message = websocket.receive_json()
    assert "roads" in message
    assert "active_phase" in message
    assert set(message["roads"].keys()) == {"north", "south", "east", "west"}


def test_intersection_state_endpoint_after_connection():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/simulation") as websocket:
            websocket.receive_json()
        response = client.get("/api/intersection/state")
    assert response.status_code == 200
    assert "roads" in response.json()
