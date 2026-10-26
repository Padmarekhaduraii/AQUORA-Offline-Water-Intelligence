from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Security, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database import get_db
from backend.models import SensorNode, SensorReading
from backend.schemas import (
    SensorNodeCreate, SensorNodeResponse,
    SensorReadingIngest, SensorReadingBatchIngest, SensorReadingResponse
)
from backend.services.sync_service import sync_service
from backend.websocket_manager import ws_manager
from backend.config import settings

router = APIRouter(prefix="/api/v1/sensors", tags=["Sensors & Telemetry"])

def verify_gateway_api_key(x_api_key: str = Header(..., description="LoRa Gateway Authentication Key")):
    if x_api_key != settings.gateway_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Gateway API Key. Ingestion denied."
        )
    return x_api_key


@router.post("/ingest", response_model=SensorReadingResponse, status_code=status.HTTP_201_CREATED)
def ingest_sensor_reading(
    reading_in: SensorReadingIngest,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_gateway_api_key)
):
    """
    Ingest a single physical ESP32 LoRa sensor observation or simulated test reading.
    Requires gateway authentication.
    Applies strict SHA-256 deduplication to prevent duplicate records during gateway retries.
    """
    # 1. Ensure node exists or register automatically
    node = db.query(SensorNode).filter(SensorNode.id == reading_in.node_id).first()
    if not node:
        node = SensorNode(
            id=reading_in.node_id,
            name=f"Field Node {reading_in.node_id}",
            canal_name="Cauvery Main Canal",
            reach_segment="Local Ayacut Reach",
            distance_from_head_km=0.0,
            last_seen_at=datetime.now(timezone.utc)
        )
        db.add(node)
        db.commit()
        db.refresh(node)

    # 2. Check for duplicate via reading_hash
    ts_iso = reading_in.timestamp_recorded.isoformat()
    r_hash = sync_service.generate_reading_hash(reading_in.node_id, ts_iso, reading_in.water_level_cm)

    existing = db.query(SensorReading).filter(SensorReading.reading_hash == r_hash).first()
    if existing:
        return SensorReadingResponse(
            id=existing.id,
            node_id=existing.node_id,
            timestamp_recorded=existing.timestamp_recorded,
            timestamp_received=existing.timestamp_received,
            water_level_cm=existing.water_level_cm,
            water_flow_rate_lps=existing.water_flow_rate_lps,
            battery_voltage=existing.battery_voltage,
            rssi_dbm=existing.rssi_dbm,
            snr_db=existing.snr_db,
            reading_hash=existing.reading_hash,
            is_simulated=existing.is_simulated,
            measurement_provenance="SIMULATED" if existing.is_simulated else "PHYSICAL",
            freshness_status="FRESH",
            sync_status=existing.sync_status,
            created_at=existing.created_at
        )

    # 3. Create new reading
    now_utc = datetime.now(timezone.utc)
    reading = SensorReading(
        node_id=reading_in.node_id,
        timestamp_recorded=reading_in.timestamp_recorded,
        timestamp_received=now_utc,
        water_level_cm=reading_in.water_level_cm,
        water_flow_rate_lps=reading_in.water_flow_rate_lps,
        battery_voltage=reading_in.battery_voltage,
        rssi_dbm=reading_in.rssi_dbm,
        snr_db=reading_in.snr_db,
        reading_hash=r_hash,
        is_simulated=reading_in.is_simulated,
        sync_status="pending",
        created_at=now_utc
    )
    db.add(reading)

    # 4. Update node's last seen timestamp
    node.last_seen_at = now_utc
    db.commit()
    db.refresh(reading)

    provenance_tag = "SIMULATED" if reading.is_simulated else "PHYSICAL"

    # 5. Broadcast to connected local WebSocket clients
    ws_manager.broadcast_sync({
        "type": "NEW_READING",
        "reading": {
            "id": reading.id,
            "node_id": reading.node_id,
            "water_level_cm": reading.water_level_cm,
            "timestamp_recorded": reading.timestamp_recorded.isoformat(),
            "timestamp_received": reading.timestamp_received.isoformat(),
            "battery_voltage": reading.battery_voltage,
            "rssi_dbm": reading.rssi_dbm,
            "is_simulated": reading.is_simulated,
            "measurement_provenance": provenance_tag
        }
    })

    return SensorReadingResponse(
        id=reading.id,
        node_id=reading.node_id,
        timestamp_recorded=reading.timestamp_recorded,
        timestamp_received=reading.timestamp_received,
        water_level_cm=reading.water_level_cm,
        water_flow_rate_lps=reading.water_flow_rate_lps,
        battery_voltage=reading.battery_voltage,
        rssi_dbm=reading.rssi_dbm,
        snr_db=reading.snr_db,
        reading_hash=reading.reading_hash,
        is_simulated=reading.is_simulated,
        measurement_provenance=provenance_tag,
        freshness_status="FRESH",
        sync_status=reading.sync_status,
        created_at=reading.created_at
    )


@router.post("/ingest-batch", response_model=List[SensorReadingResponse])
def ingest_batch_readings(
    batch_in: SensorReadingBatchIngest,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_gateway_api_key)
):
    """
    Ingest buffered packets replayed from gateway after local connectivity interruption.
    """
    results = []
    for r_in in batch_in.readings:
        res = ingest_sensor_reading(r_in, db, api_key)
        results.append(res)
    return results


@router.get("/nodes", response_model=List[SensorNodeResponse])
def list_sensor_nodes(db: Session = Depends(get_db)):
    """
    Lists registered sensor nodes along with timestamps, source provenance, freshness, and disconnection flags.
    """
    nodes = db.query(SensorNode).all()
    now = datetime.now(timezone.utc)
    timeout_delta = timedelta(seconds=settings.stale_sensor_timeout_seconds)

    responses = []
    for n in nodes:
        latest = (
            db.query(SensorReading)
            .filter(SensorReading.node_id == n.id)
            .order_by(desc(SensorReading.timestamp_recorded))
            .first()
        )

        is_disconnected = False
        is_stale = False
        freshness = "FRESH"

        if not n.last_seen_at:
            is_disconnected = True
            is_stale = True
            freshness = "DISCONNECTED"
        else:
            if n.last_seen_at.tzinfo is None:
                last_seen = n.last_seen_at.replace(tzinfo=timezone.utc)
            else:
                last_seen = n.last_seen_at
            delta = now - last_seen
            if delta > timeout_delta:
                is_stale = True
                is_disconnected = True
                freshness = "DISCONNECTED"
            elif delta > timedelta(minutes=15):
                is_stale = True
                freshness = "STALE"

        provenance = "NO_DATA"
        is_sim = False
        if latest:
            is_sim = latest.is_simulated
            provenance = "SIMULATED" if latest.is_simulated else "PHYSICAL"

        responses.append(
            SensorNodeResponse(
                id=n.id,
                name=n.name,
                canal_name=n.canal_name,
                reach_segment=n.reach_segment,
                distance_from_head_km=n.distance_from_head_km,
                latitude=n.latitude,
                longitude=n.longitude,
                zero_datum_offset_cm=n.zero_datum_offset_cm,
                max_depth_cm=n.max_depth_cm,
                is_active=n.is_active,
                last_seen_at=n.last_seen_at,
                created_at=n.created_at,
                is_stale=is_stale,
                is_disconnected=is_disconnected,
                current_water_level_cm=latest.water_level_cm if latest else None,
                current_water_level_is_simulated=is_sim,
                current_water_level_provenance=provenance,
                last_observation_timestamp=latest.timestamp_recorded if latest else None,
                last_gateway_receipt_timestamp=latest.timestamp_received if latest else None,
                freshness_status=freshness
            )
        )
    return responses


@router.post("/nodes", response_model=SensorNodeResponse, status_code=status.HTTP_201_CREATED)
def register_node(node_in: SensorNodeCreate, db: Session = Depends(get_db)):
    """
    Register or update physical canal sensor node metadata.
    """
    existing = db.query(SensorNode).filter(SensorNode.id == node_in.id).first()
    if existing:
        for k, v in node_in.model_dump().items():
            setattr(existing, k, v)
        db.commit()
        db.refresh(existing)
        target = existing
    else:
        target = SensorNode(**node_in.model_dump())
        db.add(target)
        db.commit()
        db.refresh(target)

    return SensorNodeResponse(
        id=target.id,
        name=target.name,
        canal_name=target.canal_name,
        reach_segment=target.reach_segment,
        distance_from_head_km=target.distance_from_head_km,
        latitude=target.latitude,
        longitude=target.longitude,
        zero_datum_offset_cm=target.zero_datum_offset_cm,
        max_depth_cm=target.max_depth_cm,
        is_active=target.is_active,
        last_seen_at=target.last_seen_at,
        created_at=target.created_at,
        is_stale=False,
        is_disconnected=False,
        current_water_level_cm=None,
        current_water_level_is_simulated=False,
        current_water_level_provenance="NO_DATA",
        last_observation_timestamp=None,
        last_gateway_receipt_timestamp=None,
        freshness_status="FRESH"
    )


@router.get("/{node_id}/history", response_model=List[SensorReadingResponse])
def get_node_readings_history(
    node_id: str,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Returns time-series telemetry for a specific sensor node with provenance labeling.
    """
    readings = (
        db.query(SensorReading)
        .filter(SensorReading.node_id == node_id)
        .order_by(desc(SensorReading.timestamp_recorded))
        .limit(limit)
        .all()
    )

    now = datetime.now(timezone.utc)
    results = []
    for r in readings:
        rec_time = r.timestamp_recorded
        if rec_time.tzinfo is None:
            rec_time = rec_time.replace(tzinfo=timezone.utc)
        age = now - rec_time
        f_status = "FRESH" if age < timedelta(minutes=15) else ("RECENT" if age < timedelta(hours=2) else "STALE")

        results.append(
            SensorReadingResponse(
                id=r.id,
                node_id=r.node_id,
                timestamp_recorded=r.timestamp_recorded,
                timestamp_received=r.timestamp_received,
                water_level_cm=r.water_level_cm,
                water_flow_rate_lps=r.water_flow_rate_lps,
                battery_voltage=r.battery_voltage,
                rssi_dbm=r.rssi_dbm,
                snr_db=r.snr_db,
                reading_hash=r.reading_hash,
                is_simulated=r.is_simulated,
                measurement_provenance="SIMULATED" if r.is_simulated else "PHYSICAL",
                freshness_status=f_status,
                sync_status=r.sync_status,
                created_at=r.created_at
            )
        )
    return results
