
# AQUORA — Offline Water Intelligence

**Smarter Water. Fairer Distribution. Connectivity Without Limits.**

AQUORA is an offline-first prototype designed to help canal-irrigated farming communities improve water-arrival awareness, detect abnormal water-level changes, and coordinate irrigation turns—even when internet connectivity is unavailable.

## Problem Statement

Farmers who depend on canal irrigation may not know when water will arrive. This uncertainty can cause wasted time, additional labour, inefficient water use, and conflicts over irrigation turns. Internet-dependent monitoring can also be unreliable in areas with poor connectivity.

## Proposed Solution

AQUORA combines local water-level monitoring, arrival-estimation logic, offline data storage, alerts, and irrigation scheduling in one platform.

The project is designed around:
- Water-level sensor integration
- ESP32-based sensor nodes
- LoRa communication for local data transmission
- A local gateway and FastAPI backend
- SQLite storage for local records
- Water-arrival estimates and abnormal-level alerts
- Offline irrigation scheduling and synchronization support
- A web dashboard for viewing system information

**Prototype status:** This repository contains software, firmware examples, and test code. Physical sensor deployment and live official-data integrations must be verified separately. Simulated readings must not be treated as live field measurements.

## Architecture

```text
Water-Level Sensors
        |
        v
ESP32 Sensor Nodes
        |
        v
LoRa Communication
        |
        v
Local Gateway
        |
        v
FastAPI Backend
   |          |
   v          v
SQLite     Prediction &
Storage    Alert Services
   |          |
   +-----+----+
         |
         v
   Web Dashboard
```

The diagram represents the intended architecture. Actual hardware and communication links depend on deployment and integration status.

See [Technical Architecture](docs/ARCHITECTURE.md) and [API Documentation](docs/API_DOCUMENTATION.md).

## Technology Stack

- **Backend:** Python, FastAPI
- **Database:** SQLite
- **Frontend:** HTML, CSS, JavaScript
- **Embedded system:** ESP32 firmware example
- **Communication:** LoRa-oriented gateway and node components
- **Testing:** pytest

## Getting Started

### Requirements

- Python 3.10 or later (Python 3.13 was used during development)
- Git
- A modern web browser

### 1. Clone the repository

```bash
git clone https://github.com/Padmarekhaduraii/AQUORA-Offline-Water-Intelligence.git
cd AQUORA-Offline-Water-Intelligence
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env` and configure values for your local environment. Use unique private credentials; never publish real API keys or passwords.

### 5. Run the application

```bash
python run_server.py
```

If startup succeeds, open the local address and port reported by the application, typically:

http://127.0.0.1:8000

Consult [Setup Instructions](docs/SETUP_INSTRUCTIONS.md) if additional configuration is required.

## Environment Configuration

The `.env.example` file documents configuration options, including:

- Application host and port
- Database location
- Gateway authentication
- Sensor staleness and surge thresholds
- Official-data provider URLs and cache settings
- Default location and weather context
- Optional synchronization settings

Use only verified sources for official data. A configured URL does not guarantee that a live feed or supported API is available.

## Tests

Run the test suite with:

```bash
python -m pytest -q
```

Tests cover arrival estimation, sensor ingestion, authentication, API behavior, alerts, irrigation scheduling, provider handling, and offline synchronization.

Passing tests validates the tested software behavior; it does not establish that physical hardware or external data feeds are operational.

## Repository Structure

```text
backend/       API, providers, routers, and services
docs/          Architecture, setup, wiring, and API documentation
firmware/      ESP32 firmware example
frontend/      Dashboard interface and JavaScript
gateway/       Local gateway and simulation utilities
tests/         Automated tests
.env.example   Example configuration
run_server.py  Application entry point
```

## Limitations and Future Work

- Validate sensor readings against real canal measurements.
- Test ESP32 and LoRa communication with physical hardware.
- Verify official data sources and their availability.
- Evaluate arrival predictions using real historical observations.
- Validate offline operation and synchronization in field conditions.
- Pilot the system with farmers before making claims about impact.

## Contributing

Contributions, testing, bug reports, and documentation improvements are welcome. Please avoid committing secrets, private data, or unverified live measurements.

## License

See the `LICENSE` file for the terms governing use, modification, and distribution.
