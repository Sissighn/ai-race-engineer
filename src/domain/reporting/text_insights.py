from __future__ import annotations

import pandas as pd


def severity_level(delta: float, thresholds: tuple[float, float] = (1.0, 3.0)) -> str:
    """Return severity label based on delta magnitude."""
    low, high = thresholds

    if abs(delta) < low:
        return "minor"
    if abs(delta) < high:
        return "moderate"
    return "severe"


def generate_corner_text_insights(
    df: pd.DataFrame, driver_a: str, driver_b: str
) -> list[str]:
    """Generate human-readable corner-by-corner performance insights."""
    insights: list[str] = []

    work = df.copy()
    work["ImpactScore"] = (
        work["Delta_ExitSpeed"].abs() * 2.0
        + work["Delta_ApexSpeed"].abs() * 1.5
        + work["Delta_EntrySpeed"].abs() * 1.0
    )
    work = work.sort_values("ImpactScore", ascending=False)

    for _, row in work.iterrows():
        c = int(row["Corner"])

        apex_delta = row["Delta_ApexSpeed"]
        exit_delta = row["Delta_ExitSpeed"]
        entry_delta = row["Delta_EntrySpeed"]
        brake_delta = row["Delta_AvgBrake"]
        throttle_low = row["Delta_ThrottleBelow30Pct"]

        line = f"Corner {c}: "

        sev = severity_level(apex_delta)
        if apex_delta > 1:
            line += (
                f"{driver_a} carries more apex speed (+{apex_delta:.1f} km/h, {sev}). "
            )
        elif apex_delta < -1:
            line += (
                f"{driver_b} is faster at the apex (+{-apex_delta:.1f} km/h, {sev}). "
            )
        else:
            line += "Apex speed is similar. "

        if entry_delta > 1:
            line += f"{driver_a} approaches faster (+{entry_delta:.1f} km/h entry). "
        elif entry_delta < -1:
            line += f"{driver_b} approaches faster (+{-entry_delta:.1f} km/h entry). "

        sev_exit = severity_level(exit_delta, thresholds=(1.0, 2.5))
        if exit_delta > 1:
            line += f"{driver_a} has stronger exit acceleration (+{exit_delta:.1f} km/h, {sev_exit}). "
        elif exit_delta < -1:
            line += f"{driver_b} has stronger exit acceleration (+{-exit_delta:.1f} km/h, {sev_exit}). "

        if abs(brake_delta) > 0.1:
            if brake_delta > 0:
                line += f"{driver_a} brakes harder. "
            else:
                line += f"{driver_b} brakes harder. "

        if abs(throttle_low) > 0.05:
            if throttle_low > 0:
                line += f"{driver_a} hesitates more on throttle at the exit. "
            else:
                line += f"{driver_b} hesitates more on throttle at the exit. "

        insights.append(line.strip())

    return insights


def add_time_loss_to_text(df: pd.DataFrame, driver_a: str, driver_b: str) -> list[str]:
    """Add human-readable time loss summary per corner."""
    texts: list[str] = []

    for _, row in df.iterrows():
        c = int(row["Corner"])
        loss = row["TimeLoss"]

        if loss < -0.01:
            text = f"In Corner {c}, {driver_a} loses ~{abs(loss):.2f}s to {driver_b}."
        elif loss > 0.01:
            text = f"In Corner {c}, {driver_b} loses ~{abs(loss):.2f}s to {driver_a}."
        else:
            text = f"Corner {c}: No meaningful time difference."

        texts.append(text)

    return texts
