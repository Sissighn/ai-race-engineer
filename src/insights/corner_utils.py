import pandas as pd


def classify_corner_type(speed):
    """
    Classifies a corner based on minimum apex speed.
    Thresholds:
    - Low: < 110 km/h (dominated by mechanical grip)
    - Medium: 110 - 180 km/h (mix of aero & mechanical grip)
    - High: > 180 km/h (dominated by aerodynamics)
    """
    if pd.isna(speed):
        return "Unknown"
    if speed < 110:
        return "Low Speed"
    elif speed < 180:
        return "Medium Speed"
    else:
        return "High Speed"


def add_corner_classification(time_loss_df):
    """
    Adds the 'CornerType' column to the DataFrame.
    """
    if time_loss_df is None or time_loss_df.empty:
        return time_loss_df

    df = time_loss_df.copy()

    # 1. Flexible search for the speed column
    # We try several common names to avoid crashes.
    possible_cols = ["ApexSpeed_A", "Speed_1", "Speed_A", "MinSpeed", "Speed"]
    target_col = None

    for col in possible_cols:
        if col in df.columns:
            target_col = col
            break

    if target_col is None:
        return None

    # 2. Apply classification
    df["CornerType"] = df[target_col].apply(classify_corner_type)
    return df


def aggregate_time_loss_by_type(df):
    """
    Aggregates the time loss per category.
    """
    if df is None or "CornerType" not in df.columns:
        return None

    agg = df.groupby("CornerType")["TimeLoss"].sum().reset_index()

    # Enforce sort order (Low -> Medium -> High)
    sorter = {"Low Speed": 0, "Medium Speed": 1, "High Speed": 2, "Unknown": 3}
    agg["sort_key"] = agg["CornerType"].map(sorter)
    agg = agg.sort_values("sort_key").drop("sort_key", axis=1)

    return agg


def get_corner_type_advice(agg_df):
    """
    Provides coaching tips based on the largest time difference.
    Distinguishes between time loss and time gain.
    """
    if agg_df is None or agg_df.empty:
        return []

    # Find category with the highest ABSOLUTE time difference
    agg_df["AbsLoss"] = agg_df["TimeLoss"].abs()
    worst = agg_df.loc[agg_df["AbsLoss"].idxmax()]

    type_name = worst["CornerType"]
    loss_val = worst["TimeLoss"]  # The sign (+/-) indicates who was faster

    tips = []

    # Ignore tiny differences (< 0.05s)
    if abs(loss_val) < 0.05:
        return ["Pace is very evenly matched across all corner types."]

    loss_str = f"{abs(loss_val):.3f}s"

    if type_name == "Low Speed":
        advice = "Focus on **mechanical grip/rotation**. Optimize trail-braking to rotate the car earlier."
    elif type_name == "Medium Speed":
        advice = (
            "Focus on **balance**. Ensure smooth transition from brake to throttle."
        )
    elif type_name == "High Speed":
        advice = "Focus on **aerodynamic trust**. Commit to throttle earlier and minimize scrubbing."
    else:
        advice = "Check telemetry consistency."

    # Distinguish: Losing (positive) or Gaining (negative)?
    # Assumption from time_loss_engine:
    # TimeLoss > 0 means Driver A is faster (gaining time)
    if loss_val > 0:
        tips.append(
            f"Major deficit in **{type_name}** corners (losing {loss_str}). {advice}"
        )
    else:
        tips.append(
            f"Strong performance in **{type_name}** corners (gaining {loss_str}). Keep it up!"
        )

    return tips
