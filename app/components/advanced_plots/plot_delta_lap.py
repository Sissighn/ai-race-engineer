import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import streamlit as st


def compute_delta_lap(telA, telB):
    """
    Computes delta time between two synchronized telemetry laps.
    Returns a dataframe with columns:
    - Distance
    - Speed_1
    - Speed_2
    - DeltaTime (A - B)
    """

    # Both already synced via merge_asof in your sync function
    df = telA.merge(telB, on="Distance", how="inner", suffixes=("_A", "_B"))

    # Time stamps must exist
    if "Time_A" not in df.columns or "Time_B" not in df.columns:
        raise ValueError("Telemetry missing Time column for delta-lap computation.")

    # Convert to seconds if needed
    df["Time_A_s"] = df["Time_A"].dt.total_seconds()
    df["Time_B_s"] = df["Time_B"].dt.total_seconds()

    # Delta (A - B): negative = A faster, positive = B faster
    df["DeltaTime"] = df["Time_A_s"] - df["Time_B_s"]

    return df[["Distance", "DeltaTime"]]


def plot_delta_lap(delta_df, driverA, driverB):
    """
    Plots Δ-time over distance.
    Negative values => driver A faster.
    """

    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(delta_df["Distance"], delta_df["DeltaTime"], linewidth=1.8)

    ax.set_title(f"Delta Lap: {driverA} vs {driverB}", fontsize=14, color="white")
    ax.set_xlabel("Distance (m)", fontsize=12, color="white")
    ax.set_ylabel("Delta Time (s)", fontsize=12, color="white")

    # Zero line for reference
    ax.axhline(0, color="gray", linewidth=1, linestyle="--")

    # Dark mode styling
    ax.set_facecolor("#111111")
    fig.patch.set_facecolor("#111111")
    ax.tick_params(axis="x", colors="white")
    ax.tick_params(axis="y", colors="white")

    st.pyplot(fig)
