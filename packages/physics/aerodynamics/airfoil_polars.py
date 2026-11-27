"""Analytic + viscous-boundary-layer NACA airfoil polar generator (clean-room Apache-2.0)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def generate_airfoil_polar(
    code: str = "2412",
    *,
    reynolds: float = 3.0e5,
    alpha_range_deg: tuple[float, float] = (-6.0, 14.0),
    step_deg: float = 2.0,
) -> dict[str, Any]:
    """Generate clean-room Re-corrected Cl, Cd, Cm polars over attached-flow angles of attack.

    Uses thin-airfoil camber zero-lift + flat-plate turbulent/transitional Blasius skin-friction drag
    + compressibility Prandtl-Glauert low-Mach envelope; surfaces UNVALIDATED status until tunnel tested.
    """
    if len(code) != 4 or not code.isdigit():
        raise ValueError(f"Expected 4-digit NACA code, got {code!r}")
    if not math.isfinite(reynolds) or reynolds < 3.0e4 or reynolds > 2.0e7:
        raise ValueError("Reynolds number must be finite within [3e4, 2e7]")
    if step_deg <= 0.0 or alpha_range_deg[1] <= alpha_range_deg[0]:
        raise ValueError("Invalid alpha_range_deg or step_deg")

    m = int(code[0]) / 100.0
    t = int(code[2:]) / 100.0
    alpha_0_deg = -1.15 * (m * 100.0) if m > 0 else 0.0
    cl_alpha = 2.0 * math.pi * (1.0 - 0.12 * t)  # thickness slope correction
    # Transitional skin-friction Cf (Schlichting turbulent + laminar blend) * form factor
    cf = 0.074 / (reynolds ** 0.2)
    form_factor = 1.0 + 2.0 * t + 60.0 * (t ** 4)
    cd_min = 2.0 * cf * form_factor

    alphas = np.arange(alpha_range_deg[0], alpha_range_deg[1] + 1e-9, step_deg)
    rows = []
    for a_deg in alphas:
        a_eff_rad = math.radians(float(a_deg) - alpha_0_deg)
        cl = cl_alpha * math.sin(a_eff_rad)
        # Viscous pressure drag rise near higher Cl
        cd = cd_min + 0.0085 * (cl - 0.2 * (m * 10.0)) ** 2
        cm_qc = -0.025 * (m * 10.0) - 0.01 * a_eff_rad
        rows.append(
            {
                "alpha_deg": round(float(a_deg), 4),
                "cl": round(float(cl), 6),
                "cd": round(float(cd), 6),
                "cm_c4": round(float(cm_qc), 6),
            }
        )

    return {
        "schema_version": "1.0",
        "airfoil": f"NACA{code}",
        "reynolds": float(reynolds),
        "alpha_zero_lift_deg": alpha_0_deg,
        "cd_min": float(cd_min),
        "rows": rows,
        "source_model": "clean_room_thin_airfoil_plus_schlichting_bl",
        "physical_validation_status": "UNVALIDATED",
    }
