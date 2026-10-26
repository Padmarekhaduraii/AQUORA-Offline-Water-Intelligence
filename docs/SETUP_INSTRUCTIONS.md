# AQUORA: Setup & Deployment Instructions (Windows & Field Deployment)

This guide documents how to set up, run, and test the **AQUORA Offline Water Intelligence Platform** on a Windows machine or edge gateway.

---

## 1. Prerequisites

- **Operating System**: Windows 10/11 (or Linux on Raspberry Pi / industrial edge gateway)
- **Python**: 3.11, 3.12, or 3.13
- **Hardware (Optional for Field Operation)**:
  - ESP32 Development board (e.g. Heltec WiFi LoRa 32 V2 / TTGO T-Beam / ESP32-WROOM)
  - HopeRF RFM95W or Semtech SX1276 LoRa transceiver (865 - 867 MHz India band)
  - Waterproof ultrasonic sensor JSN-SR04T (or HC-SR04)
  - USB-to-UART bridge / LoRa receiver dongle plugged into Windows USB port

---

## 2. Installation on Windows

### Step 1: Open Terminal in Project Directory
Open PowerShell or Command Prompt in the repository folder:
```powershell
cd c:\Users\padma\OneDrive\AQUORA-Offline-Water-Intelligence\AQUORA-Offline-Water-Intelligence
```

### Step 2: Install Python Dependencies
```powershell
python -m pip install -r requirements.txt
```

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
copy .env.example .env
```
Key configuration parameters:
- `AQUORA_HOST=127.0.0.1` (or `0.0.0.0` for local Wi-Fi router access)
- `AQUORA_PORT=8000`
- `AQUORA_GATEWAY_API_KEY`: Secret key shared between LoRa gateway bridge and FastAPI backend
- `AQUORA_STALE_SENSOR_TIMEOUT_SECONDS=1800` (30 minutes)
- `AQUORA_SURGE_THRESHOLD_CM=15.0` (depth change trigger for water wave front)

---

## 3. Starting the Platform

### Start the Backend & Web Dashboard
```powershell
python run_server.py
```
Open your web browser and navigate to:
```
http://127.0.0.1:8000/
```

The responsive dashboard will load with:
- **Canal Water Arrival Estimation** (Hydrodynamic kinematic wave model)
- **Canal Reach Hydrograph & Wave Front Telemetry** (Interactive SVG time-series chart)
- **Canal Level Ground-Truth Stations** (ESP32 LoRa field nodes)
- **Verified Tamil Nadu Reservoir Status** (TN Agriculture ARS & CFM-DSS)
- **Ayacut Irrigation Turns** (Offline crop scheduling)
- **Canal Zone Weather Context** (Supporting environmental data)
- **System Event & Audit Log**

---

## 4. Running the LoRa Gateway Bridge (Field Operation)

When connecting a physical LoRa receiver dongle to Windows USB:
```powershell
python gateway/lora_gateway_serial.py --port COM3 --baud 115200
```
- Listens to incoming radio packets over serial COM.
- Pushes verified packets to `http://127.0.0.1:8000/api/v1/sensors/ingest`.
- **Offline disk buffer**: If the backend is restarting or stopped, packets are written to `gateway_buffer.json` and automatically replayed once backend is back up.

---

## 5. Simulating Field Telemetry (Development & Demonstration)

To test the platform without physical hardware attached:

### Simulate Sluice Gate Opening (Water Surge)
```powershell
python gateway/simulate_lora_nodes.py --scenario surge
```
- Injects ground-truth telemetry showing water rising from 8 cm to 85 cm at the head regulator.
- Immediately calculates downstream wave arrival with travel time and uncertainty range ($\pm$ hours).
- **All test data is transparently flagged with `"is_simulated": true`**.

### Simulate Dry Canal
```powershell
python gateway/simulate_lora_nodes.py --scenario dry
```
- Sets canal depth to 4 cm (dry bed).
- Dashboard reports `NO_FLOW_DETECTED` and holds irrigation gates closed.

---

## 6. Running Automated Tests

Run the complete 33-test suite:
```powershell
python -m pytest -v
```
All tests verify:
- Authentication & input validation
- Hydrodynamic wave calculations & uncertainty reporting
- Stale sensor disconnection alerts
- TN Agriculture portal scraper & Chennai Flood Monitor honest adapter
- SHA-256 deduplication & offline queue preservation
- Frontend accessibility, landmarks, and contracts
