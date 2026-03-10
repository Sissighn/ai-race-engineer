"""Compatibility shim for legacy imports."""

from src.domain.analysis.driver_dna import (
    calculate_driver_dna,
    compare_driver_dna,
    get_driver_dna_comparison_df,
)

__all__ = [
    "calculate_driver_dna",
    "compare_driver_dna",
    "get_driver_dna_comparison_df",
]
