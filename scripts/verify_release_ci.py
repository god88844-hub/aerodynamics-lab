"""Verify AeroForge's software CI evidence for a frozen GitHub main commit."""

from __future__ import annotations

import argparse
import base64
from hashlib import sha256
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


WORKFLOW = ".github/workflows/ci.yml"
AUDIT_STEP = "Audit all frontend dependencies (including development tools)"
REQUIRED = {
    "python-tests": ("Audit locked backend dependencies", "Run pytest (physics, integration, regression)"),
    "web-build": (AUDIT_STEP, "Typecheck + build", "Unit tests"),
    "packaged-app": (
        "Verify browser, proxy, solver, and stored data",
        "Verify API responsiveness under load",
        "Verify authenticated HTTPS deployment",
    ),
}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Keep optional authorization headers on the GitHub API origin.
        return None


def read_json(path: str) -> dict:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2026-03-10"}
    token = os.getenv("AEROFORGE_GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"https://api.github.com{path}", headers=headers)
    with build_opener(NoRedirect).open(request, timeout=20) as response:
        return json.load(response)


def matches_run(run: dict, repo: str, commit: str, run_id: int) -> bool:
    return (
        run.get("id") == run_id
        and (run.get("repository") or {}).get("full_name", "").casefold() == repo.casefold()
        and (run.get("head_repository") or {}).get("full_name", "").casefold() == repo.casefold()
        and run.get("head_sha") == commit
        and run.get("head_branch") == "main"
        and run.get("event") == "push"
        and run.get("path") == WORKFLOW
    )


def check_attempt(run: dict, jobs: list[dict], workflow: bytes) -> dict:
    blockers = []
    if (run.get("status"), run.get("conclusion")) != ("completed", "success"):
        blockers.append("The selected GitHub workflow attempt has not succeeded")

    # Require the existing audited command as a distinct workflow step.
    audit = re.compile(r"(?m)^( +)- name: " + re.escape(AUDIT_STEP)
                       + r"\n\1  run: npm audit --audit-level=moderate\n(?=\1- |\n|\Z)")
    if not audit.search(workflow.decode("utf-8").replace("\r\n", "\n")):
        blockers.append("The frozen workflow lacks the required npm audit command step")

    verified = {}
    for name, required_steps in REQUIRED.items():
        candidates = [job for job in jobs if job.get("name") == name]
        if len(candidates) != 1:
            blockers.append(f"Expected exactly one GitHub job named {name}")
            continue
        job = candidates[0]
        if (job.get("run_id"), job.get("head_sha")) != (run["id"], run["head_sha"]):
            blockers.append(f"Job {name} differs from the frozen workflow run")
            continue
        if (job.get("status"), job.get("conclusion")) != ("completed", "success"):
            blockers.append(f"Job {name} has not succeeded")
        steps = job.get("steps", [])
        for step in required_steps:
            actual = [row for row in steps if row.get("name") == step]
            if len(actual) != 1 or (actual[0].get("status"), actual[0].get("conclusion")) != ("completed", "success"):
                blockers.append(f"Required step {step} in {name} has not succeeded")
        verified[name] = {"id": job.get("id"), "url": job.get("html_url"), "conclusion": job.get("conclusion")}

    return {
        "software_ci_verified": not blockers,
        "repository": run["repository"]["full_name"],
        "commit_sha": run["head_sha"],
        "run_id": run["id"],
        "attempt": run["run_attempt"],
        "run_url": run.get("html_url"),
        "workflow_sha256": sha256(workflow).hexdigest(),
        "required_jobs": verified,
        "blockers": blockers,
        "physical_acceptance": "requires_separate_measured_evidence_and_review",
    }


def verify(repo: str, commit: str, run_id: int) -> dict:
    base = f"/repos/{repo}"
    run = read_json(f"{base}/actions/runs/{run_id}")
    if not matches_run(run, repo, commit, run_id):
        raise ValueError("GitHub run must be this CI workflow's main push for the frozen commit")
    attempt = run.get("run_attempt")
    if type(attempt) is not int or attempt < 1:
        raise ValueError("GitHub Actions did not report a valid attempt number")
    jobs_document = read_json(f"{base}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100")
    jobs = jobs_document["jobs"]
    if len(jobs) != jobs_document["total_count"]:
        raise ValueError("GitHub returned an incomplete jobs page")
    source = read_json(f"{base}/contents/{WORKFLOW}?ref={commit}")
    if source.get("type") != "file" or source.get("encoding") != "base64" or source.get("path") != WORKFLOW:
        raise ValueError("GitHub did not return the frozen CI workflow file")
    return check_attempt(run, jobs, base64.b64decode("".join(source["content"].split()), validate=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("commit", help="Full frozen main commit SHA")
    parser.add_argument("run_id", type=int, help="GitHub Actions run ID for that main push")
    parser.add_argument("--repository", default="god88844-hub/aeroforge")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.commit) or args.run_id < 1:
        parser.error("supply a lowercase 40-character SHA and a positive run ID")
    if not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9_-][A-Za-z0-9_.-]*", args.repository):
        parser.error("repository must be a GitHub owner/name")
    try:
        report = verify(args.repository, args.commit, args.run_id)
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError, TypeError) as exc:
        print(f"CI evidence unavailable: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 0 if report["software_ci_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
