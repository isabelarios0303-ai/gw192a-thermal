"""Application settings, loaded from environment variables (12-factor)."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="THERMOBABY_", env_file=".env", extra="ignore")

    # --- server ---
    app_name: str = "ThermoBaby"
    debug: bool = False
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # --- security ---
    jwt_secret: str = "CHANGE-ME-IN-PRODUCTION"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 14

    # --- database --- PostgreSQL in prod, SQLite for local mode
    database_url: str = "sqlite+pysqlite:///./thermobaby.db"
    # example prod: postgresql+psycopg://user:pass@localhost:5432/thermobaby

    # --- thermal device calibration (GW192A / InfiRay family) ---
    sensor_width: int = 192
    sensor_height: int = 192
    # T(C) = raw16 / kelvin_scale - kelvin_offset, then linear trim: T*gain + offset
    kelvin_scale: float = 64.0
    kelvin_offset: float = 273.15
    calib_gain: float = 1.0
    calib_offset: float = 0.0
    emissivity: float = 0.98  # human skin

    # --- storage ---
    media_dir: str = "./media"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
