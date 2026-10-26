# AQUORA: Hardware Wiring & Sensor Station Schematics

This document provides complete wiring schematics, pinouts, and bill of materials for building physical AQUORA canal monitoring stations.

---

## 1. Bill of Materials (BOM) per Node

| Component | Part / Model | Purpose | Approx Cost (INR) |
| :--- | :--- | :--- | :--- |
| **Microcontroller** | ESP32-WROOM-32 or Heltec WiFi LoRa 32 V2 | Low-power MCU with deep sleep & RTC | ₹450 - ₹1200 |
| **LoRa Radio** | HopeRF RFM95W / Semtech SX1276 (865-867 MHz) | Rural long-range radio (5 - 10 km reach) | ₹650 |
| **Water Level Sensor** | JSN-SR04T (Waterproof Ultrasonic Sensor) | Non-contact distance to water surface (20 - 450 cm) | ₹400 |
| **Solar Power Module** | 6V 2W Monocrystalline Solar Panel + TP4056 | Continuous field power harvesting | ₹350 |
| **Battery** | 18650 Li-ion Rechargeable Battery (3.7V 2600mAh) | Overnight power storage | ₹220 |
| **Enclosure** | IP66 Weatherproof Junction Box with Cable Glands | Environmental protection against monsoon & humidity | ₹280 |
| **Resistors** | 2x 100kΩ 1% metal film resistors | Battery ADC voltage divider | ₹5 |

---

## 2. Wiring Connections

### A. ESP32 to LoRa Transceiver (SPI Interface)
If using standalone RFM95W with ESP32-WROOM:
```
RFM95W Pin       ESP32 GPIO Pin
---------------------------------
3.3V             3.3V (Do NOT connect to 5V)
GND              GND
MISO             GPIO 19
MOSI             GPIO 27
SCK              GPIO 5
NSS (CS)         GPIO 18
RST              GPIO 14
DIO0 (IRQ)       GPIO 26
ANT              865MHz Spring / SMA Antenna
```
*(If using integrated boards like Heltec WiFi LoRa 32 or TTGO T-Beam, LoRa pins are routed internally.)*

### B. ESP32 to JSN-SR04T Waterproof Ultrasonic Sensor
```
JSN-SR04T Pin    ESP32 GPIO Pin    Notes
------------------------------------------------------------------------
VCC              5V (VIN / VBUS)   Powered from battery boost or 5V rail
GND              GND               Common ground
TRIG             GPIO 23           Trigger pulse output (10 µs pulse)
ECHO             GPIO 22           Echo input pulse (via 1k/2k divider if 5V)
```

### C. Battery Voltage Divider to ADC (GPIO 34)
To measure battery voltage (3.0V - 4.2V) safely within ESP32 ADC range (0 - 3.3V):
```
Battery (+) ────[ 100kΩ ]────┬────[ 100kΩ ]──── GND
                             │
                             └──── ESP32 GPIO 34 (ADC1_CH6)
```
- Formula in firmware: `V_batt = (ADC_reading / 4095.0) * 3.3V * 2.0 * calibration_factor`

---

## 3. Physical Canal Mounting

1. **Mounting Arm**: Secure sensor face perpendicular to the water surface using a galvanized iron bracket attached to canal revetment or sluice gate wall.
2. **Mounting Height ($H_0$)**: Mount sensor between **150 cm and 200 cm** above the dry canal bed.
3. **Dead Zone**: JSN-SR04T has a 20 cm blind zone. Ensure sensor face is at least 25 cm above maximum high-flood water level.
4. **Water Level Calculation**:
   $$\text{Water Depth (cm)} = H_{\text{mount}} - D_{\text{measured}}$$
   Firmware applies 5-sample median filtering to eliminate wave chop and splash bounce.

---

## 4. Gateway Receiver Hardware (Windows Host)

- **Receiver Dongle**: An ESP32 flashed with LoRa Receiver firmware connected to Windows via USB.
- **Port Detection**: Shows up in Windows Device Manager as **Silicon Labs CP210x** or **CH340** on `COM3`, `COM4`, etc.
- Run `python gateway/lora_gateway_serial.py --port COM3 --baud 115200` to start streaming packets into AQUORA.
