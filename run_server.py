"""
=============================================================================
AQUORA - Real-Data Offline Water Intelligence Platform
Local Server Runner for Windows & Embedded Edge Devices
=============================================================================
Usage:
    python run_server.py
=============================================================================
"""

import sys
import os
import uvicorn

from backend.config import settings

def main():
    print("=" * 72)
    print("  AQUORA - Offline-First Real-Data Water Intelligence Platform")
    print("  Cauvery Delta Canal Network • Tamil Nadu, India")
    print("=" * 72)
    print(f"[*] Environment        : {settings.env}")
    print(f"[*] Local Host         : {settings.host}:{settings.port}")
    print(f"[*] Local Database     : {settings.database_url} (WAL Mode)")
    print(f"[*] LoRa Gateway Auth  : Enabled (API Key required)")
    print(f"[*] Official Reservoir : TN Agriculture ARS & Chennai Flood Monitor")
    print(f"[*] Web Dashboard      : http://{settings.host if settings.host != '0.0.0.0' else '127.0.0.1'}:{settings.port}/")
    print("=" * 72)

    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=(settings.env == "development"),
        log_level="info"
    )

if __name__ == "__main__":
    main()
