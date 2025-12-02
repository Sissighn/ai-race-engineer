import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# -------------------------------------------------------
# GLOBAL DARK THEME
# -------------------------------------------------------
DARK_BG = "#141414"
DARK_PAPER = "#191919"
TEXT_COLOR = "#FFFFFF"

PASTEL_COLORS = ["#A48FFF", "#FFB7D5", "#8FD3FE", "#FFDD94", "#C9F7C5", "#FDCFE8"]


def dark_layout(fig, title=None):
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor=DARK_BG,
        paper_bgcolor=DARK_PAPER,
        font_color=TEXT_COLOR,
        title_font=dict(size=22, color=TEXT_COLOR),
        hovermode="x unified",
        margin=dict(l=40, r=40, t=60, b=40),
    )
    if title:
        fig.update_layout(title=title)
    return fig


# -------------------------------------------------------
# 1) TIME LOSS BAR CHART
# -------------------------------------------------------
def plot_time_loss_bar(df, key="time_loss_bar"):
    fig = px.bar(
        df,
        x="Corner",
        y="TimeLoss",
        color="TimeLoss",
        color_continuous_scale=px.colors.sequential.Purples,
        height=380,
    )

    fig = dark_layout(fig, "Time Loss per Corner")
    fig.update_traces(marker_line_width=0)
    fig.update_xaxes(title_text="Corner")
    fig.update_yaxes(title_text="Time Loss (s)")

    st.plotly_chart(fig, use_container_width=True, key=key)


# -------------------------------------------------------
# 2) SPEED DELTAS – APEX & EXIT
# -------------------------------------------------------
def plot_speed_deltas(df, driver_a, driver_b, key="speed_deltas"):

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=df["Corner"],
            y=df["Delta_ApexSpeed"],
            name="Apex Speed Delta",
            marker_color="#A48FFF",
        )
    )

    fig.add_trace(
        go.Bar(
            x=df["Corner"],
            y=df["Delta_ExitSpeed"],
            name="Exit Speed Delta",
            marker_color="#8FD3FE",
        )
    )

    fig = dark_layout(fig, f"Speed Deltas – {driver_a} vs {driver_b}")
    fig.update_xaxes(title_text="Corner")
    fig.update_yaxes(title_text="Speed Delta (km/h)")

    st.plotly_chart(fig, use_container_width=True, key=key)


# -------------------------------------------------------
# 3) SPEED PROFILE – LINE PLOT
# -------------------------------------------------------
def plot_speed_profile(telA, telB, driverA, driverB, key="speed_profile"):

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=telA["Distance"],
            y=telA["Speed"],
            mode="lines",
            name=f"{driverA} Speed",
            line=dict(color="#A48FFF", width=2),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=telB["Distance"],
            y=telB["Speed"],
            mode="lines",
            name=f"{driverB} Speed",
            line=dict(color="#FFB7D5", width=2),
        )
    )

    fig = dark_layout(fig, f"Speed Profile – {driverA} vs {driverB}")
    fig.update_xaxes(title_text="Distance (m)")
    fig.update_yaxes(title_text="Speed (km/h)")

    st.plotly_chart(fig, use_container_width=True, key=key)


# -------------------------------------------------------
# 4) BRAKE & THROTTLE INPUTS
# -------------------------------------------------------
def plot_brake_throttle(telA, telB, driverA, driverB, key="brake_throttle"):

    fig = go.Figure()

    # --- Driver A ---
    fig.add_trace(
        go.Scatter(
            x=telA["Distance"],
            y=telA["Brake"],
            name=f"{driverA} Brake",
            mode="lines",
            line=dict(color="#A48FFF", width=2),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=telA["Distance"],
            y=telA["Throttle"],
            name=f"{driverA} Throttle",
            mode="lines",
            line=dict(color="#8FD3FE", width=2),
        )
    )

    # --- Driver B ---
    fig.add_trace(
        go.Scatter(
            x=telB["Distance"],
            y=telB["Brake"],
            name=f"{driverB} Brake",
            mode="lines",
            line=dict(color="#FFB7D5", width=2),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=telB["Distance"],
            y=telB["Throttle"],
            name=f"{driverB} Throttle",
            mode="lines",
            line=dict(color="#FFDD94", width=2),
        )
    )

    fig = dark_layout(fig, f"Brake & Throttle – {driverA} vs {driverB}")
    fig.update_xaxes(title_text="Distance (m)")
    fig.update_yaxes(title_text="Input (%)")

    st.plotly_chart(fig, use_container_width=True, key=key)


# -------------------------------------------------------
# 5) GEAR USAGE – DONUT
# -------------------------------------------------------
def plot_gear_usage(tel, driver, key=None):
    # Falls key nicht übergeben wurde, generieren wir einen aus dem Fahrernamen
    if key is None:
        key = f"gear_usage_{driver}"

    gear_counts = tel["nGear"].value_counts().sort_index()

    fig = px.pie(
        values=gear_counts.values,
        names=gear_counts.index,
        hole=0.55,
        title=f"Gear Usage – {driver}",
        color_discrete_sequence=PASTEL_COLORS,
    )

    fig = dark_layout(fig)
    st.plotly_chart(fig, use_container_width=True, key=key)


# -------------------------------------------------------
# 6) APEX SPEED DISTRIBUTION – DONUT (FIXED)
# -------------------------------------------------------
def plot_apex_speed_share(df, key="apex_share"):
    if df is None or df.empty or "Delta_ApexSpeed" not in df.columns:
        return

    # Fix für Pie-Charts (keine negativen Werte)
    plot_df = df.copy()
    plot_df["Absolute_Delta"] = plot_df["Delta_ApexSpeed"].abs()

    fig = px.pie(
        plot_df,
        values="Absolute_Delta",
        names="Corner",
        hole=0.55,
        title="Apex Speed Difference (Magnitude)",
        hover_data=["Delta_ApexSpeed"],
        color_discrete_sequence=PASTEL_COLORS,
    )

    fig = dark_layout(fig)
    st.plotly_chart(fig, use_container_width=True, key=key)


# -------------------------------------------------------
# 7) DRIVER DNA RADAR CHART (MIT KEY FIX)
# -------------------------------------------------------
def plot_driver_dna(dna_df, driver_a, driver_b, key="driver_dna_radar"):
    """
    Plots a Radar Chart comparing two drivers' characteristics.
    """
    fig = go.Figure()

    # Trace für Driver A
    fig.add_trace(
        go.Scatterpolar(
            r=dna_df[driver_a],
            theta=dna_df["Metric"],
            fill="toself",
            name=driver_a,
            line=dict(color="#A48FFF", width=2),
            fillcolor="rgba(164, 143, 255, 0.3)",
        )
    )

    # Trace für Driver B
    fig.add_trace(
        go.Scatterpolar(
            r=dna_df[driver_b],
            theta=dna_df["Metric"],
            fill="toself",
            name=driver_b,
            line=dict(color="#FFB7D5", width=2),
            fillcolor="rgba(255, 183, 213, 0.3)",
        )
    )

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                gridcolor="#333",
                linecolor="#333",
                tickfont=dict(color="#888"),
            ),
            angularaxis=dict(
                gridcolor="#333", linecolor="#333", tickfont=dict(color="#FFF", size=12)
            ),
            bgcolor="#141414",
        ),
        title=dict(
            text="<b>Driver DNA Comparison</b>",
            y=0.95,
            x=0.5,
            xanchor="center",
            yanchor="top",
            font=dict(size=20, color="#FFF"),
        ),
        paper_bgcolor="#191919",
        font=dict(color="#FFF"),
        margin=dict(l=40, r=40, t=80, b=40),
        legend=dict(x=0.8, y=0.95),
    )

    # Hier übergeben wir den Key an Streamlit!
    st.plotly_chart(fig, use_container_width=True, key=key)


# -------------------------------------------------------
# 8) CORNER TYPE PERFORMANCE
# -------------------------------------------------------
def plot_corner_type_performance(agg_df, key="corner_type_perf"):
    """
    Zeigt den kumulierten Zeitverlust pro Kurventyp an.
    """
    if agg_df is None or agg_df.empty:
        st.info("No classification data available.")
        return

    color_map = {
        "Low Speed": "#FFDD94",  # Gelb
        "Medium Speed": "#8FD3FE",  # Blau
        "High Speed": "#FFB7D5",  # Rot/Rosa
    }

    fig = px.bar(
        agg_df,
        x="CornerType",
        y="TimeLoss",
        text="TimeLoss",
        title="Time Loss by Corner Category",
        color="CornerType",
        color_discrete_map=color_map,
    )

    fig.update_traces(
        texttemplate="%{text:.3f}s",
        textposition="outside",
        width=0.5,  # Balken nicht zu fett machen
    )

    # Layout Anpassungen
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor=DARK_BG,
        paper_bgcolor=DARK_PAPER,
        font_color=TEXT_COLOR,
        showlegend=False,
        yaxis=dict(title="Total Time Delta (s)", zeroline=True, zerolinecolor="#555"),
        xaxis=dict(title=""),
    )

    st.plotly_chart(fig, use_container_width=True, key=key)
