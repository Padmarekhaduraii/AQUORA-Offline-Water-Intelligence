"""
=============================================================================
AQUORA - Local Offline LoRa Gateway Bridge Daemon
=============================================================================
Listens for LoRa radio packets received on a USB Serial COM port from a local 
ESP32 / SX1276 receiver dongle.

Offline Resilience Features:
1. Operates 100% locally on Windows without cloud dependencies.
2. Ingests packets directly into the local FastAPI platform via HTTP localhost.
3. If FastAPI is restarting or offline, incoming packets are safely buffered
   to a local disk queue (gateway_buffer.json) and drained automatically.
=============================================================================
"""

import sys
import os
import time
import json
import logging
import argparse
from datetime import datetime, timezone
import urllib.request
import urllib.error

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (Gateway) %(message)s"
)
logger = logging.getLogger("aquora.gateway")

DEFAULT_SERVER_URL = "http://127.0.0.1:8000/api/v1/sensors/ingest"
DEFAULT_API_KEY = "aquora_live_lora_secret_key_2026"
BUFFER_FILE = "gateway_buffer.json"


def load_disk_buffer() -> list:
    if os.path.exists(BUFFER_FILE):
        try:
            with open(BUFFER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read disk buffer: {e}")
    return []


def save_disk_buffer(buffer: list):
    try:
        with open(BUFFER_FILE, "w", encoding="utf-8") as f:
            json.dump(buffer, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write disk buffer: {e}")


def post_to_backend(payload: dict, server_url: str, api_key: str) -> bool:
    """
    Submits sensor reading payload to local FastAPI ingestion endpoint.
    """
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        server_url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
            "User-Agent": "AQUORA-LoRa-Gateway/1.0"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            if resp.status in [200, 201]:
                return True
    except urllib.error.HTTPError as e:
        logger.warning(f"Backend HTTP error {e.code}: {e.read().decode('utf-8', 'ignore')}")
    except Exception as e:
        logger.debug(f"Backend connection failed: {e}")
    return False


def flush_disk_buffer(server_url: str, api_key: str):
    """
    Attempts to drain buffered packets when backend becomes reachable.
    """
    buffer = load_disk_buffer()
    if not buffer:
        return

    logger.info(f"Draining {len(buffer)} buffered packets to backend...")
    remaining = []
    success_count = 0

    for item in buffer:
        if post_to_backend(item, server_url, api_key):
            success_count += 1
        else:
            remaining.append(item)

    save_disk_buffer(remaining)
    logger.info(f"Drained {success_count} packets. {len(remaining)} remaining in buffer.")


def parse_lora_raw_line(raw_line: str) -> dict | None:
    """
    Parses incoming raw serial line.
    Format 1: JSON packet from firmware: {"n":"NODE-UPSTREAM-01","s":14,"w":82.4,"b":3.92,"c":49210}
    Format 2: Key-Value text: NODE=NODE-UPSTREAM-01,LEVEL=82.4,BATT=3.92,RSSI=-78
    """
    cleaned = raw_line.strip()
    if not cleaned:
        return None

    # Handle JSON format
    if cleaned.startswith("{") and cleaned.endswith("}"):
        try:
            data = json.loads(cleaned)
            node_id = data.get("n") or data.get("node_id")
            water_level = data.get("w") if "w" in data else data.get("water_level_cm")
            battery = data.get("b") if "b" in data else data.get("battery_voltage")
            rssi = data.get("rssi", -75.0)
            snr = data.get("snr", 8.5)

            if node_id and water_level is not None:
                return {
                    "node_id": str(node_id),
                    "timestamp_recorded": datetime.now(timezone.utc).isoformat(),
                    "water_level_cm": float(water_level),
                    "battery_voltage": float(battery) if battery is not None else 3.9,
                    "rssi_dbm": float(rssi),
                    "snr_db": float(snr),
                    "is_simulated": False
                }
        except Exception as e:
            logger.warning(f"Error parsing JSON packet '{cleaned}': {e}")
            return None

    return None


def run_gateway(port: str, baudrate: int, server_url: str, api_key: str):
    logger.info(f"Starting AQUORA LoRa Gateway Bridge on Windows port '{port}' @ {baudrate} baud...")
    logger.info(f"Target local endpoint: {server_url}")

    # Check if pyserial is installed
    try:
        import serial
    except ImportError:
        logger.error("pyserial is required to run serial gateway: pip install pyserial")
        sys.exit(1)

    while True:
        try:
            # Drain disk buffer first
            flush_disk_buffer(server_url, api_key)

            logger.info(f"Attempting connection to Serial Port {port}...")
            with serial.Serial(port, baudrate, timeout=2) as ser:
                logger.info(f"Serial port {port} opened successfully! Listening for LoRa packets...")
                while True:
                    line = ser.readline().decode("utf-8", "ignore")
                    if line:
                        logger.info(f"[LORA-RX] {line.strip()}")
                        reading = parse_lora_raw_line(line)
                        if reading:
                            sent = post_to_backend(reading, server_url, api_key)
                            if sent:
                                logger.info(f"[INGEST-OK] Node {reading['node_id']}: {reading['water_level_cm']} cm")
                            else:
                                logger.warning(f"[BUFFERING] Backend offline. Storing packet in local disk queue.")
                                buf = load_disk_buffer()
                                buf.append(reading)
                                save_disk_buffer(buf)

                    # Periodic buffer flush check
                    flush_disk_buffer(server_url, api_key)

        except Exception as e:
            logger.warning(f"Serial port {port} unavailable: {e}. Retrying in 5 seconds...")
            time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AQUORA LoRa Gateway Serial Daemon")
    parser.add_argument("--port", default="COM3", help="Serial COM port (default: COM3 on Windows)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--url", default=DEFAULT_SERVER_URL, help="Backend ingestion URL")
    parser.add_argument("--key", default=DEFAULT_API_KEY, help="Gateway API Key")

    args = parser.parse_args()
    run_gateway(args.port, args.baud, args.url, args.key)
