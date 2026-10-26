import os
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.config import settings
from backend.database import get_db
from backend.models import SensorNode, SensorReading, SystemAlert
from backend.services.arrival_engine import arrival_engine
from backend.services.alert_service import AlertService

client = TestClient(app)

def test_simulator_modal_and_button_naming():
    """Requirement 1: Rename 'Physical Telemetry Injector & Simulator' to 'Sensor Test Simulator & Telemetry Tools'."""
    html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html"))
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    assert "Sensor Test Simulator & Telemetry Tools" in html
    assert "Physical Telemetry Injector & Simulator" not in html
    assert "Inject Simulated Test Reading [SIMULATED]" in html


def test_manually_injected_or_generated_reading_labeled_simulated(db_session):
    """Requirements 2 & 3: Label every manually injected reading as SIMULATED in UI and API response."""
    test_node_id = f"TEST-NODE-{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)

    # 1. Ingest simulated reading
    sim_payload = {
        "node_id": test_node_id,
        "timestamp_recorded": now.isoformat(),
        "water_level_cm": 65.5,
        "water_flow_rate_lps": 420.0,
        "battery_voltage": 4.10,
        "rssi_dbm": -72.0,
        "is_simulated": True
    }
    res = client.post(
        "/api/v1/sensors/ingest",
        json=sim_payload,
        headers={"X-API-KEY": settings.gateway_api_key}
    )
    assert res.status_code == 201
    data = res.json()
    assert data["is_simulated"] is True
    assert data["measurement_provenance"] == "SIMULATED"
    assert data["timestamp_recorded"] is not None
    assert data["timestamp_received"] is not None

    # 2. Verify node status reflects simulation provenance
    res_nodes = client.get("/api/v1/sensors/nodes")
    assert res_nodes.status_code == 200
    matched = [n for n in res_nodes.json() if n["id"] == test_node_id]
    assert len(matched) == 1
    node_info = matched[0]
    assert node_info["current_water_level_is_simulated"] is True
    assert node_info["current_water_level_provenance"] == "SIMULATED"
    assert node_info["last_observation_timestamp"] is not None
    assert node_info["last_gateway_receipt_timestamp"] is not None

    # 3. Ingest real physical reading (is_simulated = False)
    phys_payload = {
        "node_id": test_node_id,
        "timestamp_recorded": (now + timedelta(minutes=5)).isoformat(),
        "water_level_cm": 67.0,
        "water_flow_rate_lps": 430.0,
        "battery_voltage": 4.08,
        "rssi_dbm": -74.0,
        "is_simulated": False
    }
    res_phys = client.post(
        "/api/v1/sensors/ingest",
        json=phys_payload,
        headers={"X-API-KEY": settings.gateway_api_key}
    )
    assert res_phys.status_code == 201
    phys_data = res_phys.json()
    assert phys_data["is_simulated"] is False
    assert phys_data["measurement_provenance"] == "PHYSICAL"

    # Verify node status updated to physical
    res_nodes2 = client.get("/api/v1/sensors/nodes")
    node_info2 = [n for n in res_nodes2.json() if n["id"] == test_node_id][0]
    assert node_info2["current_water_level_is_simulated"] is False
    assert node_info2["current_water_level_provenance"] == "PHYSICAL"


def test_confidence_score_removed_when_data_sufficiency_unmet(db_session):
    """Requirements 4 & 5: Explain confidence score, remove unsupported percentages, and enforce data sufficiency."""
    fresh_node_up = f"NODE-UP-{uuid.uuid4().hex[:6]}"
    fresh_node_down = f"NODE-DOWN-{uuid.uuid4().hex[:6]}"

    up_node = SensorNode(
        id=fresh_node_up,
        name="Upstream Test Sluice",
        canal_name="Cauvery Test Reach",
        reach_segment="Intake",
        distance_from_head_km=0.0,
        last_seen_at=datetime.now(timezone.utc)
    )
    down_node = SensorNode(
        id=fresh_node_down,
        name="Downstream Test Offtake",
        canal_name="Cauvery Test Reach",
        reach_segment="Tail",
        distance_from_head_km=10.0,
        last_seen_at=datetime.now(timezone.utc)
    )
    db_session.add(up_node)
    db_session.add(down_node)
    db_session.commit()

    # Case A: Only 1 reading exists (less than 3 required)
    now = datetime.now(timezone.utc)
    db_session.add(SensorReading(
        node_id=fresh_node_up,
        timestamp_recorded=now,
        timestamp_received=now,
        water_level_cm=75.0,
        reading_hash=f"hash_{uuid.uuid4().hex}",
        is_simulated=False,
        sync_status="pending"
    ))
    db_session.commit()

    result = arrival_engine.estimate_arrival(
        db=db_session,
        target_node_id=fresh_node_down,
        reference_upstream_node_id=fresh_node_up
    )

    assert result.status == "INSUFFICIENT_DATA"
    assert result.data_sufficiency_met is False
    assert result.confidence_percent is None  # Unsupported percentage removed!
    assert result.estimated_arrival_time is None
    assert len(result.unmet_sufficiency_requirements) > 0
    assert "minimum 3 required" in result.unmet_sufficiency_requirements[0]
    assert "Confidence score not applicable" in result.confidence_explanation


def test_arrival_prediction_with_verifiable_confidence_breakdown(db_session):
    """Requirements 4 & 5: When sufficiency is met, confidence breakdown is computed and explained."""
    up_id = f"NODE-UP-{uuid.uuid4().hex[:6]}"
    down_id = f"NODE-DOWN-{uuid.uuid4().hex[:6]}"

    now = datetime.now(timezone.utc)
    up_node = SensorNode(
        id=up_id,
        name="Upstream Intake Verified",
        canal_name="Cauvery Main Canal",
        reach_segment="Head Reach",
        distance_from_head_km=0.0,
        last_seen_at=now
    )
    down_node = SensorNode(
        id=down_id,
        name="Downstream Tail Verified",
        canal_name="Cauvery Main Canal",
        reach_segment="Tail Reach",
        distance_from_head_km=8.5,
        last_seen_at=now
    )
    db_session.add(up_node)
    db_session.add(down_node)

    # Add 4 consecutive readings showing a verified surge (>15 cm)
    levels = [10.0, 12.0, 45.0, 85.0]
    for idx, lvl in enumerate(levels):
        r_time = now - timedelta(minutes=(4 - idx) * 10)
        db_session.add(SensorReading(
            node_id=up_id,
            timestamp_recorded=r_time,
            timestamp_received=r_time,
            water_level_cm=lvl,
            reading_hash=f"hash_{uuid.uuid4().hex}",
            is_simulated=False,
            sync_status="pending"
        ))
    db_session.commit()

    result = arrival_engine.estimate_arrival(
        db=db_session,
        target_node_id=down_id,
        reference_upstream_node_id=up_id
    )

    # Must produce prediction
    assert result.status == "SUFFICIENT_DATA"
    assert result.data_sufficiency_met is True
    assert result.estimated_arrival_time is not None
    assert result.travel_time_hours is not None
    assert result.upstream_surge_magnitude_cm > 15.0
    assert result.telemetry_source_mode == "PHYSICAL_GROUND_TRUTH"

    # Confidence must be supported and mathematically grounded
    assert result.confidence_percent is not None
    assert 0 <= result.confidence_percent <= 100
    assert result.confidence_score_breakdown is not None
    breakdown = result.confidence_score_breakdown
    assert "telemetry_freshness" in breakdown
    assert "wave_trend_stability" in breakdown
    assert "hydraulic_calibration" in breakdown
    assert breakdown["telemetry_freshness"]["score"] <= 35.0
    assert breakdown["wave_trend_stability"]["score"] <= 35.0
    assert breakdown["hydraulic_calibration"]["score"] <= 30.0

    # Explanation must clearly describe the points
    assert "Confidence score of" in result.confidence_explanation
    assert "Telemetry Freshness" in result.confidence_explanation
    assert "Wave Trend Stability" in result.confidence_explanation
    assert "Hydraulic Geometry Calibration" in result.confidence_explanation


def test_simulated_readings_flagged_in_arrival_source_mode(db_session):
    """Requirement 3: Never allow simulated readings to be mistaken for real ESP32 sensor measurements."""
    up_id = f"NODE-UP-{uuid.uuid4().hex[:6]}"
    down_id = f"NODE-DOWN-{uuid.uuid4().hex[:6]}"

    now = datetime.now(timezone.utc)
    up_node = SensorNode(
        id=up_id,
        name="Upstream Simulation Reach",
        canal_name="Cauvery Main Canal",
        reach_segment="Head Reach",
        distance_from_head_km=0.0,
        last_seen_at=now
    )
    down_node = SensorNode(
        id=down_id,
        name="Downstream Tail Reach",
        canal_name="Cauvery Main Canal",
        reach_segment="Tail Reach",
        distance_from_head_km=8.5,
        last_seen_at=now
    )
    db_session.add(up_node)
    db_session.add(down_node)

    # Ingest simulated surge
    levels = [10.0, 12.0, 50.0, 90.0]
    for idx, lvl in enumerate(levels):
        r_time = now - timedelta(minutes=(4 - idx) * 10)
        db_session.add(SensorReading(
            node_id=up_id,
            timestamp_recorded=r_time,
            timestamp_received=r_time,
            water_level_cm=lvl,
            reading_hash=f"hash_{uuid.uuid4().hex}",
            is_simulated=True,  # SIMULATED!
            sync_status="pending"
        ))
    db_session.commit()

    result = arrival_engine.estimate_arrival(
        db=db_session,
        target_node_id=down_id,
        reference_upstream_node_id=up_id
    )

    assert result.status == "SUFFICIENT_DATA"
    assert result.telemetry_source_mode == "SIMULATED_TEST_RUN"
    assert "[SIMULATED TEST DATA - NOT PHYSICAL MEASUREMENT]" in result.explanation


def test_sensor_observation_and_gateway_receipt_timestamps(db_session):
    """Requirement 6: Display sensor observation timestamps, gateway receipt timestamps, source IDs, and freshness."""
    node_id = f"NODE-TS-{uuid.uuid4().hex[:6]}"
    obs_time = datetime(2026, 10, 26, 10, 15, 30, tzinfo=timezone.utc)
    
    # Ingest
    payload = {
        "node_id": node_id,
        "timestamp_recorded": obs_time.isoformat(),
        "water_level_cm": 52.0,
        "water_flow_rate_lps": 300.0,
        "battery_voltage": 3.99,
        "rssi_dbm": -80.0,
        "is_simulated": False
    }
    res = client.post(
        "/api/v1/sensors/ingest",
        json=payload,
        headers={"X-API-KEY": settings.gateway_api_key}
    )
    assert res.status_code == 201

    # Check node details
    res_nodes = client.get("/api/v1/sensors/nodes")
    node = [n for n in res_nodes.json() if n["id"] == node_id][0]
    assert node["id"] == node_id
    assert node["last_observation_timestamp"] is not None
    assert node["last_gateway_receipt_timestamp"] is not None
    assert node["freshness_status"] in ["FRESH", "RECENT", "STALE", "DISCONNECTED"]

    # Check history
    res_hist = client.get(f"/api/v1/sensors/{node_id}/history")
    assert res_hist.status_code == 200
    readings = res_hist.json()
    assert len(readings) >= 1
    r = readings[0]
    assert r["node_id"] == node_id
    assert r["timestamp_recorded"] is not None
    assert r["timestamp_received"] is not None
    assert r["measurement_provenance"] == "PHYSICAL"


def test_official_reservoir_classification_and_offline_disconnection_alerts(db_session):
    """Requirements 7 & 8: Distinguish official observations from model predictions, and handle disconnection alerts."""
    # Official vs model predictions
    res_res = client.get("/api/v1/official/reservoirs")
    assert res_res.status_code == 200
    for r in res_res.json():
        assert r["data_classification"] == "OFFICIAL_RESERVOIR_OBSERVATION"
        assert r["freshness_status"] is not None

    res_arr = client.get("/api/v1/intelligence/arrival-estimates")
    assert res_arr.status_code == 200
    assert res_arr.json()["data_classification"] == "MODEL_GENERATED_PREDICTION"

    # Offline disconnection warning
    stale_node_id = f"STALE-NODE-{uuid.uuid4().hex[:6]}"
    stale_node = SensorNode(
        id=stale_node_id,
        name="Stale Canal Monitor",
        canal_name="Cauvery Distributary",
        reach_segment="Mid Reach",
        distance_from_head_km=5.0,
        last_seen_at=datetime.now(timezone.utc) - timedelta(hours=3),  # 3 hours ago > 45m threshold
        is_active=True
    )
    db_session.add(stale_node)
    db_session.commit()

    alert_service = AlertService()
    alerts = alert_service.scan_and_update_alerts(db_session)
    stale_alerts = [a for a in alerts if a.source_id == stale_node_id and a.alert_type == "SENSOR_DISCONNECTED"]
    assert len(stale_alerts) == 1
    assert "offline" in stale_alerts[0].message.lower()
