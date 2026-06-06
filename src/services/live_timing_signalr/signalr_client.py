import logging
import os
import time
from contextlib import suppress
from threading import Event, Thread

import requests
from fastf1.internals.f1auth import get_auth_token
from signalrcore.hub_connection_builder import HubConnectionBuilder

from src.logging import get_logger

from .normalizer import LiveTimingState

logger = get_logger(__name__)

SIGNALR_CONNECTION_URL = os.getenv(
    "F1_SIGNALR_CONNECTION_URL",
    "wss://livetiming.formula1.com/signalrcore",
)
SIGNALR_NEGOTIATE_URL = os.getenv(
    "F1_SIGNALR_NEGOTIATE_URL",
    "https://livetiming.formula1.com/signalrcore/negotiate",
)

DEFAULT_TOPICS = [
    "Heartbeat",
    "DriverList",
    "ExtrapolatedClock",
    "RaceControlMessages",
    "SessionInfo",
    "SessionStatus",
    "TimingAppData",
    "TimingStats",
    "TrackStatus",
    "WeatherData",
    "Position.z",
    "CarData.z",
    "SessionData",
    "TimingData",
    "TopThree",
    "LapCount",
]


def _empty_auth_token() -> str:
    return ""


class F1SignalRWorker:
    """Background worker that consumes the F1 SignalR live timing stream."""

    def __init__(
        self,
        state: LiveTimingState,
        *,
        topics: list[str] | None = None,
        no_auth: bool | None = None,
        reconnect_delay: float | None = None,
    ):
        self.state = state
        self.topics = topics or DEFAULT_TOPICS
        self.no_auth = (
            os.getenv("F1_SIGNALR_NO_AUTH", "false").lower() == "true"
            if no_auth is None
            else no_auth
        )
        self.reconnect_delay = reconnect_delay or float(
            os.getenv("F1_SIGNALR_RECONNECT_DELAY", "5")
        )
        self._stop = Event()
        self._thread: Thread | None = None
        self._connection = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = Thread(target=self._run_forever, name="f1-signalr-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._connection is not None:
            try:
                self._connection.stop()
            except Exception:
                logger.warning("Failed to stop SignalR connection", exc_info=True)

    def _on_message(self, message) -> None:
        self.state.apply_message(message)

    def _on_open(self) -> None:
        logger.info("F1 SignalR connection established")
        self.state.mark_connected(True)
        self.state.mark_error(None)

    def _on_close(self) -> None:
        logger.info("F1 SignalR connection closed")
        self.state.mark_connected(False)

    def _build_connection(self):
        headers = {}
        response = requests.options(SIGNALR_NEGOTIATE_URL, headers=headers, timeout=10)
        if "AWSALBCORS" in response.cookies:
            headers["Cookie"] = f"AWSALBCORS={response.cookies['AWSALBCORS']}"

        options = {
            "verify_ssl": True,
            "headers": headers,
            "access_token_factory": _empty_auth_token if self.no_auth else get_auth_token,
        }

        connection = (
            HubConnectionBuilder()
            .with_url(SIGNALR_CONNECTION_URL, options=options)
            .configure_logging(logging.INFO)
            .build()
        )
        connection.on_open(self._on_open)
        connection.on_close(self._on_close)
        connection.on("feed", self._on_message)
        return connection

    def _run_once(self) -> None:
        self._connection = self._build_connection()
        self._connection.start()

        started_wait = time.time()
        while not self.state.connected and not self._stop.is_set():
            if time.time() - started_wait > 20:
                raise TimeoutError("Timed out waiting for SignalR connection.")
            time.sleep(0.1)

        self._connection.send("Subscribe", [self.topics], on_invocation=self._on_message)

        while not self._stop.is_set() and self.state.connected:
            time.sleep(0.5)

    def _run_forever(self) -> None:
        while not self._stop.is_set():
            try:
                self._run_once()
            except Exception as e:
                logger.warning("F1 SignalR worker error", error=str(e), exc_info=True)
                self.state.mark_connected(False)
                self.state.mark_error(str(e))
                if self._connection is not None:
                    with suppress(Exception):
                        self._connection.stop()

            if not self._stop.is_set():
                time.sleep(self.reconnect_delay)
