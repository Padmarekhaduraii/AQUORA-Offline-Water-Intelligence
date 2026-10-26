from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

# --- Sensor Node Schemas ---
class SensorNodeBase(BaseModel):
    id: str = Field(..., json_schema_extra={"example": "NODE-UPSTREAM-01"})
    name: str = Field(..., json_schema_extra={"example": "Canal Intake - Upper Sluice"})
    canal_name: str = Field(default="Cauvery Main Canal", json_schema_extra={"example": "Cauvery Main Canal"})
    reach_segment: str = Field(default="Upper Intake Reach", json_schema_extra={"example": "Upper Intake Reach"})
    distance_from_head_km: float = Field(default=0.0, ge=0.0, json_schema_extra={"example": 0.0})
    latitude: Optional[float] = Field(None, json_schema_extra={"example": 10.8350})
    longitude: Optional[float] = Field(None, json_schema_extra={"example": 78.8180})
    zero_datum_offset_cm: float = Field(default=0.0, ge=0.0, json_schema_extra={"example": 150.0})
    max_depth_cm: float = Field(default=300.0, gt=0.0, json_schema_extra={"example": 300.0})
    is_active: bool = True

class SensorNodeCreate(SensorNodeBase):
    pass

class SensorNodeResponse(SensorNodeBase):
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    is_stale: bool = False
    is_disconnected: bool = False
    current_water_level_cm: Optional[float] = None
    current_water_level_is_simulated: bool = False
    current_water_level_provenance: str = "NO_DATA" # "PHYSICAL", "SIMULATED", "NO_DATA"
    last_observation_timestamp: Optional[datetime] = None
    last_gateway_receipt_timestamp: Optional[datetime] = None
    freshness_status: str = "FRESH"

    model_config = ConfigDict(from_attributes=True)


# --- Sensor Reading Schemas ---
class SensorReadingIngest(BaseModel):
    node_id: str = Field(..., json_schema_extra={"example": "NODE-UPSTREAM-01"})
    timestamp_recorded: datetime = Field(..., json_schema_extra={"example": "2026-10-26T10:00:00Z"})
    water_level_cm: float = Field(..., ge=0.0, le=1000.0, json_schema_extra={"example": 84.5})
    water_flow_rate_lps: Optional[float] = Field(None, ge=0.0, json_schema_extra={"example": 450.0})
    battery_voltage: Optional[float] = Field(None, ge=0.0, le=15.0, json_schema_extra={"example": 3.95})
    rssi_dbm: Optional[float] = Field(None, le=0.0, ge=-140.0, json_schema_extra={"example": -72.0})
    snr_db: Optional[float] = Field(None, ge=-30.0, le=30.0, json_schema_extra={"example": 9.5})
    is_simulated: bool = Field(default=False, description="Transparent label indicating if data is simulated or physical")

class SensorReadingBatchIngest(BaseModel):
    readings: List[SensorReadingIngest]

class SensorReadingResponse(BaseModel):
    id: str
    node_id: str
    timestamp_recorded: datetime
    timestamp_received: datetime
    water_level_cm: float
    water_flow_rate_lps: Optional[float] = None
    battery_voltage: Optional[float] = None
    rssi_dbm: Optional[float] = None
    snr_db: Optional[float] = None
    reading_hash: str
    is_simulated: bool
    measurement_provenance: str = "PHYSICAL" # "PHYSICAL" or "SIMULATED"
    freshness_status: str = "FRESH"
    sync_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Official Reservoir Schemas ---
class OfficialReservoirResponse(BaseModel):
    id: Optional[int] = None
    provider_name: str # "tn_agriculture", "chennai_flood_monitor"
    reservoir_name: str
    observation_date: str # e.g. "2026-10-26"
    full_depth_ft: Optional[float] = None
    full_capacity_mcft: Optional[float] = None
    current_level_ft: Optional[float] = None
    current_storage_mcft: Optional[float] = None
    inflow_cusecs: Optional[float] = None
    outflow_cusecs: Optional[float] = None
    last_year_level_ft: Optional[float] = None
    last_year_storage_mcft: Optional[float] = None
    retrieved_at: datetime
    freshness_status: str # FRESH, RECENT, STALE, UNAVAILABLE
    source_url: str
    data_classification: str = "OFFICIAL_RESERVOIR_OBSERVATION"

    model_config = ConfigDict(from_attributes=True)


# --- Water Arrival Estimate Schemas ---
class WaterArrivalEstimateResponse(BaseModel):
    id: Optional[int] = None
    canal_name: str
    target_reach: str
    target_node_id: Optional[str] = None
    reference_upstream_node_id: Optional[str] = None
    status: str # "SUFFICIENT_DATA", "INSUFFICIENT_DATA", "NO_FLOW_DETECTED", "SURGE_IN_PROGRESS"
    estimated_arrival_time: Optional[datetime] = None
    travel_time_hours: Optional[float] = None
    uncertainty_range_hours: Optional[float] = None # +/- bounds
    confidence_percent: Optional[float] = None # Documented score based on hydraulics, or None when data insufficient
    confidence_explanation: Optional[str] = None
    confidence_score_breakdown: Optional[Dict[str, Any]] = None
    data_sufficiency_met: bool = False
    unmet_sufficiency_requirements: List[str] = []
    telemetry_source_mode: str = "NO_TELEMETRY" # "PHYSICAL_GROUND_TRUTH", "SIMULATED_TEST_RUN", "NO_TELEMETRY"
    upstream_surge_magnitude_cm: Optional[float] = None
    explanation: str
    calculated_at: datetime
    data_classification: str = "MODEL_GENERATED_PREDICTION"

    model_config = ConfigDict(from_attributes=True)


# --- Irrigation Schedule Schemas ---
class IrrigationScheduleCreate(BaseModel):
    zone_id: str = Field(..., json_schema_extra={"example": "ZONE-EAST-01"})
    zone_name: str = Field(..., json_schema_extra={"example": "East Canal Ayacut - Sector 4"})
    crop_type: str = Field(..., json_schema_extra={"example": "Paddy (Samba)"})
    recommended_start: datetime
    recommended_duration_minutes: int = Field(..., gt=0, le=1440)
    water_volume_liters: float = Field(..., gt=0)
    trigger_reason: str

class IrrigationScheduleResponse(BaseModel):
    id: int
    zone_id: str
    zone_name: str
    crop_type: str
    recommended_start: datetime
    recommended_duration_minutes: int
    water_volume_liters: float
    status: str
    trigger_reason: str
    offline_generated: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Alert Schemas ---
class AlertResponse(BaseModel):
    id: int
    alert_type: str
    severity: str # INFO, WARNING, CRITICAL
    title: str
    message: str
    source_id: Optional[str] = None
    is_acknowledged: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Weather Context Schema ---
class WeatherContextResponse(BaseModel):
    location: str
    latitude: float
    longitude: float
    temperature_c: Optional[float] = None
    humidity_percent: Optional[float] = None
    precipitation_mm: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    observation_time: Optional[datetime] = None
    retrieved_at: datetime
    is_cached: bool = False
    freshness_status: str
    source: str
    data_classification: str = "SUPPORTING_CONTEXT_ONLY"


# --- Sync Schemas ---
class SyncStatusResponse(BaseModel):
    pending_sensor_readings: int
    pending_irrigation_schedules: int
    last_sync_attempt: Optional[datetime] = None
    sync_engine_status: str # "IDLE", "SYNCING", "OFFLINE_STANDBY"
    cloud_reachability: bool
