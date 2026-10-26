import logging
from typing import Optional
from datetime import datetime, timezone
import httpx

from backend.schemas import WeatherContextResponse
from backend.providers.base import BaseWeatherProvider
from backend.config import settings

logger = logging.getLogger("aquora.providers.weather")

class OpenMeteoWeatherProvider(BaseWeatherProvider):
    """
    Supporting Weather Context Provider using Open-Meteo.
    IMPORTANT: Under AQUORA governance principles, weather data serves ONLY as
    environmental context (evapotranspiration, local rainfall potential).
    It is NEVER substituted for physical canal water level measurements.
    """
    
    def __init__(self):
        # In-memory local cache for offline scenarios
        self._cached_weather: Optional[WeatherContextResponse] = None

    @property
    def provider_id(self) -> str:
        return "open_meteo"

    async def fetch_current_weather(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        location_name: Optional[str] = None
    ) -> WeatherContextResponse:
        latitude = lat if lat is not None else settings.latitude
        longitude = lon if lon is not None else settings.longitude
        loc_name = location_name or settings.location_name
        retrieved_at = datetime.now(timezone.utc)

        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
            "timezone": "auto"
        }

        try:
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                current = data.get("current", {})

                obs_time = datetime.fromisoformat(current.get("time")) if "time" in current else retrieved_at

                response = WeatherContextResponse(
                    location=loc_name,
                    latitude=latitude,
                    longitude=longitude,
                    temperature_c=current.get("temperature_2m"),
                    humidity_percent=current.get("relative_humidity_2m"),
                    precipitation_mm=current.get("precipitation"),
                    wind_speed_kmh=current.get("wind_speed_10m"),
                    observation_time=obs_time,
                    retrieved_at=retrieved_at,
                    is_cached=False,
                    freshness_status="FRESH",
                    source="Open-Meteo Public API",
                    data_classification="SUPPORTING_CONTEXT_ONLY"
                )
                self._cached_weather = response
                return response

        except Exception as e:
            logger.warning(f"Live weather fetch failed: {e}. Falling back to cached supporting context.")
            if self._cached_weather:
                # Return existing cache marked as stale
                cached_copy = self._cached_weather.model_copy()
                cached_copy.is_cached = True
                cached_copy.freshness_status = "STALE (OFFLINE CACHED)"
                cached_copy.retrieved_at = retrieved_at
                return cached_copy

            # Baseline regional climate default for Cauvery Delta when fully offline
            return WeatherContextResponse(
                location=loc_name,
                latitude=latitude,
                longitude=longitude,
                temperature_c=31.5,
                humidity_percent=68.0,
                precipitation_mm=0.0,
                wind_speed_kmh=12.0,
                observation_time=retrieved_at,
                retrieved_at=retrieved_at,
                is_cached=True,
                freshness_status="STALE (OFFLINE BASELINE)",
                source="Offline Climatological Baseline",
                data_classification="SUPPORTING_CONTEXT_ONLY"
            )
