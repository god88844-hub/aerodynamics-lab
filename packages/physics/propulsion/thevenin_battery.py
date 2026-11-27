"""2-RC Thevenin electro-thermal battery model (transient polarization + thermal sag/cutoff)."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


@dataclass(frozen=True)
class Thevenin2RcParams:
    ocv_full_v: float = 25.2
    ocv_empty_v: float = 19.2
    capacity_ah: float = 16.0
    r0_ohm: float = 0.018
    r1_ohm: float = 0.008
    c1_f: float = 2500.0
    r2_ohm: float = 0.012
    c2_f: float = 12000.0
    thermal_cap_j_k: float = 650.0
    thermal_cond_w_k: float = 3.2
    max_temp_c: float = 65.0
    cutoff_voltage_v: float = 19.2
    provenance_status: str = "UNVERIFIED_ESTIMATE"


def simulate_thevenin_2rc_discharge(
    params: Thevenin2RcParams,
    *,
    current_profile_a: list[float],
    dt_s: float = 0.1,
    ambient_temp_c: float = 25.0,
) -> dict[str, Any]:
    """Simulate causal 2-RC polarization dynamics and cell-pack temperature evolution."""
    if dt_s <= 0.0 or not current_profile_a:
        raise ValueError("dt_s > 0 and non-empty current_profile_a required")

    soc = 1.0
    v1 = 0.0
    v2 = 0.0
    temp_c = float(ambient_temp_c)
    tau1 = params.r1_ohm * params.c1_f
    tau2 = params.r2_ohm * params.c2_f

    voltages = []
    temps = []
    socs = []
    verdict = "NO_MODELED_LIMIT_BREACHED"
    abort_reason: str | None = None

    for current_a in current_profile_a:
        if not math.isfinite(current_a) or current_a < 0.0:
            raise ValueError("Discharge current must be finite and >= 0")

        # Exact exponential ZOH update for each RC branch
        e1 = math.exp(-dt_s / max(1e-6, tau1))
        e2 = math.exp(-dt_s / max(1e-6, tau2))
        v1 = v1 * e1 + params.r1_ohm * current_a * (1.0 - e1)
        v2 = v2 * e2 + params.r2_ohm * current_a * (1.0 - e2)

        soc = max(0.0, soc - (current_a * dt_s) / (params.capacity_ah * 3600.0))
        ocv = params.ocv_empty_v + (params.ocv_full_v - params.ocv_empty_v) * soc
        v_term = ocv - current_a * params.r0_ohm - v1 - v2

        # Coupled Joule heating + Newtonian cooling
        p_heat = (current_a ** 2) * (params.r0_ohm + params.r1_ohm + params.r2_ohm)
        dtemp = (p_heat - params.thermal_cond_w_k * (temp_c - ambient_temp_c)) / params.thermal_cap_j_k
        temp_c += dtemp * dt_s

        voltages.append(float(v_term))
        temps.append(float(temp_c))
        socs.append(float(soc * 100.0))

        if v_term < params.cutoff_voltage_v:
            verdict = "FAIL"
            abort_reason = f"Loaded voltage {v_term:.2f} V dropped below cutoff {params.cutoff_voltage_v:.2f} V"
            break
        if temp_c > params.max_temp_c:
            verdict = "FAIL"
            abort_reason = f"Pack core temperature {temp_c:.1f} C exceeded limit {params.max_temp_c:.1f} C"
            break

    return {
        "schema_version": "1.0",
        "model": "thevenin_2rc_electrothermal",
        "provenance_status": params.provenance_status,
        "status": "failed" if abort_reason else "completed",
        "verdict": verdict,
        "abort_reason": abort_reason,
        "final_voltage_v": voltages[-1],
        "final_temp_c": temps[-1],
        "final_soc_pct": socs[-1],
        "voltages_v": voltages,
        "temps_c": temps,
        "physical_validation_status": "UNVALIDATED",
    }
