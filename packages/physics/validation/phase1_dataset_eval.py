"""Phase 1 collected public benchmark verification evaluator (DEVELOPMENT provenance only)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from aeroforge_schemas.bioinspired import FlappingWingKinematics
from physics.aerodynamics.bioinspired_flapping import evaluate_flapping_cycle_quasi_steady

ROOT = Path(__file__).resolve().parents[3]
PUBLIC_DIR = ROOT / "data" / "benchmarks" / "public"


def evaluate_delfly_flex_benchmark() -> dict[str, Any]:
    """Verify measured TU Delft DelFly Flex vs DelFly Nimble 6-DOF balance forces/moments (CC-BY-4.0)."""
    payload = json.loads((PUBLIC_DIR / "delfly_flex_2026" / "forces_moments_benchmark.json").read_text(encoding="utf-8"))
    flex_rows = payload["delfly_flex"]
    nimble_rows = payload["delfly_nimble"]
    flex_hover_fy = [r["fy_n"] for r in flex_rows if r["maneuver"] == "hover_neutral"]
    nimble_hover_fy = [r["fy_n"] for r in nimble_rows if r["maneuver"] == "hover_neutral"]
    flex_pitch_fwd_mx = [r["mx_n_mm"] for r in flex_rows if r["maneuver"] == "pitch_forward"]
    flex_pitch_bwd_mx = [r["mx_n_mm"] for r in flex_rows if r["maneuver"] == "pitch_backward"]
    return {
        "benchmark_id": "delfly_flex_2026",
        "license": payload["license"],
        "policy_role": "DEVELOPMENT",
        "flex_rows": len(flex_rows),
        "nimble_rows": len(nimble_rows),
        "flex_mean_hover_fy_n": round(sum(flex_hover_fy) / len(flex_hover_fy), 5),
        "nimble_mean_hover_fy_n": round(sum(nimble_hover_fy) / len(nimble_hover_fy), 5),
        "pitch_moment_reversal_verified": (sum(flex_pitch_fwd_mx) > 0.0 and sum(flex_pitch_bwd_mx) < 0.0),
    }


def evaluate_flapsim_flapper_baseline() -> dict[str, Any]:
    """Evaluate clean-room quasi-steady flapping hover lift against Apache-2.0 FlapSim 30g wing parameters."""
    wp = json.loads((PUBLIC_DIR / "flapsim_single_thrust_flapper" / "wing_parameters.json").read_text(encoding="utf-8"))
    kin = FlappingWingKinematics(
        wing_span_r_m=float(wp["R"]),
        mean_chord_c_m=float(wp["c"]),
        flap_frequency_hz=40.0,
        stroke_amplitude_rad=1.5,
        stroke_plane_angle_rad=0.0,
        feathering_amplitude_rad=0.78,
        deviation_amplitude_rad=0.0,
        r11_moment=float(wp["r11"]),
        r22_moment=float(wp["r22"]),
        r33_moment=float(wp["r33"]),
    )
    res = evaluate_flapping_cycle_quasi_steady(kin, vehicle_mass_kg=0.030, rho_kg_m3=float(wp["rho"]), n_wings=2)
    return {
        "benchmark_id": "flapsim_single_thrust_flapper",
        "license": "Apache-2.0",
        "policy_role": "DEVELOPMENT",
        "wing_radius_m": wp["R"],
        "hover_tw": round(res["hover_thrust_to_weight"], 3),
        "peak_tip_mach": round(res["peak_tip_mach"], 4),
        "reduced_frequency_k": round(res["reduced_frequency_k"], 4),
        "verdict": res["verdict"],
    }


def evaluate_pigeonbot_manifest_and_avian_ct() -> dict[str, Any]:
    """Verify PigeonBot II 81-state morph manifest and Bristol CT density calibration monotonicity."""
    pb = json.loads((PUBLIC_DIR / "pigeonbot_ii_2024" / "morph_matrix_manifest.json").read_text(encoding="utf-8"))
    ct = json.loads((PUBLIC_DIR / "calibrated_ct_avian_inertia_2021" / "calibration_curves.json").read_text(encoding="utf-8"))
    bo1 = ct["specimens"]["bo1_tyto_alba"]["points"]
    pf4 = ct["specimens"]["pf4_falco_peregrinus"]["points"]
    # Density sorted order monotonically increases with normalized CT gray intensity
    bo1_sorted = sorted(bo1, key=lambda x: x[1])
    pf4_sorted = sorted(pf4, key=lambda x: x[1])
    bo1_mono = all(bo1_sorted[i][0] < bo1_sorted[i + 1][0] for i in range(len(bo1_sorted) - 1))
    pf4_mono = all(pf4_sorted[i][0] < pf4_sorted[i + 1][0] for i in range(len(pf4_sorted) - 1))
    grid = pb["sweep_grid"]
    n_morph_combos = len(grid["dev_idx"]) * len(grid["aoa_idx"]) * len(grid["wing_idx"]) * len(grid["tail_idx"])
    return {
        "pigeonbot_morph_combos": n_morph_combos,
        "pigeonbot_turbulence_levels": len(grid["turbulence_ti_pct"]),
        "ct_bo1_monotonic": bo1_mono,
        "ct_pf4_monotonic": pf4_mono,
        "policy_role": "DEVELOPMENT",
    }


def evaluate_all_phase1_datasets() -> dict[str, Any]:
    """Run all collected Phase 1 dataset interface & analytical baseline verifications."""
    return {
        "schema_version": "1.0",
        "phase": 1,
        "policy_role": "DEVELOPMENT",
        "physical_acceptance_granted": False,
        "delfly_flex_2026": evaluate_delfly_flex_benchmark(),
        "flapsim_single_thrust_flapper": evaluate_flapsim_flapper_baseline(),
        "pigeonbot_and_avian_ct": evaluate_pigeonbot_manifest_and_avian_ct(),
    }
