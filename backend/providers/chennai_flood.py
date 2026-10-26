import re
import json
import logging
from typing import List, Optional
from datetime import datetime, timezone
import httpx

from backend.schemas import OfficialReservoirResponse
from backend.providers.base import BaseReservoirProvider
from backend.config import settings

logger = logging.getLogger("aquora.providers.chennai_flood")

class ChennaiFloodMonitorAdapter(BaseReservoirProvider):
    """
    Provider Adapter for Chennai Flood Monitoring System (CFM-DSS).
    Official Portal: https://chennaifloodmonitor.tn.gov.in/HomePage/Dashboard
    
    CRITICAL ARCHITECTURAL FINDING:
    Investigation of the CFM web portal revealed that:
    1. No documented public REST API or downloadable CSV feed exists for reservoir levels.
    2. Internal ASP.NET AJAX endpoints (e.g., /Master/GetStorageLevels) are commented out 
       in the client source and return HTTP 404 Not Found to external clients.
    3. The portal does embed client-side ARG/AWS rain gauge arrays, but does not provide
       an open, stable feed for real-time canal or reservoir discharge.
       
    Per system specification: Do not invent endpoints or claim an undocumented feed works.
    This adapter explicitly marks observations as 'FEED_UNAVAILABLE' / 'STALE_OFFLINE',
    and provides verified static design parameters for Chennai reservoirs (Poondi, Chembarambakkam, Red Hills).
    """

    @property
    def provider_id(self) -> str:
        return "chennai_flood_monitor"

    @property
    def provider_display_name(self) -> str:
        return "Chennai Flood Monitoring Dashboard (CFM-DSS)"

    @property
    def source_url(self) -> str:
        return settings.cfm_url

    async def fetch_observations(self, date_str: Optional[str] = None) -> List[OfficialReservoirResponse]:
        retrieved_at = datetime.now(timezone.utc)
        
        # We attempt a non-destructive handshake to verify portal reachability
        portal_reachable = False
        try:
            async with httpx.AsyncClient(timeout=10, verify=False) as client:
                resp = await client.get(self.source_url)
                if resp.status_code == 200:
                    portal_reachable = True
        except Exception as e:
            logger.warning(f"CFM Portal reachability check failed: {e}")

        # Chennai major reservoirs baseline capacity references
        chennai_reservoirs = [
            {
                "name": "POONDI",
                "full_depth_ft": 35.0,
                "full_capacity_mcft": 3231.0,
                "note": "Kosasthalaiyar Basin - Head storage"
            },
            {
                "name": "CHEMBARAMBAKKAM",
                "full_depth_ft": 24.0,
                "full_capacity_mcft": 3645.0,
                "note": "Adyar Basin - City supply reservoir"
            },
            {
                "name": "RED HILLS (PUZHAL)",
                "full_depth_ft": 21.2,
                "full_capacity_mcft": 3300.0,
                "note": "Direct Chennai drinking water source"
            },
            {
                "name": "CHOLAVARAM",
                "full_depth_ft": 18.8,
                "full_capacity_mcft": 1081.0,
                "note": "Feeding reservoir"
            }
        ]

        results = []
        freshness_label = "FEED_UNAVAILABLE (NO_PUBLIC_API)" if portal_reachable else "OFFLINE (PORTAL_UNREACHABLE)"

        for r in chennai_reservoirs:
            results.append(
                OfficialReservoirResponse(
                    provider_name=self.provider_id,
                    reservoir_name=r["name"],
                    observation_date="NO_PUBLIC_FEED",
                    full_depth_ft=r["full_depth_ft"],
                    full_capacity_mcft=r["full_capacity_mcft"],
                    current_level_ft=None, # Explicitly None - never fabricate live readings
                    current_storage_mcft=None,
                    inflow_cusecs=None,
                    outflow_cusecs=None,
                    retrieved_at=retrieved_at,
                    freshness_status=freshness_label,
                    source_url=self.source_url,
                    data_classification="OFFICIAL_RESERVOIR_OBSERVATION"
                )
            )

        return results
