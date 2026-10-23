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
    body = response.json()
    assert "roads" in body
    for road in body["roads"].values():
        assert "density_score" in road
        assert road["density_score"] >= 0.0
        for lane in road["lanes"]:
            assert "density_score" in lane
            assert lane["density_score"] >= 0.0


def test_websocket_receives_vision_snapshot():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/vision") as websocket:
            message = websocket.receive_json()
    assert set(message["roads"].keys()) == {"north", "south", "east", "west"}
    for road in message["roads"].values():
        assert "frame_jpeg_base64" in road
        assert "detections" in road


def test_vision_latest_endpoint_after_connection():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/vision") as websocket:
            websocket.receive_json()
        response = client.get("/api/vision/latest")
    assert response.status_code == 200
    assert "roads" in response.json()


def test_explain_endpoint_exposes_live_constants():
    with TestClient(app) as client:
        body = client.get("/api/explain").json()
    assert body["congestion"]["low_max"] < body["congestion"]["high_min"]
    assert body["adaptive"]["min_green_s"] < body["adaptive"]["max_green_s"]
    assert "car" in body["density"]["weights"]
    assert body["tracking"]["min_hits"] >= 1
    assert body["congestion"]["alert_hold_s"] > 0


def test_state_carries_congestion_level_and_density_breakdown():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/simulation") as websocket:
            websocket.receive_json()
        state = client.get("/api/intersection/state").json()
    for road in state["roads"].values():
        assert road["congestion_level"] in {"low", "medium", "high"}
        assert isinstance(road["high_traffic_alert"], bool)
        total = sum(row["contribution"] for row in road["density_breakdown"])
        assert abs(total - road["density_score"]) < 0.05
