from typing import Any

from src.data.compare import compare_drivers_corner_level
from src.data.load_data import get_tracks_for_year, load_telemetry
from src.domain.analysis.coaching import coaching_suggestions
from src.domain.analysis.corner import (
    add_corner_classification,
    aggregate_time_loss_by_type,
    get_corner_type_advice,
)
from src.domain.analysis.time_loss import estimate_time_loss_per_corner
from src.domain.reporting.report_generator import generate_race_engineer_report
from src.models import ComparisonComputeResult, CornerAnalysisPayload


def get_tracks_for_year_for_ui(year: int) -> list[str]:
    return get_tracks_for_year(year)


def build_driver_map(session: Any) -> tuple[list[str], dict[str, str], list[str]]:
    drivers_with_cardata: set[str] = set()
    if hasattr(session, "car_data") and session.car_data:
        try:
            for drv_num, df in session.car_data.items():
                if df is not None and not df.empty:
                    drivers_with_cardata.add(str(drv_num))
        except Exception:
            pass

    if hasattr(session, "laps"):
        try:
            unique_drivers = sorted(session.laps["Driver"].unique())
        except Exception:
            unique_drivers = []
    else:
        unique_drivers = []

    driver_map: dict[str, str] = {}
    for code in unique_drivers:
        try:
            info = session.get_driver(code)
            fn = info.get("FirstName", info.get("given_name", ""))
            ln = info.get("LastName", info.get("family_name", ""))
            drv_num = str(info.get("DriverNumber", ""))
            has_tel = (not drivers_with_cardata) or drv_num in drivers_with_cardata
            label = f"{fn} {ln} ({code})" if has_tel else f"⚠️ {fn} {ln} ({code})"
            driver_map[label] = code
        except Exception:
            driver_map[code] = code

    no_tel_drivers = [
        code for label, code in driver_map.items() if label.startswith("⚠️")
    ]

    return list(driver_map.keys()), driver_map, no_tel_drivers


def compare_session_drivers(
    session: Any, driver_a: str, driver_b: str
) -> ComparisonComputeResult:
    tel_a = load_telemetry(session, driver_a)
    tel_b = load_telemetry(session, driver_b)

    missing = []
    if tel_a is None:
        missing.append(driver_a)
    if tel_b is None:
        missing.append(driver_b)

    if missing:
        return ComparisonComputeResult(
            missing=missing,
            tel_a=tel_a,
            tel_b=tel_b,
            comp=None,
            tl=None,
        )

    comp = compare_drivers_corner_level(session, driver_a, driver_b)
    tl = estimate_time_loss_per_corner(comp, driver_a, driver_b)

    return ComparisonComputeResult(
        missing=[],
        tel_a=tel_a,
        tel_b=tel_b,
        comp=comp,
        tl=tl,
    )


def build_corner_analysis(tl, driver_a: str, driver_b: str) -> CornerAnalysisPayload:
    tl_classified = add_corner_classification(tl)
    agg_types = aggregate_time_loss_by_type(tl_classified)
    advice_list = []

    if agg_types is not None and not agg_types.empty:
        advice_list = get_corner_type_advice(
            agg_types, driver_a=driver_a, driver_b=driver_b
        )

    return CornerAnalysisPayload(
        tl_classified=tl_classified,
        agg_types=agg_types,
        advice_list=advice_list,
    )


def build_race_engineer_report(
    tl_classified,
    agg_types,
    driver_a: str,
    driver_b: str,
    track: str,
):
    if agg_types is None or tl_classified is None or tl_classified.empty:
        return None

    return generate_race_engineer_report(
        tl_classified,
        agg_types,
        driver_a,
        driver_b,
        track,
    )


def build_coaching_suggestions(tl, driver_a: str, driver_b: str) -> list[str]:
    return coaching_suggestions(tl, driver_a, driver_b)
