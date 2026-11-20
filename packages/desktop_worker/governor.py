"""Supervisor-side resource checks and approval of prepared numerical results."""

from hashlib import file_digest
import os
from pathlib import Path
import time

from desktop_worker.io import json_bytes, write_result
from desktop_worker.metrics import ProcessTreeObserver
from desktop_worker.resources import capacity_snapshot, runtime_failure, workspace_size
from desktop_worker.supervision import PROTOCOL, read_record


def digest(path: Path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


class BudgetGovernor:
    def __init__(self, session, budget):
        self.session = session
        self.budget = budget
        self.observer = ProcessTreeObserver(os.getpid(), retain_samples=False)
        self.last_sample = -1.0
        self.usage = {"contract_version": budget.contract_version, "session_id": session.name,
                      "sample_count": 0, "peak_resident_bytes": 0, "peak_workspace_bytes": 0}

    def check(self, *, force=False):
        if not force and time.monotonic() - self.last_sample < 0.1:
            return None
        sample = self.observer.sample()
        resident = sum(process["resident_bytes"] for process in sample["processes"])
        workspace = workspace_size(self.session)
        capacity = capacity_snapshot(self.session)
        self.usage.update(sample_count=self.usage["sample_count"] + 1,
                          latest_resident_bytes=resident, latest_workspace_bytes=workspace,
                          capacity=capacity, observed_processes=[p for p in sample["processes"]],
                          peak_resident_bytes=max(resident, self.usage["peak_resident_bytes"]),
                          peak_workspace_bytes=max(workspace, self.usage["peak_workspace_bytes"]))
        failure = runtime_failure(self.budget, capacity, resident, workspace)
        self.usage["failure"] = failure
        write_result(self.session / "resource-usage.json", self.usage)
        self.last_sample = time.monotonic()
        return failure

    def approve(self, job_id):
        directory = self.session / "jobs" / job_id
        prepared_path = directory / "prepared.json"
        if not prepared_path.is_file() or (directory / "approved.json").exists():
            return None
        failure = self.check(force=True)
        if failure:
            return failure
        prepared = read_record(prepared_path)
        expected = {"protocol": PROTOCOL, "session_id": self.session.name, "job_id": job_id,
                    "request_sha256": digest(directory / "request.json"),
                    "output_sha256": digest(directory / "result.json")}
        if any(prepared.get(key) != value for key, value in expected.items()):
            raise ValueError("Prepared result does not match this frozen job")
        approval = {**expected, "resource_usage": self.usage}
        # Count publication records as well as native output before success.
        # 4096 bytes covers the bounded completion receipt and active cleanup.
        if workspace_size(self.session) + len(json_bytes(approval)) + 4096 > self.budget.workspace_bytes:
            return "workspace_budget_exceeded"
        write_result(directory / "approved.json", approval)
        return None

    def close(self):
        self.observer.close()
