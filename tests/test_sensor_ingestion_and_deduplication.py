import pytest
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from backend.main import app
from backend.config import settings
from tests.conftest import TestingSessionLocal
from backend.models import SensorReading

client = TestClient(app)

def test_deduplication_of_sensor_readings():
    """
    Submitting the exact same sensor packet twice (e.g. gateway radio retransmission)
    must NOT duplicate records in the database.
    """
    db = TestingSessionLocal()
    initial_count = db.query(SensorReading).count()
    db.close()

    unique_ts = f"2026-10-26T{str(uuid.uuid4())[:8]}Z"
    payload = {
        "node_id": "NODE-UPSTREAM-01",
        "timestamp_recorded": "2026-10-26T18:15:20Z",
        "water_level_cm": 74.5,
        "battery_voltage": 4.02,
        "rssi_dbm": -71.0,
        "snr_db": 8.8,
        "is_simulated": True
    }

    # 1. First submission
    res1 = client.post(
        "/api/v1/sensors/ingest",
        json=payload,
        headers={"X-API-Key": settings.gateway_api_key}
    )
    assert res1.status_code == 201
    reading_id_1 = res1.json()["id"]

    # 2. Second duplicate submission
    res2 = client.post(
        "/api/v1/sensors/ingest",
        json=payload,
        headers={"X-API-Key": settings.gateway_api_key}
    )
    assert res2.status_code in [200, 201]
    reading_id_2 = res2.json()["id"]

    # Must return the identical reading ID without creating a 2nd record
    assert reading_id_1 == reading_id_2

    db = TestingSessionLocal()
    final_count = db.query(SensorReading).count()
    db.close()

    assert final_count == initial_count + 1


def test_input_validation_negative_water_level():
    payload = {
        "node_id": "NODE-UPSTREAM-01",
        "timestamp_recorded": "2026-10-26T14:35:00Z",
        "water_level_cm": -15.0 # Invalid negative level
    }
    res = client.post(
        "/api/v1/sensors/ingest",
        json=payload,
        headers={"X-API-Key": settings.gateway_api_key}
    )
    assert res.status_code == 422 # Pydantic validation error


def test_batch_ingestion():
    payload = {
        "readings": [
            {
                "node_id": "NODE-UPSTREAM-01",
                "timestamp_recorded": "2026-10-26T19:00:00Z",
                "water_level_cm": 60.0,
                "is_simulated": True
            },
            {
                "node_id": "NODE-MIDSTREAM-01",
                "timestamp_recorded": "2026-10-26T19:00:00Z",
                "water_level_cm": 35.0,
                "is_simulated": True
            }
        ]
    }
    res = client.post(
        "/api/v1/sensors/ingest-batch",
        json=payload,
        headers={"X-API-Key": settings.gateway_api_key}
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    assert data[0]["node_id"] == "NODE-UPSTREAM-01"
    assert data[1]["node_id"] == "NODE-MIDSTREAM-01"
