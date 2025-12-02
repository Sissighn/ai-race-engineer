import numpy as np
import pandas as pd


def calculate_driver_dna(telemetry):
    """
    Berechnet Fahrer-Charakteristiken (DNA) mit F1-spezifischer Skalierung.
    """
    if telemetry is None or telemetry.empty:
        return {}

    # 1. Aggressiveness (Brake Deceleration)
    telemetry["acc"] = telemetry["Speed"].diff() / 0.1
    braking_zones = telemetry[telemetry["Brake"] > 0]

    if not braking_zones.empty:
        top_decel = braking_zones["acc"].abs().quantile(0.95)
        aggressiveness = np.interp(top_decel, [20, 65], [0, 100])
    else:
        aggressiveness = 50

    # 2. Cornering (Confidence)
    max_speed = telemetry["Speed"].max()
    avg_corner_speed = telemetry[telemetry["Speed"] < max_speed * 0.85]["Speed"].mean()

    cornering_ability = np.interp(avg_corner_speed, [80, 230], [0, 100])

    # 3. Traction (Smoothness)
    throttle_transition = telemetry[
        (telemetry["Throttle"] > 20) & (telemetry["Throttle"] < 95)
    ]
    if not throttle_transition.empty:
        throttle_std = throttle_transition["Throttle"].diff().abs().mean()
        smoothness = np.interp(throttle_std, [0.5, 8.0], [100, 20])
    else:
        smoothness = 80

    # 4. Full Throttle %
    full_throttle_pct = (
        telemetry[telemetry["Throttle"] >= 99].count()["Throttle"] / len(telemetry)
    ) * 100
    full_throttle_score = np.interp(full_throttle_pct, [40, 85], [0, 100])

    # 5. Gear Usage (Workload)
    gear_changes = telemetry["nGear"].diff().abs().sum()
    gear_workload = np.interp(gear_changes, [30, 90], [0, 100])

    return {
        "Aggressiveness": round(aggressiveness, 1),
        "Cornering": round(cornering_ability, 1),
        "Traction/Smoothness": round(smoothness, 1),
        "Full Throttle %": round(full_throttle_score, 1),
        "Workload (Gears)": round(gear_workload, 1),
    }


def compare_driver_dna(tel_driver_1, tel_driver_2, name_1, name_2):
    dna_1 = calculate_driver_dna(tel_driver_1)
    dna_2 = calculate_driver_dna(tel_driver_2)

    categories = list(dna_1.keys())

    return pd.DataFrame(
        {
            "Metric": categories,
            name_1: [dna_1[c] for c in categories],
            name_2: [dna_2[c] for c in categories],
        }
    )
