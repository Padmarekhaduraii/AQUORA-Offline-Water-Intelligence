from backend.routers.sensors import router as sensors_router
from backend.routers.official import router as official_router
from backend.routers.intelligence import router as intelligence_router
from backend.routers.irrigation import router as irrigation_router
from backend.routers.alerts import router as alerts_router
from backend.routers.sync import router as sync_router

__all__ = [
    "sensors_router",
    "official_router",
    "intelligence_router",
    "irrigation_router",
    "alerts_router",
    "sync_router"
]
