import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.config import settings

client = TestClient(app)

def test_health_endpoint():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["mode"] == "offline_first"
    assert data["database"] == "sqlite_wal_active"


def test_list_nodes_endpoint():
    res = client.get("/api/v1/sensors/nodes")
    assert res.status_code == 200
    nodes = res.json()
    assert isinstance(nodes, list)


def test_official_reservoirs_endpoint():
    res = client.get("/api/v1/official/reservoirs")
    assert res.status_code == 200
    reservoirs = res.json()
    assert isinstance(reservoirs, list)
    assert len(reservoirs) > 0
    first = reservoirs[0]
    assert "reservoir_name" in first
    assert "observation_date" in first
    assert "freshness_status" in first
    assert "source_url" in first


def test_arrival_estimate_endpoint():
    res = client.get("/api/v1/intelligence/arrival-estimates")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "confidence_percent" in data
    assert "explanation" in data
    assert data["data_classification"] == "MODEL_GENERATED_PREDICTION"


def test_weather_context_endpoint():
    res = client.get("/api/v1/intelligence/weather-context")
    assert res.status_code == 200
    data = res.json()
    assert data["data_classification"] == "SUPPORTING_CONTEXT_ONLY"


def test_irrigation_schedules_endpoint():
    res = client.get("/api/v1/irrigation/schedules")
    assert res.status_code == 200
    schedules = res.json()
    assert isinstance(schedules, list)


def test_alerts_endpoint():
    res = client.get("/api/v1/alerts")
    assert res.status_code == 200
    alerts = res.json()
    assert isinstance(alerts, list)


def test_sync_status_endpoint():
    res = client.get("/api/v1/sync/status")
    assert res.status_code == 200
    data = res.json()
    assert "pending_sensor_readings" in data
