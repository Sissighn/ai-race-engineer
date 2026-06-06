import json

import pytest

from src.infrastructure.openf1 import client


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def test_fetch_json_returns_list(monkeypatch):
    monkeypatch.setattr(
        client,
        "urlopen",
        lambda *_args, **_kwargs: _FakeResponse([{"session_key": 1}]),
    )

    assert client._fetch_json("sessions", {"session_key": "latest"}) == [
        {"session_key": 1}
    ]


def test_fetch_json_rejects_error_payload(monkeypatch):
    monkeypatch.setattr(
        client,
        "urlopen",
        lambda *_args, **_kwargs: _FakeResponse({"detail": "No results found."}),
    )

    with pytest.raises(client.OpenF1Error):
        client._fetch_json("position", {"session_key": "latest"})


def test_latest_positions_keeps_latest_record_per_driver(monkeypatch):
    monkeypatch.setattr(
        client,
        "_fetch_json",
        lambda *_args, **_kwargs: [
            {
                "date": "2026-06-06T13:00:00+00:00",
                "driver_number": 1,
                "position": 3,
            },
            {
                "date": "2026-06-06T13:01:00+00:00",
                "driver_number": 1,
                "position": 1,
            },
            {
                "date": "2026-06-06T13:01:00+00:00",
                "driver_number": 44,
                "position": 2,
            },
        ],
    )

    latest = client.get_latest_positions(123)

    assert [row["driver_number"] for row in latest] == [1, 44]
    assert [row["position"] for row in latest] == [1, 2]


def test_latest_car_snapshot_uses_latest_record(monkeypatch):
    monkeypatch.setattr(
        client,
        "_fetch_json",
        lambda *_args, **_kwargs: [
            {"date": "2026-06-06T13:00:00+00:00", "speed": 210},
            {"date": "2026-06-06T13:01:00+00:00", "speed": 250},
        ],
    )

    snapshot = client.get_latest_car_snapshot(
        123,
        1,
        session={"date_end": "2026-06-06T13:02:00+00:00"},
    )

    assert snapshot["speed"] == 250
