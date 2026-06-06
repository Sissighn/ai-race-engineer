import numpy as np
import pandas as pd
import pytest
from types import SimpleNamespace

from src.data import load_data
from src.exceptions import FastF1APIError, SessionDataError, TelemetryError


RAW_LOAD_SESSION = load_data.load_session
RAW_LOAD_TELEMETRY = load_data.load_telemetry
RAW_LOAD_TELEMETRY_WITH_POSITION = load_data.load_telemetry_with_position
RAW_GET_TRACKS_FOR_YEAR = load_data.get_tracks_for_year


class _FakeEvent:
    def __init__(self, name="Monaco", year=2025):
        self._data = {"EventName": name}
        self.Year = year

    def __contains__(self, key):
        return key in self._data

    def __getitem__(self, key):
        return self._data[key]


class _FakeLaps:
    def __init__(self, empty=False, fastest=None):
        self.empty = empty
        self._fastest = fastest

    def pick_drivers(self, _driver_code):
        return self

    def pick_fastest(self):
        return self._fastest


class _FakeFastestLap:
    def __init__(self, tel=None, telemetry=None, pos_data=None):
        self._tel = tel
        self._telemetry = telemetry
        self._pos_data = pos_data

    def get_car_data(self):
        class _Car:
            def __init__(self, df):
                self._df = df

            def add_distance(self):
                return self._df.copy()

            def copy(self):
                return self._df.copy()

        return _Car(self._tel)

    def get_telemetry(self):
        if isinstance(self._telemetry, Exception):
            raise self._telemetry
        return self._telemetry.copy()

    def get_pos_data(self):
        if isinstance(self._pos_data, Exception):
            raise self._pos_data
        if self._pos_data is None:
            raise AttributeError("no pos data")
        return self._pos_data.copy()


class _FakeSession:
    def __init__(self, date, load_exception=None, laps=None):
        self.date = date
        self._load_exception = load_exception
        self.name = "Q"
        self.event = _FakeEvent(name="Monaco", year=2025)
        if laps is not None:
            self.laps = laps

    def load(self):
        if self._load_exception is not None:
            raise self._load_exception


def test_hash_session_id_variants():
    assert load_data.hash_session_id(None) == "no_session"

    s = _FakeSession(date=pd.Timestamp("2025-01-01", tz="UTC"))
    assert load_data.hash_session_id(s) == "2025_Monaco_Q"


def test_clear_specific_session_cache_handles_error(monkeypatch):
    monkeypatch.setattr(
        load_data.os.path,
        "exists",
        lambda _p: (_ for _ in ()).throw(RuntimeError("fs")),
    )
    assert load_data.clear_specific_session_cache(2025, "Monaco", "Q") is False


def test_load_session_raises_when_future_session(monkeypatch):
    future = pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=1)
    monkeypatch.setattr(
        load_data.fastf1, "get_session", lambda *_a, **_k: _FakeSession(future)
    )

    with pytest.raises(SessionDataError):
        RAW_LOAD_SESSION(2025, "Monaco", "Q")


def test_load_session_success(monkeypatch):
    past = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=1)
    sess = _FakeSession(past)
    monkeypatch.setattr(load_data.fastf1, "get_session", lambda *_a, **_k: sess)

    loaded = RAW_LOAD_SESSION(2025, "Monaco", "Q")
    assert loaded is sess


def test_load_session_cache_corruption_retry_success(monkeypatch):
    past = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=1)
    calls = {"n": 0}

    def fake_get_session(*_a, **_k):
        if calls["n"] == 0:
            calls["n"] += 1
            return _FakeSession(
                past, load_exception=Exception("dictionary changed size")
            )
        return _FakeSession(past)

    monkeypatch.setattr(load_data.fastf1, "get_session", fake_get_session)
    monkeypatch.setattr(
        load_data.fastf1,
        "Cache",
        SimpleNamespace(disable_cache=lambda: None, enable_cache=lambda _p: None),
    )

    loaded = RAW_LOAD_SESSION(2025, "Monaco", "Q")
    assert isinstance(loaded, _FakeSession)


def test_load_session_non_cache_error_raises_fastf1_error(monkeypatch):
    past = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=1)
    monkeypatch.setattr(
        load_data.fastf1,
        "get_session",
        lambda *_a, **_k: _FakeSession(past, load_exception=Exception("network down")),
    )

    with pytest.raises(FastF1APIError):
        RAW_LOAD_SESSION(2025, "Monaco", "Q")


def test_load_telemetry_none_session_returns_none():
    assert RAW_LOAD_TELEMETRY(None, "VER") is None


def test_load_telemetry_missing_laps_raises():
    sess = _FakeSession(pd.Timestamp("2025-01-01", tz="UTC"))
    if hasattr(sess, "laps"):
        delattr(sess, "laps")

    with pytest.raises(TelemetryError):
        RAW_LOAD_TELEMETRY(sess, "VER")


def test_load_telemetry_empty_or_no_fastest_returns_none():
    sess_empty = _FakeSession(
        pd.Timestamp("2025-01-01", tz="UTC"), laps=_FakeLaps(empty=True, fastest=None)
    )
    assert RAW_LOAD_TELEMETRY(sess_empty, "VER") is None

    sess_no_fastest = _FakeSession(
        pd.Timestamp("2025-01-01", tz="UTC"), laps=_FakeLaps(empty=False, fastest=None)
    )
    assert RAW_LOAD_TELEMETRY(sess_no_fastest, "VER") is None


def test_load_telemetry_success_adds_ngear():
    tel = pd.DataFrame({"Speed": [100, 120], "Distance": [0.0, 10.0]})
    fastest = _FakeFastestLap(tel=tel)
    sess = _FakeSession(
        pd.Timestamp("2025-01-01", tz="UTC"),
        laps=_FakeLaps(empty=False, fastest=fastest),
    )

    out = RAW_LOAD_TELEMETRY(sess, "VER")

    assert isinstance(out, pd.DataFrame)
    assert "nGear" in out.columns


def test_load_telemetry_with_position_handles_missing_position_data():
    fastest = _FakeFastestLap(
        tel=pd.DataFrame({"Time": pd.to_timedelta([0.0], unit="s"), "Speed": [100]}),
        telemetry=RuntimeError("no pos"),
    )
    sess = _FakeSession(
        pd.Timestamp("2025-01-01", tz="UTC"),
        laps=_FakeLaps(empty=False, fastest=fastest),
    )

    assert RAW_LOAD_TELEMETRY_WITH_POSITION(sess, "VER") is None


def test_load_telemetry_with_position_success_fills_columns():
    telemetry = pd.DataFrame(
        {
            "Time": pd.to_timedelta([0.0, 0.1, 0.2], unit="s"),
            "X": [0.0, 1.0, 2.0],
            "Y": [0.0, 1.0, 0.0],
        }
    )
    car_df = pd.DataFrame(
        {
            "Time": pd.to_timedelta([0.0, 0.1, 0.2], unit="s"),
            "Speed": [np.nan, 120.0, np.nan],
        }
    )

    fastest = _FakeFastestLap(tel=car_df, telemetry=telemetry)
    sess = _FakeSession(
        pd.Timestamp("2025-01-01", tz="UTC"),
        laps=_FakeLaps(empty=False, fastest=fastest),
    )

    out = RAW_LOAD_TELEMETRY_WITH_POSITION(sess, "VER")

    assert isinstance(out, pd.DataFrame)
    assert "Distance" in out.columns
    assert "Speed" in out.columns
    assert out["Distance"].isna().sum() == 0
    assert out["Speed"].isna().sum() == 0
    assert out["Speed"].max() <= load_data.settings.MAX_REALISTIC_SPEED


def test_load_telemetry_with_position_interpolates_impossible_speed_spikes():
    telemetry = pd.DataFrame(
        {
            "Time": pd.to_timedelta([0.0, 0.1, 0.2, 0.3], unit="s"),
            "X": [0.0, 10.0, 20.0, 30.0],
            "Y": [0.0, 5.0, 0.0, -5.0],
        }
    )
    car_df = pd.DataFrame(
        {
            "Time": pd.to_timedelta([0.0, 0.1, 0.2, 0.3], unit="s"),
            "Speed": [120.0, 1700.0, 220.0, 240.0],
        }
    )

    fastest = _FakeFastestLap(tel=car_df, telemetry=telemetry)
    sess = _FakeSession(
        pd.Timestamp("2025-01-01", tz="UTC"),
        laps=_FakeLaps(empty=False, fastest=fastest),
    )

    out = RAW_LOAD_TELEMETRY_WITH_POSITION(sess, "VER")

    assert out["Speed"].max() <= load_data.settings.MAX_REALISTIC_SPEED
    assert out["Speed"].iloc[1] == pytest.approx(170.0)


def test_load_telemetry_with_position_falls_back_to_telemetry_if_pos_data_fails():
    telemetry = pd.DataFrame(
        {
            "Time": pd.to_timedelta([0.0, 0.1, 0.2], unit="s"),
            "X": [0.0, 1.0, 2.0],
            "Y": [0.0, 1.0, 0.0],
        }
    )
    car_df = pd.DataFrame(
        {
            "Time": pd.to_timedelta([0.0, 0.1, 0.2], unit="s"),
            "Speed": [100.0, 120.0, 110.0],
        }
    )

    fastest = _FakeFastestLap(
        tel=car_df,
        telemetry=telemetry,
        pos_data=RuntimeError("pos source failed"),
    )
    sess = _FakeSession(
        pd.Timestamp("2025-01-01", tz="UTC"),
        laps=_FakeLaps(empty=False, fastest=fastest),
    )

    out = RAW_LOAD_TELEMETRY_WITH_POSITION(sess, "VER")

    assert isinstance(out, pd.DataFrame)
    assert not out.empty
    assert {"X", "Y", "Speed", "Distance"}.issubset(set(out.columns))


def test_get_tracks_for_year_handles_empty_and_success(monkeypatch):
    monkeypatch.setattr(
        load_data.fastf1, "get_event_schedule", lambda *_a, **_k: pd.DataFrame()
    )
    assert RAW_GET_TRACKS_FOR_YEAR(2025) == []

    schedule = pd.DataFrame({"Location": ["Monaco", "Monaco", " Monza ", None]})
    monkeypatch.setattr(
        load_data.fastf1, "get_event_schedule", lambda *_a, **_k: schedule
    )
    assert RAW_GET_TRACKS_FOR_YEAR(2025) == ["Monaco", "Monza"]


def test_get_tracks_for_year_exception_returns_empty(monkeypatch):
    monkeypatch.setattr(
        load_data.fastf1,
        "get_event_schedule",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("api down")),
    )
    assert RAW_GET_TRACKS_FOR_YEAR(2025) == []
