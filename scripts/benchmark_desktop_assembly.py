"""Run the rendered 200-part workload with external process-memory observation."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))
sys.path[:0] = [str(ROOT / "apps/api"), str(ROOT / "packages/shared-schemas")]

from desktop_worker.io import write_result
from desktop_worker.metrics import ProcessTreeObserver
from desktop_worker.supervision import terminate_record
from aeroforge_schemas.project import EngineeringProject
from app.services.project_assets import verify_assets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True, help="New absolute .json path")
    parser.add_argument("--frames", type=int, default=600)
    parser.add_argument("--context", type=Path)
    parser.add_argument("--interactive", action="store_true", help="Visible window; wait for real OS input")
    args = parser.parse_args()
    report = args.report
    if not report.is_absolute() or report.suffix != ".json" or not 120 <= args.frames <= 3600:
        parser.error("Use an absolute .json report and 120–3600 frames")
    metrics_path = report.with_name(report.stem + "-memory.json")
    reserved = [report, metrics_path, report.with_suffix(".log"), report.with_suffix(".err")]
    if any(path.exists() for path in reserved):
        parser.error("All report/log paths must be new")
    fixture = ROOT / "data/benchmarks/assembly-200/project.json"
    project = EngineeringProject.model_validate_json(fixture.read_bytes())
    verify_assets(project, fixture.parent)
    context = json.loads(args.context.read_bytes()) if args.context else {}
    head = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    if subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain"], text=True).strip():
        parser.error("Commit the workload and observers before recording a source-bound result")
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.with_suffix(".log").open("wb") as stdout, report.with_suffix(".err").open("wb") as stderr:
        launched = time.monotonic()
        process = subprocess.Popen([str(args.godot.resolve()), "--path", str(ROOT / "apps/desktop"),
             "--rendering-method", "gl_compatibility", "--script", "benchmark_assembly.gd", "--",
             "--report=" + str(report), "--frames=" + str(args.frames), *(["--interactive"] if args.interactive else [])], stdout=stdout, stderr=stderr,
             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" and not args.interactive else 0, start_new_session=os.name != "nt")
        observer = ProcessTreeObserver(process.pid)
        failure = None
        cancellations = {}
        roundtrip_verified = False
        assets_verified = False
        try:
            deadline = time.monotonic() + 600
            while process.poll() is None:
                sample = observer.sample()
                for kind in ("cad", "legacy"):
                    marker = report.with_name(report.stem + "-cancel-" + kind + ".json")
                    if kind not in cancellations and marker.exists():
                        event = json.loads(marker.read_bytes())
                        worker_pid = event["worker_pid"]
                        records = [p for s in observer.samples for p in s["processes"] if p["pid"] == worker_pid]
                        cancellations[kind] = {**event, "marker_first_observed_s": sample["elapsed_s"],
                            "worker_observed": worker_pid in observer.processes,
                            "worker_peak_observed_resident_bytes": max((p["resident_bytes"] for p in records), default=None)}
                    if kind in cancellations and "worker_gone_observed_s" not in cancellations[kind]:
                        event = cancellations[kind]
                        ref = observer.processes.get(event["worker_pid"])
                        if ref is not None and not ref.alive():
                            event["worker_gone_observed_s"] = sample["elapsed_s"]
                            event["post_cancel_worker_resident_bytes"] = 0
                            event["owned_worker_resident_reclaimed_percent"] = 100.0 if event["worker_peak_observed_resident_bytes"] else None
                if "startup" not in context and report.with_name(report.stem + "-startup.json").exists():
                    context["startup"] = {"launch_to_ready_observed_s": time.monotonic() - launched,
                        "observation_resolution_s": 0.1}
                if time.monotonic() > deadline:
                    raise TimeoutError("Rendered benchmark exceeded 600 seconds")
                time.sleep(0.1)
            process.wait(timeout=5)
            verify_assets(project, fixture.parent)
            assets_verified = True
            saved = report.with_name(report.stem + "-saved")
            reopened = EngineeringProject.model_validate_json((saved / "project.json").read_bytes())
            verify_assets(reopened, saved)
            if reopened.fingerprint() != project.fingerprint():
                raise ValueError("Saved assembly differs from the frozen workload")
            roundtrip_verified = True
        except Exception as error:
            failure = str(error)
        finally:
            # The Godot owner has ended; its supervisor must release observed descendants.
            deadline = time.monotonic() + 4
            while any(ref.alive() for pid, ref in observer.processes.items() if pid != process.pid) and time.monotonic() < deadline:
                time.sleep(0.05)
            live = [ref.record() for ref in observer.processes.values() if ref.alive()]
            data = json.loads(report.read_bytes()) if report.is_file() else {}
            actual_pid = data.get("desktop_pid")
            if actual_pid not in observer.processes:
                failure = failure or "Actual desktop PID was not reported/observed; memory attribution is invalid"
            measurement = {**observer.report(actual_pid), "commit_sha": head,
                "memory_attribution_valid": actual_pid in observer.processes,
                "canonical_roundtrip_verified": roundtrip_verified, "source_assets_unchanged_verified": assets_verified,
                "observer_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
                "metrics_module_sha256": sha256((ROOT / "packages/desktop_worker/metrics.py").read_bytes()).hexdigest(),
                "window_launch": "visible interactive window" if args.interactive else "hidden graphical process on Windows", "external_context": context,
                "godot_exit_code": process.poll(), "cleanup_verified": not live, "failure": failure}
            measurement["cancellations"] = cancellations
            measurement["cancellation_memory_scope"] = "Observed actual worker working set reclaimed when birth-bound process exits; excludes OS cache/available-memory recovery and GPU/shared-page guarantees. 100 ms observer resolution."
            if not measurement["memory_attribution_valid"]:
                measurement["desktop_os_peak_resident_bytes"] = None
                measurement["sampled_peak_worker_resident_sum_bytes"] = None
            for record in live:
                terminate_record(record, group=record["pid"] == process.pid)
            process.wait(timeout=5)
            observer.close()
            write_result(metrics_path, measurement)
    if report.exists():
        data = json.loads(report.read_bytes())
        print(json.dumps({"report": str(report), "memory": str(metrics_path), "p95_ms": data.get("p95_ms"),
                          "viewport_target_met": data.get("viewport_target_met"), "cleanup_verified": not live,
                          "canonical_roundtrip_verified": roundtrip_verified, "failure": failure}))
    return process.returncode if not failure and not live and report.is_file() else 1


if __name__ == "__main__":
    raise SystemExit(main())
