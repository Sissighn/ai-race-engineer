"""
Application Settings & Configuration Management.

Uses environment variables with sensible defaults.
Supports .env file loading for local development.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load .env file if it exists
ENV_FILE = Path(__file__).parent.parent.parent / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)


class Settings:
    """Application configuration settings."""

    # ─────────────────────────────────────────────────────────────────
    # ENVIRONMENT
    # ─────────────────────────────────────────────────────────────────

    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = ENVIRONMENT != "production"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "DEBUG" if DEBUG else "INFO")

    # ─────────────────────────────────────────────────────────────────
    # PATHS
    # ─────────────────────────────────────────────────────────────────

    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    CACHE_DIR: Path = PROJECT_ROOT / "cache"
    LOGS_DIR: Path = PROJECT_ROOT / "logs"

    # Ensure directories exist
    DATA_DIR.mkdir(exist_ok=True)
    CACHE_DIR.mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)

    # ─────────────────────────────────────────────────────────────────
    # FASTF1 API SETTINGS
    # ─────────────────────────────────────────────────────────────────

    FASTF1_CACHE_PATH: str = str(CACHE_DIR)
    FASTF1_CACHE_ENABLED: bool = (
        os.getenv("FASTF1_CACHE_ENABLED", "true").lower() == "true"
    )
    FASTF1_REQUEST_TIMEOUT: int = int(os.getenv("FASTF1_REQUEST_TIMEOUT", "30"))

    # ─────────────────────────────────────────────────────────────────
    # STREAMLIT SETTINGS
    # ─────────────────────────────────────────────────────────────────

    STREAMLIT_LOGGER_LEVEL: str = os.getenv("STREAMLIT_LOGGER_LEVEL", "warning")

    # ─────────────────────────────────────────────────────────────────
    # CACHE & PERFORMANCE
    # ─────────────────────────────────────────────────────────────────

    # Session cache TTL in seconds
    SESSION_CACHE_TTL: int = int(os.getenv("SESSION_CACHE_TTL", "3600"))
    # Telemetry cache TTL in seconds
    TELEMETRY_CACHE_TTL: int = int(os.getenv("TELEMETRY_CACHE_TTL", "7200"))

    # ─────────────────────────────────────────────────────────────────
    # DATA VALIDATION
    # ─────────────────────────────────────────────────────────────────

    # Minimum samples for valid telemetry segment
    MIN_TELEMETRY_SAMPLES: int = 10
    # Maximum speed (km/h) - realistic limit for F1
    MAX_REALISTIC_SPEED: int = 380
    # Minimum speed (km/h) - ignore noise
    MIN_REALISTIC_SPEED: int = 0

    # ─────────────────────────────────────────────────────────────────
    # CORNER DETECTION
    # ─────────────────────────────────────────────────────────────────

    # Prominence threshold for corner detection
    CORNER_PROMINENCE: int = int(os.getenv("CORNER_PROMINENCE", "5"))
    # Window size for corner segmentation
    CORNER_WINDOW: int = int(os.getenv("CORNER_WINDOW", "40"))

    # ─────────────────────────────────────────────────────────────────
    # CLASS METHODS
    # ─────────────────────────────────────────────────────────────────

    @classmethod
    def get_setting(cls, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a setting by key with environment fallback.

        Args:
            key: Setting name
            default: Default value if not found

        Returns:
            Setting value or default
        """
        return os.getenv(key, default)

    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production."""
        return cls.ENVIRONMENT.lower() == "production"

    @classmethod
    def is_development(cls) -> bool:
        """Check if running in development."""
        return cls.ENVIRONMENT.lower() in ("development", "dev")


# Global settings instance
settings = Settings()
