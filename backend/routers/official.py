from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import OfficialReservoirObservation
from backend.schemas import OfficialReservoirResponse
from backend.providers.registry import registry

router = APIRouter(prefix="/api/v1/official", tags=["Official Reservoir Intelligence"])

@router.get("/reservoirs", response_model=List[OfficialReservoirResponse])
async def get_official_reservoirs(
    provider: Optional[str] = Query(None, description="Filter by provider: 'tn_agriculture' or 'chennai_flood_monitor'"),
    date: Optional[str] = Query(None, description="Observation date filter (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Fetch official verified reservoir storage and flow metrics.
    Integrates verified Tamil Nadu Agriculture ARS Portal and Chennai Flood Monitor adapters.
    Returns: Source URL, Observation Date, Retrieval Timestamp, and Freshness Status.
    """
    all_observations: List[OfficialReservoirResponse] = []

    if provider:
        providers = [registry.get_reservoir_provider(provider)]
    else:
        providers = registry.list_reservoir_providers()

    for p in providers:
        obs_list = await p.fetch_observations(date_str=date)
        all_observations.extend(obs_list)

        # Cache in local SQLite database for offline persistence
        for item in obs_list:
            existing = db.query(OfficialReservoirObservation).filter(
                OfficialReservoirObservation.provider_name == item.provider_name,
                OfficialReservoirObservation.reservoir_name == item.reservoir_name,
                OfficialReservoirObservation.observation_date == item.observation_date
            ).first()

            if not existing:
                rec = OfficialReservoirObservation(
                    provider_name=item.provider_name,
                    reservoir_name=item.reservoir_name,
                    observation_date=item.observation_date,
                    full_depth_ft=item.full_depth_ft,
                    full_capacity_mcft=item.full_capacity_mcft,
                    current_level_ft=item.current_level_ft,
                    current_storage_mcft=item.current_storage_mcft,
                    inflow_cusecs=item.inflow_cusecs,
                    outflow_cusecs=item.outflow_cusecs,
                    last_year_level_ft=item.last_year_level_ft,
                    last_year_storage_mcft=item.last_year_storage_mcft,
                    retrieved_at=item.retrieved_at,
                    freshness_status=item.freshness_status,
                    source_url=item.source_url
                )
                db.add(rec)
            else:
                existing.current_level_ft = item.current_level_ft
                existing.current_storage_mcft = item.current_storage_mcft
                existing.inflow_cusecs = item.inflow_cusecs
                existing.outflow_cusecs = item.outflow_cusecs
                existing.retrieved_at = item.retrieved_at
                existing.freshness_status = item.freshness_status

    db.commit()
    return all_observations


@router.get("/providers")
def list_providers():
    """
    Returns transparency metadata on official provider adapters and their interface capabilities.
    """
    return [
        {
            "id": "tn_agriculture",
            "name": "Tamil Nadu Agriculture Department (ARS)",
            "url": "https://tnagriculture.in/ARS/home/reservoir/",
            "interface_type": "HTML_TABLE_SCRAPER",
            "has_public_rest_api": False,
            "has_downloadable_feed": False,
            "description": "Daily reservoir storage and discharge reporting across major TN reservoirs (Mettur, Bhavanisagar, etc.)."
        },
        {
            "id": "chennai_flood_monitor",
            "name": "Chennai Flood Monitoring Dashboard (CFM-DSS)",
            "url": "https://chennaifloodmonitor.tn.gov.in/HomePage/Dashboard",
            "interface_type": "UNAVAILABLE_PUBLIC_API",
            "has_public_rest_api": False,
            "has_downloadable_feed": False,
            "description": "Internal government dashboard; no public API or authenticated endpoint exposed for reservoir feeds."
        }
    ]
