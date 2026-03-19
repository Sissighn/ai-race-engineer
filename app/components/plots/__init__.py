"""
app.components.plots – Public plotting API for the AI Race Engineer dashboard.

Import chart functions directly from this package; callers never need to
know the internal submodule layout:

    from app.components.plots import plot_time_loss_bar, plot_driver_dna, ...

Package layout
──────────────
  _theme.py             – dark-theme constants, dark_layout, _safe_plotly_chart
  _helpers.py           – pure formatting / sorting / classification utilities
  time_loss.py          – plot_time_loss_bar
  speed_deltas.py       – plot_speed_deltas, plot_apex_speed_share,
                          plot_exit_speed_delta
  telemetry.py          – plot_speed_profile, plot_brake_throttle, plot_gear_usage
  driver_dna.py         – plot_driver_dna  (+ DNA_METRIC_META, DNA_METRIC_ORDER)
  corner_performance.py – plot_corner_type_performance
"""

# ── Kept at package level for backwards-compatible test monkeypatching ────────
# Tests patch app.components.plots.st.*  and app.components.plots.px.*
# Both resolve to the underlying library modules, so the patch propagates
# automatically to all submodules that also import streamlit / plotly.express.
import plotly.express as px  # noqa: F401
import streamlit as st  # noqa: F401

from ._theme import _safe_plotly_chart, dark_layout
from .corner_performance import plot_corner_type_performance
from .driver_dna import plot_driver_dna
from .speed_deltas import plot_apex_speed_share, plot_exit_speed_delta, plot_speed_deltas
from .telemetry import plot_brake_throttle, plot_gear_usage, plot_speed_profile
from .time_loss import plot_time_loss_bar

__all__ = [
    # Theme helpers
    "dark_layout",
    "_safe_plotly_chart",
    # Chart functions
    "plot_time_loss_bar",
    "plot_speed_deltas",
    "plot_apex_speed_share",
    "plot_exit_speed_delta",
    "plot_speed_profile",
    "plot_brake_throttle",
    "plot_gear_usage",
    "plot_driver_dna",
    "plot_corner_type_performance",
]
