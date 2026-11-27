"""P0B-019: Fixed-wing CAD application recovery, exchange/run/save/reopen/cancel, and multirotor preservation."""

from __future__ import annotations

import json

from desktop_worker.project_workflow import create_project_document, inspect_and_validate_project, save_and_version_project
from geometry.fixed_wing_cad import ParametricWingSpec, export_cad_exchange_manifest, import_cad_exchange_manifest
from physics.aerodynamics.fixed_wing import run_fixed_wing_analysis_job, run_fixed_wing_mission


def _wing() -> ParametricWingSpec:
    return ParametricWingSpec(
        name="AeroGlider-Wing",
        wingspan_m=1.80,
        root_chord_m=0.26,
        tip_chord_m=0.14,
        sweep_le_deg=4.0,
        dihedral_deg=3.0,
        twist_tip_deg=-2.0,
        airfoil_code="2412",
        material_density_kg_m3=110.0,
        density_source="UNVERIFIED_ESTIMATE_EPS_CARBON_SPAR",
    )


def test_p0b_019_fixed_wing_edit_exchange_cancel_save_and_multirotor_compatibility(tmp_path):
    wing = _wing()
    manifest = export_cad_exchange_manifest(wing, exchange_format="STEP_AP214")
    assert import_cad_exchange_manifest(manifest)["wingspan_m"] == wing.wingspan_m

    cancelled_job = run_fixed_wing_analysis_job(wing, cancel_requested=True)
    assert cancelled_job["status"] == "cancelled"

    mission = run_fixed_wing_mission(wing, mass_kg=1.8, duration_s=4.0)
    proj_file = tmp_path / "fw_recovery.json"
    proj_file.write_text(json.dumps({"cad": manifest, "mission": mission}), encoding="utf-8")
    reloaded = json.loads(proj_file.read_text(encoding="utf-8"))
    assert reloaded["mission"]["verdict"] == "NO_MODELED_LIMIT_BREACHED"

    # Existing multirotor standalone create/save/version/recover workflow remains intact
    mr_doc = create_project_document("MR-Compat-Check", aircraft_family="multirotor")
    mr_dest = tmp_path / "mr_proj" / "project.json"
    save_and_version_project(mr_doc, tmp_path, mr_dest)
    reopened = inspect_and_validate_project(mr_dest.read_text(encoding="utf-8"), mr_dest.parent)
    assert reopened.aircraft_family == "multirotor"
