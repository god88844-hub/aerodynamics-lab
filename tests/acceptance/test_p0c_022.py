"""P0C-022: Four-family compatibility, project recovery preservation across cancelled/failed detailed jobs."""

from __future__ import annotations

import json

from desktop_worker.project_workflow import create_project_document, inspect_and_validate_project, save_and_version_project
from physics.aerodynamics.rotorcraft_vtol import execute_detailed_solver_job


def test_p0c_022_four_family_project_recovery_and_failed_job_isolation(tmp_path):
    for fam in ("multirotor", "fixed_wing", "helicopter", "vtol"):
        doc = create_project_document(f"Compat-{fam}", aircraft_family=fam)
        dest = tmp_path / fam / "project.json"
        save_and_version_project(doc, tmp_path, dest)
        failed_job = execute_detailed_solver_job(
            solver_kind="openfoam_rans", mesh_cell_count=9_000_000, estimated_ram_mb=32_000, available_ram_mb=16_000
        )
        assert failed_job["job_status"] == "refused_budget"
        reopened = inspect_and_validate_project(dest.read_text(encoding="utf-8"), dest.parent)
        assert reopened.aircraft_family == fam
        assert json.loads(dest.read_text(encoding="utf-8"))["document_version"] == "1.0"
