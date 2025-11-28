import pandas as pd

def estimate_time_loss_per_corner(df: pd.DataFrame, driver_a: str, driver_b: str):
    """
    Estimates time loss per corner using weighted deltas:
    Entry, Apex, Exit Speed.
    Positive = driver_a faster
    Negative = driver_b faster
    """

    df = df.copy()

    # Weighting factors (F1-like approximation)
    w_entry = 0.015   # sec per km/h
    w_apex  = 0.030
    w_exit  = 0.060

    df["TimeLoss"] = (
        df["Delta_EntrySpeed"] * w_entry +
        df["Delta_ApexSpeed"]  * w_apex  +
        df["Delta_ExitSpeed"]  * w_exit
    )

    # Negative TimeLoss bedeutet:
    # driver_b ist schneller → driver_a verliert Zeit
    df["TimeLossSeconds_A_loses"] = df["TimeLoss"].apply(lambda x: -x if x < 0 else 0)
    df["TimeGainSeconds_A_gains"] = df["TimeLoss"].apply(lambda x:  x if x > 0 else 0)

    return df
