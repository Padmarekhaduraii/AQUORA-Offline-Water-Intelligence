from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas import WaterArrivalEstimateResponse, WeatherContextResponse
from backend.services.arrival_engine import arrival_engine
from backend.providers.registry import registry

router = APIRouter(prefix="/api/v1/intelligence", tags=["Hydrodynamic Intelligence & Arrival"])

@router.get("/arrival-estimates", response_model=WaterArrivalEstimateResponse)
def get_canal_water_arrival_estimate(
    target_node_id: str = Query("NODE-DOWNSTREAM-02", description="Target offtake / farmer sluice node ID"),
    reference_upstream_node_id: str = Query("NODE-UPSTREAM-01", description="Intake / upstream monitor node ID"),
    db: Session = Depends(get_db)
):
    """
    Computes canal water arrival estimates based STRICTLY on physical upstream sensor telemetry.
    Adheres strictly to the rule: Never infer downstream canal arrival from reservoir level alone.
    """
    return arrival_engine.estimate_arrival(
        db,
        target_node_id=target_node_id,
        reference_upstream_node_id=reference_upstream_node_id
    )


@router.get("/weather-context", response_model=WeatherContextResponse)
async def get_supporting_weather_context(
    lat: float = Query(None, description="Latitude"),
    lon: float = Query(None, description="Longitude")
):
    """
    Provides environmental weather context (evaporative demand, precipitation).
    Strictly classified as SUPPORTING CONTEXT ONLY. Never substituted for canal water level.
    """
    provider = registry.get_weather_provider()
    return await provider.fetch_current_weather(lat=lat, lon=lon)
