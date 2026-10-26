from datetime import datetime, timezone, timedelta
from typing import List
from sqlalchemy.orm import Session

from backend.models import SensorNode, SystemAlert, SensorReading
from backend.schemas import AlertResponse
from backend.config import settings

class AlertService:
    """
    Automated Local Alert Engine for Sensor Disconnections, Stale Data, and Canal Surges.
    Runs 100% offline.
    """

    def scan_and_update_alerts(self, db: Session) -> List[AlertResponse]:
        now = datetime.now(timezone.utc)
        timeout_delta = timedelta(seconds=settings.stale_sensor_timeout_seconds)

        # 1. Check all sensor nodes for disconnection / stale data
        nodes = db.query(SensorNode).filter(SensorNode.is_active == True).all()

        for node in nodes:
            is_disconnected = False
            time_diff_str = "Never connected"

            if not node.last_seen_at:
                is_disconnected = True
            else:
                if node.last_seen_at.tzinfo is None:
                    last_seen_utc = node.last_seen_at.replace(tzinfo=timezone.utc)
                else:
                    last_seen_utc = node.last_seen_at
                elapsed = now - last_seen_utc
                if elapsed > timeout_delta:
                    is_disconnected = True
                    time_diff_str = f"{int(elapsed.total_seconds() // 60)} minutes ago"

            if is_disconnected:
                # Check if unacknowledged alert already exists for this node
                existing = db.query(SystemAlert).filter(
                    SystemAlert.source_id == node.id,
                    SystemAlert.alert_type == "SENSOR_DISCONNECTED",
                    SystemAlert.is_acknowledged == False
                ).first()

                if not existing:
                    alert = SystemAlert(
                        alert_type="SENSOR_DISCONNECTED",
                        severity="WARNING",
                        title=f"Sensor Disconnected: {node.name}",
                        message=f"Node '{node.name}' ({node.id}) on canal '{node.canal_name}' is offline. Last seen: {time_diff_str}. Downstream water arrival estimates for this reach are currently paused.",
                        source_id=node.id,
                        is_acknowledged=False,
                        created_at=now
                    )
                    db.add(alert)
                    db.commit()

        # 2. Check for battery warnings (< 3.5V for LiPo/Li-ion)
        recent_readings = (
            db.query(SensorReading)
            .filter(SensorReading.timestamp_received >= now - timedelta(hours=1))
            .all()
        )
        for r in recent_readings:
            if r.battery_voltage and r.battery_voltage < 3.45:
                existing_batt = db.query(SystemAlert).filter(
                    SystemAlert.source_id == r.node_id,
                    SystemAlert.alert_type == "BATTERY_CRITICAL",
                    SystemAlert.is_acknowledged == False
                ).first()
                if not existing_batt:
                    alert = SystemAlert(
                        alert_type="BATTERY_CRITICAL",
                        severity="CRITICAL",
                        title=f"Critical Battery Warning: Node {r.node_id}",
                        message=f"ESP32 node battery voltage dropped to {r.battery_voltage:.2f}V. Node requires solar charge or battery replacement.",
                        source_id=r.node_id,
                        is_acknowledged=False,
                        created_at=now
                    )
                    db.add(alert)
                    db.commit()

        # Return all active unacknowledged alerts
        active_alerts = (
            db.query(SystemAlert)
            .order_by(SystemAlert.created_at.desc())
            .limit(50)
            .all()
        )

        return [
            AlertResponse(
                id=a.id,
                alert_type=a.alert_type,
                severity=a.severity,
                title=a.title,
                message=a.message,
                source_id=a.source_id,
                is_acknowledged=a.is_acknowledged,
                created_at=a.created_at
            )
            for a in active_alerts
        ]

alert_service = AlertService()
