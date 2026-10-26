# AQUORA: Documented API Contract & Data Governance

AQUORA exposes a RESTful API and WebSocket telemetry stream designed for offline-first, local-gateway field operation.

---

## 1. Governance & Data Classification Taxonomy

Every endpoint and dashboard response returns a strict `data_classification` field:

| Classification | Meaning | Guarantee |
| :--- | :--- | :--- |
| `ACTUAL_SENSOR` / `ACTUAL_PHYSICAL_SENSOR` | Physical ultrasonic measurement from field ESP32 LoRa node | Primary ground truth; never estimated |
| `OFFICIAL_RESERVOIR_OBSERVATION` | Official State Government water resources department data | Attributed to verified source URL with observation and retrieval timestamps |
| `MODEL_GENERATED_PREDICTION` | Hydrodynamic kinematic wave calculation | Computed strictly from upstream physical sensor; includes uncertainty interval ($\pm$ hrs) |
| `SUPPORTING_CONTEXT_ONLY` | Environmental meteorological data (Open-Meteo) | Contextual only; **NEVER** substituted for canal water level |

---

## 2. API Endpoints

### A. Health & Operational Diagnostics
- **`GET /api/v1/health`**
  - **Description**: Probes local gateway, database WAL status, active node count, and stored readings.
  - **Response 200 OK**:
    ```json
    {
      "status": "healthy",
      "system": "AQUORA Water Intelligence",
      "mode": "offline_first",
      "active_nodes": 3,
      "total_readings_stored": 142,
      "database": "sqlite_wal_active",
      "timestamp_utc": "2026-10-26T15:30:00Z"
    }
    ```

---

### B. Physical Sensor Ingestion & Telemetry
- **`POST /api/v1/sensors/ingest`**
  - **Headers**: `X-API-Key: <gateway_secret_key>`
  - **Payload**:
    ```json
    {
      "node_id": "NODE-UPSTREAM-01",
      "timestamp_recorded": "2026-10-26T15:30:00Z",
      "water_level_cm": 82.5,
      "water_flow_rate_lps": 536.25,
      "battery_voltage": 4.08,
      "rssi_dbm": -74.0,
      "snr_db": 9.2,
      "is_simulated": false
    }
    ```
  - **Deduplication**: Automatically calculates SHA-256 of `(node_id, timestamp, water_level)`. Duplicate retransmissions return HTTP 200 without creating duplicate database rows.
  - **Real-Time Push**: Broadcasts new reading to local WebSocket clients.

- **`POST /api/v1/sensors/ingest-batch`**
  - **Headers**: `X-API-Key: <gateway_secret_key>`
  - **Description**: Replays queued packets buffered by LoRa serial gateway during platform restarts.

- **`GET /api/v1/sensors/nodes`**
  - **Description**: Returns all registered canal nodes with real-time water level, disconnection flag (`is_disconnected`), and stale flag (`is_stale`).

- **`GET /api/v1/sensors/{node_id}/history?limit=100`**
  - **Description**: Returns time-series readings for graphing.

---

### C. Official Reservoir Intelligence
- **`GET /api/v1/official/reservoirs?provider=tn_agriculture&date=YYYY-MM-DD`**
  - **Description**: Scrapes and parses verified Tamil Nadu Agriculture ARS table or queries CFM adapter.
  - **Response 200 OK**:
    ```json
    [
      {
        "provider_name": "tn_agriculture",
        "reservoir_name": "METTUR",
        "observation_date": "26-10-2026",
        "full_depth_ft": 120.0,
        "full_capacity_mcft": 93470.0,
        "current_level_ft": 54.68,
        "current_storage_mcft": 20887.0,
        "inflow_cusecs": 1582.0,
        "outflow_cusecs": 1003.0,
        "retrieved_at": "2026-10-26T15:30:00Z",
        "freshness_status": "FRESH",
        "source_url": "https://tnagriculture.in/ARS/home/reservoir/",
        "data_classification": "OFFICIAL_RESERVOIR_OBSERVATION"
      }
    ]
    ```

- **`GET /api/v1/official/providers`**
  - **Description**: Provides transparency report on official provider interfaces.

---

### D. Hydrodynamic Water Arrival Engine
- **`GET /api/v1/intelligence/arrival-estimates?target_node_id=NODE-DOWNSTREAM-02&reference_upstream_node_id=NODE-UPSTREAM-01`**
  - **Governance Rule**: Never infer downstream canal arrival from reservoir level alone.
  - **Response 200 OK (Sufficient Data / Active Surge)**:
    ```json
    {
      "canal_name": "Cauvery Main Canal",
      "target_reach": "Tail-End Farmer Offtake",
      "status": "SUFFICIENT_DATA",
      "estimated_arrival_time": "2026-10-26T19:45:00Z",
      "travel_time_hours": 4.25,
      "uncertainty_range_hours": 0.85,
      "confidence_percent": 82.5,
      "upstream_surge_magnitude_cm": 74.0,
      "explanation": "Physical water wave surge of +74.0 cm recorded at upstream node 'Grand Anicut Intake Regulator'...",
      "calculated_at": "2026-10-26T15:30:00Z",
      "data_classification": "MODEL_GENERATED_PREDICTION"
    }
    ```
  - **Response 200 OK (Insufficient Data / Node Offline)**:
    ```json
    {
      "status": "INSUFFICIENT_DATA",
      "estimated_arrival_time": null,
      "travel_time_hours": null,
      "uncertainty_range_hours": null,
      "confidence_percent": 0.0,
      "explanation": "Cannot estimate water arrival: Upstream node is disconnected or stale. Physical field sensor verification is mandatory. Reservoir release data alone cannot be used."
    }
    ```

---

### E. Offline Irrigation Scheduler
- **`GET /api/v1/irrigation/schedules`**
  - **Description**: Returns offline rotational schedules matched to physical canal arrival window.
- **`POST /api/v1/irrigation/recalculate`**
  - **Description**: Forces immediate schedule re-evaluation.

---

### F. Alerts & Warnings
- **`GET /api/v1/alerts`**
  - **Description**: Scans for sensor disconnections, stale data, and critical battery warnings.
- **`POST /api/v1/alerts/{alert_id}/acknowledge`**
  - **Description**: Acknowledges alert to silence visual banner.

---

### G. Cloud Synchronization
- **`GET /api/v1/sync/status`**
  - **Description**: Returns count of pending offline records queued for cloud sync.
- **`POST /api/v1/sync/trigger`**
  - **Description**: Pushes pending records upstream; retains records locally if cloud is unreachable.

---

### H. Local WebSocket Real-Time Stream
- **`ws://<host>:<port>/api/v1/ws/telemetry`**
  - **Description**: Streams incoming LoRa telemetry packets directly to connected dashboards.
  - **Heartbeat**: Send `"ping"` to receive `"pong"`.
