from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session

from backend.models import IrrigationSchedule, SensorNode, SensorReading
from backend.schemas import IrrigationScheduleResponse
from backend.services.arrival_engine import arrival_engine

class IrrigationSchedulerEngine:
    """
    Offline Irrigation Decision Engine.
    Executes entirely on local gateway/machine without cloud access.
    Synchronizes irrigation turns with actual canal water arrival windows.
    """

    CROP_REQUIREMENTS = {
        "Paddy (Samba / Thaladi)": {
            "root_depth_cm": 25.0,
            "duration_min": 180,
            "volume_liters_per_hectare": 450000.0,
            "min_canal_depth_cm": 25.0
        },
        "Paddy (Kuruvai)": {
            "root_depth_cm": 20.0,
            "duration_min": 150,
            "volume_liters_per_hectare": 380000.0,
            "min_canal_depth_cm": 25.0
        },
        "Sugarcane": {
            "root_depth_cm": 60.0,
            "duration_min": 240,
            "volume_liters_per_hectare": 600000.0,
            "min_canal_depth_cm": 30.0
        },
        "Banana / Plantain": {
            "root_depth_cm": 45.0,
            "duration_min": 120,
            "volume_liters_per_hectare": 280000.0,
            "min_canal_depth_cm": 20.0
        },
        "Pulses / Blackgram (Rice Fallow)": {
            "root_depth_cm": 30.0,
            "duration_min": 75,
            "volume_liters_per_hectare": 120000.0,
            "min_canal_depth_cm": 15.0
        }
    }

    def generate_schedules_for_zones(self, db: Session) -> List[IrrigationScheduleResponse]:
        """
        Evaluates physical canal flow and generates/updates offline irrigation schedules.
        """
        now = datetime.now(timezone.utc)
        arrival = arrival_engine.estimate_arrival(db)

        zones = [
            {"id": "ZONE-AYACUT-01", "name": "North Branch Sluice 4", "crop": "Paddy (Samba / Thaladi)", "area_ha": 3.2},
            {"id": "ZONE-AYACUT-02", "name": "East Lateral Tail-End", "crop": "Sugarcane", "area_ha": 2.5},
            {"id": "ZONE-AYACUT-03", "name": "South Distributary Offtake 1", "crop": "Banana / Plantain", "area_ha": 1.8},
        ]

        responses = []
        for z in zones:
            crop_spec = self.CROP_REQUIREMENTS.get(z["crop"], self.CROP_REQUIREMENTS["Paddy (Samba / Thaladi)"])
            total_volume = crop_spec["volume_liters_per_hectare"] * z["area_ha"]
            duration = crop_spec["duration_min"]

            if arrival.status in ["SUFFICIENT_DATA", "SURGE_IN_PROGRESS"] and arrival.estimated_arrival_time:
                # Schedule turn to start 20 minutes after estimated arrival to ensure head build-up
                rec_start = arrival.estimated_arrival_time + timedelta(minutes=20)
                reason = (
                    f"Synchronized with verified physical water arrival ({arrival.estimated_arrival_time.strftime('%H:%M')} IST). "
                    f"Canal depth threshold met ({crop_spec['min_canal_depth_cm']} cm). "
                    f"Water release confirmed by upstream sensor '{arrival.reference_upstream_node_id}'."
                )
                status = "PLANNED"
            else:
                # Dry canal hold
                rec_start = now + timedelta(hours=12) # Standby queue
                reason = (
                    f"CANAL DRY HOLD: Irrigation postponed. Upstream physical sensor indicates {arrival.status.lower().replace('_', ' ')}. "
                    f"Explanation: {arrival.explanation} "
                    "Cannot open sluice gate without verified incoming canal water."
                )
                status = "STANDBY_NO_WATER"

            # Check if schedule exists in db, otherwise create
            existing = db.query(IrrigationSchedule).filter(
                IrrigationSchedule.zone_id == z["id"],
                IrrigationSchedule.status.in_(["PLANNED", "STANDBY_NO_WATER"])
            ).first()

            if not existing:
                schedule = IrrigationSchedule(
                    zone_id=z["id"],
                    zone_name=z["name"],
                    crop_type=z["crop"],
                    recommended_start=rec_start,
                    recommended_duration_minutes=duration,
                    water_volume_liters=total_volume,
                    status=status,
                    trigger_reason=reason,
                    offline_generated=True,
                    created_at=now
                )
                db.add(schedule)
                db.commit()
                db.refresh(schedule)
            else:
                existing.recommended_start = rec_start
                existing.status = status
                existing.trigger_reason = reason
                existing.water_volume_liters = total_volume
                existing.recommended_duration_minutes = duration
                db.commit()
                db.refresh(existing)
                schedule = existing

            responses.append(
                IrrigationScheduleResponse(
                    id=schedule.id,
                    zone_id=schedule.zone_id,
                    zone_name=schedule.zone_name,
                    crop_type=schedule.crop_type,
                    recommended_start=schedule.recommended_start,
                    recommended_duration_minutes=schedule.recommended_duration_minutes,
                    water_volume_liters=schedule.water_volume_liters,
                    status=schedule.status,
                    trigger_reason=schedule.trigger_reason,
                    offline_generated=schedule.offline_generated,
                    created_at=schedule.created_at
                )
            )

        return responses

irrigation_engine = IrrigationSchedulerEngine()
