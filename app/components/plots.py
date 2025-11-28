import matplotlib.pyplot as plt
import streamlit as st

def plot_time_loss_bar(df):
    plt.figure(figsize=(12,5))
    plt.bar(df["Corner"], df["TimeLoss"])
    plt.axhline(0, color="black", linewidth=1)
    plt.xlabel("Corner")
    plt.ylabel("Time Loss (s)")
    plt.title("Time Loss per Corner")
    plt.grid(True)
    st.pyplot(plt.gcf())
    plt.close()


def plot_speed_deltas(df, driver_a, driver_b):
    fig, ax = plt.subplots(figsize=(12,5))
    ax.bar(df["Corner"], df["Delta_ApexSpeed"], label="Apex", alpha=0.7)
    ax.bar(df["Corner"], df["Delta_ExitSpeed"], label="Exit", alpha=0.7)
    ax.axhline(0, color="black", linewidth=1)
    ax.set_title(f"Speed Deltas per Corner ({driver_a} - {driver_b})")
    ax.set_xlabel("Corner")
    ax.set_ylabel("Delta Speed (km/h)")
    ax.legend()
    ax.grid(True)
    st.pyplot(fig)
    plt.close()
