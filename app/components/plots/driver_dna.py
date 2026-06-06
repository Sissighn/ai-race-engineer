"""
Driver DNA telemetry-derived heuristic score chart (Section 7).

Exposes one public function:
    plot_driver_dna – grouped horizontal bar chart of telemetry-derived
                      heuristic driving-style scores on a normalised 0-100 scale.

DNA_METRIC_META and DNA_METRIC_ORDER define the canonical metric labels,
descriptions, and display ordering used in the chart.
"""

import plotly.express as px
import streamlit as st

from src.logging import get_logger

from ._theme import TITLE_LINE_SPACER, _safe_plotly_chart, dark_layout

logger = get_logger(__name__)

# ── Metric registry ───────────────────────────────────────────────────────────
# Each entry maps an internal metric key to a display label and a one-sentence
# description that appears in the chart tooltip under "Meaning:".

DNA_METRIC_META = {
    "Aggressiveness": {
        "label": "Braking Aggressiveness",
        "description": "Derived from high deceleration events in braking zones.",
    },
    "Cornering": {
        "label": "Corner Speed Profile",
        "description": "Derived from average speed in cornering phases.",
    },
    "Smoothness": {
        "label": "Throttle Smoothness",
        "description": "Derived from throttle input stability during transitions.",
    },
    "FullThrottle": {
        "label": "Full-Throttle Usage",
        "description": "Derived from the share of telemetry samples at near-full throttle.",
    },
    "GearWorkload": {
        "label": "Gear Shift Activity",
        "description": "Derived from total gear-change activity over the lap.",
    },
}

# Canonical display order; metrics not listed here are appended at the end.
DNA_METRIC_ORDER = [
    "Aggressiveness",
    "Cornering",
    "Smoothness",
    "FullThrottle",
    "GearWorkload",
]


def plot_driver_dna(dna_df, driver_a, driver_b, key="driver_dna_radar"):
    """Render telemetry-derived heuristic scores as a grouped horizontal bar chart.

    Scores are normalised heuristics on a 0-100 scale and should be read as
    relative style indicators, not absolute performance ratings.

    Args:
        dna_df:   DataFrame with columns Metric, *driver_a*, *driver_b*.
        driver_a: Name of the first driver (must match a column in dna_df).
        driver_b: Name of the second driver (must match a column in dna_df).
        key:      Streamlit widget key.
    """
    if dna_df is None or dna_df.empty:
        logger.warning(
            "No data for driver DNA chart", driver_a=driver_a, driver_b=driver_b
        )
        st.info("Driver DNA chart unavailable.")
        return

    required_cols = {"Metric", driver_a, driver_b}
    if not required_cols.issubset(set(dna_df.columns)):
        logger.warning(
            "Driver DNA chart missing required columns",
            required=list(required_cols),
            available=list(dna_df.columns),
            driver_a=driver_a,
            driver_b=driver_b,
        )
        st.info("Driver DNA chart unavailable.")
        return

    plot_df = dna_df.copy()

    # Resolve human-readable labels and tooltip descriptions from the registry.
    plot_df["MetricLabel"] = plot_df["Metric"].apply(
        lambda m: DNA_METRIC_META.get(m, {}).get("label", m)
    )
    plot_df["MetricDescription"] = plot_df["Metric"].apply(
        lambda m: DNA_METRIC_META.get(m, {}).get(
            "description",
            "Telemetry-derived normalized heuristic score.",
        )
    )

    # Build ordered label list: canonical order first, then any extras.
    ordered_metrics = [m for m in DNA_METRIC_ORDER if m in plot_df["Metric"].values]
    ordered_metrics += [
        m for m in plot_df["Metric"].values if m not in set(ordered_metrics)
    ]
    ordered_labels = [
        DNA_METRIC_META.get(metric, {}).get("label", metric)
        for metric in ordered_metrics
    ]

    # Melt to long format so both drivers appear as a "Driver" column.
    long_df = plot_df.melt(
        id_vars=["Metric", "MetricLabel", "MetricDescription"],
        value_vars=[driver_a, driver_b],
        var_name="Driver",
        value_name="Score",
    )

    fig = px.bar(
        long_df,
        x="Score",
        y="MetricLabel",
        color="Driver",
        orientation="h",
        barmode="group",
        text="Score",
        custom_data=["Metric", "MetricDescription"],
        category_orders={"MetricLabel": ordered_labels, "Driver": [driver_a, driver_b]},
        color_discrete_map={driver_a: "#A48FFF", driver_b: "#FFB7D5"},
        labels={
            "Score": "Telemetry-Derived Heuristic Score [0-100]",
            "MetricLabel": "Metric",
        },
        title=(
            "Driver Style Heuristic Score Comparison"
            f"{TITLE_LINE_SPACER}<sup><span style='color:#AEB4BE;font-weight:400'>"
            f"{driver_a} vs {driver_b}  -  "
            "Telemetry-derived heuristic scores (0-100)</span></sup>"
            f"{TITLE_LINE_SPACER}<sup><span style='color:#AEB4BE;font-weight:400'>"
            "Higher score = stronger expression of that style characteristic, "
            "not an objective performance rating</span></sup>"
        ),
        height=480,
    )

    fig = dark_layout(fig)
    fig.update_layout(
        margin=dict(l=60, r=40, t=170, b=50),
        legend=dict(
            orientation="h",
            x=0.5,
            xanchor="center",
            y=1.02,
            yanchor="bottom",
            title_text="",
        ),
    )
    fig.update_xaxes(range=[0, 100], dtick=20)
    fig.update_yaxes(categoryorder="array", categoryarray=ordered_labels)
    fig.update_traces(
        texttemplate="%{x:.1f}",
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            + "Driver: %{fullData.name}<br>"
            + "Telemetry-derived heuristic score: %{x:.1f}/100<br>"
            + "Meaning: %{customdata[1]}"
            + "<extra></extra>"
        ),
    )

    _safe_plotly_chart(fig, key=key, context="driver_dna")
