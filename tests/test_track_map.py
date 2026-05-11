import pandas as pd
import pytest

from app.components import track_map


class _DummyColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _track_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "X": [0.0, 1.0, 2.0],
            "Y": [0.0, 1.0, 0.0],
            "Speed": [100.0, 120.0, 110.0],
            "Time_s": [0.0, 0.1, 0.2],
        }
    )


def test_prepare_track_map_data_raises_on_short_series():
    with pytest.raises(ValueError):
        track_map._prepare_track_map_data(
            pd.DataFrame({"X": [0.0], "Y": [0.0], "Speed": [100.0]}),
            "speed",
        )


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
    charts = []

    monkeypatch.setattr(
        "app.components.track_map.load_telemetry_with_position",
        lambda *_a, **_k: _track_df(),
    )
    monkeypatch.setattr(
        "app.components.track_map._render_track_map_figure",
        lambda *_a, **_k: charts.append((_a, _k)),
    )
    monkeypatch.setattr(
        "app.components.track_map.st.warning", lambda *a, **k: warnings.append((a, k))
    )

    track_map.plot_track_map(
        session=object(), driver_code="VER", track="Monaco", mode="gear"
    )

    assert len(warnings) >= 1
    assert len(charts) == 1


def test_plot_track_map_comparison_uses_shared_scale(monkeypatch):
    warnings = []
    captured = []

    data = {
        "HAM": pd.DataFrame(
            {
                "X": [0.0, 1.0, 2.0],
                "Y": [0.0, 1.0, 0.0],
                "Speed": [105.0, 325.0, 210.0],
            }
        ),
        "VER": pd.DataFrame(
            {
                "X": [0.0, 1.2, 2.2],
                "Y": [0.0, 0.8, -0.1],
                "Speed": [115.0, 305.0, 220.0],
            }
        ),
    }

    monkeypatch.setattr(
        "app.components.track_map.load_telemetry_with_position",
        lambda _session, driver_code: data[driver_code],
    )

    monkeypatch.setattr(
        "app.components.track_map.st.warning", lambda *a, **k: warnings.append((a, k))
    )
    monkeypatch.setattr(
        "app.components.track_map.st.plotly_chart",
        lambda fig, **kwargs: captured.append((fig, kwargs)),
    )

    track_map.plot_track_map_comparison(
        session=object(), driver_a="HAM", driver_b="VER", track="Silverstone"
    )

    assert warnings == []
    # Single figure rendered via one st.plotly_chart call (subplots approach).
    assert len(captured) == 1

    fig, kwargs = captured[0]
    assert kwargs["use_column_width"] is True
    assert kwargs["config"]["responsive"] is True
    assert "track-map-comparison-speed-Silverstone" in kwargs["key"]

    # Shared colour scale applied to the single figure.
    assert fig.layout.coloraxis.cmin == pytest.approx(105.5)
    assert fig.layout.coloraxis.cmax == pytest.approx(324.0)

    # Both drivers produce marker traces (one per subplot).
    marker_traces = [
        trace
        for trace in fig.data
        if trace.type == "scatter" and trace.mode == "markers"
    ]
    assert len(marker_traces) == 2
    assert all(trace.marker.coloraxis == "coloraxis" for trace in marker_traces)

    # Subplot titles for both drivers.
    title_texts = [a.text for a in fig.layout.annotations]
    assert "Silverstone — HAM" in title_texts
    assert "Silverstone — VER" in title_texts


def test_track_map_hover_template_includes_value_and_unit():
    prepared = track_map._prepare_track_map_data(
        pd.DataFrame(
            {
                "X": [0.0, 1.0, 2.0],
                "Y": [0.0, 1.0, 0.0],
                "Speed": [100.0, 120.0, 110.0],
                "Distance": [0.0, 50.0, 100.0],
            }
        ),
        "speed",
    )

    traces = track_map._build_track_panel_traces(prepared)
    hover_trace = traces[1]

    assert "Value: %{marker.color:.1f} km/h" in hover_trace.hovertemplate
    assert "Distance: %{customdata[0]:.0f} m" in hover_trace.hovertemplate
    assert "Segment: %{customdata[1]:.0f}" in hover_trace.hovertemplate
    assert hover_trace.customdata.shape == (3, 2)


def test_sanitize_metric_values_clips_unrealistic_speed_spikes():
    cleaned = track_map._sanitize_metric_values([110.0, 5200.0, 315.0], "speed")

    assert cleaned[0] == 110.0
    assert cleaned[1] == 380.0
    assert cleaned[2] == 315.0
