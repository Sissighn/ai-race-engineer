import pandas as pd
import streamlit as st


def render_countdown_section(next_session_time) -> None:
    """Render a countdown card showing time until next F1 session.

    Args:
        next_session_time: UTC timestamp of the next session, or None/NaT.
    """
    st.markdown(
        "<h2 class='section-title'>Next Session Countdown</h2>",
        unsafe_allow_html=True,
    )

    if next_session_time is None or pd.isna(next_session_time):
        _render_countdown_card("n/a")
        return

    now = pd.Timestamp.now(tz="UTC")
    delta = next_session_time - now

    if delta.total_seconds() <= 0:
        countdown_text = "Session in progress"
    else:
        total = int(delta.total_seconds())
        days = total // 86400
        hrs = (total % 86400) // 3600
        mins = (total % 3600) // 60
        secs = total % 60
        countdown_text = (
            f"{days}d {hrs}h {mins:02d}m {secs:02d}s"
            if days > 0
            else f"{hrs:02d}h {mins:02d}m {secs:02d}s"
        )

    _render_countdown_card(countdown_text)


def _render_countdown_card(text: str) -> None:
    st.markdown(
        f"""
        <div class="glow-card-wrapper">
            <div class="glow-card-content">
                <div class="gc-title">Time until next session</div>
                <div class="gc-value">{text}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
