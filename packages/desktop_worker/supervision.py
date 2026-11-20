"""Standard-library supervisor, kept independent of a busy native CAD engine.

Supports the current Windows desktop and Linux CI. Process birth identities
prevent a stored PID from authorizing termination of a subsequently reused PID.
"""

import ctypes
from ctypes import wintypes
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from desktop_worker.io import write_result

PROTOCOL = "desktop_worker_1"
IDENTIFIER = re.compile(r"^[0-9a-f]{32}$")


def source_identity(root: Path) -> str:
    paths = [*root.glob("packages/**/*.py"), *root.glob("apps/api/app/**/*.py"),
             *root.glob("data/components/**/*.json"), root / "scripts/lab_worker.py",
             root / "apps/api/requirements.lock", root / "apps/desktop/requirements-cad.lock"]
    record = {path.relative_to(root).as_posix(): sha256(path.read_bytes()).hexdigest() for path in sorted(paths)}
    return sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ProcessRef:
    def __init__(self, pid: int):
        if pid <= 1:
            raise ValueError("A monitored process needs a positive non-system PID")
        self.pid = pid
        self.handle = None
        if os.name == "nt":
            self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            self.kernel.OpenProcess.restype = wintypes.HANDLE
            self.kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
            self.kernel.GetProcessTimes.restype = wintypes.BOOL
            self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            self.kernel.WaitForSingleObject.restype = wintypes.DWORD
            self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            self.kernel.CloseHandle.restype = wintypes.BOOL
            self.handle = self.kernel.OpenProcess(0x100000 | 0x1000, False, pid)
            if not self.handle:
                error = ctypes.get_last_error()
                if error in (87, 1168):
                    raise ProcessLookupError(f"Process {pid} has exited")
                raise ctypes.WinError(error)
            timestamps = [wintypes.FILETIME() for _ in range(4)]
            if not self.kernel.GetProcessTimes(self.handle, *(ctypes.byref(item) for item in timestamps)):
                self.close()
                raise OSError("Cannot read process creation identity")
            self.birth = str((timestamps[0].dwHighDateTime << 32) | timestamps[0].dwLowDateTime)
        elif sys.platform.startswith("linux"):
            self.birth, _ = self._linux_identity()
        else:
            raise ValueError("Reusable worker supervision currently supports Windows and Linux")

    def _linux_identity(self):
        fields = Path(f"/proc/{self.pid}/stat").read_text().rsplit(")", 1)[1].split()
        return fields[19], fields[0]

    def alive(self) -> bool:
        if os.name == "nt":
            state = self.kernel.WaitForSingleObject(self.handle, 0)
            if state == 0xFFFFFFFF:
                raise OSError("Could not inspect the monitored process")
            return state == 0x102
        try:
            birth, state = self._linux_identity()
            return birth == self.birth and state not in ("Z", "X")
        except FileNotFoundError:
            return False

    def record(self) -> dict:
        return {"pid": self.pid, "birth": self.birth}

    def close(self):
        if self.handle is not None:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def terminate_record(record: dict, *, group: bool) -> None:
    try:
        process = ProcessRef(int(record["pid"]))
    except (ProcessLookupError, FileNotFoundError):
        return
    try:
        if process.birth != record["birth"] or not process.alive():
            return
        if os.name == "nt":
            result = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode and process.alive():
                raise OSError("Could not terminate the owned worker process tree")
        elif group:
            os.killpg(process.pid, signal.SIGKILL)
        else:
            os.kill(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    finally:
        process.close()


def record_alive(record: dict) -> bool:
    try:
        process = ProcessRef(int(record["pid"]))
    except (ProcessLookupError, FileNotFoundError):
        return False
    try:
        return process.birth == record["birth"] and process.alive()
    finally:
        process.close()


def read_record(path: Path) -> dict:
    with path.open("rb") as source:
        raw = source.read(64 * 1024 + 1)
    if len(raw) > 64 * 1024:
        raise ValueError("Worker control record is oversized")
    return json.loads(raw)


def stop_session(session: Path, session_id: str) -> None:
    if not IDENTIFIER.fullmatch(session_id) or session.name != session_id:
        raise ValueError("Session directory and identity must match")
    info_path = session / "supervisor.json"
    if info_path.is_file() and read_record(info_path).get("session_id") != session_id:
        raise ValueError("Worker session identity does not match")
    write_result(session / "stop.json", {"session_id": session_id})
    deadline = time.monotonic() + 2
    while not (session / "supervisor.json").is_file() and time.monotonic() < deadline:
        time.sleep(0.025)
    info = read_record(session / "supervisor.json")
    if info.get("protocol") != PROTOCOL or info.get("session_id") != session_id:
        raise ValueError("Worker session identity does not match")
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if (session / "retired.json").is_file():
            if read_record(session / "retired.json").get("cleaned_up") is True:
                return
            break
        time.sleep(0.025)
    # If the supervisor itself failed, its engine group still has a birth-bound owner record.
    engine = session / "engine-launcher.json"
    if engine.is_file():
        terminate_record(read_record(engine)["process"], group=True)
    ready = session / "ready.json"
    if ready.is_file():
        terminate_record(read_record(ready)["process"], group=False)
    terminate_record(info["process"], group=False)
    records = [info["process"]]
    if engine.is_file():
        records.append(read_record(engine)["process"])
    if ready.is_file():
        records.append(read_record(ready)["process"])
    deadline = time.monotonic() + 3
    while any(record_alive(record) for record in records):
        if time.monotonic() > deadline:
            raise OSError("Owned worker processes did not stop")
        time.sleep(0.025)


def supervise(session: Path, session_id: str, owner_pid: int, *, startup_timeout: float = 30,
              job_timeout: float = 60, idle_timeout: float = 300, resources=None) -> int:
    from desktop_worker.resources import ResourceBudget, admission, capacity_snapshot
    from desktop_worker.governor import BudgetGovernor

    budget = ResourceBudget.from_dict(resources or {})
    job_timeout = min(job_timeout, budget.wall_time_s)
    if not IDENTIFIER.fullmatch(session_id) or session.name != session_id:
        raise ValueError("Invalid worker session ID")
    session.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(session, 0o700)
    # A session directory is single-use, even after failure or cancellation.
    with (session / "session.lock").open("x"):
        pass
    owner = ProcessRef(owner_pid)
    supervisor = ProcessRef(os.getpid())
    write_result(session / "supervisor.json", {"protocol": PROTOCOL, "session_id": session_id,
                 "owner": owner.record(), "process": supervisor.record(),
                 "source_sha256": source_identity(Path(__file__).resolve().parents[2])})
    if (session / "stop.json").exists():
        owner.close()
        supervisor.close()
        write_result(session / "retired.json", {"protocol": PROTOCOL, "session_id": session_id,
                     "reason": "cancelled_before_start", "cleaned_up": True})
        return 0
    script = Path(__file__).resolve().parents[2] / "scripts/lab_worker.py"
    started = last_activity = time.monotonic()
    active_id = None
    active_since = None
    reason = "engine_exited"
    code = 1
    engine_ref = None
    cleaned_up = False
    ready_seen = False
    governor = None
    try:
        admitted = admission(budget, capacity_snapshot(session), wall_limit_s=job_timeout)
        write_result(session / "resource-admission.json", admitted)
        if admitted["status"] != "admitted":
            reason = "resource_admission_refused: " + ", ".join(admitted["reasons"])
            cleaned_up = True  # no engine was launched
            return 2
        scratch = session / "scratch"
        scratch.mkdir()
        environment = {**os.environ, "TEMP": str(scratch), "TMP": str(scratch), "TMPDIR": str(scratch)}
        with (session / "engine.log").open("wb") as log:
            engine = subprocess.Popen([sys.executable, str(script), "--engine", "--session", str(session),
                                       "--session-id", session_id], stdin=subprocess.DEVNULL,
                                      stdout=log, stderr=subprocess.STDOUT, start_new_session=os.name != "nt",
                                      creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                                      env=environment)
            try:
                engine_ref = ProcessRef(engine.pid)
                write_result(session / "engine-launcher.json", {"process": engine_ref.record(), "session_id": session_id})
                governor = BudgetGovernor(session, budget)
                while True:
                    now = time.monotonic()
                    if not owner.alive():
                        reason, code = "owner_exited", 0
                        break
                    if (session / "stop.json").exists():
                        reason, code = "cancelled", 0
                        break
                    if engine.poll() is not None:
                        reason = "engine_exited"
                        break
                    resource_failure = governor.check()
                    if resource_failure:
                        reason = resource_failure
                        break
                    if not (session / "ready.json").exists() and now - started > startup_timeout:
                        reason = "startup_timeout"
                        break
                    if not ready_seen and (session / "ready.json").exists():
                        ready_seen = True
                        last_activity = now
                    active = session / "active.json"
                    if active.exists():
                        job = read_record(active).get("job_id")
                        if not isinstance(job, str) or not IDENTIFIER.fullmatch(job):
                            raise ValueError("Invalid active-job identity")
                        if job != active_id:
                            active_id, active_since = job, now
                        last_activity = now
                        if now - active_since > job_timeout:
                            reason = "job_timeout"
                            break
                        resource_failure = governor.approve(job)
                        if resource_failure:
                            reason = resource_failure
                            break
                    else:
                        active_id, active_since = None, None
                        if ready_seen and now - last_activity > idle_timeout:
                            reason, code = "idle_timeout", 0
                            break
                    time.sleep(0.025)
            finally:
                if engine_ref is not None:
                    terminate_record(engine_ref.record(), group=True)
                elif engine.poll() is None:
                    engine.kill()
                ready = session / "ready.json"
                if ready.is_file():
                    ready_record = read_record(ready)
                    if ready_record.get("session_id") == session_id:
                        terminate_record(ready_record["process"], group=False)
                engine.wait(timeout=5)
                if ready.is_file():
                    deadline = time.monotonic() + 3
                    while record_alive(read_record(ready)["process"]):
                        if time.monotonic() > deadline:
                            raise OSError("Actual CAD interpreter did not stop")
                        time.sleep(0.025)
                cleaned_up = True
    except Exception as error:
        reason = str(error)
    finally:
        if governor is not None:
            governor.close()
        if engine_ref is not None:
            engine_ref.close()
        owner.close()
        supervisor.close()
        active = session / "active.json"
        if active.is_file():
            current = read_record(active).get("job_id")
            if isinstance(current, str) and IDENTIFIER.fullmatch(current):
                directory = session / "jobs" / current
                if directory.is_dir() and not (directory / "complete.json").exists() and not (directory / "error.json").exists():
                    write_result(directory / "error.json", {"protocol": PROTOCOL, "status": "failed", "error": reason,
                                 "job_id": current, "session_id": session_id,
                                 "request_sha256": sha256((directory / "request.json").read_bytes()).hexdigest()})
        write_result(session / "retired.json", {"protocol": PROTOCOL, "session_id": session_id,
                     "reason": reason, "cleaned_up": cleaned_up})
    return code
