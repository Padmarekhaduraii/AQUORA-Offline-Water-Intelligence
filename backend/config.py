from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    env: str = Field(default="development", alias="AQUORA_ENV")
    host: str = Field(default="0.0.0.0", alias="AQUORA_HOST")
    port: int = Field(default=8000, alias="AQUORA_PORT")
    database_url: str = Field(default="sqlite:///./aquora_offline.db", alias="AQUORA_DATABASE_URL")
    
    # LoRa Gateway Ingestion Authentication
    gateway_api_key: str = Field(default="aquora_live_lora_secret_key_2026", alias="AQUORA_GATEWAY_API_KEY")
    
    # Telemetry and Disconnection Thresholds
    stale_sensor_timeout_seconds: int = Field(default=1800, alias="AQUORA_STALE_SENSOR_TIMEOUT_SECONDS") # 30 mins
    surge_threshold_cm: float = Field(default=15.0, alias="AQUORA_SURGE_THRESHOLD_CM") # Surge step detection in cm
    
    # Official Source URLs & Cache
    tn_agri_url: str = Field(default="https://tnagriculture.in/ARS/home/reservoir/", alias="AQUORA_TN_AGRI_URL")
    cfm_url: str = Field(default="https://chennaifloodmonitor.tn.gov.in/HomePage/Dashboard", alias="AQUORA_CFM_URL")
    official_cache_ttl_minutes: int = Field(default=60, alias="AQUORA_OFFICIAL_CACHE_TTL_MINUTES")
    http_timeout_seconds: int = Field(default=15, alias="AQUORA_HTTP_TIMEOUT_SECONDS")
    
    # Location Defaults (Grand Anicut, Tamil Nadu)
    location_name: str = Field(default="Grand Anicut - Cauvery Lower Canal Reach", alias="AQUORA_LOCATION_NAME")
    latitude: float = Field(default=10.8350, alias="AQUORA_LATITUDE")
    longitude: float = Field(default=78.8180, alias="AQUORA_LONGITUDE")
    
    # Offline Sync Settings
    sync_upstream_url: str = Field(default="https://sync.aquora.internal/api/v1/sync", alias="AQUORA_SYNC_UPSTREAM_URL")
    sync_api_key: str = Field(default="upstream_sync_token_sample", alias="AQUORA_SYNC_API_KEY")
    auto_sync_enabled: bool = Field(default=False, alias="AQUORA_AUTO_SYNC_ENABLED")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
