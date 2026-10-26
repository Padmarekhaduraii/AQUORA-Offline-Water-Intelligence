import pytest
from datetime import datetime, timezone
from tests.conftest import TestingSessionLocal
from backend.models import SensorReading, SyncAuditLog
from backend.services.sync_service import sync_service

def test_sync_status_pending_count():
    db = TestingSessionLocal()
    status = sync_service.get_sync_status(db)
    assert status.pending_sensor_readings >= 0
    assert status.sync_engine_status in ["IDLE", "OFFLINE_STANDBY"]
    db.close()


@pytest.mark.anyio
async def test_sync_preserves_records_when_cloud_unreachable():
    """
    CRITICAL OFFLINE REQUIREMENT:
    When cloud sync endpoint is unreachable, local SQLite records must NOT be deleted.
    They must remain in pending sync status with full audit log tracking.
    """
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    reading = SensorReading(
        node_id="NODE-SYNC-TEST",
        timestamp_recorded=now,
        timestamp_received=now,
        water_level_cm=45.0,
        reading_hash="sync_offline_preserve_hash_1",
        sync_status="pending",
        is_simulated=True
    )
    db.add(reading)
    db.commit()

    # Attempt synchronization to non-existent endpoint
    count, msg = await sync_service.synchronize_pending(db)

    # Must fail gracefully without exception
    assert count == 0
    assert "Offline standby" in msg or "Cloud server unreachable" in msg

    # Verify reading still exists and remains 'pending'
    recheck = db.query(SensorReading).filter(SensorReading.reading_hash == "sync_offline_preserve_hash_1").first()
    assert recheck is not None
    assert recheck.sync_status == "pending"

    # Verify audit log was recorded
    audit = db.query(SyncAuditLog).filter(SyncAuditLog.status == "FAILED").first()
    assert audit is not None
    db.close()
