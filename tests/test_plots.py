import pandas as pd

from app.components import plots


def _sample_delta_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Corner": [1, 2],
            "TimeLoss": [0.2, -0.1],
            "Delta_ApexSpeed": [-2.0, 1.0],
            "Delta_ExitSpeed": [-1.0, 2.0],
            "CornerType": ["Low Speed", "High Speed"],
        }
    )


def _sample_tel() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Distance": [0, 50, 100],
            "Speed": [120, 140, 130],
            "Brake": [0, 20, 0],
            "Throttle": [100, 60, 100],
            "nGear": [4, 5, 4],
        }
    )


def test_safe_plotly_chart_handles_render_error(monkeypatch):
    warned = {"value": False}

    monkeypatch.setattr(
        "app.components.plots.st.plotly_chart",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(
        "app.components.plots.st.warning",
        lambda *_a, **_k: warned.__setitem__("value", True),
    )

    fig = plots.px.bar(_sample_delta_df(), x="Corner", y="TimeLoss")
    plots._safe_plotly_chart(fig, key="x", context="test")

    assert warned["value"] is True


def test_plot_functions_render_when_data_available(monkeypatch):
    chart_calls = []
    info_calls = []

    monkeypatch.setattr(
        "app.components.plots.st.plotly_chart",
        lambda *a, **k: chart_calls.append((a, k)),
    )
    monkeypatch.setattr(
        "app.components.plots.st.info", lambda *a, **k: info_calls.append((a, k))
    )

    df = _sample_delta_df()
    tel_a = _sample_tel()
    tel_b = _sample_tel()

    plots.plot_time_loss_bar(df, "VER", "HAM")
    plots.plot_speed_deltas(df, "VER", "HAM")
    plots.plot_speed_profile(tel_a, tel_b, "VER", "HAM")
    plots.plot_brake_throttle(tel_a, tel_b, "VER", "HAM")
    plots.plot_gear_usage(tel_a, "VER")
    plots.plot_apex_speed_share(df, "VER", "HAM")
    plots.plot_exit_speed_delta(df, "VER", "HAM")
    plots.plot_corner_type_performance(df[["CornerType", "TimeLoss"]])

    dna_df = pd.DataFrame(
        {
            "Metric": ["Aggressiveness", "Smoothness"],
            "VER": [80, 70],
            "HAM": [75, 72],
        }
    )
    plots.plot_driver_dna(dna_df, "VER", "HAM")

    assert len(chart_calls) >= 8
    assert info_calls == []


def test_plot_time_loss_bar_uses_signed_bar_chart(monkeypatch):
    captured = []

    monkeypatch.setattr(
        "app.components.plots.st.plotly_chart",
        lambda fig, **kwargs: captured.append((fig, kwargs)),
    )

    df = pd.DataFrame(
        {
            "Corner": [1, 2, 3],
            "TimeLoss": [0.120, -0.080, 0.005],  # A gains, B gains, nearly equal
        }
    )

    plots.plot_time_loss_bar(df, "HAM", "VER")

    assert len(captured) == 1
    fig, kwargs = captured[0]

    assert kwargs["key"] == "time_loss_bar"
    assert fig.layout.yaxis.title.text == "Δ Time (HAM − VER) [s]"

    title_text = fig.layout.title.text
    assert "HAM gains" in title_text
    assert "VER gains" in title_text
    assert "Nearly equal" in title_text

    trace_names = {trace.name for trace in fig.data}
    assert "HAM gains" in trace_names
    assert "VER gains" in trace_names
    assert "Nearly equal" in trace_names

    # Circle-open marker must appear for the nearly-equal corner
    scatter_traces = [t for t in fig.data if t.type == "scatter"]
    assert len(scatter_traces) == 1
    assert scatter_traces[0].name == "Nearly equal marker"
    assert list(scatter_traces[0].x) == ["Corner 3"]


def test_plot_driver_dna_uses_grouped_horizontal_bar_with_transparency(monkeypatch):
    captured = []

    monkeypatch.setattr(
        "app.components.plots.st.plotly_chart",
        lambda fig, **kwargs: captured.append((fig, kwargs)),
    )

    dna_df = pd.DataFrame(
        {
            "Metric": ["Aggressiveness", "Cornering", "Smoothness"],
            "HAM": [82.3, 76.1, 69.5],
            "VER": [85.1, 79.0, 64.2],
        }
    )

    plots.plot_driver_dna(dna_df, "HAM", "VER")

    assert len(captured) == 1
    fig, kwargs = captured[0]

    assert kwargs["key"] == "driver_dna_radar"
    assert all(trace.type == "bar" for trace in fig.data)
    assert fig.layout.xaxis.title.text == "Telemetry-Derived Heuristic Score [0-100]"
    assert fig.layout.xaxis.range == (0, 100)

    title_text = fig.layout.title.text
    assert "Driver Style Heuristic Score Comparison" in title_text
    assert "Telemetry-derived heuristic scores" in title_text
    assert "HAM vs VER" in title_text

    hover = fig.data[0].hovertemplate
    assert "Meaning:" in hover
    assert "Note:" not in hover


def test_plot_apex_speed_share_uses_signed_bar_chart(monkeypatch):
    captured = []

    monkeypatch.setattr(
        "app.components.plots.st.plotly_chart",
        lambda fig, **kwargs: captured.append((fig, kwargs)),
    )

    df = _sample_delta_df().assign(
        ApexSpeed_A=[135.0, 142.0],
        ApexSpeed_B=[137.0, 141.0],
    )

    plots.plot_apex_speed_share(df, "VER", "NOR")

    assert len(captured) == 1

    fig, kwargs = captured[0]
    assert kwargs["key"] == "apex_share"
    assert all(trace.type == "bar" for trace in fig.data)
    assert fig.layout.yaxis.title.text == "Δ Apex Speed (VER - NOR) [km/h]"
    title_text = fig.layout.title.text
    assert "VER faster" in title_text
    assert "NOR faster" in title_text
    assert "Nearly equal" in title_text

    x_values = {x for trace in fig.data for x in trace.x}
    assert {"Corner 1", "Corner 2"}.issubset(x_values)

    trace_names = {trace.name for trace in fig.data}
    assert "VER faster" in trace_names
    assert "NOR faster" in trace_names


def test_plot_apex_speed_share_legend_is_always_complete(monkeypatch):
    captured = []

    monkeypatch.setattr(
        "app.components.plots.st.plotly_chart",
        lambda fig, **kwargs: captured.append((fig, kwargs)),
    )

    # Only negative deltas -> data contains only "NOR faster"
    df = pd.DataFrame(
        {
            "Corner": [1, 2, 3],
            "Delta_ApexSpeed": [-1.5, -2.0, -0.5],
        }
    )

    plots.plot_apex_speed_share(df, "VER", "NOR")

    assert len(captured) == 1
    fig, _kwargs = captured[0]
    trace_names = {trace.name for trace in fig.data}

    assert "VER faster" in trace_names
    assert "NOR faster" in trace_names
    assert "Nearly equal" in trace_names


def test_plot_apex_speed_share_shows_nearly_equal_markers(monkeypatch):
    captured = []

    monkeypatch.setattr(
        "app.components.plots.st.plotly_chart",
        lambda fig, **kwargs: captured.append((fig, kwargs)),
    )

    df = pd.DataFrame(
        {
            "Corner": [1, 2, 3],
            "Delta_ApexSpeed": [0.0, 0.05, -2.0],
        }
    )

    plots.plot_apex_speed_share(df, "VER", "NOR")

    assert len(captured) == 1
    fig, _kwargs = captured[0]

    scatter_traces = [trace for trace in fig.data if trace.type == "scatter"]
    assert len(scatter_traces) == 1
    marker_trace = scatter_traces[0]

    assert marker_trace.name == "Nearly equal marker"
    assert all(y == 0 for y in marker_trace.y)
    assert set(marker_trace.x) == {"Corner 1", "Corner 2"}


def test_plot_exit_speed_delta_uses_signed_bar_chart(monkeypatch):
    captured = []

    monkeypatch.setattr(
        "app.components.plots.st.plotly_chart",
        lambda fig, **kwargs: captured.append((fig, kwargs)),
    )

    df = _sample_delta_df()

    plots.plot_exit_speed_delta(df, "VER", "NOR")

    assert len(captured) == 1
    fig, kwargs = captured[0]

    assert kwargs["key"] == "exit_speed_delta"
    assert fig.layout.yaxis.title.text == "Δ Exit Speed (VER - NOR) [km/h]"
    title_text = fig.layout.title.text
    assert "VER faster" in title_text
    assert "NOR faster" in title_text
    assert "Nearly equal" in title_text


def test_plot_speed_deltas_uses_signed_semantics(monkeypatch):
    captured = []

    monkeypatch.setattr(
        "app.components.plots.st.plotly_chart",
        lambda fig, **kwargs: captured.append((fig, kwargs)),
    )

    df = _sample_delta_df()

    plots.plot_speed_deltas(df, "VER", "NOR")

    assert len(captured) == 1
    fig, kwargs = captured[0]

    assert kwargs["key"] == "speed_deltas"
    assert len(fig.data) == 2
    assert fig.data[0].name == "Apex Speed Delta"
    assert fig.data[1].name == "Exit Speed Delta"
    assert (
        fig.layout.title.text
        == "Speed Delta Comparison by Corner<br><sup>Signed Δ Speed (VER - NOR)</sup>"
    )
    assert fig.layout.yaxis.title.text == "Δ Apex Speed (VER - NOR) [km/h]"
    assert fig.layout.yaxis2.title.text == "Δ Exit Speed (VER - NOR) [km/h]"
    assert any(
        "Positive: VER faster | Negative: NOR faster | 0: effectively equal" in ann.text
        for ann in fig.layout.annotations
    )

    x_values = {x for trace in fig.data for x in trace.x}
    assert {"Corner 1", "Corner 2"}.issubset(x_values)


def test_plot_speed_deltas_shows_nearly_equal_markers(monkeypatch):
    captured = []

    monkeypatch.setattr(
        "app.components.plots.st.plotly_chart",
        lambda fig, **kwargs: captured.append((fig, kwargs)),
    )

    df = pd.DataFrame(
        {
            "Corner": [1, 2, 3],
            "Delta_ApexSpeed": [0.0, -2.0, 0.05],
            "Delta_ExitSpeed": [0.02, 1.2, 0.0],
        }
    )

    plots.plot_speed_deltas(df, "VER", "NOR")

    assert len(captured) == 1
    fig, _kwargs = captured[0]

    scatter_traces = [trace for trace in fig.data if trace.type == "scatter"]
    assert len(scatter_traces) == 2


def test_plot_functions_show_info_on_missing_data(monkeypatch):
    info_calls = []
    monkeypatch.setattr(
        "app.components.plots.st.info", lambda *a, **k: info_calls.append((a, k))
    )

    plots.plot_time_loss_bar(pd.DataFrame())
    plots.plot_speed_deltas(pd.DataFrame(), "A", "B")
    plots.plot_speed_profile(pd.DataFrame(), pd.DataFrame(), "A", "B")
    plots.plot_brake_throttle(pd.DataFrame(), pd.DataFrame(), "A", "B")
    plots.plot_gear_usage(pd.DataFrame(), "A")
    plots.plot_driver_dna(pd.DataFrame(), "A", "B")
    plots.plot_corner_type_performance(pd.DataFrame())

    assert len(info_calls) >= 7
