import pytest
import asyncio
from datetime import datetime, timezone

from backend.providers.tn_reservoir import TNReservoirScraperProvider
from backend.providers.chennai_flood import ChennaiFloodMonitorAdapter
from backend.providers.weather import OpenMeteoWeatherProvider
from backend.providers.registry import registry

@pytest.mark.anyio
async def test_tn_reservoir_scraper_and_fallback():
    provider = TNReservoirScraperProvider()
    assert provider.provider_id == "tn_agriculture"
    assert "https://tnagriculture.in" in provider.source_url

    # Test fetching observations (works online via live scraping or offline via verified fallback)
    results = await provider.fetch_observations()
    assert len(results) > 0

    mettur = next((r for r in results if "METTUR" in r.reservoir_name), None)
    assert mettur is not None
    assert mettur.full_depth_ft == 120.0
    assert mettur.full_capacity_mcft == 93470.0
    assert mettur.retrieved_at is not None
    assert mettur.observation_date is not None
    assert mettur.freshness_status in ["FRESH", "RECENT", "STALE (OFFLINE CACHED)"]
    assert mettur.data_classification == "OFFICIAL_RESERVOIR_OBSERVATION"


@pytest.mark.anyio
async def test_chennai_flood_monitor_honest_reporting():
    """
    CRITICAL QUALITY REQUIREMENT:
    CFM does not expose an open documented public API.
    Adapter must honestly report 'FEED_UNAVAILABLE' / 'OFFLINE' rather than inventing numbers.
    """
    provider = ChennaiFloodMonitorAdapter()
    assert provider.provider_id == "chennai_flood_monitor"

    results = await provider.fetch_observations()
    assert len(results) >= 4

    poondi = next((r for r in results if "POONDI" in r.reservoir_name), None)
    assert poondi is not None
    assert poondi.full_capacity_mcft == 3231.0
    # Must NOT invent arbitrary live levels
    assert poondi.current_level_ft is None
    assert "FEED_UNAVAILABLE" in poondi.freshness_status or "OFFLINE" in poondi.freshness_status


@pytest.mark.anyio
async def test_weather_supporting_context_only():
    """
    Weather data is classified as SUPPORTING_CONTEXT_ONLY and never substituted for canal readings.
    """
    provider = OpenMeteoWeatherProvider()
    weather = await provider.fetch_current_weather(lat=10.8350, lon=78.8180, location_name="Cauvery Delta")

    assert weather.data_classification == "SUPPORTING_CONTEXT_ONLY"
    assert weather.location == "Cauvery Delta"
    assert weather.temperature_c is not None
    assert weather.retrieved_at is not None


def test_provider_registry():
    prov_tn = registry.get_reservoir_provider("tn_agriculture")
    assert prov_tn.provider_id == "tn_agriculture"

    prov_cfm = registry.get_reservoir_provider("chennai_flood_monitor")
    assert prov_cfm.provider_id == "chennai_flood_monitor"

    all_provs = registry.list_reservoir_providers()
    assert len(all_provs) >= 2
