import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.logging import get_logger

logger = get_logger(__name__)

LIVE_TIMING_SIGNALR_URL = os.getenv(
    "LIVE_TIMING_SIGNALR_URL",
    "http://localhost:8765",
)
LIVE_TIMING_SIGNALR_TIMEOUT = float(os.getenv("LIVE_TIMING_SIGNALR_TIMEOUT", "2"))


class LiveTimingServiceError(RuntimeError):
    """Raised when the local SignalR live timing service is unavailable."""


def get_signalr_snapshot(base_url: str | None = None) -> dict[str, Any]:
    url = f"{(base_url or LIVE_TIMING_SIGNALR_URL).rstrip('/')}/snapshot"
    request = Request(url, headers={"User-Agent": "ai-race-engineer/0.1"})

    try:
        with urlopen(request, timeout=LIVE_TIMING_SIGNALR_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as e:
        logger.warning("SignalR live timing service unavailable", url=url, error=str(e))
        raise LiveTimingServiceError(str(e)) from e

    if not isinstance(payload, dict):
        raise LiveTimingServiceError("SignalR live timing service returned invalid data.")

    return payload
