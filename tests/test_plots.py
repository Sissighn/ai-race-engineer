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

    plots.plot_time_loss_bar(df)
    plots.plot_speed_deltas(df, "VER", "HAM")
    plots.plot_speed_profile(tel_a, tel_b, "VER", "HAM")
    plots.plot_brake_throttle(tel_a, tel_b, "VER", "HAM")
    plots.plot_gear_usage(tel_a, "VER")
    plots.plot_apex_speed_share(df)
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
