# app/components/track_map.py

import os
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from matplotlib.colors import LinearSegmentedColormap
from plotly.subplots import make_subplots

from src.data.load_data import load_telemetry_with_position
from src.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------
# GLOBAL DARK THEME COLORS
# ---------------------------------------------------------
DARK_BG = "#141414"
DARK_PAPER = "#191919"
TEXT_COLOR = "#FFFFFF"
SUBTLE_TEXT = "#B8BEC8"
OUTLINE_COLOR = "#3A404B"
START_FINISH_COLOR = "#FFFFFF"


def _dark_pastel_speed_cmap():
    colors = [
        (0.45, 0.76, 1.00),
        (0.64, 0.56, 0.98),
        (0.93, 0.66, 0.83),
        (1.00, 0.86, 0.52),
    ]
    return LinearSegmentedColormap.from_list("dark_pastel_speed", colors)


def _dark_throttle_cmap():
    colors = [
        (0.20, 0.35, 0.28),
        (0.39, 0.74, 0.55),
        (0.71, 0.94, 0.72),
        (0.98, 0.98, 0.72),
    ]
    return LinearSegmentedColormap.from_list("dark_throttle", colors)


def _dark_brake_cmap():
    colors = [
        (0.23, 0.28, 0.38),
        (0.55, 0.70, 0.95),
        (0.99, 0.77, 0.55),
        (1.00, 0.56, 0.56),
    ]
    return LinearSegmentedColormap.from_list("dark_brake", colors)


def _matplotlib_cmap_to_plotly(cmap, steps: int = 12) -> list[list[Any]]:
    return [
        [i / (steps - 1), f"rgb({int(r*255)}, {int(g*255)}, {int(b*255)})"]
        for i, (r, g, b, _a) in enumerate(cmap(np.linspace(0, 1, steps)))
    ]


TRACK_MAP_METRICS = {
    "speed": {
        "column": "Speed",
        "label": "Speed",
        "unit": "km/h",
        "title": "Track Speed Maps",
        "description": "Fastest-lap track position colored by speed.",
        "valid_range": (0.0, 380.0),
        "cmap": _dark_pastel_speed_cmap(),
    },
    "throttle": {
        "column": "Throttle",
        "label": "Throttle",
        "unit": "%",
        "title": "Track Throttle Maps",
        "description": "Fastest-lap track position colored by throttle application.",
        "valid_range": (0.0, 100.0),
        "cmap": _dark_throttle_cmap(),
    },
    "brake": {
        "column": "Brake",
        "label": "Brake",
        "unit": "%",
        "title": "Track Brake Maps",
        "description": "Fastest-lap track position colored by brake application.",
        "valid_range": (0.0, 100.0),
        "cmap": _dark_brake_cmap(),
    },
}


def _resolve_metric(mode: str) -> tuple[str, dict, bool]:
    metric_key = str(mode or "speed").strip().lower()
    if metric_key not in TRACK_MAP_METRICS:
        return "speed", TRACK_MAP_METRICS["speed"], True
    return metric_key, TRACK_MAP_METRICS[metric_key], False


def _sanitize_metric_values(values, metric_key: str) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    values[~np.isfinite(values)] = np.nan

    lo, hi = TRACK_MAP_METRICS[metric_key]["valid_range"]
    values = np.clip(values, lo, hi)

    if np.all(np.isnan(values)):
        raise ValueError("Track-map metric contains no valid values.")

    cleaned = pd.Series(values).interpolate(limit_direction="both").to_numpy()
    if np.all(np.isnan(cleaned)):
        raise ValueError("Track-map metric interpolation failed.")

    return cleaned


def _prepare_track_map_data(tel: pd.DataFrame, metric_key: str) -> dict:
    metric_cfg = TRACK_MAP_METRICS[metric_key]
    required_cols = ["X", "Y", metric_cfg["column"]]

    for col in required_cols:
        if col not in tel.columns:
            raise KeyError(col)

    work = tel[required_cols].copy()
    work = work.replace([np.inf, -np.inf], np.nan).dropna(subset=["X", "Y"])
    if len(work) < 2:
        raise ValueError("Telemetry too short for track map.")

    x = work["X"].astype(float).to_numpy()
    y = work["Y"].astype(float).to_numpy()
    values = _sanitize_metric_values(work[metric_cfg["column"]], metric_key)
    if "Distance" in tel.columns:
        distance = (
            tel.loc[work.index, "Distance"]
            .astype(float)
            .interpolate(limit_direction="both")
            .to_numpy()
        )
    else:
        distance = np.arange(len(work), dtype=float)

    segment_index = np.arange(len(work), dtype=int)

    return {
        "x": x,
        "y": y,
        "values": values,
        "distance": distance,
        "segment_index": segment_index,
        "metric_cfg": metric_cfg,
    }


def _compute_shared_scale(
    value_arrays: list[np.ndarray], metric_key: str
) -> tuple[float, float]:
    metric_cfg = TRACK_MAP_METRICS[metric_key]
    lo_bound, hi_bound = metric_cfg["valid_range"]

    combined = np.concatenate(
        [
            arr[np.isfinite(arr)]
            for arr in value_arrays
            if arr is not None and len(arr) > 0
        ]
    )
    if combined.size == 0:
        return lo_bound, hi_bound

    vmin = float(np.nanpercentile(combined, 1))
    vmax = float(np.nanpercentile(combined, 99))
    vmin = max(lo_bound, min(vmin, hi_bound))
    vmax = max(lo_bound, min(vmax, hi_bound))

    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
        vmin = float(np.nanmin(combined))
        vmax = float(np.nanmax(combined))

    if vmax <= vmin:
        pad = max(1.0, 0.05 * max(abs(vmin), 1.0))
        vmin -= pad
        vmax += pad

    return max(lo_bound, vmin), min(hi_bound, vmax)


def _build_track_panel_traces(
    prepared: dict, coloraxis: str = "coloraxis"
) -> list[go.Scatter]:
    x = prepared["x"]
    y = prepared["y"]
    values = prepared["values"]
    distance = prepared["distance"]
    segment_index = prepared["segment_index"]
    metric_cfg = prepared["metric_cfg"]

    hover_custom = np.column_stack((distance, segment_index))

    return [
        go.Scatter(
            x=x,
            y=y,
            mode="lines",
            line=dict(color=OUTLINE_COLOR, width=10),
            hoverinfo="skip",
            showlegend=False,
        ),
        go.Scatter(
            x=x,
            y=y,
            mode="markers",
            marker=dict(
                size=7,
                color=values,
                coloraxis=coloraxis,
                opacity=0.98,
            ),
            customdata=hover_custom,
            hovertemplate=(
                f"<b>{metric_cfg['label']}</b><br>"
                + f"Value: %{{marker.color:.1f}} {metric_cfg['unit']}<br>"
                + "Distance: %{customdata[0]:.0f} m<br>"
                + "Segment: %{customdata[1]:.0f}"
                + "<extra></extra>"
            ),
            showlegend=False,
        ),
        go.Scatter(
            x=[x[0]],
            y=[y[0]],
            mode="markers+text",
            marker=dict(
                size=10, color=START_FINISH_COLOR, line=dict(color="#111111", width=1)
            ),
            text=["S/F"],
            textposition="middle right",
            textfont=dict(size=10, color=TEXT_COLOR),
            hovertemplate="<b>Start / Finish</b><extra></extra>",
            showlegend=False,
        ),
    ]


def _create_track_map_figure(
    track: str,
    driver_code: str,
    prepared: dict,
    metric_key: str,
    *,
    vmin: float,
    vmax: float,
    show_colorbar: bool,
) -> go.Figure:
    metric_cfg = TRACK_MAP_METRICS[metric_key]
    fig = go.Figure()

    for trace in _build_track_panel_traces(prepared):
        fig.add_trace(trace)

    fig.update_layout(
        paper_bgcolor=DARK_PAPER,
        plot_bgcolor=DARK_PAPER,
        font=dict(color=TEXT_COLOR),
        margin=dict(l=10, r=40 if not show_colorbar else 76, t=52, b=10),
        hovermode="closest",
        hoverlabel=dict(bgcolor="#22252B", font=dict(color=TEXT_COLOR, size=12)),
        title=dict(
            text=f"{track} — {driver_code}",
            x=0.5,
            xanchor="center",
            y=0.97,
            yanchor="top",
            font=dict(size=12, color=TEXT_COLOR),
        ),
        coloraxis=dict(
            colorscale=_matplotlib_cmap_to_plotly(metric_cfg["cmap"]),
            cmin=vmin,
            cmax=vmax,
            colorbar=(
                dict(
                    title=dict(
                        text=f"{metric_cfg['label']} [{metric_cfg['unit']}]",
                        font=dict(color=TEXT_COLOR, size=11),
                    ),
                    tickfont=dict(color=TEXT_COLOR, size=10),
                    thickness=16,
                    len=0.82,
                    x=1.02,
                    y=0.5,
                    outlinecolor=TEXT_COLOR,
                    bgcolor=DARK_PAPER,
                )
                if show_colorbar
                else dict(
                    thickness=0,
                    len=0,
                    outlinewidth=0,
                    tickfont=dict(color=TEXT_COLOR, size=1),
                )
            ),
        ),
        showlegend=False,
    )
    fig.update_xaxes(visible=False, showgrid=False, zeroline=False)
    fig.update_yaxes(
        visible=False,
        showgrid=False,
        zeroline=False,
        scaleanchor="x",
        scaleratio=1,
    )

    return fig


def _render_track_map_figure(
    track: str, panels: list[tuple[str, dict]], metric_key: str
) -> None:
    value_arrays = [prepared["values"] for _driver, prepared in panels]
    vmin, vmax = _compute_shared_scale(value_arrays, metric_key)

    if len(panels) == 1:
        driver_code, prepared = panels[0]
        fig = _create_track_map_figure(
            track,
            driver_code,
            prepared,
            metric_key,
            vmin=vmin,
            vmax=vmax,
            show_colorbar=True,
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
            key=f"track-map-{metric_key}-{track}-{driver_code}",
            config={
                "displayModeBar": False,
                "responsive": True,
                "scrollZoom": False,
            },
        )
        return

    columns = st.columns(len(panels), gap="medium")
    for idx, ((driver_code, prepared), column) in enumerate(zip(panels, columns)):
        fig = _create_track_map_figure(
            track,
            driver_code,
            prepared,
            metric_key,
            vmin=vmin,
            vmax=vmax,
            show_colorbar=idx == len(panels) - 1,
        )
        with column:
            st.plotly_chart(
                fig,
                use_container_width=True,
                key=f"track-map-{metric_key}-{track}-{driver_code}-{idx}",
                config={
                    "displayModeBar": False,
                    "responsive": True,
                    "scrollZoom": False,
                },
            )


def show_track_outline_svg(track: str):
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    svg_path = os.path.join(
        project_root, "app", "assets", "tracks", f"{track.lower()}.svg"
    )

    if os.path.exists(svg_path):
        st.image(svg_path, width="stretch")
    else:
        logger.info("Track outline SVG not found", track=track, svg_path=svg_path)
        st.info(f"No SVG outline found for {track}")


def plot_track_map(session, driver_code: str, track: str, mode="speed"):
    logger.debug(
        "Plotting single track map", driver_code=driver_code, track=track, mode=mode
    )

    metric_key, _metric_cfg, used_fallback = _resolve_metric(mode)
    tel = load_telemetry_with_position(session, driver_code)

    if tel is None or tel.empty:
        logger.warning(
            "No telemetry for track map", driver_code=driver_code, track=track
        )
        st.warning(f"No telemetry with position data for {driver_code}.")
        return

    if used_fallback:
        logger.warning("Unsupported track map mode, falling back to speed", mode=mode)
        st.warning(f"Mode '{mode}' not implemented. Using Speed instead.")

    try:
        prepared = _prepare_track_map_data(tel, metric_key)
        _render_track_map_figure(track, [(driver_code, prepared)], metric_key)
    except KeyError as missing_col:
        logger.error(
            "Telemetry missing required track-map column",
            missing_column=str(missing_col),
            driver_code=driver_code,
            track=track,
        )
        st.error(f"Telemetry missing '{missing_col.args[0]}' for track map.")
    except Exception as e:
        logger.error("Track map draw error", error=str(e), exc_info=True)
        st.error(f"Track map draw error: {e}")


def plot_track_map_comparison(
    session,
    driver_a: str,
    driver_b: str,
    track: str,
    metric: str = "speed",
):
    logger.debug(
        "Plotting track map comparison",
        driver_a=driver_a,
        driver_b=driver_b,
        track=track,
        metric=metric,
    )

    metric_key, metric_cfg, used_fallback = _resolve_metric(metric)
    if used_fallback:
        logger.warning(
            "Unsupported track map metric, falling back to speed", metric=metric
        )
        st.warning(f"Metric '{metric}' not implemented. Using Speed instead.")

    prepared_by_driver: dict[str, dict] = {}
    missing_drivers: list[str] = []
    prepare_errors: dict[str, str] = {}

    for driver_code in [driver_a, driver_b]:
        tel = load_telemetry_with_position(session, driver_code)
        if tel is None or tel.empty:
            missing_drivers.append(driver_code)
            continue

        try:
            prepared = _prepare_track_map_data(tel, metric_key)
            prepared_by_driver[driver_code] = prepared
        except KeyError as missing_col:
            logger.error(
                "Telemetry missing required comparison track-map column",
                missing_column=str(missing_col),
                driver_code=driver_code,
                track=track,
                metric=metric_cfg["label"],
            )
            prepare_errors[driver_code] = (
                f"Telemetry missing '{missing_col.args[0]}' for {driver_code} track map."
            )
        except Exception as e:
            logger.error(
                "Track map comparison draw error",
                driver_code=driver_code,
                error=str(e),
                exc_info=True,
            )
            prepare_errors[driver_code] = f"Track map draw error for {driver_code}: {e}"

    if missing_drivers:
        st.warning(
            f"No telemetry with position data for: {', '.join(missing_drivers)}."
        )

    if not prepared_by_driver:
        # If no panel is renderable, still surface specific per-driver errors.
        for driver_code in [driver_a, driver_b]:
            if driver_code in prepare_errors:
                st.error(prepare_errors[driver_code])
        return

    # --- Build a single Plotly figure with two side-by-side subplots ---
    # Using make_subplots avoids the Streamlit st.columns rendering issue
    # where one plotly_chart widget can become invisible in a column.
    drivers = [driver_a, driver_b]
    subplot_titles = [f"{track} — {d}" for d in drivers]

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=subplot_titles,
        horizontal_spacing=0.08,
    )

    # Compute shared colour scale across all available drivers.
    value_arrays = [prepared["values"] for prepared in prepared_by_driver.values()]
    vmin, vmax = _compute_shared_scale(value_arrays, metric_key)

    for idx, driver_code in enumerate(drivers):
        col = idx + 1  # Plotly subplots are 1-indexed
        prepared = prepared_by_driver.get(driver_code)

        if prepared is None:
            # Show "no data" annotation in the empty subplot.
            msg = prepare_errors.get(
                driver_code, f"No track map data for {driver_code}"
            )
            fig.add_annotation(
                text=msg,
                xref=f"x{col}" if col > 1 else "x",
                yref=f"y{col}" if col > 1 else "y",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(color=SUBTLE_TEXT, size=12),
                row=1,
                col=col,
            )
            continue

        # Add track outline + coloured markers + start/finish marker.
        for trace in _build_track_panel_traces(prepared):
            fig.add_trace(trace, row=1, col=col)

    # --- Shared layout ------------------------------------------------
    fig.update_layout(
        paper_bgcolor=DARK_PAPER,
        plot_bgcolor=DARK_PAPER,
        font=dict(color=TEXT_COLOR),
        height=500,
        margin=dict(l=10, r=80, t=52, b=10),
        hovermode="closest",
        hoverlabel=dict(bgcolor="#22252B", font=dict(color=TEXT_COLOR, size=12)),
        coloraxis=dict(
            colorscale=_matplotlib_cmap_to_plotly(metric_cfg["cmap"]),
            cmin=vmin,
            cmax=vmax,
            colorbar=dict(
                title=dict(
                    text=f"{metric_cfg['label']} [{metric_cfg['unit']}]",
                    font=dict(color=TEXT_COLOR, size=11),
                ),
                tickfont=dict(color=TEXT_COLOR, size=10),
                thickness=16,
                len=0.82,
                x=1.02,
                y=0.5,
                outlinecolor=TEXT_COLOR,
                bgcolor=DARK_PAPER,
            ),
        ),
        showlegend=False,
    )

    # Style subplot titles to match the dark theme.
    for annotation in fig.layout.annotations:
        annotation.update(font=dict(size=12, color=TEXT_COLOR))

    # Hide axes and lock 1:1 aspect ratio for each subplot independently.
    for col in [1, 2]:
        x_axis = f"xaxis{col}" if col > 1 else "xaxis"
        y_axis = f"yaxis{col}" if col > 1 else "yaxis"
        x_ref = f"x{col}" if col > 1 else "x"

        fig.layout[x_axis].update(visible=False, showgrid=False, zeroline=False)
        fig.layout[y_axis].update(
            visible=False,
            showgrid=False,
            zeroline=False,
            scaleanchor=x_ref,
            scaleratio=1,
        )

    st.plotly_chart(
        fig,
        use_container_width=True,
        key=f"track-map-comparison-{metric_key}-{track}",
        config={
            "displayModeBar": False,
            "responsive": True,
            "scrollZoom": False,
        },
    )
