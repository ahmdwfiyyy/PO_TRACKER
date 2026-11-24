"""App settings, read from environment variables (see .env.example)."""
from datetime import date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Carsem PO Tracker"
    secret_key: str = "change-me"
    token_hours: int = 8
    database_url: str = "postgresql+psycopg://po_tracker:po_tracker@localhost:5432/po_tracker"
    test_database_url: str = "postgresql+psycopg://po_tracker:po_tracker@localhost:5432/po_tracker_test"
    seed_password: str = "Password123!"
    upload_dir: str = "uploads"
    max_upload_mb: int = 10
    min_password_length: int = 8
    # Business timezone: decides what "today" is for overdue checks
    app_timezone: str = "Asia/Kuala_Lumpur"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def today() -> date:
    """Today's date in Carsem's timezone (not the server's)."""
    return datetime.now(ZoneInfo(get_settings().app_timezone)).date()
