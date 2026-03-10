import pandas as pd
import pytest

from app.components import track_map


def _track_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "X": [0.0, 1.0, 2.0],
            "Y": [0.0, 1.0, 0.0],
            "Speed": [100.0, 120.0, 110.0],
            "Time_s": [0.0, 0.1, 0.2],
        }
    )


def test_line_heatmap_dark_raises_on_short_series():
    fig, ax = track_map.plt.subplots()
    with pytest.raises(ValueError):
        track_map._line_heatmap_dark([0], [0], [100], ax, fig)
    track_map.plt.close(fig)


def test_show_track_outline_svg_missing(monkeypatch):
    info_calls = []
    monkeypatch.setattr("app.components.track_map.os.path.exists", lambda _p: False)
    monkeypatch.setattr(
        "app.components.track_map.st.info", lambda *a, **k: info_calls.append((a, k))
    )

    track_map.show_track_outline_svg("Monaco")

    assert len(info_calls) == 1


def test_plot_track_map_handles_missing_telemetry(monkeypatch):
    warnings = []
    monkeypatch.setattr(
        "app.components.track_map.load_telemetry_with_position",
        lambda *_a, **_k: pd.DataFrame(),
    )
    monkeypatch.setattr(
        "app.components.track_map.st.warning", lambda *a, **k: warnings.append((a, k))
    )

    track_map.plot_track_map(session=object(), driver_code="VER", track="Monaco")

    assert len(warnings) == 1


def test_plot_track_map_handles_missing_required_columns(monkeypatch):
    errors = []
    monkeypatch.setattr(
        "app.components.track_map.load_telemetry_with_position",
        lambda *_a, **_k: pd.DataFrame({"X": [1], "Y": [2]}),
    )
    monkeypatch.setattr(
        "app.components.track_map.st.error", lambda *a, **k: errors.append((a, k))
    )

    track_map.plot_track_map(session=object(), driver_code="VER", track="Monaco")

    assert len(errors) == 1


def test_plot_track_map_renders_and_warns_for_unsupported_mode(monkeypatch):
    warnings = []
    pyplots = []

    monkeypatch.setattr(
        "app.components.track_map.load_telemetry_with_position",
        lambda *_a, **_k: _track_df(),
    )
    monkeypatch.setattr(
        "app.components.track_map._line_heatmap_dark", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        "app.components.track_map.st.warning", lambda *a, **k: warnings.append((a, k))
    )
    monkeypatch.setattr(
        "app.components.track_map.st.pyplot", lambda *a, **k: pyplots.append((a, k))
    )

    track_map.plot_track_map(
        session=object(), driver_code="VER", track="Monaco", mode="gear"
    )

    assert len(warnings) >= 1
    assert len(pyplots) == 1
