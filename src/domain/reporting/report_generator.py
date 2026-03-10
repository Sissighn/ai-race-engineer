from __future__ import annotations

"""
Report generation domain logic.
"""

import pandas as pd

from src.exceptions import ReportGenerationError
from src.logging import get_logger
from src.models import RaceEngineerReport

logger = get_logger(__name__)


def generate_race_engineer_report(
    tl_df: pd.DataFrame,
    agg_types_df: pd.DataFrame,
    driver_a: str,
    driver_b: str,
    track_name: str,
) -> dict[str, str | list[str]]:
    log_context = {
        "driver_a": driver_a,
        "driver_b": driver_b,
        "track": track_name,
        "rows": len(tl_df) if tl_df is not None else 0,
    }

    try:
        logger.info("Generating race engineer report", **log_context)

        if tl_df is None or tl_df.empty:
            report = RaceEngineerReport(
                headline="No Data Available",
                type_summary=["Insufficient telemetry data."],
                key_fix="Check data source.",
            )
            return report.model_dump()

        total_delta = tl_df["TimeLoss"].sum()
        gap = abs(total_delta)
        if total_delta > 0:
            headline = f"**{track_name} Analysis**: {driver_a} is **{gap:.3f}s ahead** of {driver_b}."
        else:
            headline = f"**{track_name} Analysis**: {driver_a} is **{gap:.3f}s behind** {driver_b}."

        summary_lines: list[str] = []

        losing_mask = tl_df["TimeLoss"] < 0
        if losing_mask.any():
            loss_by_type = (
                tl_df[losing_mask]
                .groupby("CornerType")["TimeLoss"]
                .sum()
                .sort_values(ascending=True)
            )

            if not loss_by_type.empty:
                worst_type = loss_by_type.index[0]
                loss_val = loss_by_type.iloc[0]

                problem_corners = tl_df[
                    (tl_df["CornerType"] == worst_type) & (tl_df["TimeLoss"] < -0.05)
                ].sort_values("TimeLoss", ascending=True)

                corner_nums = problem_corners["Corner"].astype(str).tolist()[:2]
                corners_str = ", ".join([f"T{c}" for c in corner_nums])

                avg_apex_delta = problem_corners["Delta_ApexSpeed"].mean()
                avg_exit_delta = problem_corners["Delta_ExitSpeed"].mean()

                reason = "general pace"
                if avg_apex_delta < -2:
                    reason = f"poor rotation speed ({avg_apex_delta:.1f} km/h)"
                elif avg_exit_delta < -2:
                    reason = f"traction deficit ({avg_exit_delta:.1f} km/h)"

                summary_lines.append(
                    f"🔴 **Major Deficit**: Losing {abs(loss_val):.2f}s in **{worst_type} corners** (mostly {corners_str}) due to {reason}."
                )

        exit_deficit = tl_df[tl_df["Delta_ExitSpeed"] < -4]
        if not exit_deficit.empty:
            top_exit = exit_deficit.sort_values("Delta_ExitSpeed").iloc[0]
            c_num = int(top_exit["Corner"])
            spd_diff = abs(top_exit["Delta_ExitSpeed"])
            summary_lines.append(
                f"⚠️ **Traction**: {driver_b} has stronger drive out of **T{c_num}** (+{spd_diff:.1f} km/h at exit)."
            )

        gaining_mask = tl_df["TimeLoss"] > 0
        if gaining_mask.any():
            gain_by_type = (
                tl_df[gaining_mask]
                .groupby("CornerType")["TimeLoss"]
                .sum()
                .sort_values(ascending=False)
            )
            if not gain_by_type.empty:
                best_type = gain_by_type.index[0]
                gain_val = gain_by_type.iloc[0]
                summary_lines.append(
                    f"✅ **Strength**: {driver_a}'s main gain is in **{best_type} sections** (+{gain_val:.2f}s)."
                )

        worst_corner = tl_df.sort_values("TimeLoss", ascending=True).iloc[0]
        key_fix = "Review consistency."

        if worst_corner["TimeLoss"] < -0.05:
            c_fix = int(worst_corner["Corner"])
            d_entry = worst_corner.get("Delta_EntrySpeed", 0)
            d_apex = worst_corner.get("Delta_ApexSpeed", 0)
            d_exit = worst_corner.get("Delta_ExitSpeed", 0)

            if d_entry < -5:
                key_fix = f"🎯 **Key Fix T{c_fix}**: Brake 5-10m later. You are giving away {abs(d_entry):.0f} km/h on entry."
            elif d_apex < -3:
                key_fix = f"🎯 **Key Fix T{c_fix}**: Release brake earlier. Target +{abs(d_apex):.0f} km/h apex speed to recover {abs(worst_corner['TimeLoss']):.2f}s."
            elif d_exit < -3:
                key_fix = f"🎯 **Key Fix T{c_fix}**: Sacrifice entry speed. Square the exit to match {driver_b}'s traction (+{abs(d_exit):.0f} km/h)."

        report = RaceEngineerReport(
            headline=headline,
            type_summary=summary_lines if summary_lines else ["Analysis inconclusive."],
            key_fix=key_fix,
        )
        return report.model_dump()

    except Exception as e:
        msg = f"Report generation failed for {driver_a} vs {driver_b}"
        logger.error(msg, error=str(e), **log_context, exc_info=True)
        raise ReportGenerationError(msg) from e
