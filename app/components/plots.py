import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

PASTEL_COLORS = [
    "#A48FFF", "#FFB7D5", "#8FD3FE", 
    "#FFDD94", "#C9F7C5", "#FDCFE8"
]

# -------------------------------------------------------
# 1) TIME LOSS BAR CHART
# -------------------------------------------------------
def plot_time_loss_bar(df):
    fig = px.bar(
        df,
        x="Corner",
        y="TimeLoss",
        title="Time Loss per Corner",
        color="TimeLoss",
        color_continuous_scale=px.colors.sequential.Purples,
        height=380
    )

    fig.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        title_font=dict(size=22),
        xaxis_title="Corner",
        yaxis_title="Time Loss (s)"
    )

    fig.update_traces(marker_line_width=0)

    st.plotly_chart(fig, use_container_width=True)


# -------------------------------------------------------
# 2) SPEED DELTAS (Apex & Exit)
# -------------------------------------------------------
def plot_speed_deltas(df, driver_a, driver_b):

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df["Corner"],
        y=df["Delta_ApexSpeed"],
        name="Apex Speed Delta",
        marker_color="#A48FFF"
    ))

    fig.add_trace(go.Bar(
        x=df["Corner"],
        y=df["Delta_ExitSpeed"],
        name="Exit Speed Delta",
        marker_color="#8FD3FE"
    ))

    fig.update_layout(
        barmode="group",
        title=f"Speed Deltas – {driver_a} vs {driver_b}",
        plot_bgcolor="white",
        paper_bgcolor="white",
        title_font=dict(size=22),
        xaxis_title="Corner",
        yaxis_title="Speed Delta (km/h)",
        legend=dict(borderwidth=0)
    )

    st.plotly_chart(fig, use_container_width=True)


# -------------------------------------------------------
# 3) SPEED PROFILE LINE PLOT (lap overlay)
# -------------------------------------------------------
def plot_speed_profile(telA, telB, driverA, driverB):
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=telA["Distance"],
        y=telA["Speed"],
        mode="lines",
        name=f"{driverA} Speed",
        line=dict(color="#A48FFF", width=2)
    ))

    fig.add_trace(go.Scatter(
        x=telB["Distance"],
        y=telB["Speed"],
        mode="lines",
        name=f"{driverB} Speed",
        line=dict(color="#FFB7D5", width=2)
    ))

    fig.update_layout(
        title=f"Speed Profile – {driverA} vs {driverB}",
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis_title="Distance (m)",
        yaxis_title="Speed (km/h)"
    )

    st.plotly_chart(fig, use_container_width=True)


# -------------------------------------------------------
# 4) BRAKE & THROTTLE COMPARISON
# -------------------------------------------------------
def plot_brake_throttle(telA, telB, driverA, driverB):
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=telA["Distance"],
        y=telA["Brake"],
        name=f"{driverA} Brake",
        mode="lines",
        line=dict(color="#A48FFF", width=2)
    ))

    fig.add_trace(go.Scatter(
        x=telB["Distance"],
        y=telB["Brake"],
        name=f"{driverB} Brake",
        mode="lines",
        line=dict(color="#FFB7D5", width=2)
    ))

    fig.add_trace(go.Scatter(
        x=telA["Distance"],
        y=telA["Throttle"],
        name=f"{driverA} Throttle",
        mode="lines",
        line=dict(color="#8FD3FE", width=2)
    ))

    fig.add_trace(go.Scatter(
        x=telB["Distance"],
        y=telB["Throttle"],
        name=f"{driverB} Throttle",
        mode="lines",
        line=dict(color="#FFDD94", width=2)
    ))

    fig.update_layout(
        title=f"Brake / Throttle Input – {driverA} vs {driverB}",
        xaxis_title="Distance (m)",
        yaxis_title="Input Value",
        plot_bgcolor="white"
    )

    st.plotly_chart(fig, use_container_width=True)


# -------------------------------------------------------
# 5) GEAR USAGE (donut / pie)
# -------------------------------------------------------
def plot_gear_usage(tel, driver):
    gear_counts = tel["nGear"].value_counts().sort_index()

    fig = px.pie(
        values=gear_counts.values,
        names=gear_counts.index,
        hole=0.5,
        title=f"Gear Usage – {driver}",
        color_discrete_sequence=PASTEL_COLORS
    )

    fig.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white"
    )

    st.plotly_chart(fig, use_container_width=True)


# -------------------------------------------------------
# 6) APEX SPEED DONUT (where driver loses most)
# -------------------------------------------------------
def plot_apex_speed_share(df):
    fig = px.pie(
        df,
        values="Delta_ApexSpeed",
        names="Corner",
        hole=0.55,
        title="Apex Speed Distribution",
        color_discrete_sequence=PASTEL_COLORS
    )

    st.plotly_chart(fig, use_container_width=True)
