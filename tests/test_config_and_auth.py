import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.config import settings

client = TestClient(app)

def test_settings_loaded():
    assert settings.gateway_api_key is not None
    assert len(settings.gateway_api_key) > 8
    assert settings.stale_sensor_timeout_seconds > 0
    assert "sqlite" in settings.database_url


def test_sensor_ingest_missing_auth():
    payload = {
        "node_id": "NODE-UPSTREAM-01",
        "timestamp_recorded": "2026-10-26T10:00:00Z",
        "water_level_cm": 50.0
    }
    response = client.post("/api/v1/sensors/ingest", json=payload)
    # Header missing
    assert response.status_code in [401, 422]


def test_sensor_ingest_invalid_auth():
    payload = {
        "node_id": "NODE-UPSTREAM-01",
        "timestamp_recorded": "2026-10-26T10:00:00Z",
        "water_level_cm": 50.0
    }
    response = client.post(
        "/api/v1/sensors/ingest",
        json=payload,
        headers={"X-API-Key": "wrong_invalid_key_1234"}
    )
    assert response.status_code == 401
    assert "Invalid Gateway API Key" in response.json()["detail"]


def test_sensor_ingest_valid_auth():
    payload = {
        "node_id": "NODE-UPSTREAM-01",
        "timestamp_recorded": "2026-10-26T10:00:00Z",
        "water_level_cm": 50.0,
        "battery_voltage": 4.10,
        "rssi_dbm": -74.0,
        "snr_db": 9.2,
        "is_simulated": True
    }
    response = client.post(
        "/api/v1/sensors/ingest",
        json=payload,
        headers={"X-API-Key": settings.gateway_api_key}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["node_id"] == "NODE-UPSTREAM-01"
    assert data["water_level_cm"] == 50.0
    assert data["is_simulated"] is True
    assert "reading_hash" in data
