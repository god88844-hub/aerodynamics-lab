"""M10.8: optional arm-axis torsion and connection load screening.

This *extends* the verified M10.7 static bending screen without altering flight
solver mechanics or inferring arm-axis torques from rotor reaction yaw torque.
It reports distinct bending, torsion and joint-capacity margins: there is
NO combined-stress/fatigue/joint-flexibility/anisotropic failure model.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from aeroforge_schemas.design import DroneDesign
from physics.structures.beam import tube_second_moment
from physics.structures.envelope import evaluate_load_envelope
from physics.structures.materials import MaterialProps


def tube_polar_second_moment_m4(od_m: float, id_m: float) -> float:
    """J = pi/32(OD^4 - ID^4), identical to 2*I for circular tubes."""
    return 2.0 * tube_second_moment(od_m, id_m)


def tube_peak_torsional_shear_pa(torque_n_m: float, od_m: float, id_m: float) -> float:
    """Absolute peak linear-elastic shear at the tube outside radius."""
    if not math.isfinite(torque_n_m):
        raise ValueError("axial torque must be finite")
    stress = abs(torque_n_m) * (od_m / 2.0) / tube_polar_second_moment_m4(od_m, id_m)
    if not math.isfinite(stress):
        raise ValueError("torsional shear stress overflowed")
    return stress


def _positive_finite(value: object, name: str) -> float:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value <= 0):
        raise ValueError(f"{name} must be a finite positive number")
    return float(value)


def _source(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 240:
        raise ValueError(f"{name} must contain 1–240 characters of provenance")
    return value.strip()


def _triage(results: Sequence[bool | None]) -> bool | None:
    """False on a known exceedance; True only if all are assessed and pass."""
    if any(outcome is False for outcome in results):
        return False
    if results and all(outcome is True for outcome in results):
        return True
    return None


def evaluate_advanced_envelope(
    design: DroneDesign,
    cases: Sequence[tuple[str, Sequence[float], Sequence[float] | None]],
    materials: dict[str, MaterialProps],
    *,
    shear_allowable_pa: float | None = None,
    shear_allowable_source: str | None = None,
    joint_allowables: Mapping[str, object] | None = None,
) -> dict:
    """Add optional arm torsion and assumed joint-capacity screens to M10.7.

    Input is explicit, and absent torsional measurements are *unknown*, not zero.
    For each rotor the bending/torsion/joint checks are kept independent: two
    individually passing margins DO NOT establish a combined-stress pass.
    """
    # Existing bending analyzer validates frame, material, case count,
    # thrust count and nonnegative finite loads before we append results.
    report = evaluate_load_envelope(
        design, [(name, forces) for name, forces, _ in cases], materials
    )
    frame = design.frame
    assert frame is not None

    if shear_allowable_pa is None and shear_allowable_source is not None:
        raise ValueError("a shear allowable is required when giving its source")
    if shear_allowable_pa is not None and shear_allowable_source is None:
        raise ValueError("shear allowable requires an explicit evidence source")
    shear = (
        _positive_finite(shear_allowable_pa, "shear allowable")
        if shear_allowable_pa is not None else None
    )
    shear_source = (
        _source(shear_allowable_source, "shear source")
        if shear_allowable_source is not None else None
    )
    joint: dict[str, object] | None = None
    if joint_allowables is not None:
        joint = {
            "bending_moment_n_m": _positive_finite(
                joint_allowables.get("bending_moment_n_m"), "joint bending capacity"
            ),
            "axial_torque_n_m": _positive_finite(
                joint_allowables.get("axial_torque_n_m"), "joint axial torque capacity"
            ),
            "evidence_source": _source(
                joint_allowables.get("evidence_source"), "joint evidence source"
            ),
        }

    if len(cases) != len(report["cases"]):
        raise ValueError("case count mismatch")
    nrotors = len(design.rotors)
    torsion_results: list[bool | None] = []
    bend_joint_results: list[bool | None] = []
    torque_joint_results: list[bool | None] = []
    known_torque_cases = 0
    applied_torque_cases = 0
    joint_bend_applied = 0

    for raw, case_report in zip(cases, report["cases"]):
        name, _, torques = raw
        if torques is not None:
            if len(torques) != nrotors or not all(
                isinstance(t, (int, float)) and not isinstance(t, bool)
                and math.isfinite(t) for t in torques
            ):
                raise ValueError(f"case {name!r}: axial torques must match the "
                                 "rotor count and all be finite N*m")
            known_torque_cases += 1
            if any(t != 0 for t in torques):
                applied_torque_cases += 1

        for arm in case_report["rotors"]:
            i = arm["rotor_index"]
            torque = float(torques[i]) if torques is not None else None
            tau = (tube_peak_torsional_shear_pa(
                torque, frame.tube_od_m, frame.tube_id_m)
                if torque is not None else None)
            arm["arm_axial_torque_n_m"] = torque
            arm["tube_peak_shear_stress_pa"] = tau
            arm["tube_shear_margin"] = (
                shear / tau if shear is not None and tau is not None and tau > 0 else None
            )
            arm["tube_shear_below_allowable"] = (
                tau < shear if shear is not None and tau is not None and tau > 0 else None
            )
            torsion_results.append(arm["tube_shear_below_allowable"])

            moment = arm["root_bending_moment_n_m"]
            arm["joint_bending_margin"] = (
                joint["bending_moment_n_m"] / moment
                if joint is not None and moment > 0 else None
            )
            arm["joint_bending_below_allowable"] = (
                moment < joint["bending_moment_n_m"]
                if joint is not None and moment > 0 else None
            )
            bend_joint_results.append(arm["joint_bending_below_allowable"])
            if moment > 0:
                joint_bend_applied += 1
            arm["joint_axial_torque_margin"] = (
                joint["axial_torque_n_m"] / abs(torque)
                if joint is not None and torque is not None and torque != 0 else None
            )
            arm["joint_axial_torque_below_allowable"] = (
                abs(torque) < joint["axial_torque_n_m"]
                if joint is not None and torque is not None and torque != 0 else None
            )
            torque_joint_results.append(arm["joint_axial_torque_below_allowable"])

    # Zero load is not proof of reserve strength. Missing allowable or missing
    # load input remains unassessed, never silently interpreted as a pass.
    torsion_screen = _triage(torsion_results) if shear is not None else None
    joint_bend_screen = _triage(bend_joint_results) if joint is not None else None
    joint_torque_screen = _triage(torque_joint_results) if joint is not None else None
    report["advanced_loads"] = {
        "model_version": "M10.8-analytic-independent-v1",
        "torsion_polar_second_moment_m4": tube_polar_second_moment_m4(
            frame.tube_od_m, frame.tube_id_m
        ),
        "axial_torque_cases_with_data": known_torque_cases,
        "axial_torque_cases_total": len(cases),
        "nonzero_axial_torque_cases": applied_torque_cases,
        "shear_allowable_pa": shear,
        "shear_allowable_source": shear_source,
        "tube_torsion_screen": torsion_screen,
        "joint_allowables": joint,
        "joint_bending_screen": joint_bend_screen,
        "joint_axial_torque_screen": joint_torque_screen,
        "combined_interaction": "NOT_MODELED",
        "screening_verdict": (
            "EXCEEDS_DECLARED_LIMIT" if any(x is False for x in
                (torsion_screen, joint_bend_screen, joint_torque_screen))
            else "INCOMPLETE_EVIDENCE"
        ),
        "limitations": [
            "Arm-axis torques are supplied by the user; rotor reaction yaw torque "
            "is NOT assumed to be arm-axis torque",
            "Linear-elastic circular-tube torsion under a fixed-root assumption",
            "Joint allowable values are externally supplied and not validated by AeroForge",
            "Bending, tube torsion and joint-capacity checks are INDEPENDENT; "
            "combined stress interaction and connection load sharing are NOT modeled",
            "No motor mount, bolts, fatigue, buckling, shear-flow redistribution, "
            "composite failure modes, dynamic loads or physical validation",
        ],
    }
    return report
