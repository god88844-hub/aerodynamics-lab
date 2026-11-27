"""P0A-034: Guided learning workflow, equations/assumptions reference, and reproducible saved experiments."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from aeroforge_schemas.project import EngineeringProject
from desktop_worker.environment_authoring import author_test_ground
from desktop_worker.twin_comparison import compare_frozen_run_and_source, compute_dual_digital_twin_metrics
from geometry.fixed_wing_cad import ParametricWingSpec
from physics.aerodynamics.fixed_wing import compute_fixed_wing_cruise_trim, run_fixed_wing_mission
from physics.scenarios.desktop_runner import run_authoritative_desktop_simulation
from physics.scenarios.mission_authoring import author_mission

EQUATIONS_AND_ASSUMPTIONS: list[dict[str, str]] = [
    {
        "topic": "6-DoF rigid-body translation & attitude",
        "equation": "m * dv/dt = R(q_bw) * f_body + m * g_world; dq/dt = 0.5 * q (*) [0, omega_body]",
        "assumptions": "Flat non-rotating Earth, constant standard gravity 9.80665 m/s^2, rigid airframe with active Hamilton wxyz quaternion.",
    },
    {
        "topic": "Airframe equivalent drag & uniform wind",
        "equation": "F_drag = -0.5 * rho * CdA * |v_world - wind_world| * (v_world - wind_world)",
        "assumptions": "Incompressible low-Mach flight, constant uniform wind vector, no gust spectra or rotor-inflow wake coupling.",
    },
    {
        "topic": "Ideal gas air density scaling",
        "equation": "rho = P / (R_air * T), R_air = 287.058 J/(kg*K); T_max_scaled = T_max_static * (rho / 1.225)",
        "assumptions": "Dry-air ideal-gas density approximation; high-humidity/icing/rain multiphase aerodynamics remain refused.",
    },
    {
        "topic": "Prandtl lifting-line fixed-wing finite span aerodynamics",
        "equation": "CL = pi * AR * A_1; CDi = CL^2 / (pi * AR * e); e = 1 / (1 + sum(n * (A_n/A_1)^2))",
        "assumptions": "Incompressible attached-flow Mach <= 0.30, linear lift curve up to stall threshold; clean-room Re drag polar UNVALIDATED until wind-tunnel calibrated.",
    },
]


def _canon_hash(data: Any) -> str:
    return sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def create_guided_experiment_bundle(
    base_project: EngineeringProject | dict[str, Any],
    *,
    hypothesis: str,
    target_altitude_m: float = 3.0,
    hover_duration_s: float = 0.4,
    wind_world_m_s: tuple[float, float, float] = (0.0, 0.0, 0.0),
    temperature_k: float = 288.15,
    pressure_pa: float = 101325.0,
    seed: int = 42,
) -> dict[str, Any]:
    """Run baseline vs learner-modified configuration and freeze an exact replay bundle."""
    clean_hyp = hypothesis.strip()
    if not clean_hyp:
        raise ValueError("Learner hypothesis must be non-empty")

    base = (
        EngineeringProject.model_validate_json(base_project.canonical_bytes())
        if isinstance(base_project, EngineeringProject)
        else EngineeringProject.model_validate(base_project)
    )
    baseline_proj = author_mission(
        base,
        {
            "controller_dt_s": 0.005,
            "seed": seed,
            "phases": [
                {"phase": "takeoff", "duration_s": hover_duration_s, "target_altitude_m": 2.0},
                {"phase": "hover", "duration_s": hover_duration_s, "target_altitude_m": 2.0},
            ],
        },
    )
    baseline_run = run_authoritative_desktop_simulation(baseline_proj)

    modified_proj = author_test_ground(
        base,
        {
            "wind_world_m_s": list(wind_world_m_s),
            "temperature_k": temperature_k,
            "pressure_pa": pressure_pa,
            "relative_humidity": 0.0,
        },
    )
    modified_proj = author_mission(
        modified_proj,
        {
            "controller_dt_s": 0.005,
            "seed": seed,
            "phases": [
                {"phase": "takeoff", "duration_s": hover_duration_s, "target_altitude_m": target_altitude_m},
                {"phase": "hover", "duration_s": hover_duration_s, "target_altitude_m": target_altitude_m},
            ],
        },
    )
    modified_run = run_authoritative_desktop_simulation(modified_proj)

    base_peak = float(baseline_run["result"]["max_altitude_m"])
    mod_peak = float(modified_run["result"]["max_altitude_m"])
    base_vmin = float(baseline_run["result"]["min_bus_voltage_v"])
    mod_vmin = float(modified_run["result"]["min_bus_voltage_v"])

    bundle = {
        "schema_version": "1.0",
        "experiment_kind": "guided_learning_experiment_1",
        "hypothesis": clean_hyp,
        "equations_and_assumptions": EQUATIONS_AND_ASSUMPTIONS,
        "frozen_baseline_project": baseline_proj.model_dump(mode="json"),
        "frozen_modified_project": modified_proj.model_dump(mode="json"),
        "frozen_inputs_sha256": _canon_hash(modified_proj.model_dump(mode="json")),
        "comparison_summary": {
            "baseline_max_altitude_m": base_peak,
            "modified_max_altitude_m": mod_peak,
            "delta_max_altitude_m": mod_peak - base_peak,
            "baseline_min_bus_voltage_v": base_vmin,
            "modified_min_bus_voltage_v": mod_vmin,
            "delta_min_bus_voltage_v": mod_vmin - base_vmin,
            "baseline_status": baseline_run["result"]["status"],
            "modified_status": modified_run["result"]["status"],
        },
        "modified_telemetry_sha256": _canon_hash(modified_run["result"]["telemetry"]),
        "modified_dual_digital_twin": compute_dual_digital_twin_metrics(modified_run),
        "physical_validation_status": "UNVALIDATED",
    }
    return bundle


def save_and_reproduce_experiment(bundle: dict[str, Any], out_path: Path) -> dict[str, Any]:
    """Save a guided experiment bundle and reproduce its frozen modified run from disk."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(bundle, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    reloaded = json.loads(out_path.read_text(encoding="utf-8"))
    reproduced_run = run_authoritative_desktop_simulation(reloaded["frozen_modified_project"])
    reproduced_sha = _canon_hash(reproduced_run["result"]["telemetry"])
    return {
        "saved_path": str(out_path),
        "hypothesis": reloaded["hypothesis"],
        "original_telemetry_sha256": reloaded["modified_telemetry_sha256"],
        "reproduced_telemetry_sha256": reproduced_sha,
        "exact_reproduction": reproduced_sha == reloaded["modified_telemetry_sha256"],
        "equations_count": len(reloaded["equations_and_assumptions"]),
    }


def create_fixed_wing_lesson_bundle(
    wing: ParametricWingSpec,
    *,
    hypothesis: str,
    mass_kg: float = 1.8,
    cruise_airspeed_m_s: float = 18.0,
    duration_s: float = 8.0,
) -> dict[str, Any]:
    """Run baseline vs higher-aspect-ratio fixed-wing lesson comparing cruise trim and mission range."""
    if not hypothesis.strip():
        raise ValueError("Learner hypothesis must be non-empty")
    base_trim = compute_fixed_wing_cruise_trim(wing, mass_kg=mass_kg, airspeed_m_s=cruise_airspeed_m_s)
    base_mission = run_fixed_wing_mission(wing, mass_kg=mass_kg, duration_s=duration_s)

    stretched_wing = ParametricWingSpec(
        name=f"{wing.name}_high_ar",
        wingspan_m=wing.wingspan_m * 1.25,
        root_chord_m=wing.root_chord_m / 1.25,
        tip_chord_m=wing.tip_chord_m / 1.25,
        sweep_le_deg=wing.sweep_le_deg,
        dihedral_deg=wing.dihedral_deg,
        twist_tip_deg=wing.twist_tip_deg,
        airfoil_code=wing.airfoil_code,
        oswald_e=wing.oswald_e,
    )
    mod_trim = compute_fixed_wing_cruise_trim(stretched_wing, mass_kg=mass_kg, airspeed_m_s=cruise_airspeed_m_s)
    mod_mission = run_fixed_wing_mission(stretched_wing, mass_kg=mass_kg, duration_s=duration_s)
    return {
        "schema_version": "1.0",
        "experiment_kind": "guided_fixed_wing_lesson_1",
        "hypothesis": hypothesis.strip(),
        "equations_and_assumptions": EQUATIONS_AND_ASSUMPTIONS,
        "baseline_cruise_ld": float(base_trim["aero"]["lift_to_drag"]),
        "modified_cruise_ld": float(mod_trim["aero"]["lift_to_drag"]),
        "baseline_range_m": float(base_mission["range_m"]),
        "modified_range_m": float(mod_mission["range_m"]),
        "bundle_sha256": _canon_hash({"base": base_mission, "mod": mod_mission}),
        "physical_validation_status": "UNVALIDATED",
    }
