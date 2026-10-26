import os
import re
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.config import settings

client = TestClient(app)

def test_static_frontend_files_exist():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
    assert os.path.exists(os.path.join(base_dir, "index.html"))
    assert os.path.exists(os.path.join(base_dir, "css", "style.css"))
    assert os.path.exists(os.path.join(base_dir, "js", "app.js"))
    assert os.path.exists(os.path.join(base_dir, "js", "api.js"))
    assert os.path.exists(os.path.join(base_dir, "js", "chart.js"))
    assert os.path.exists(os.path.join(base_dir, "js", "storage.js"))


def test_frontend_index_accessibility_and_semantic_structure():
    html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html"))
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Accessible landmarks & roles
    assert 'role="banner"' in html
    assert 'role="main"' in html
    assert 'role="alert"' in html
    assert 'aria-live="polite"' in html or 'aria-live="assertive"' in html
    assert 'aria-label=' in html

    # Strict Provenance Labels Present
    assert "ACTUAL PHYSICAL SENSOR" in html
    assert "OFFICIAL RESERVOIR OBSERVATION" in html
    assert "MODEL-GENERATED PREDICTION" in html
    assert "SUPPORTING CONTEXT ONLY" in html

    # Key UI Element IDs referenced by JavaScript
    required_ids = [
        "arrivalStatusBadge", "arrivalMainTime", "arrivalUncertaintyLabel",
        "arrivalTravelTime", "confidenceBar", "confidencePercent",
        "arrivalExplanationText", "sensorNodesList", "reservoirTableBody",
        "irrigationSchedulesList", "weatherTemp", "eventLogContainer",
        "canalChartContainer", "settingsModal", "telemetryModal", "nodeDetailModal"
    ]
    for element_id in required_ids:
        assert f'id="{element_id}"' in html, f"Missing required ID {element_id} in index.html"


def test_websocket_telemetry_handshake():
    """Test WebSocket connection and ping/pong heartbeat."""
    with client.websocket_connect("/api/v1/ws/telemetry") as websocket:
        websocket.send_text("ping")
        data = websocket.receive_text()
        assert data == "pong"


def test_provenance_labels_in_api_responses():
    # 1. Arrival Estimate Classification
    res_arr = client.get("/api/v1/intelligence/arrival-estimates")
    assert res_arr.status_code == 200
    assert res_arr.json()["data_classification"] == "MODEL_GENERATED_PREDICTION"

    # 2. Weather Classification
    res_w = client.get("/api/v1/intelligence/weather-context")
    assert res_w.status_code == 200
    assert res_w.json()["data_classification"] == "SUPPORTING_CONTEXT_ONLY"

    # 3. Official Reservoir Classification
    res_r = client.get("/api/v1/official/reservoirs")
    assert res_r.status_code == 200
    res_list = res_r.json()
    assert len(res_list) > 0
    assert res_list[0]["data_classification"] == "OFFICIAL_RESERVOIR_OBSERVATION"


def test_stale_and_insufficient_data_handling():
    res = client.get("/api/v1/intelligence/arrival-estimates?target_node_id=NODE-DOWNSTREAM-02&reference_upstream_node_id=NODE-UPSTREAM-01")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["SUFFICIENT_DATA", "INSUFFICIENT_DATA", "NO_FLOW_DETECTED", "SURGE_IN_PROGRESS"]
    assert "explanation" in data
    assert len(data["explanation"]) > 10
