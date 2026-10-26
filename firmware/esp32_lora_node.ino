/*
  =============================================================================
  AQUORA - Real-Data Offline Water Intelligence Platform
  ESP32 LoRa Canal Water Level Sensor Node Firmware
  =============================================================================
  Target Hardware: 
    - ESP32 Development Board (e.g. ESP32-WROOM-32 or Heltec WiFi LoRa 32 V2)
    - Ultrasonic Sensor: Waterproof JSN-SR04T (or HC-SR04)
    - LoRa Transceiver: HopeRF RFM95W / Semtech SX1276 (865 - 867 MHz India band)
  
  Power Management:
    - High-efficiency deep sleep between measurement cycles (e.g., 5 min interval)
    - Solar harvesting with LiPo battery monitoring via analog voltage divider

  Safety & Integrity:
    - Multi-sample median filtering to remove surface wave ripple & splash noise
    - CRC16 validation payload to prevent corrupt radio transmissions
  =============================================================================
*/

#include <SPI.h>
#include <LoRa.h> // Sandeep Mistry LoRa Library

// --- Hardware Pin Definitions ---
// LoRa SPI Pinout (RFM95 / SX1276)
#define LORA_SS    18
#define LORA_RST   14
#define LORA_DIO0  26
#define LORA_SCK   5
#define LORA_MISO  19
#define LORA_MOSI  27

// Ultrasonic Sensor Pins (JSN-SR04T)
#define TRIG_PIN   23
#define ECHO_PIN   22

// Battery ADC Pin (100k / 100k voltage divider to GPIO 34)
#define BATTERY_ADC_PIN 34

// --- Node Configuration ---
const char* NODE_ID = "NODE-UPSTREAM-01"; // Change to "NODE-DOWNSTREAM-02" for field nodes
const float MOUNTING_HEIGHT_CM = 180.0;    // Distance from sensor face to dry canal bed
const float CANAL_MAX_DEPTH_CM = 350.0;
const long LORA_FREQUENCY = 865200000;    // 865.2 MHz (India License-Free Band)
const int SLEEP_INTERVAL_SECONDS = 300;   // 5 minutes between transmissions

// RTC Slow Memory (persists across deep sleep)
RTC_DATA_ATTR uint32_t packetSequence = 0;

// --- CRC16 Calculation for Packet Integrity ---
uint16_t calculateCRC16(const uint8_t *data, size_t length) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < length; i++) {
    crc ^= (uint16_t)data[i];
    for (int j = 0; j < 8; j++) {
      if (crc & 0x0001) {
        crc = (crc >> 1) ^ 0xA001;
      } else {
        crc = crc >> 1;
      }
    }
  }
  return crc;
}

// --- Multi-Sample Ultrasonic Depth Measurement ---
float measureDistanceCM() {
  const int NUM_SAMPLES = 5;
  float samples[NUM_SAMPLES];

  for (int i = 0; i < NUM_SAMPLES; i++) {
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);

    // 35ms timeout corresponds to approx 6 meters maximum distance
    long duration = pulseIn(ECHO_PIN, HIGH, 35000);

    if (duration == 0) {
      samples[i] = MOUNTING_HEIGHT_CM; // Timeout: assume dry bed or empty channel
    } else {
      // Speed of sound in air ~0.0343 cm/microsecond at 25C
      samples[i] = (duration * 0.0343) / 2.0;
    }
    delay(40);
  }

  // Simple bubble sort to find median and reject water surface bounce
  for (int i = 0; i < NUM_SAMPLES - 1; i++) {
    for (int j = i + 1; j < NUM_SAMPLES; j++) {
      if (samples[i] > samples[j]) {
        float temp = samples[i];
        samples[i] = samples[j];
        samples[j] = temp;
      }
    }
  }
  return samples[NUM_SAMPLES / 2];
}

float measureBatteryVoltage() {
  int raw = analogRead(BATTERY_ADC_PIN);
  // ADC full scale 3.3V, 12-bit (4095), 2x voltage divider (100k / 100k)
  float pinVoltage = (raw / 4095.0) * 3.3 * 1.05; // 1.05 calibration factor
  return pinVoltage * 2.0;
}

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("\n[AQUORA] Sensor Node Booting...");

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(BATTERY_ADC_PIN, INPUT);

  // Initialize LoRa Hardware
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
  if (!LoRa.begin(LORA_FREQUENCY)) {
    Serial.println("[AQUORA-ERR] LoRa Radio initialization failed!");
    // Power down and retry next cycle
    esp_sleep_enable_timer_wakeup(60 * 1000000ULL);
    esp_deep_sleep_start();
  }

  // Configure LoRa RF parameters for long-range rural penetration
  LoRa.setTxPower(17);          // 17 dBm EIRP
  LoRa.setSpreadingFactor(10);   // SF10 for up to 5-10 km rural line-of-sight
  LoRa.setSignalBandwidth(125E3); // 125 kHz
  LoRa.setCodingRate4(5);        // CR 4/5
  LoRa.enableCrc();

  // 1. Take physical water depth reading
  float distanceCM = measureDistanceCM();
  float waterLevelCM = MOUNTING_HEIGHT_CM - distanceCM;
  if (waterLevelCM < 0.0) waterLevelCM = 0.0;
  if (waterLevelCM > CANAL_MAX_DEPTH_CM) waterLevelCM = CANAL_MAX_DEPTH_CM;

  // 2. Measure Battery Voltage
  float batteryVolts = measureBatteryVoltage();

  packetSequence++;

  // 3. Assemble JSON LoRa Packet Payload
  // Example: {"n":"NODE-UPSTREAM-01","s":14,"w":82.4,"b":3.92,"c":49210}
  char payload[160];
  snprintf(payload, sizeof(payload),
           "{\"n\":\"%s\",\"s\":%lu,\"w\":%.1f,\"b\":%.2f}",
           NODE_ID, packetSequence, waterLevelCM, batteryVolts);

  uint16_t crc = calculateCRC16((const uint8_t*)payload, strlen(payload));
  char fullPacket[200];
  snprintf(fullPacket, sizeof(fullPacket),
           "{\"n\":\"%s\",\"s\":%lu,\"w\":%.1f,\"b\":%.2f,\"c\":%u}",
           NODE_ID, packetSequence, waterLevelCM, batteryVolts, crc);

  Serial.print("[AQUORA-TX] Sending LoRa Packet: ");
  Serial.println(fullPacket);

  // 4. Transmit via LoRa
  LoRa.beginPacket();
  LoRa.print(fullPacket);
  LoRa.endPacket();

  Serial.println("[AQUORA-TX] Transmission complete. Entering deep sleep.");

  // Put LoRa module into low-power sleep mode
  LoRa.sleep();

  // 5. Enter ESP32 Deep Sleep for power conservation
  esp_sleep_enable_timer_wakeup((uint64_t)SLEEP_INTERVAL_SECONDS * 1000000ULL);
  esp_deep_sleep_start();
}

void loop() {
  // Not reached in deep-sleep architecture
}
