"""Headless client for the same on-disk protocol used by the desktop."""

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

from desktop_worker.io import json_bytes, write_result
from desktop_worker.supervision import stop_session
from desktop_worker.resources import ResourceBudget


class WorkerClient:
    def __init__(self, root: Path, session_parent: Path, *, python: str = sys.executable,
                 owner_pid: int | None = None, job_timeout: float = 60, idle_timeout: float = 300,
                 resources: ResourceBudget | None = None):
        self.session_id = uuid4().hex
        self.session = session_parent.resolve() / self.session_id
        self.session.mkdir(parents=True, mode=0o700)
        self.resources = resources or ResourceBudget()
        write_result(self.session / "resource-request.json", self.resources.document())
        self.process = subprocess.Popen([
            python, str(root / "scripts/lab_worker.py"), "--session", str(self.session),
            "--session-id", self.session_id, "--owner-pid", str(owner_pid or os.getpid()),
            "--job-timeout", str(job_timeout), "--idle-timeout", str(idle_timeout),
            "--resources-file", str(self.session / "resource-request.json")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        self.last_job = None

    def wait_ready(self, timeout: float = 35) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if (self.session / "ready.json").exists():
                ready = json.loads((self.session / "ready.json").read_bytes())
                if ready.get("protocol") != "desktop_worker_1" or ready.get("session_id") != self.session_id:
                    raise ValueError("Worker readiness belongs to a different session")
                return ready
            if self.process.poll() is not None:
                retired = self.session / "retired.json"
                reason = json.loads(retired.read_bytes()).get("reason") if retired.exists() else "inspect its session log"
                raise RuntimeError("CAD worker failed to start: " + str(reason))
            time.sleep(0.01)
        raise TimeoutError("CAD worker readiness deadline exceeded")

    def request(self, operation: str, payload: dict, *, asset_root: Path | None = None, timeout: float = 95) -> dict:
        if (self.session / "retired.json").exists() or self.process.poll() is not None:
            raise RuntimeError("Worker has retired; create a new session")
        job_id = uuid4().hex
        packet = {"protocol": "desktop_worker_1", "session_id": self.session_id,
                  "job_id": job_id, "operation": operation, "payload": payload,
                  "resources": self.resources.document(),
                  "asset_root": str(asset_root.resolve()) if asset_root is not None else None}
        if (self.session / "pending.json").exists():
            raise RuntimeError("The worker already has a queued request")
        self.last_job = self.session / "jobs" / job_id
        digest = sha256(json_bytes(packet)).hexdigest()
        write_result(self.session / "pending.json", packet)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            error = self.last_job / "error.json"
            if error.is_file():
                failure = json.loads(error.read_bytes())
                if any(failure.get(key) != value for key, value in (("protocol", "desktop_worker_1"),
                       ("session_id", self.session_id), ("job_id", job_id), ("request_sha256", digest))):
                    raise ValueError("Worker error does not match this request")
                raise RuntimeError(failure.get("error", "Worker request failed"))
            receipt_path = self.last_job / "complete.json"
            if receipt_path.is_file():
                receipt = json.loads(receipt_path.read_bytes())
                result = (self.last_job / "result.json").read_bytes()
                if any(receipt.get(key) != value for key, value in (
                    ("protocol", "desktop_worker_1"), ("session_id", self.session_id),
                    ("job_id", job_id), ("request_sha256", digest), ("output_sha256", sha256(result).hexdigest()))):
                    raise ValueError("Worker completion does not match this session, request and result")
                verify_approval(self.last_job, receipt)
                return json.loads(result)
            if (self.session / "retired.json").exists() or self.process.poll() is not None:
                raise RuntimeError("Worker retired before publishing this job's result")
            time.sleep(0.01)
        raise TimeoutError("Worker result deadline exceeded")

    def close(self):
        if (self.session / "supervisor.json").is_file():
            stop_session(self.session, self.session_id)
        elif self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=5)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def verify_approval(directory: Path, receipt: dict) -> None:
    raw = (directory / "approved.json").read_bytes()
    approval = json.loads(raw)
    if receipt.get("resource_approval_sha256") != sha256(raw).hexdigest() or any(
        approval.get(key) != receipt.get(key)
        for key in ("protocol", "session_id", "job_id", "request_sha256", "output_sha256")
    ):
        raise ValueError("Resource approval does not match this completion")
