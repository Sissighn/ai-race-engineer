import pandas as pd

def severity_level(delta, thresholds=(1.0, 3.0)):
    """
    Return severity label based on delta magnitude.
    thresholds: (low, high)
    """
    low, high = thresholds
    
    if abs(delta) < low:
        return "minor"
    elif abs(delta) < high:
        return "moderate"
    else:
        return "severe"


def generate_corner_text_insights(df: pd.DataFrame, driver_a: str, driver_b: str):
    """
    Human-readable race-engineer insights for corner-by-corner deltas.
    Prioritizes significant performance differences.
    """

    insights = []

    # Score to rank importance of each corner
    # Exit Speed is the most valuable (affects straight)
    df["ImpactScore"] = (
        df["Delta_ExitSpeed"].abs() * 2.0 +
        df["Delta_ApexSpeed"].abs() * 1.5 +
        df["Delta_EntrySpeed"].abs() * 1.0
    )

    # Sort by most important differences (descending)
    df = df.sort_values("ImpactScore", ascending=False)

    for _, row in df.iterrows():
        c = int(row["Corner"])

        apex_delta   = row["Delta_ApexSpeed"]
        exit_delta   = row["Delta_ExitSpeed"]
        entry_delta  = row["Delta_EntrySpeed"]
        brake_delta  = row["Delta_AvgBrake"]
        throttle_low = row["Delta_ThrottleBelow30Pct"]

        line = f"Corner {c}: "

        # 1. Apex Speed
        sev = severity_level(apex_delta)
        if apex_delta > 1:
            line += f"{driver_a} carries more apex speed (+{apex_delta:.1f} km/h, {sev}). "
        elif apex_delta < -1:
            line += f"{driver_b} is faster at the apex (+{-apex_delta:.1f} km/h, {sev}). "
        else:
            line += "Apex speed is similar. "

        # 2. Entry Speed
        if entry_delta > 1:
            line += f"{driver_a} approaches faster (+{entry_delta:.1f} km/h entry). "
        elif entry_delta < -1:
            line += f"{driver_b} approaches faster (+{-entry_delta:.1f} km/h entry). "

        # 3. Exit Speed (VERY IMPORTANT)
        sev_exit = severity_level(exit_delta, thresholds=(1.0, 2.5))
        if exit_delta > 1:
            line += f"{driver_a} has stronger exit acceleration (+{exit_delta:.1f} km/h, {sev_exit}). "
        elif exit_delta < -1:
            line += f"{driver_b} has stronger exit acceleration (+{-exit_delta:.1f} km/h, {sev_exit}). "

        # 4. Braking
        if abs(brake_delta) > 0.1:
            if brake_delta > 0:
                line += f"{driver_a} brakes harder. "
            else:
                line += f"{driver_b} brakes harder. "

        # 5. Throttle hesitation
        if abs(throttle_low) > 0.05:
            if throttle_low > 0:
                line += f"{driver_a} hesitates more on throttle at the exit. "
            else:
                line += f"{driver_b} hesitates more on throttle at the exit. "

        insights.append(line.strip())

    return insights
