import json
import os
import signal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event
from urllib.parse import urlparse

from src.logging import get_logger, initialize_logging

from .normalizer import LiveTimingState
from .signalr_client import F1SignalRWorker

initialize_logging()
logger = get_logger(__name__)


class LiveTimingHTTPHandler(BaseHTTPRequestHandler):
    state: LiveTimingState

    def log_message(self, format, *args):  # noqa: A002
        logger.debug("Live timing HTTP request", message=format % args)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")

    def _send_json(self, status: int, payload: dict | list) -> None:
        body = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        snapshot = self.state.snapshot()

        if path == "/health":
            self._send_json(
                200 if snapshot["connected"] or snapshot["message_count"] > 0 else 503,
                {
                    "connected": snapshot["connected"],
                    "healthy": snapshot["healthy"],
                    "message_count": snapshot["message_count"],
                    "seconds_since_last_message": snapshot["seconds_since_last_message"],
                    "error": snapshot["error"],
                },
            )
        elif path == "/snapshot":
            self._send_json(200, snapshot)
        elif path == "/drivers":
            self._send_json(200, snapshot["drivers"])
        elif path == "/timing":
            self._send_json(200, snapshot["timing"])
        elif path == "/race-control":
            self._send_json(200, snapshot["race_control"])
        else:
            self._send_json(
                404,
                {
                    "error": "not found",
                    "routes": ["/health", "/snapshot", "/drivers", "/timing", "/race-control"],
                },
            )


def run_server() -> None:
    host = os.getenv("F1_SIGNALR_SERVICE_HOST", "0.0.0.0")
    port = int(os.getenv("F1_SIGNALR_SERVICE_PORT", "8765"))

    state = LiveTimingState()
    worker = F1SignalRWorker(state)
    worker.start()

    LiveTimingHTTPHandler.state = state
    server = ThreadingHTTPServer((host, port), LiveTimingHTTPHandler)
    server.timeout = 1.0
    stop_event = Event()

    def shutdown(_signum=None, _frame=None):
        logger.info("Stopping F1 SignalR live timing service")
        worker.stop()
        stop_event.set()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    logger.info("F1 SignalR live timing service started", host=host, port=port)
    while not stop_event.is_set():
        server.handle_request()
    server.server_close()


if __name__ == "__main__":
    run_server()
