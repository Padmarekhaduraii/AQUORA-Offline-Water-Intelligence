import pytest
from datetime import datetime, timezone, timedelta
from tests.conftest import TestingSessionLocal
from backend.models import SensorNode, SensorReading
from backend.services.arrival_engine import arrival_engine

def test_arrival_engine_requires_physical_upstream_node():
    """
    Never infer water arrival from reservoir alone.
    If upstream physical sensor node does not exist, status must be INSUFFICIENT_DATA.
    """
    db = TestingSessionLocal()
    estimate = arrival_engine.estimate_arrival(
        db,
        target_node_id="NON_EXISTENT_DOWNSTREAM",
        reference_upstream_node_id="NON_EXISTENT_UPSTREAM"
    )
    db.close()

    assert estimate.status == "INSUFFICIENT_DATA"
    assert estimate.confidence_percent is None
    assert estimate.estimated_arrival_time is None
    assert "not registered in the local database" in estimate.explanation


def test_arrival_engine_disconnected_upstream_sensor():
    """
    If upstream sensor has not transmitted recent telemetry, status must be INSUFFICIENT_DATA.
    """
    db = TestingSessionLocal()
    # Register upstream node with old last_seen_at (e.g. 2 hours ago)
    old_time = datetime.now(timezone.utc) - timedelta(hours=2)
    node_up = SensorNode(
        id="NODE-TEST-DISCONNECTED",
        name="Test Old Node",
        canal_name="Cauvery Distributary",
        reach_segment="Head Regulator",
        distance_from_head_km=0.0,
        last_seen_at=old_time
    )
    node_down = SensorNode(
        id="NODE-TEST-DOWN-1",
        name="Test Downstream Sluice",
        canal_name="Cauvery Distributary",
        reach_segment="Tail Offtake",
        distance_from_head_km=10.0,
        last_seen_at=datetime.now(timezone.utc)
    )
    db.add_all([node_up, node_down])
    db.commit()

    estimate = arrival_engine.estimate_arrival(
        db,
        target_node_id="NODE-TEST-DOWN-1",
        reference_upstream_node_id="NODE-TEST-DISCONNECTED"
    )
    db.close()

    assert estimate.status == "INSUFFICIENT_DATA"
    assert estimate.confidence_percent is None
    assert "disconnected or stale" in estimate.explanation
    assert "Reservoir release data alone cannot be used" in estimate.explanation


def test_arrival_engine_insufficient_history():
    """
    With only 1 or 2 readings, wave front cannot be verified. Must return INSUFFICIENT_DATA.
    """
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)

    node_up = SensorNode(
        id="NODE-TEST-INSUFF",
        name="Test Intake",
        canal_name="Cauvery Distributary",
        distance_from_head_km=0.0,
        last_seen_at=now
    )
    node_down = SensorNode(
        id="NODE-TEST-DOWN-2",
        name="Test Tail",
        canal_name="Cauvery Distributary",
        distance_from_head_km=8.0,
        last_seen_at=now
    )
    db.add_all([node_up, node_down])

    # Add only 1 reading
    r = SensorReading(
        node_id="NODE-TEST-INSUFF",
        timestamp_recorded=now,
        timestamp_received=now,
        water_level_cm=75.0,
        reading_hash="unique_hash_insuff_1",
        is_simulated=True
    )
    db.add(r)
    db.commit()

    estimate = arrival_engine.estimate_arrival(
        db,
        target_node_id="NODE-TEST-DOWN-2",
        reference_upstream_node_id="NODE-TEST-INSUFF"
    )
    db.close()

    assert estimate.status == "INSUFFICIENT_DATA"
    assert "Insufficient physical history" in estimate.explanation


def test_arrival_engine_dry_canal():
    """
    When water level is low (< 12 cm), status is NO_FLOW_DETECTED.
    """
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)

    node_up = SensorNode(
        id="NODE-TEST-DRY",
        name="Test Dry Intake",
        canal_name="Cauvery Distributary",
        distance_from_head_km=0.0,
        last_seen_at=now
    )
    node_down = SensorNode(
        id="NODE-TEST-DOWN-3",
        name="Test Tail Sluice",
        canal_name="Cauvery Distributary",
        distance_from_head_km=8.0,
        last_seen_at=now
    )
    db.add_all([node_up, node_down])

    # 3 dry readings
    for i in range(3):
        r = SensorReading(
            node_id="NODE-TEST-DRY",
            timestamp_recorded=now - timedelta(minutes=15 * (3 - i)),
            timestamp_received=now,
            water_level_cm=4.5,
            reading_hash=f"dry_hash_{i}",
            is_simulated=True
        )
        db.add(r)
    db.commit()

    estimate = arrival_engine.estimate_arrival(
        db,
        target_node_id="NODE-TEST-DOWN-3",
        reference_upstream_node_id="NODE-TEST-DRY"
    )
    db.close()

    assert estimate.status == "NO_FLOW_DETECTED"
    assert estimate.estimated_arrival_time is None
    assert "Canal upstream is dry" in estimate.explanation


def test_arrival_engine_surge_detection_and_uncertainty():
    """
    When upstream detects a verified surge (+40 cm), arrival estimate is computed
    with explicit uncertainty range and confidence > 70%.
    """
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)

    node_up = SensorNode(
        id="NODE-TEST-SURGE",
        name="Grand Anicut Intake",
        canal_name="Cauvery Main Canal",
        distance_from_head_km=0.0,
        last_seen_at=now
    )
    node_down = SensorNode(
        id="NODE-TEST-DOWN-SURGE",
        name="Tail Sluice 4",
        canal_name="Cauvery Main Canal",
        distance_from_head_km=12.5,
        last_seen_at=now
    )
    db.add_all([node_up, node_down])

    # Sequence of readings showing surge from 8 cm to 85 cm
    readings = [
        (now - timedelta(hours=2), 8.0),
        (now - timedelta(hours=1, minutes=30), 8.5),
        (now - timedelta(minutes=45), 45.0), # Inflection point
        (now - timedelta(minutes=15), 78.0),
        (now, 85.0)
    ]
    for idx, (t, lvl) in enumerate(readings):
        r = SensorReading(
            node_id="NODE-TEST-SURGE",
            timestamp_recorded=t,
            timestamp_received=now,
            water_level_cm=lvl,
            reading_hash=f"surge_hash_{idx}",
            is_simulated=True
        )
        db.add(r)
    db.commit()

    estimate = arrival_engine.estimate_arrival(
        db,
        target_node_id="NODE-TEST-DOWN-SURGE",
        reference_upstream_node_id="NODE-TEST-SURGE"
    )
    db.close()

    assert estimate.status == "SUFFICIENT_DATA"
    assert estimate.estimated_arrival_time is not None
    assert estimate.travel_time_hours > 0.0
    # Must report explicit uncertainty range (+/- hours)
    assert estimate.uncertainty_range_hours is not None
    assert estimate.uncertainty_range_hours > 0.0
    assert estimate.confidence_percent >= 70.0
    assert "Manning's open-channel hydraulics" in estimate.explanation
