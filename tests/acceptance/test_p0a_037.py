"""P0A-037: Regression, dependency security, budget refusal, and headless compatibility suite."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from aeroforge_schemas.project import EngineeringProject, import_legacy_project
from app.main import app
from desktop_worker.project_workflow import ProjectWorkflowError, inspect_and_validate_project, recover_last_valid_project
from desktop_worker.resources import ResourceBudget
from physics.scenarios.desktop_runner import run_authoritative_desktop_simulation

ROOT = Path(__file__).resolve().parents[2]
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"
LEGACY_DESIGN = ROOT / "data" / "designs" / "quad_mn3508_6s.json"


def test_ci_workflow_preserves_five_required_jobs_and_unbypassed_security_audits():
    text = CI_YML.read_text(encoding="utf-8").replace("\r\n", "\n")
    for job in ("windows-worker:", "desktop-foundation:", "python-tests:", "web-build:", "packaged-app:"):
        assert job in text, f"missing CI job {job}"
    assert "npm audit --audit-level=moderate" in text
    assert "--omit=dev" not in text
    assert "--require-hashes" in text
    assert "check_master_plan.py --check" in text
    assert "reconcile_registry.py --check" in text
    assert "export_contracts.py --check" in text


def test_migration_incompatible_assets_recovery_budgets_and_api_compatibility(tmp_path):
    raw_legacy = json.loads(LEGACY_DESIGN.read_text(encoding="utf-8"))
    migrated = import_legacy_project(raw_legacy)
    assert migrated.document_version == "1.0"

    # Incompatible document version refuses fail-closed
    bad_ver = migrated.model_dump(mode="json")
    bad_ver["document_version"] = "99.0"
    with pytest.raises(ProjectWorkflowError) as exc_info:
        inspect_and_validate_project(json.dumps(bad_ver), tmp_path)
    assert exc_info.value.category == "incompatible_version"

    # Save + corrupt + recover preserves last valid project
    proj_path = tmp_path / "project.json"
    proj_path.write_text(migrated.canonical_bytes().decode("utf-8"), encoding="utf-8")
    from desktop_worker.project_workflow import write_recovery_snapshot

    write_recovery_snapshot(migrated, proj_path, tmp_path)
    proj_path.write_text("{broken", encoding="utf-8")
    rec = recover_last_valid_project(proj_path, restore_to=proj_path)
    assert rec["project_sha256"] == migrated.fingerprint()

    # Budget refusal leaves project unchanged
    budget = ResourceBudget(memory_bytes=512 * 1024 * 1024, workspace_bytes=128 * 1024 * 1024, wall_time_s=10.0)
    assert budget.contract_version == "local_cad_resources_1"
    with pytest.raises(ValueError, match="step_budget_exceeded"):
        run_authoritative_desktop_simulation(migrated, dt_s=0.0001, step_budget=10)

    # Headless API /projects/validate compatibility
    doc = {"id": str(uuid4()), "name": "Compat Check", "aircraft_family": "multirotor", "vehicle": {"format": "assembly_1"}}
    with TestClient(app) as client:
        resp = client.post("/api/projects/validate", json=doc)
        schema_resp = client.get("/api/projects/schema")
    assert resp.status_code == 200
    assert schema_resp.status_code == 200
