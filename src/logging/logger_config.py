"""
Structured Logging Configuration for AI Race Engineer.

Sets up centralized logging with file rotation, structured output,
and environment-based configuration.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional
import structlog


_LOGGING_INITIALIZED = False

# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"

# Environment-based log level
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
IS_PRODUCTION = os.getenv("ENVIRONMENT", "dev").lower() == "prod"
IS_STREAMLIT = "streamlit" in sys.modules

# Log files
LOG_FILE = LOGS_DIR / "app.log"
ERROR_LOG_FILE = LOGS_DIR / "errors.log"
DEBUG_LOG_FILE = LOGS_DIR / "debug.log"

# Rotation settings
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5


# ─────────────────────────────────────────────────────────────────────
# STRUCTLOG CONFIGURATION
# ─────────────────────────────────────────────────────────────────────


def configure_structlog():
    """Configure structlog with processors and output format."""

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            (
                structlog.processors.JSONRenderer()
                if IS_PRODUCTION
                else structlog.dev.ConsoleRenderer()
            ),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# ─────────────────────────────────────────────────────────────────────
# STANDARD LOGGING CONFIGURATION
# ─────────────────────────────────────────────────────────────────────


def setup_logging(level: str = LOG_LEVEL) -> None:
    """
    Configure standard Python logging with file and console handlers.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """

    LOGS_DIR.mkdir(exist_ok=True)

    # Convert to logging level
    log_level = getattr(logging, level, logging.INFO)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # ─────────────────────────────────────────────────────────────────
    # LOG FORMATTERS
    # ─────────────────────────────────────────────────────────────────

    # Production: JSON format
    if IS_PRODUCTION:
        formatter = logging.Formatter(
            '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s", "module": "%(module)s", "line": "%(lineno)d"}'
        )
    # Development: Colorized format
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # ─────────────────────────────────────────────────────────────────
    # CONSOLE HANDLER (always enabled in dev)
    # ─────────────────────────────────────────────────────────────────

    if not IS_STREAMLIT:  # Skip console handler in Streamlit
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # ─────────────────────────────────────────────────────────────────
    # FILE HANDLERS
    # ─────────────────────────────────────────────────────────────────

    # General application log
    app_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
    )
    app_handler.setLevel(log_level)
    app_handler.setFormatter(formatter)
    root_logger.addHandler(app_handler)

    # Error log (ERROR and above)
    error_handler = RotatingFileHandler(
        ERROR_LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    # Debug log (only in development)
    if not IS_PRODUCTION:
        debug_handler = RotatingFileHandler(
            DEBUG_LOG_FILE,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(formatter)
        root_logger.addHandler(debug_handler)


# ─────────────────────────────────────────────────────────────────────
# GET LOGGER FUNCTION
# ─────────────────────────────────────────────────────────────────────


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Structured logger bound to the given name

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started", session="Monaco", year=2024)
    """
    _ensure_logging_initialized()
    return structlog.get_logger(name)


def bind_context(**context) -> structlog.BoundLogger:
    """
    Bind context variables to the logger.

    Args:
        **context: Key-value pairs to bind to logs

    Example:
        >>> logger = get_logger(__name__)
        >>> logger = logger.bind(driver="VER", session="Q")
        >>> logger.info("Processing complete")
    """
    _ensure_logging_initialized()
    return structlog.get_logger().bind(**context)


# ─────────────────────────────────────────────────────────────────────
# INITIALIZATION
# ─────────────────────────────────────────────────────────────────────


def initialize_logging(level: Optional[str] = None) -> None:
    """
    Initialize all logging infrastructure.

    Should be called once at application startup.

    Args:
        level: Optional log level override
    """
    global _LOGGING_INITIALIZED
    if _LOGGING_INITIALIZED:
        return

    setup_logging(level or LOG_LEVEL)
    configure_structlog()
    _LOGGING_INITIALIZED = True


def _ensure_logging_initialized() -> None:
    if not _LOGGING_INITIALIZED:
        initialize_logging()
