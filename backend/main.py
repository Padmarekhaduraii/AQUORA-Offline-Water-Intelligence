import os
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import engine, Base, get_db
from backend.models import SensorNode, SensorReading
from backend.websocket_manager import ws_manager
from backend.routers import (
    sensors_router,
    official_router,
    intelligence_router,
    irrigation_router,
    alerts_router,
    sync_router
)

# Initialize database schema
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AQUORA Offline Water Intelligence Platform",
    description="Real-data, offline-first water intelligence platform combining physical ESP32 LoRa sensor nodes with verified Tamil Nadu reservoir telemetry.",
    version="1.0.0"
)

# Enable CORS for local and offline gateway network access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(sensors_router)
app.include_router(official_router)
app.include_router(intelligence_router)
app.include_router(irrigation_router)
app.include_router(alerts_router)
app.include_router(sync_router)

def seed_default_nodes():
    """Seed initial canal topology nodes if database is brand new."""
    db = next(get_db())
    try:
        if db.query(SensorNode).count() == 0:
            default_nodes = [
                SensorNode(
                    id="NODE-UPSTREAM-01",
                    name="Grand Anicut Intake Regulator",
                    canal_name="Cauvery Main Canal",
                    reach_segment="Head Regulator Reach",
                    distance_from_head_km=0.0,
                    latitude=10.8350,
                    longitude=78.8180,
                    zero_datum_offset_cm=180.0,
                    max_depth_cm=350.0,
                    is_active=True
                ),
                SensorNode(
                    id="NODE-MIDSTREAM-01",
                    name="Kallanai Mid-Reach Siphon",
                    canal_name="Cauvery Main Canal",
                    reach_segment="Intermediate Distributary",
                    distance_from_head_km=5.2,
                    latitude=10.8120,
                    longitude=78.8650,
                    zero_datum_offset_cm=160.0,
                    max_depth_cm=300.0,
                    is_active=True
                ),
                SensorNode(
                    id="NODE-DOWNSTREAM-02",
                    name="Thanjavur Farmer Ayacut Sluice 4",
                    canal_name="Cauvery Main Canal",
                    reach_segment="Tail-End Farmer Offtake",
                    distance_from_head_km=12.5,
                    latitude=10.7870,
                    longitude=78.9240,
                    zero_datum_offset_cm=140.0,
                    max_depth_cm=250.0,
                    is_active=True
                ),
            ]
            db.add_all(default_nodes)
            db.commit()
    finally:
        db.close()

seed_default_nodes()


@app.get("/api/v1/health")
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint providing offline operational state."""
    active_node_count = db.query(SensorNode).filter(SensorNode.is_active == True).count()
    reading_count = db.query(SensorReading).count()
    return {
        "status": "healthy",
        "system": "AQUORA Water Intelligence",
        "mode": "offline_first",
        "active_nodes": active_node_count,
        "total_readings_stored": reading_count,
        "database": "sqlite_wal_active",
        "timestamp_utc": datetime.now(timezone.utc).isoformat()
    }


@app.websocket("/api/v1/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    """Real-time LoRa sensor telemetry broadcast over local WebSocket."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep socket open and accept client heartbeats/pings
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


# Static Frontend mounting
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/")
    def serve_dashboard():
        index_file = os.path.join(frontend_path, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "AQUORA API running. Frontend index.html not yet initialized."}
