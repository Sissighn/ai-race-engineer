# app/components/track_map.py
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap
import streamlit as st

from src.data.load_data import load_telemetry_with_position


# ---------------------------------------------------------
# 1. Pastel Colormap
# ---------------------------------------------------------
def _pastel_speed_cmap():
    """Soft pastel color map for clean speed visualization."""
    colors = [
        (0.85, 0.90, 1.00),   # light blue
        (0.80, 0.75, 1.00),   # lavender
        (0.95, 0.80, 0.95),   # soft pink
        (1.00, 0.90, 0.75),   # pastel peach
    ]
    return LinearSegmentedColormap.from_list("pastel_speed", colors)


# ---------------------------------------------------------
# 2. Draw heat-colored line
# ---------------------------------------------------------
def _line_heatmap(x, y, values, ax, fig):
    """
    Draws line segments colored by telemetry values.
    """

    x = np.asarray(x)
    y = np.asarray(y)
    values = np.asarray(values)

    if len(x) < 2 or len(values) < 2:
        raise ValueError("Telemetry too short to draw track map.")

    points = np.column_stack((x, y))
    segments = np.stack([points[:-1], points[1:]], axis=1)

    norm = plt.Normalize(vmin=np.nanmin(values), vmax=np.nanmax(values))
    cmap = _pastel_speed_cmap()

    lc = LineCollection(
        segments, cmap=cmap, norm=norm, linewidth=4.0
    )
    lc.set_array(values)

    ax.add_collection(lc)
    ax.set_aspect("equal", "box")
    ax.autoscale()
    ax.axis("off")

    # Add colorbar
    cbar = fig.colorbar(lc, ax=ax, fraction=0.04, pad=0.03)
    cbar.set_label("Speed (km/h)", fontsize=9)

    return lc


# ---------------------------------------------------------
# 3. Display static SVG outline (optional)
# ---------------------------------------------------------
def show_track_outline_svg(track: str):
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    svg_path = os.path.join(project_root, "app", "assets", "tracks", f"{track.lower()}.svg")

    if os.path.exists(svg_path):
        st.image(svg_path, use_container_width=True)
    else:
        st.info(f"No SVG outline found for {track}")


# ---------------------------------------------------------
# 4. Main function — Track Map
# ---------------------------------------------------------
def plot_track_map(session, driver_code: str, track: str, mode="speed"):
    """
    Plots a heat-colored track map for the driver's fastest lap.
    """

    # Load telemetry with X/Y and speed
    tel = load_telemetry_with_position(session, driver_code)

    # Validate required data
    for col in ["X", "Y", "Speed"]:
        if col not in tel.columns:
            st.error(f"Telemetry missing '{col}' for track map.")
            return

    x = tel["X"].values
    y = tel["Y"].values

    if mode.lower() == "speed":
        values = tel["Speed"].values
        label = "Speed (km/h)"
    else:
        st.warning(f"Mode '{mode}' not implemented. Falling back to speed.")
        values = tel["Speed"].values
        label = "Speed (km/h)"

    # Drawing figure
    fig, ax = plt.subplots(figsize=(2.4, 2.4), dpi=300)

    try:
        _line_heatmap(x, y, values, ax, fig)
    except Exception as e:
        st.error(f"Track map draw error: {e}")
        plt.close(fig)
        return

    ax.set_title(f"{track} – {driver_code}", fontsize=10, pad=6)

    st.pyplot(fig)
    plt.close(fig)
