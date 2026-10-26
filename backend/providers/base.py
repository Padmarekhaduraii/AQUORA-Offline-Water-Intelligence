from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime, timezone, timedelta

from backend.schemas import OfficialReservoirResponse, WeatherContextResponse

class BaseReservoirProvider(ABC):
    """
    Abstract Provider Adapter for Official Reservoir Data Sources.
    Allows swappable integration of government portals without modifying core application logic.
    """
    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique machine identifier for the provider."""
        pass

    @property
    @abstractmethod
    def provider_display_name(self) -> str:
        """Human readable title of the data authority."""
        pass

    @property
    @abstractmethod
    def source_url(self) -> str:
        """Official web portal URL."""
        pass

    @abstractmethod
    async def fetch_observations(self, date_str: Optional[str] = None) -> List[OfficialReservoirResponse]:
        """
        Fetch reservoir levels and storage observations from the source.
        Returns a validated list of OfficialReservoirResponse objects.
        Must handle connectivity failures gracefully.
        """
        pass

    def calculate_freshness(self, observation_date_str: str, retrieved_at: datetime) -> str:
        """
        Evaluates data freshness based on the observation date vs retrieval date.
        """
        try:
            # Parse observation date (supports DD-MM-YYYY or YYYY-MM-DD)
            if "-" in observation_date_str:
                parts = observation_date_str.split("-")
                if len(parts[0]) == 4: # YYYY-MM-DD
                    obs_date = datetime.strptime(observation_date_str, "%Y-%m-%d").date()
                else: # DD-MM-YYYY
                    obs_date = datetime.strptime(observation_date_str, "%d-%m-%Y").date()
            else:
                return "UNKNOWN"

            today = retrieved_at.date()
            delta_days = (today - obs_date).days

            if delta_days <= 0:
                return "FRESH"
            elif delta_days == 1:
                return "RECENT"
            else:
                return f"STALE ({delta_days}d old)"
        except Exception:
            return "RECENT"


class BaseWeatherProvider(ABC):
    """
    Abstract Provider for supporting meteorological context.
    Strictly defined as secondary context; NEVER used to infer canal water arrival.
    """
    @property
    @abstractmethod
    def provider_id(self) -> str:
        pass

    @abstractmethod
    async def fetch_current_weather(self, lat: float, lon: float, location_name: str) -> WeatherContextResponse:
        pass
