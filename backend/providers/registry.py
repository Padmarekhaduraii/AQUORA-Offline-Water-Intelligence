from typing import Dict, List
from backend.providers.base import BaseReservoirProvider, BaseWeatherProvider
from backend.providers.tn_reservoir import TNReservoirScraperProvider
from backend.providers.chennai_flood import ChennaiFloodMonitorAdapter
from backend.providers.weather import OpenMeteoWeatherProvider

class ProviderRegistry:
    """
    Central registry for external data provider adapters.
    Allows swappable multi-provider architecture.
    """
    def __init__(self):
        self._reservoir_providers: Dict[str, BaseReservoirProvider] = {
            "tn_agriculture": TNReservoirScraperProvider(),
            "chennai_flood_monitor": ChennaiFloodMonitorAdapter(),
        }
        self._weather_provider: BaseWeatherProvider = OpenMeteoWeatherProvider()

    def get_reservoir_provider(self, provider_id: str) -> BaseReservoirProvider:
        if provider_id not in self._reservoir_providers:
            raise ValueError(f"Unknown reservoir provider: {provider_id}")
        return self._reservoir_providers[provider_id]

    def list_reservoir_providers(self) -> List[BaseReservoirProvider]:
        return list(self._reservoir_providers.values())

    def get_weather_provider(self) -> BaseWeatherProvider:
        return self._weather_provider

    def register_reservoir_provider(self, provider: BaseReservoirProvider):
        self._reservoir_providers[provider.provider_id] = provider

registry = ProviderRegistry()
