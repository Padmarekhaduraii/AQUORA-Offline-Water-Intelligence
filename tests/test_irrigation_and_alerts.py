import pytest
from datetime import datetime, timezone, timedelta
from tests.conftest import TestingSessionLocal
from backend.models import SensorNode, SensorReading, SystemAlert
from backend.services.irrigation_engine import irrigation_engine
from backend.services.alert_service import alert_service

def test_offline_irrigation_scheduling():
    db = TestingSessionLocal()
    schedules = irrigation_engine.generate_schedules_for_zones(db)
    db.close()

    assert len(schedules) >= 3
    for s in schedules:
        assert s.offline_generated is True
        assert s.recommended_duration_minutes > 0
        assert s.water_volume_liters > 0
        assert s.trigger_reason is not None


def test_alert_service_detects_stale_sensor():
    db = TestingSessionLocal()
    # Add a disconnected sensor node
    stale_time = datetime.now(timezone.utc) - timedelta(hours=3)
    node = SensorNode(
        id="NODE-ALERT-DISCONNECT-1",
        name="Canal Tail Node",
        canal_name="Cauvery Distributary",
        last_seen_at=stale_time,
        is_active=True
    )
    db.add(node)
    db.commit()

    alerts = alert_service.scan_and_update_alerts(db)
    db.close()

    disconnect_alert = next((a for a in alerts if a.source_id == "NODE-ALERT-DISCONNECT-1"), None)
    assert disconnect_alert is not None
    assert disconnect_alert.alert_type == "SENSOR_DISCONNECTED"
    assert disconnect_alert.severity == "WARNING"
    assert "is offline" in disconnect_alert.message
