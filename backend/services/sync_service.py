import hashlib
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
import httpx

from backend.models import SensorReading, IrrigationSchedule, SyncAuditLog
from backend.schemas import SyncStatusResponse
from backend.config import settings

logger = logging.getLogger("aquora.services.sync")

class SyncService:
    """
    Offline-to-Cloud Synchronization Service.
    Enforces idempotent synchronization and strict deduplication.
    """

    @staticmethod
    def generate_reading_hash(node_id: str, timestamp_iso: str, water_level_cm: float) -> str:
        """
        Generates deterministic SHA-256 hash for deduplicating sensor readings.
        """
        payload = f"{node_id}|{timestamp_iso}|{water_level_cm:.2f}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get_sync_status(self, db: Session) -> SyncStatusResponse:
        pending_readings = (
            db.query(SensorReading)
            .filter(SensorReading.sync_status == "pending")
            .count()
        )
        pending_schedules = (
            db.query(IrrigationSchedule)
            .filter(IrrigationSchedule.status == "PLANNED")
            .count()
        )

        last_log = (
            db.query(SyncAuditLog)
            .order_by(SyncAuditLog.created_at.desc())
            .first()
        )

        return SyncStatusResponse(
            pending_sensor_readings=pending_readings,
            pending_irrigation_schedules=pending_schedules,
            last_sync_attempt=last_log.created_at if last_log else None,
            sync_engine_status="IDLE" if pending_readings == 0 else "OFFLINE_STANDBY",
            cloud_reachability=False # Evaluated dynamically on trigger
        )

    async def synchronize_pending(self, db: Session) -> Tuple[int, str]:
        """
        Synchronizes all pending local records with the upstream cloud server if connectivity is available.
        Maintains full audit trail and prevents duplicate uploads.
        """
        pending_readings = (
            db.query(SensorReading)
            .filter(SensorReading.sync_status == "pending")
            .limit(100)
            .all()
        )

        if not pending_readings:
            return 0, "No pending records to synchronize."

        batch_id = str(uuid.uuid4())
        payload = {
            "batch_id": batch_id,
            "device_source": settings.location_name,
            "readings": [
                {
                    "reading_id": r.id,
                    "node_id": r.node_id,
                    "timestamp_recorded": r.timestamp_recorded.isoformat(),
                    "water_level_cm": r.water_level_cm,
                    "water_flow_rate_lps": r.water_flow_rate_lps,
                    "reading_hash": r.reading_hash,
                    "is_simulated": r.is_simulated
                }
                for r in pending_readings
            ]
        }

        # Attempt transmission to upstream URL
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                headers = {"Authorization": f"Bearer {settings.sync_api_key}"}
                resp = await client.post(settings.sync_upstream_url, json=payload, headers=headers)
                
                if resp.status_code in [200, 201]:
                    # Update sync status to 'synced'
                    for r in pending_readings:
                        r.sync_status = "synced"
                        r.sync_tx_id = batch_id
                        
                        log = SyncAuditLog(
                            batch_id=batch_id,
                            record_type="sensor_reading",
                            record_id=r.id,
                            action="PUSHED",
                            status="SUCCESS",
                            created_at=datetime.now(timezone.utc)
                        )
                        db.add(log)
                    
                    db.commit()
                    return len(pending_readings), f"Successfully synced {len(pending_readings)} records to cloud."
                else:
                    raise Exception(f"Upstream returned HTTP {resp.status_code}")

        except Exception as e:
            logger.info(f"Cloud upstream unreachable ({e}). Records retained safely in local SQLite storage.")
            # Record failed sync attempt in audit log
            log = SyncAuditLog(
                batch_id=batch_id,
                record_type="sensor_reading",
                record_id="BATCH",
                action="PUSHED",
                status="FAILED",
                error_message=str(e),
                created_at=datetime.now(timezone.utc)
            )
            db.add(log)
            db.commit()
            return 0, f"Offline standby: Cloud server unreachable ({str(e)}). Telemetry preserved locally."

sync_service = SyncService()
