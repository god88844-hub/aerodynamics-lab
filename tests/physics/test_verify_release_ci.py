"""Exercise frozen workflow provenance and the required release checks."""

from pathlib import Path
import runpy

import pytest

ROOT = Path(__file__).resolve().parents[2]
VERIFY = runpy.run_path(str(ROOT / "scripts/verify_release_ci.py"))


@pytest.fixture
def published_run():
    repository = {"full_name": "god88844-hub/aerodynamics-lab"}
    run = {"id": 200, "head_sha": "a" * 40, "repository": repository,
           "head_repository": repository, "head_branch": "main", "event": "push",
           "path": VERIFY["WORKFLOW"], "run_attempt": 2, "status": "completed", "conclusion": "success"}
    jobs = [{"name": name, "run_id": run["id"], "head_sha": run["head_sha"],
             "status": "completed", "conclusion": "success",
             "steps": [{"name": step, "status": "completed", "conclusion": "success"} for step in steps]}
            for name, steps in VERIFY["REQUIRED"].items()]
    return run, jobs, (ROOT / VERIFY["WORKFLOW"]).read_bytes()


def test_official_main_run_identity_is_bound_to_the_frozen_commit(published_run):
    run, _, _ = published_run
    matches = VERIFY["matches_run"]
    assert matches(run, "god88844-hub/aerodynamics-lab", "a" * 40, 200)
    assert not matches({**run, "event": "pull_request"}, "god88844-hub/aerodynamics-lab", "a" * 40, 200)
    assert not matches(run, "god88844-hub/aerodynamics-lab", "b" * 40, 200)


def test_full_verification_requires_every_packaged_and_audit_step(published_run):
    run, jobs, source = published_run
    verify = VERIFY["check_attempt"]
    assert verify(run, jobs, source)["software_ci_verified"]
    jobs[-1]["steps"][-1]["conclusion"] = "skipped"
    web_job = next(job for job in jobs if job["name"] == "web-build")
    web_job["steps"][0]["conclusion"] = "failure"
    report = verify(run, jobs, source)
    assert not report["software_ci_verified"]
    assert any("authenticated HTTPS" in reason for reason in report["blockers"])
    assert any("Audit all frontend" in reason for reason in report["blockers"])


def test_ci_success_status_cannot_replace_the_frozen_audit_command(published_run):
    run, jobs, source = published_run
    report = VERIFY["check_attempt"](run, jobs, source.replace(b"npm audit --audit-level=moderate", b"npm --version"))
    assert not report["software_ci_verified"]
    assert report["blockers"] == ["The frozen workflow lacks the required npm audit command step"]
