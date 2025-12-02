# app/components/track_map.py

import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap
import streamlit as st

from src.data.load_data import load_telemetry_with_position

# ---------------------------------------------------------
# GLOBAL DARK THEME COLORS
# ---------------------------------------------------------
DARK_BG = "#141414"
DARK_PAPER = "#191919"
TEXT_COLOR = "#FFFFFF"

# ---------------------------------------------------------
# Pastel Neon Speed Colormap (matching your plotly theme)
# ---------------------------------------------------------
def _dark_pastel_speed_cmap():
    colors = [
        (0.75, 0.82, 1.00),   # neon-light blue
        (0.80, 0.70, 1.00),   # neon lavender
        (0.95, 0.75, 0.95),   # soft pink
        (1.00, 0.88, 0.60),   # pastel peach
    ]
    return LinearSegmentedColormap.from_list("dark_pastel_speed", colors)


# ---------------------------------------------------------
# 1. Dark mode line heatmap
# ---------------------------------------------------------
def _line_heatmap_dark(x, y, values, ax, fig):
    x = np.asarray(x)
    y = np.asarray(y)
    values = np.asarray(values)

    if len(x) < 2:
        raise ValueError("Telemetry too short for track map.")

    points = np.column_stack((x, y))
    segments = np.stack([points[:-1], points[1:]], axis=1)

    norm = plt.Normalize(vmin=np.nanmin(values), vmax=np.nanmax(values))
    cmap = _dark_pastel_speed_cmap()

    lc = LineCollection(
        segments,
        cmap=cmap,
        norm=norm,
        linewidth=3.2
    )
    lc.set_array(values)

    ax.add_collection(lc)
    ax.set_aspect("equal", "box")
    ax.autoscale()
    ax.axis("off")

    # Colorbar
    cbar = fig.colorbar(lc, ax=ax, fraction=0.045, pad=0.02)
    cbar.set_label("Speed (km/h)", fontsize=8, color=TEXT_COLOR)

    # Colorbar dark styling
    cbar.outline.set_edgecolor(TEXT_COLOR)
    cbar.ax.yaxis.set_tick_params(color=TEXT_COLOR)
    plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color=TEXT_COLOR)

    return lc


# ---------------------------------------------------------
# 2. Optional SVG Outline
# ---------------------------------------------------------
def show_track_outline_svg(track: str):
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    svg_path = os.path.join(project_root, "app", "assets", "tracks", f"{track.lower()}.svg")

    if os.path.exists(svg_path):
        st.image(svg_path, use_container_width=True)
    else:
        st.info(f"No SVG outline found for {track}")


# ---------------------------------------------------------
# 3. MAIN FUNCTION — Track Map (Dark Mode)
# ---------------------------------------------------------
def plot_track_map(session, driver_code: str, track: str, mode="speed"):
    tel = load_telemetry_with_position(session, driver_code)

    for col in ["X", "Y", "Speed"]:
        if col not in tel.columns:
            st.error(f"Telemetry missing '{col}' for track map.")
            return

    x = tel["X"].values
    y = tel["Y"].values

    if mode.lower() == "speed":
        values = tel["Speed"].values
    else:
        values = tel["Speed"].values
        st.warning(f"Mode '{mode}' not implemented. Using Speed instead.")

    # --------------- FIGURE ------------------
    fig, ax = plt.subplots(figsize=(2.5, 2.5), dpi=260)

    # DARK BACKGROUND for the whole map
    fig.patch.set_facecolor(DARK_PAPER)
    ax.set_facecolor(DARK_PAPER)

    try:
        _line_heatmap_dark(x, y, values, ax, fig)
    except Exception as e:
        st.error(f"Track map draw error: {e}")
        plt.close(fig)
        return

    # Dark title
    ax.set_title(
        f"{track} – {driver_code}",
        fontsize=10,
        pad=6,
        color=TEXT_COLOR
    )

    st.pyplot(fig)
    plt.close(fig)
