import pandas as pd


def estimate_time_loss_per_corner(df: pd.DataFrame, driver_a: str, driver_b: str):
    """
    Estimates time loss per corner using weighted deltas:
    Entry, Apex, Exit Speed.
    Positive = driver_a faster (gaining time)
    Negative = driver_b faster (losing time)
    """
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    # ---------------------------------------------------------
    # 1. FORMULA LOGIC (Weighting factors)
    # ---------------------------------------------------------
    w_entry = 0.015  # sec per km/h
    w_apex = 0.030
    w_exit = 0.060

    # Safety check: Ensure columns exist before calculation
    required_cols = ["Delta_EntrySpeed", "Delta_ApexSpeed", "Delta_ExitSpeed"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = 0.0

    df["TimeLoss"] = (
        df["Delta_EntrySpeed"] * w_entry
        + df["Delta_ApexSpeed"] * w_apex
        + df["Delta_ExitSpeed"] * w_exit
    )

    # ---------------------------------------------------------
    # 2. DIRECTION LOGIC
    # ---------------------------------------------------------
    # Negative TimeLoss means Driver A is slower (loses time)
    # Positive TimeLoss means Driver A is faster (gains time)
    df["TimeLossSeconds_A_loses"] = df["TimeLoss"].apply(lambda x: -x if x < 0 else 0)
    df["TimeGainSeconds_A_gains"] = df["TimeLoss"].apply(lambda x: x if x > 0 else 0)

    # ---------------------------------------------------------
    # 3. PREPARE FOR CLASSIFICATION (CRITICAL FIX)
    # ---------------------------------------------------------

    # Mapping: Speed_1 -> ApexSpeed_A
    if "Speed_1" in df.columns:
        df["ApexSpeed_A"] = df["Speed_1"]
    elif "Speed_A" in df.columns:
        df["ApexSpeed_A"] = df["Speed_A"]
    elif "ApexSpeed" in df.columns:
        df["ApexSpeed_A"] = df["ApexSpeed"]

    # Mapping: Speed_2 -> ApexSpeed_B
    if "Speed_2" in df.columns:
        df["ApexSpeed_B"] = df["Speed_2"]
    elif "Speed_B" in df.columns:
        df["ApexSpeed_B"] = df["Speed_B"]

    return df
