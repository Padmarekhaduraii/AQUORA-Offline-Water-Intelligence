# AQUORA: System Architecture & Hydrodynamic Principles

## 1. Architectural Mission

AQUORA is engineered for rural canal command areas in Tamil Nadu where cellular and cloud connectivity are intermittent or non-existent during flood emergencies and remote farming seasons. 

It provides an end-to-end ground-truth water intelligence chain:
```
[Physical Canal Water] 
       │
       ▼ (Ultrasonic Time-of-Flight)
[ESP32 Field Station] 
       │
       ▼ (LoRa 865 MHz Radio Packet)
[Local Gateway Dongle] 
       │
       ▼ (USB Serial / Python Daemon)
[FastAPI Local Server + SQLite WAL] 
       │
       ▼ (Kinematic Wave Engine & Offline Scheduler)
[Responsive UI Dashboard (IndexedDB)]
```

---

## 2. Hydrodynamic Arrival Model vs. Reservoir Inferences

### The Downstream Fallacy
A common flaw in water resource tools is inferring canal water delivery from upstream dam release. For example, assuming that 5,000 CuSecs discharged from Mettur Dam or Bhavanisagar Dam guarantees water arrival at a specific farmer sluice 40 km downstream.

In reality:
1. **Barrage & Weir Diversions**: Head regulators split water into multiple distributaries and river branches according to rotational quotas.
2. **Transmission & Infiltration Losses**: Unlined earthen canals absorb significant volume into dry bank subsoil before a steady water column forms.
3. **Lock Gate Interventions**: Intermediate gates may be closed or diverted for emergency repairs or upstream ayacuts.

### AQUORA Principle
**Downstream water arrival is NEVER inferred from reservoir discharge alone.**
Arrival estimation requires **active physical telemetry from upstream canal sensor nodes**.

### Kinematic Wave Equations

### Kinematic Wave Equations

When an upstream intake node detects a water-wave surge of `Δh ≥ 15.0 cm`, AQUORA estimates the water-wave travel time using the following equations.

**1. Hydraulic Radius (`R`)**

```text
A = (B + m × y) × y
P = B + 2y × √(1 + m²)
R = A / P
```

Where:
- `A` = cross-sectional flow area (m²)
- `P` = wetted perimeter (m)
- `R` = hydraulic radius (m)
- `B = 4.0 m` = assumed canal bed width
- `m = 1.5` = assumed side slope
- `y` = water depth (m)

**2. Mean Section Velocity (`V`) — Manning's Formula**

```text
V = (1/n) × R^(2/3) × S₀^(1/2)
```

Where:
- `n = 0.028` = assumed Manning roughness coefficient
- `S₀ = 0.00025` = assumed channel bed slope
- `V` = mean flow velocity (m/s)

**3. Kinematic Wave Celerity (`Cₖ`)**

```text
Cₖ ≈ (5/3) × V
```

Here, `Cₖ` represents the approximate speed at which a change in water flow propagates downstream (m/s).

**4. Estimated Travel Time (`T`) and Uncertainty (`ΔT`)**

```text
T = ΔD / Cₖ
ΔT = ± max(0.4 hours, 0.22 × T)
```

Where:
- `ΔD` = distance between monitoring nodes (m)
- `T` = estimated travel time (seconds when `ΔD` is in metres and `Cₖ` is in m/s)
- `ΔT` = uncertainty allowance, expressed in the same time unit as `T`

The uncertainty allowance is intended to account for factors such as vegetation friction, canal infiltration, and gate throttling.

**Prototype assumptions:** The canal dimensions, roughness coefficient, bed slope, and uncertainty allowance are initial model assumptions. They require calibration against field measurements before AQUORA's estimates can be relied upon for real irrigation decisions.


## 3. Offline-First Resilience Engine

### Local Database WAL Mode
AQUORA uses SQLite with Write-Ahead Logging (`PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;`). This enables concurrent reads by multiple dashboard clients while the LoRa serial gateway continuously writes telemetry packets without lock contention.

### LoRa Retransmission & SHA-256 Deduplication
Due to radio packet loss in rural environments, ESP32 nodes and repeaters retransmit packets. To avoid double-counting volume or distorting wave front statistics:
$$\text{Hash} = \text{SHA256}(\text{node\_id} \mid \text{timestamp\_iso} \mid \text{water\_level\_cm})$$
Incoming packets with existing hashes are acknowledged idempotently without creating duplicate database records.

### Client-Side IndexedDB Cache
The frontend dashboard integrates `AquoraStorage` in IndexedDB. If the local gateway is momentarily offline (e.g. laptop moved across field), the dashboard continues rendering cached hydrographs and irrigation turns with clear `[OFFLINE CACHED]` badges, preserving original observation dates.

---

## 4. Official Provider Adapter Architecture

AQUORA separates official external data sources behind swappable provider adapters:

```
                  ┌───────────────────────────────┐
                  │    BaseReservoirProvider      │
                  └───────────────┬───────────────┘
                                  │
          ┌───────────────────────┴───────────────────────┐
          ▼                                               ▼
┌───────────────────────────────┐       ┌───────────────────────────────┐
│  TNReservoirScraperProvider   │       │  ChennaiFloodMonitorAdapter   │
├───────────────────────────────┤       ├───────────────────────────────┤
│ Parses HTML table at:         │       │ Honestly reports:             │
│ tnagriculture.in/ARS/home/... │       │ No public feed / unavailable  │
│ Sets source, date, freshness  │       │ Does not invent mock numbers  │
└───────────────────────────────┘       └───────────────────────────────┘
```
This architecture ensures that if government web formats change or new official APIs are published, adapters can be updated independently without affecting sensor processing or irrigation logic.
