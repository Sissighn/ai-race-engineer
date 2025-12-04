import pandas as pd
import numpy as np


def generate_race_engineer_report(tl_df, agg_types_df, driver_a, driver_b, track_name):
    """
    Generates a deeply detailed natural-language report.
    Drills down into specific corners to explain WHY time is lost.
    """
    if tl_df is None or tl_df.empty:
        return {
            "headline": "No Data Available",
            "type_summary": ["Insufficient telemetry data."],
            "key_fix": "Check data source.",
        }

    # ----------------------------------------------------
    # 1. HEADLINE (Gap & Status)
    # ----------------------------------------------------
    total_delta = tl_df["TimeLoss"].sum()
    gap = abs(total_delta)

    if total_delta > 0:
        status = "behind"
        tone_color = "red"  # Emotional logic
        headline = f"**{track_name} Analysis**: {driver_a} is **{gap:.3f}s {status}** {driver_b}."
    else:
        status = "ahead"
        tone_color = "green"
        headline = f"**{track_name} Analysis**: {driver_a} is **{gap:.3f}s {status}** {driver_b}."

    # ----------------------------------------------------
    # 2. DEEP DIVE ANALYSIS (The "Why" & "Where")
    # ----------------------------------------------------
    summary_lines = []

    # --- A. PROBLEM AREA (Where do we lose the most?) ---
    # Wir filtern nur Kurven, wo wir Zeit verlieren (>0)
    losing_mask = tl_df["TimeLoss"] > 0
    if losing_mask.any():
        # Wir schauen, welcher Kurven-Typ (Low/Med/High) am meisten schmerzt
        loss_by_type = (
            tl_df[losing_mask]
            .groupby("CornerType")["TimeLoss"]
            .sum()
            .sort_values(ascending=False)
        )

        if not loss_by_type.empty:
            worst_type = loss_by_type.index[0]  # z.B. "Low Speed"
            loss_val = loss_by_type.iloc[0]

            # JETZT DER TRICK: Welche Kurven genau sind das?
            # Wir holen die Top 2 Kurven dieses Typs
            problem_corners = tl_df[
                (tl_df["CornerType"] == worst_type) & (tl_df["TimeLoss"] > 0.05)
            ].sort_values("TimeLoss", ascending=False)

            corner_nums = (
                problem_corners["Corner"].astype(str).tolist()[:2]
            )  # z.B. ['3', '4']
            corners_str = ", ".join([f"T{c}" for c in corner_nums])

            # Diagnose: Warum? (Wir schauen auf den Durchschnitt der Deltas dieser Kurven)
            avg_apex_delta = problem_corners["Delta_ApexSpeed"].mean()
            avg_exit_delta = problem_corners["Delta_ExitSpeed"].mean()

            reason = "general pace"
            if avg_apex_delta < -2:
                reason = f"poor rotation speed ({avg_apex_delta:.1f} km/h)"
            elif avg_exit_delta < -2:
                reason = f"traction deficit ({avg_exit_delta:.1f} km/h)"

            summary_lines.append(
                f"🔴 **Major Deficit**: Losing {loss_val:.2f}s in **{worst_type} corners** (mostly {corners_str}) due to {reason}."
            )

    # --- B. OPPONENT STRENGTH (Where is he better?) ---
    # Wir suchen Kurven mit krassem Exit-Unterschied
    exit_deficit = tl_df[
        tl_df["Delta_ExitSpeed"] < -4
    ]  # Wenn Gegner 4kmh schneller rauskommt
    if not exit_deficit.empty:
        top_exit = exit_deficit.sort_values("Delta_ExitSpeed").iloc[0]
        c_num = int(top_exit["Corner"])
        spd_diff = abs(top_exit["Delta_ExitSpeed"])
        summary_lines.append(
            f"⚠️ **Traction**: {driver_b} has stronger drive out of **T{c_num}** (+{spd_diff:.1f} km/h at exit)."
        )

    # --- C. OUR STRENGTH (Where are we winning?) ---
    # Wo gewinnen wir Zeit (TimeLoss < 0)?
    gaining_mask = tl_df["TimeLoss"] < 0
    if gaining_mask.any():
        gain_by_type = (
            tl_df[gaining_mask]
            .groupby("CornerType")["TimeLoss"]
            .sum()
            .sort_values(ascending=True)
        )
        if not gain_by_type.empty:
            best_type = gain_by_type.index[0]
            gain_val = abs(gain_by_type.iloc[0])
            summary_lines.append(
                f"✅ **Strength**: {driver_a}'s main gain is in **{best_type} sections** (-{gain_val:.2f}s)."
            )

    # ----------------------------------------------------
    # 3. THE "KEY FIX" (High Precision Advice)
    # ----------------------------------------------------
    # Wir nehmen die absolut schlechteste Kurve
    worst_corner = tl_df.sort_values("TimeLoss", ascending=False).iloc[0]

    key_fix = "Review consistency."

    if worst_corner["TimeLoss"] > 0.05:
        c_fix = int(worst_corner["Corner"])
        d_entry = worst_corner["Delta_EntrySpeed"]
        d_apex = worst_corner["Delta_ApexSpeed"]
        d_brake = worst_corner.get("Delta_AvgBrake", 0)

        # Data-Driven Advice Logic
        if d_entry < -5:
            # Wir bremsen zu früh
            key_fix = f"🎯 **Key Fix T{c_fix}**: Brake 5-10m later. You are giving away {abs(d_entry):.0f} km/h on entry."
        elif d_apex < -3:
            # Wir sind im Scheitel zu langsam
            key_fix = f"🎯 **Key Fix T{c_fix}**: Release brake earlier. Target +{abs(d_apex):.0f} km/h apex speed to reduce {worst_corner['TimeLoss']:.2f}s loss."
        elif worst_corner["Delta_ExitSpeed"] < -3:
            # Wir kommen schlecht raus
            key_fix = f"🎯 **Key Fix T{c_fix}**: Sacrifice entry speed. Square the exit to match {driver_b}'s traction (+{abs(worst_corner['Delta_ExitSpeed']):.0f} km/h)."
        else:
            key_fix = f"🎯 **Key Fix T{c_fix}**: Optimize line. losing {worst_corner['TimeLoss']:.2f}s despite similar inputs."

    return {
        "headline": headline,
        "type_summary": summary_lines,  # Das ist jetzt eine Liste von detaillierten Sätzen
        "key_fix": key_fix,
    }
