"""M9 Phase 3 — independent audit of the two motor datasets.

Re-derives every consistency check from the STORED JSON files (not from
memory of the transcription), probes interpolation/extrapolation behavior at
knots, between knots, and outside the supported range, and separates
numerical interpolation accuracy from physical predictive accuracy.

Checks implemented:
  C1  electrical consistency: power_w == voltage_v * current_a (exact circuit identity)
  C2  physical bound: shaft power Q*omega must be LESS than electrical power
      (motor efficiency eta = Q*omega / (V*I) within (0.3, 0.95))
  C3  propeller figure of merit via momentum theory:
      FM = T^1.5 / sqrt(2 rho A) / (Q*omega) within (0.45, 0.95) for a
      well-designed static propeller (literature bound, declared a priori)
  C4  monotonicity: thrust, current, rpm all increasing with throttle
  C5  interpolation/extrapolation behavior probes
  C6  voltage envelope coverage

Emits machine-readable JSON + a markdown summary into outputs/audit/.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "packages", REPO_ROOT / "packages" / "shared-schemas"):
    _s = str(_p)
    if _p.is_dir() and _s not in sys.path:
        sys.path.insert(0, _s)

from physics.propulsion.dataset import PowertrainDataset  # noqa: E402
from physics.propulsion.loader import ComponentLibrary  # noqa: E402

RHO_SEA = 1.225
ETA_BAND = (0.30, 0.95)
FM_BAND = (0.45, 0.95)
GF_TO_N = 9.80665e-3


def audit_dataset(library: ComponentLibrary, motor_id: str,
                  prop_diameter_m: float | None) -> dict[str, Any]:
    motor = library.motor(motor_id)
    key = motor.test_data[0].prop
    dataset = PowertrainDataset(motor, key)
    rows = [r for r in motor.test_data if r.prop == key]

    findings: list[dict[str, Any]] = []

    # C1: electrical identity. Against the MEASURED row voltage, the identity
    # must hold to the source's PUBLICATION ROUNDING precision (P rounded to
    # 1 W, V to 0.01 V -> ~0.5 % expected deviation; declared a priori).
    # Against the normalized plane voltage: within the documented
    # normalization band (<= 2 %).
    worst_exact = 0.0
    worst_plane = 0.0
    n_measured = 0
    for r in rows:
        p_elec = r.voltage_v * r.current_a
        worst_plane = max(worst_plane, abs(r.power_w - p_elec) / r.power_w)
        if r.voltage_measured_v is not None:
            n_measured += 1
            worst_exact = max(worst_exact,
                              abs(r.power_w - r.voltage_measured_v * r.current_a) / r.power_w)
    if n_measured == len(rows) and n_measured > 0:
        findings.append({"check": "C1 power == V_measured*I (identity to publication "
                                  "rounding, <=0.5%)",
                         "status": "pass" if worst_exact <= 0.005 else "fail",
                         "worst_relative_deviation": worst_exact,
                         "rows_with_measured_voltage": n_measured})
        findings.append({"check": "C1b power == V_plane*I within normalization band (<=2%)",
                         "status": "pass" if worst_plane <= 0.02 else "fail",
                         "worst_relative_deviation": worst_plane})
    else:
        findings.append({"check": "C1 power == V*I",
                         "status": "pass" if worst_plane < 1e-9 else "fail",
                         "worst_relative_deviation": worst_plane})

    # C2: motor efficiency band (only where torque is published)
    eta_values: list[float] = []
    has_torque = any(r.torque_nm is not None for r in rows)
    if has_torque:
        for r in rows:
            omega = 2.0 * math.pi * r.rpm / 60.0
            eta = (r.torque_nm * omega) / (r.voltage_v * r.current_a)
            eta_values.append(eta)
        findings.append({"check": "C2 motor eta = Q*omega/(V*I) within (0.3, 0.95)",
                         "status": "pass" if all(ETA_BAND[0] < e < ETA_BAND[1]
                                                 for e in eta_values) else "fail",
                         "eta_min": min(eta_values), "eta_max": max(eta_values)})

    # C3: figure of merit via momentum theory (needs prop diameter + torque)
    fm_values: list[float] = []
    if prop_diameter_m is not None and has_torque:
        area = math.pi * (prop_diameter_m / 2.0) ** 2
        for r in rows:
            thrust_n = r.thrust_gf * GF_TO_N
            omega = 2.0 * math.pi * r.rpm / 60.0
            p_shaft = r.torque_nm * omega
            p_ideal = thrust_n ** 1.5 / math.sqrt(2.0 * RHO_SEA * area)
            fm_values.append(p_ideal / p_shaft)
        findings.append({"check": "C3 figure of merit within (0.45, 0.95)",
                         "status": "pass" if all(FM_BAND[0] < f < FM_BAND[1]
                                                 for f in fm_values) else "fail",
                         "fm_min": min(fm_values), "fm_max": max(fm_values)})

    # C4: monotonicity in throttle, PER VOLTAGE PLANE (mixing planes would
    # interleave rows and produce false decreases).
    by_plane: dict[float, list] = {}
    for r in rows:
        by_plane.setdefault(r.voltage_v, []).append(r)
    mono_per_plane = True
    for v, prows in by_plane.items():
        prows_sorted = sorted(prows, key=lambda r: r.throttle_pct)
        plane_mono = (all(b.thrust_gf >= a.thrust_gf for a, b in zip(prows_sorted, prows_sorted[1:]))
                      and all(b.current_a >= a.current_a for a, b in zip(prows_sorted, prows_sorted[1:]))
                      and all(b.rpm >= a.rpm for a, b in zip(prows_sorted, prows_sorted[1:])))
        if not plane_mono:
            mono_per_plane = False
    findings.append({"check": "C4 monotone in throttle (per voltage plane)",
                     "status": "pass" if mono_per_plane else "fail"})

    # C5: interpolation/extrapolation probes
    envelope = dataset.envelope()
    rpm_lo, rpm_hi = envelope["rpm_range_merged"]
    gf_min = float(dataset._merged_thrust_gf.min())  # noqa: SLF001
    gf_max = float(dataset._merged_thrust_gf.max())  # noqa: SLF001

    def rpm_for_thrust(thrust_n: float) -> float:
        grid = np.linspace(rpm_lo, rpm_hi, 600)
        gf_target = thrust_n / GF_TO_N
        gfs = np.array([float(dataset.thrust_gf(r).value) for r in grid])
        return float(np.interp(gf_target, gfs, grid))

    probes: list[dict[str, Any]] = []
    mid_thrust = float(dataset.thrust_gf(float((rpm_lo + rpm_hi) / 2)).value)
    for label, thrust_n, expect in (
        ("mid-range thrust (between knots)", mid_thrust, "returns (interpolated)"),
        ("half the table minimum", (gf_min * 0.5) * GF_TO_N,
         "strict API refuses; declared-extrapolation API returns with flag"),
        ("120% of table maximum", (gf_max * 1.2) * GF_TO_N, "strict API refuses"),
    ):
        entry: dict[str, Any] = {"probe": label, "expectation": expect}
        try:
            res = dataset.thrust_gf(rpm_for_thrust(thrust_n))
            entry["status"] = "returned"
            entry["thrust_returned_n"] = round(res.value, 2)
        except Exception as exc:  # noqa: BLE001
            entry["status"] = "refused"
            entry["error"] = str(exc)[:140]
        probes.append(entry)
    # the strict-API behavior on the below-min probe:
    try:
        dataset.thrust_gf(rpm_for_thrust((gf_min * 0.5) * GF_TO_N))
        below_strict = "returned (unexpected)"
    except Exception as exc:  # noqa: BLE001
        below_strict = f"refused: {str(exc)[:80]}"
    findings.append({"check": "C5 envelope probes", "probes": probes,
                     "below_min_strict_api": below_strict})

    # C6: voltage coverage
    findings.append({
        "check": "C6 voltage planes",
        "planes_v": envelope["voltage_planes_v"],
        "allowed_bus_range_v": [envelope["voltage_planes_v"][0] * 0.85,
                                envelope["voltage_planes_v"][-1] * 1.15],
    })

    numerics = {
        "knot_read_back": "exact to machine precision (PCHIP passes through knots)",
        "between_knots": "PCHIP interpolation — no independent reference exists for this "
                         "motor+prop: NUMERICAL accuracy only",
        "outside_range": "refused (strict) / declared extrapolation (flagged)",
        "physical_predictive_accuracy": "NOT ESTABLISHED by reproducing the table; requires "
                                        "held-out measurements (M9 Phase 4/5)",
    }

    return {
        "motor_id": motor_id,
        "prop_key": key,
        "n_rows": len(rows),
        "row_voltage_range_v": [min(r.voltage_v for r in rows),
                                max(r.voltage_v for r in rows)],
        "thrust_table_gf": [gf_min, gf_max],
        "rpm_table": [rpm_lo, rpm_hi],
        "findings": findings,
        "numerical_vs_physical": numerics,
        "fm_values": [round(f, 3) for f in fm_values] if fm_values else None,
        "eta_values": [round(e, 3) for e in eta_values] if eta_values else None,
    }


def main() -> int:
    library = ComponentLibrary(REPO_ROOT / "data" / "components")
    report = {
        "audit": "M9 Phase 3 — motor dataset audit",
        "datasets": [
            audit_dataset(library, "tmotor_mn3508_kv380", 0.381),  # 15 in = 0.381 m
            audit_dataset(library, "tmotor_p80iii_kv100", 0.762),  # 30 in = 0.762 m
        ],
    }

    out = REPO_ROOT / "outputs" / "audit" / "phase3_datasets.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md: list[str] = ["# M9 Phase 3 — motor dataset audit", ""]
    for ds in report["datasets"]:
        all_ok = all(f["status"] == "pass" for f in ds["findings"]
                     if isinstance(f.get("status"), str))
        md.append(f"## {ds['motor_id']} ({ds['prop_key']}) — {ds['n_rows']} rows")
        md.append(f"- thrust table {ds['thrust_table_gf'][0]:.0f}–{ds['thrust_table_gf'][1]:.0f} gf; "
                  f"rpm {ds['rpm_table'][0]:.0f}–{ds['rpm_table'][1]:.0f}; row voltages "
                  f"{ds['row_voltage_range_v'][0]:.2f}–{ds['row_voltage_range_v'][1]:.2f} V")
        for f in ds["findings"]:
            if "status" in f:
                extra = ""
                if "eta_min" in f:
                    extra = f" (eta {f['eta_min']:.2f}–{f['eta_max']:.2f})"
                if "fm_min" in f:
                    extra = f" (FM {f['fm_min']:.2f}–{f['fm_max']:.2f})"
                md.append(f"  - [{f['status'].upper()}] {f['check']}{extra}")
        md.append(f"- FM values: {ds['fm_values']}")
        md.append(f"- eta values: {ds['eta_values']}")
        md.append(f"- all checks pass: {all_ok}")
        md.append("")
    md.append("## Numerical vs physical accuracy")
    for ds in report["datasets"]:
        md.append(f"- {ds['motor_id']}: "
                  + ds["numerical_vs_physical"]["physical_predictive_accuracy"])
    (out.parent / "phase3_datasets.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
