"""Unified Virtual-vs-Real Evidence Scorecard across numerical parity, benchmarks, and custom envelopes."""

from __future__ import annotations

import math
from typing import Any


def compute_virtual_evidence_scorecard(
    *,
    vehicle_family: str,
    cpp_mass_kg: float,
    python_mass_kg: float,
    clearance_ok: bool,
    mach: float,
    alpha_deg: float,
    has_custom_modified_part: bool = False,
    benchmark_twin_percent: float | None = None,
) -> dict[str, Any]:
    """Classify virtual vs physical confidence transparently without overclaiming."""
    for name, val in (
        ("cpp_mass_kg", cpp_mass_kg),
        ("python_mass_kg", python_mass_kg),
        ("mach", mach),
        ("alpha_deg", alpha_deg),
    ):
        if not math.isfinite(val):
            raise ValueError(f"{name} must be finite")

    mass_rel_diff = abs(cpp_mass_kg - python_mass_kg) / max(1e-9, abs(python_mass_kg))
    numerical_parity_pass = mass_rel_diff <= 1e-6

    envelope_failures: list[str] = []
    if not clearance_ok:
        envelope_failures.append("rotor_tip_clearance_below_minimum")
    if mach > 0.30:
        envelope_failures.append(f"incompressible_mach_exceeded:{mach:.3f}>0.30")
    if abs(alpha_deg) > 14.0:
        envelope_failures.append(f"stall_envelope_exceeded:|alpha|={abs(alpha_deg):.2f}>14.0")

    if envelope_failures:
        overall_status = "FAIL"
    elif has_custom_modified_part:
        overall_status = "UNVALIDATED_CUSTOM"
    elif numerical_parity_pass:
        overall_status = "DEVELOPMENT"
    else:
        overall_status = "INCONCLUSIVE"

    return {
        "schema_version": "1.0",
        "vehicle_family": vehicle_family,
        "numerical_verification": {
            "cpp_python_mass_rel_diff": mass_rel_diff,
            "parity_pass": numerical_parity_pass,
        },
        "pinned_benchmark_status": "DEVELOPMENT",
        "benchmark_twin_percent": benchmark_twin_percent,
        "envelope_failures": envelope_failures,
        "custom_modification_present": has_custom_modified_part,
        "physical_acceptance_granted": False,
        "overall_status": overall_status,
    }
